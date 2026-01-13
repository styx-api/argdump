"""Value serialization for JSON compatibility."""

from __future__ import annotations

import argparse
import base64
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set


def serialize_value(value: Any, _seen: Optional[Set[int]] = None) -> Any:
    """Serialize a value for JSON compatibility.

    Handles Python types that aren't directly JSON-serializable,
    including argparse special values, enums, bytes, sets, and more.
    """
    if _seen is None:
        _seen = set()

    if value is None:
        return None

    # argparse special values (check before string since REMAINDER is "...")
    if value is argparse.SUPPRESS:
        return {"__argparse__": "SUPPRESS"}
    if value == argparse.REMAINDER:
        return {"__argparse__": "REMAINDER"}

    # Primitives pass through directly
    if isinstance(value, (bool, int, float, str)):
        return value

    # Circular reference protection
    obj_id = id(value)
    if obj_id in _seen:
        return {"__circular_ref__": True}

    # Delegate to type-specific handlers
    if isinstance(value, (list, tuple)):
        return _serialize_sequence(value, _seen, obj_id)

    if isinstance(value, dict):
        return _serialize_dict(value, _seen, obj_id)

    if isinstance(value, set):
        return _serialize_set(value, _seen, obj_id)

    if isinstance(value, frozenset):
        return _serialize_frozenset(value, _seen, obj_id)

    if isinstance(value, Enum):
        return _serialize_enum(value)

    if isinstance(value, bytes):
        return _serialize_bytes(value)

    if isinstance(value, range):
        return {"__range__": [value.start, value.stop, value.step]}

    if isinstance(value, type):
        return {"__type__": True, "name": value.__name__, "module": value.__module__}

    # Fallback for unknown types
    return {
        "__repr__": repr(value),
        "__type_name__": type(value).__name__,
        "__serializable__": False,
    }


def _serialize_sequence(value: Any, seen: Set[int], obj_id: int) -> List[Any]:
    """Serialize a list or tuple."""
    seen.add(obj_id)
    result = [serialize_value(v, seen) for v in value]
    seen.discard(obj_id)
    return result


def _serialize_dict(value: Dict[Any, Any], seen: Set[int], obj_id: int) -> Dict[str, Any]:
    """Serialize a dictionary."""
    seen.add(obj_id)
    result = {str(k): serialize_value(v, seen) for k, v in value.items()}
    seen.discard(obj_id)
    return result


def _serialize_set(value: Set[Any], seen: Set[int], obj_id: int) -> Dict[str, List[Any]]:
    """Serialize a set."""
    seen.add(obj_id)
    result: Dict[str, List[Any]] = {
        "__set__": [serialize_value(v, seen) for v in sorted(value, key=str)]
    }
    seen.discard(obj_id)
    return result


def _serialize_frozenset(
    value: FrozenSet[Any], seen: Set[int], obj_id: int
) -> Dict[str, List[Any]]:
    """Serialize a frozenset."""
    seen.add(obj_id)
    result: Dict[str, List[Any]] = {
        "__frozenset__": [serialize_value(v, seen) for v in sorted(value, key=str)]
    }
    seen.discard(obj_id)
    return result


def _serialize_enum(value: Enum) -> Dict[str, Any]:
    """Serialize an enum value."""
    return {
        "__enum__": True,
        "class": type(value).__name__,
        "module": type(value).__module__,
        "value": value.value,
        "name": value.name,
    }


def _serialize_bytes(value: bytes) -> Dict[str, str]:
    """Serialize bytes, using base64 if not valid UTF-8."""
    try:
        return {"__bytes__": value.decode("utf-8")}
    except UnicodeDecodeError:
        return {"__bytes_b64__": base64.b64encode(value).decode("ascii")}


def deserialize_value(value: Any) -> Any:
    """Deserialize a value from JSON representation.

    Reconstructs Python objects from their serialized form.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, list):
        return [deserialize_value(v) for v in value]

    if isinstance(value, dict):
        return _deserialize_dict(value)

    return value


def _deserialize_dict(value: Dict[str, Any]) -> Any:
    """Deserialize a dictionary, handling special markers."""
    # argparse special values
    if "__argparse__" in value:
        return _deserialize_argparse_marker(value["__argparse__"])

    # Container types
    if "__set__" in value:
        return set(deserialize_value(v) for v in value["__set__"])

    if "__frozenset__" in value:
        return frozenset(deserialize_value(v) for v in value["__frozenset__"])

    # Bytes
    if "__bytes__" in value:
        return value["__bytes__"].encode("utf-8")

    if "__bytes_b64__" in value:
        return base64.b64decode(value["__bytes_b64__"])

    # Range
    if "__range__" in value:
        return range(*value["__range__"])

    # Enum
    if "__enum__" in value:
        return _deserialize_enum(value)

    # Type reference
    if "__type__" in value:
        return _deserialize_type(value)

    # Non-serializable placeholder
    if "__repr__" in value:
        return None if value.get("__serializable__") is False else value

    # Circular reference placeholder
    if "__circular_ref__" in value:
        return None

    # Regular dict - recurse into values
    return {k: deserialize_value(v) for k, v in value.items()}


def _deserialize_argparse_marker(marker: str) -> Any:
    """Deserialize argparse special values."""
    if marker == "SUPPRESS":
        return argparse.SUPPRESS
    if marker == "REMAINDER":
        return argparse.REMAINDER
    return None


def _deserialize_enum(value: Dict[str, Any]) -> Any:
    """Attempt to deserialize an enum value."""
    try:
        import importlib

        module = importlib.import_module(value["module"])
        enum_class = getattr(module, value["class"])
        return enum_class(value["value"])
    except (ImportError, AttributeError, ValueError, KeyError):
        # Fall back to raw value if enum can't be reconstructed
        return value.get("value")


def _deserialize_type(value: Dict[str, Any]) -> Any:
    """Attempt to deserialize a type reference."""
    try:
        import importlib

        module = importlib.import_module(value["module"])
        return getattr(module, value["name"])
    except (ImportError, AttributeError, KeyError):
        return value
