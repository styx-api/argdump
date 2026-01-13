"""Type introspection and resolution utilities."""

from __future__ import annotations

import argparse
import builtins
import importlib
from typing import Any, Callable, Dict, Optional, Union

from .models import FileTypeInfo, TypeInfo

# Type converter callable signature (permissive to accommodate builtins)
TypeConverter = Callable[..., Any]

# Builtin types we can serialize/deserialize
_BUILTIN_CONVERTERS: Dict[str, TypeConverter] = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "complex": complex,
    "bytes": bytes,
    "bytearray": bytearray,
    "ascii": ascii,
}

_BUILTIN_TYPES = (int, float, str, bool, complex, bytes, bytearray)


class UnresolvableTypeError(Exception):
    """Raised when a type converter cannot be reconstructed."""

    pass


def type_info_from_callable(type_func: Any) -> Optional[TypeInfo]:
    """Extract TypeInfo from a type callable.

    Introspects a callable to determine how it should be serialized.
    """
    if type_func is None:
        return None

    # Python builtin types
    if type_func in _BUILTIN_TYPES:
        return TypeInfo(name=type_func.__name__, builtin=True)

    if type_func is ascii:
        return TypeInfo(name="ascii", builtin=True)

    if type_func is open:
        return TypeInfo(name="open", builtin=True, serializable=False)

    # argparse.FileType is handled specially by the caller
    if isinstance(type_func, argparse.FileType):
        return TypeInfo(name="FileType", module="argparse", serializable=True)

    # Extract name and module
    name = getattr(type_func, "__name__", None)
    module = getattr(type_func, "__module__", None)

    # Lambdas cannot be serialized
    if name == "<lambda>":
        return TypeInfo(name="<lambda>", module=module, serializable=False)

    # Named functions/classes
    if name:
        serializable = module is not None and not name.startswith("<")
        return TypeInfo(name=name, module=module, serializable=serializable)

    # Fallback for unusual callables
    return TypeInfo(name=repr(type_func), module=module, serializable=False)


def file_type_info_from_instance(file_type: argparse.FileType) -> FileTypeInfo:
    """Extract FileTypeInfo from argparse.FileType instance."""
    return FileTypeInfo(
        mode=getattr(file_type, "_mode", "r"),
        bufsize=getattr(file_type, "_bufsize", -1),
        encoding=getattr(file_type, "_encoding", None),
        errors=getattr(file_type, "_errors", None),
    )


def resolve_type(
    type_info: Union[TypeInfo, Dict[str, Any], None],
    file_type_info: Union[FileTypeInfo, Dict[str, Any], None] = None,
    *,
    strict: bool = True,
) -> Optional[TypeConverter]:
    """Resolve TypeInfo back to a callable type converter.

    Args:
        type_info: Type information to resolve
        file_type_info: Additional info for FileType reconstruction
        strict: If True, raise on unresolvable types; if False, return None

    Returns:
        The resolved callable, or None if unresolvable in non-strict mode

    Raises:
        UnresolvableTypeError: In strict mode when type cannot be resolved
    """
    if type_info is None:
        return None

    # Normalize dict inputs to dataclass instances
    if isinstance(type_info, dict):
        type_info = TypeInfo(**type_info)
    if isinstance(file_type_info, dict):
        file_type_info = FileTypeInfo(**file_type_info)

    # Check if explicitly marked as non-serializable first
    if not type_info.serializable:
        if strict:
            raise UnresolvableTypeError(f"Type '{type_info.name}' was marked as non-serializable")
        return None

    # Try resolution strategies in order
    result = (
        _resolve_file_type(type_info, file_type_info)
        or _resolve_builtin(type_info, strict)
        or _resolve_by_import(type_info, strict)
        or _resolve_from_builtins_module(type_info)
    )

    if result is not None:
        return result

    if strict:
        raise UnresolvableTypeError(f"Could not resolve type '{type_info.name}'")
    return None


def _resolve_file_type(
    type_info: TypeInfo, file_type_info: Optional[FileTypeInfo]
) -> Optional[argparse.FileType]:
    """Resolve argparse.FileType."""
    if type_info.name == "FileType" and type_info.module == "argparse":
        if file_type_info:
            return argparse.FileType(
                mode=file_type_info.mode,
                bufsize=file_type_info.bufsize,
                encoding=file_type_info.encoding,
                errors=file_type_info.errors,
            )
        return argparse.FileType()
    return None


def _resolve_builtin(type_info: TypeInfo, strict: bool) -> Optional[TypeConverter]:
    """Resolve builtin type converters."""
    if not type_info.builtin:
        return None

    if type_info.name in _BUILTIN_CONVERTERS:
        return _BUILTIN_CONVERTERS[type_info.name]

    return None


def _resolve_by_import(type_info: TypeInfo, strict: bool) -> Optional[TypeConverter]:
    """Resolve type by importing from module."""
    if not type_info.module or not type_info.serializable:
        return None

    try:
        module = importlib.import_module(type_info.module)
        attr = getattr(module, type_info.name)
        if callable(attr):
            result: TypeConverter = attr
            return result
        if strict:
            raise UnresolvableTypeError(f"'{type_info.module}.{type_info.name}' is not callable")
        return None
    except (ImportError, AttributeError) as e:
        if strict:
            raise UnresolvableTypeError(
                f"Could not import '{type_info.module}.{type_info.name}': {e}"
            ) from e
        return None


def _resolve_from_builtins_module(type_info: TypeInfo) -> Optional[TypeConverter]:
    """Fallback resolution from builtins module."""
    if hasattr(builtins, type_info.name):
        attr = getattr(builtins, type_info.name)
        if callable(attr):
            result: TypeConverter = attr
            return result
    return None
