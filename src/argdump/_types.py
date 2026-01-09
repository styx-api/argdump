"""Type introspection and resolution utilities."""

from __future__ import annotations

import argparse
import importlib
from typing import Any, Callable

from .models import FileTypeInfo, TypeInfo

# Builtins we can serialize/deserialize
_BUILTINS = {
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


def type_info_from_callable(type_func: Any) -> TypeInfo | None:
    """Extract TypeInfo from a type callable."""
    if type_func is None:
        return None

    # Python builtins
    if type_func in _BUILTIN_TYPES:
        return TypeInfo(name=type_func.__name__, builtin=True)

    if type_func is ascii:
        return TypeInfo(name="ascii", builtin=True)

    if type_func is open:
        return TypeInfo(name="open", builtin=True, serializable=False)

    # argparse.FileType handled by caller
    if isinstance(type_func, argparse.FileType):
        return TypeInfo(name="FileType", module="argparse", serializable=True)

    name = getattr(type_func, "__name__", None)
    module = getattr(type_func, "__module__", None)

    # Lambdas are not serializable
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


class UnresolvableTypeError(Exception):
    """Raised when a type converter cannot be reconstructed."""

    pass


def resolve_type(
    type_info: TypeInfo | dict | None,
    file_type_info: FileTypeInfo | dict | None = None,
    *,
    strict: bool = True,
) -> Callable | None:
    """Resolve TypeInfo back to a callable type converter."""
    if type_info is None:
        return None

    # Handle dict input (from JSON)
    if isinstance(type_info, dict):
        type_info = TypeInfo(**type_info)
    if isinstance(file_type_info, dict):
        file_type_info = FileTypeInfo(**file_type_info)

    # FileType
    if type_info.name == "FileType" and type_info.module == "argparse":
        if file_type_info:
            return argparse.FileType(
                mode=file_type_info.mode,
                bufsize=file_type_info.bufsize,
                encoding=file_type_info.encoding,
                errors=file_type_info.errors,
            )
        return argparse.FileType()

    # Builtins
    if type_info.builtin:
        if type_info.name in _BUILTINS:
            return _BUILTINS[type_info.name]
        if type_info.name == "open":
            if strict:
                raise UnresolvableTypeError("Cannot deserialize 'open' as type converter")
            return None

    # Non-serializable
    if not type_info.serializable:
        if strict:
            raise UnresolvableTypeError(f"Type '{type_info.name}' was marked as non-serializable")
        return None

    # Import by module.name
    if type_info.module:
        try:
            module = importlib.import_module(type_info.module)
            return getattr(module, type_info.name)
        except (ImportError, AttributeError) as e:
            if strict:
                raise UnresolvableTypeError(
                    f"Could not import '{type_info.module}.{type_info.name}': {e}"
                ) from e
            return None

    # Check builtins as fallback
    import builtins

    if hasattr(builtins, type_info.name):
        return getattr(builtins, type_info.name)

    if strict:
        raise UnresolvableTypeError(f"Could not resolve type '{type_info.name}'")
    return None
