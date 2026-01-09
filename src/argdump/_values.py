"""Value serialization for JSON compatibility."""

from __future__ import annotations

import argparse
import base64
from enum import Enum
from typing import Any


def serialize_value(value: Any, _seen: set[int] | None = None) -> Any:
    """Serialize a value for JSON compatibility."""
    if _seen is None:
        _seen = set()

    if value is None:
        return None

    # argparse special values (check before string since REMAINDER is "...")
    if value is argparse.SUPPRESS:
        return {"__argparse__": "SUPPRESS"}
    if value == argparse.REMAINDER:
        return {"__argparse__": "REMAINDER"}

    # Primitives
    if isinstance(value, (bool, int, float, str)):
        return value

    # Circular reference check
    obj_id = id(value)
    if obj_id in _seen:
        return {"__circular_ref__": True}

    # Containers
    if isinstance(value, (list, tuple)):
        _seen.add(obj_id)
        result = [serialize_value(v, _seen) for v in value]
        _seen.discard(obj_id)
        return result

    if isinstance(value, dict):
        _seen.add(obj_id)
        result = {str(k): serialize_value(v, _seen) for k, v in value.items()}
        _seen.discard(obj_id)
        return result

    if isinstance(value, set):
        _seen.add(obj_id)
        result = {"__set__": [serialize_value(v, _seen) for v in sorted(value, key=str)]}
        _seen.discard(obj_id)
        return result

    if isinstance(value, frozenset):
        _seen.add(obj_id)
        result = {"__frozenset__": [serialize_value(v, _seen) for v in sorted(value, key=str)]}
        _seen.discard(obj_id)
        return result

    # Enum
    if isinstance(value, Enum):
        return {
            "__enum__": True,
            "class": type(value).__name__,
            "module": type(value).__module__,
            "value": value.value,
            "name": value.name,
        }

    # Bytes
    if isinstance(value, bytes):
        try:
            return {"__bytes__": value.decode("utf-8")}
        except UnicodeDecodeError:
            return {"__bytes_b64__": base64.b64encode(value).decode("ascii")}

    # Range
    if isinstance(value, range):
        return {"__range__": [value.start, value.stop, value.step]}

    # Type objects
    if isinstance(value, type):
        return {"__type__": True, "name": value.__name__, "module": value.__module__}

    # Fallback
    return {
        "__repr__": repr(value),
        "__type_name__": type(value).__name__,
        "__serializable__": False,
    }


def deserialize_value(value: Any) -> Any:
    """Deserialize a value from JSON representation."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, list):
        return [deserialize_value(v) for v in value]

    if isinstance(value, dict):
        # Special markers
        if "__argparse__" in value:
            marker = value["__argparse__"]
            if marker == "SUPPRESS":
                return argparse.SUPPRESS
            if marker == "REMAINDER":
                return argparse.REMAINDER
            return value

        if "__set__" in value:
            return set(deserialize_value(v) for v in value["__set__"])

        if "__frozenset__" in value:
            return frozenset(deserialize_value(v) for v in value["__frozenset__"])

        if "__bytes__" in value:
            return value["__bytes__"].encode("utf-8")

        if "__bytes_b64__" in value:
            return base64.b64decode(value["__bytes_b64__"])

        if "__range__" in value:
            return range(*value["__range__"])

        if "__enum__" in value:
            try:
                import importlib

                module = importlib.import_module(value["module"])
                enum_class = getattr(module, value["class"])
                return enum_class(value["value"])
            except (ImportError, AttributeError, ValueError):
                return value["value"]

        if "__type__" in value:
            try:
                import importlib

                module = importlib.import_module(value["module"])
                return getattr(module, value["name"])
            except (ImportError, AttributeError):
                return value

        if "__repr__" in value:
            return None if value.get("__serializable__") is False else value

        if "__circular_ref__" in value:
            return None

        # Regular dict
        return {k: deserialize_value(v) for k, v in value.items()}

    return value
