"""Tests for value serialization/deserialization."""

import argparse
from enum import Enum
from typing import Any

import pytest

from argdump._values import deserialize_value, serialize_value


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class TestSerializeValue:
    """Test serialize_value function."""

    def test_primitives(self):
        assert serialize_value(None) is None
        assert serialize_value(True) is True
        assert serialize_value(42) == 42
        assert serialize_value(3.14) == 3.14
        assert serialize_value("hello") == "hello"

    def test_containers(self):
        assert serialize_value([1, 2, 3]) == [1, 2, 3]
        assert serialize_value({"a": 1}) == {"a": 1}

    def test_set(self):
        result = serialize_value({1, 2, 3})
        assert "__set__" in result
        assert set(result["__set__"]) == {1, 2, 3}

    def test_frozenset(self):
        result = serialize_value(frozenset([1, 2]))
        assert "__frozenset__" in result

    def test_bytes(self):
        result = serialize_value(b"hello")
        assert result == {"__bytes__": "hello"}

    def test_bytes_non_utf8(self):
        result = serialize_value(b"\xff\xfe")
        assert "__bytes_b64__" in result

    def test_range(self):
        result = serialize_value(range(1, 10, 2))
        assert result == {"__range__": [1, 10, 2]}

    def test_enum(self):
        result = serialize_value(Color.RED)
        assert result["__enum__"] is True
        assert result["value"] == "red"
        assert result["name"] == "RED"

    def test_argparse_suppress(self):
        result = serialize_value(argparse.SUPPRESS)
        assert result == {"__argparse__": "SUPPRESS"}

    def test_argparse_remainder(self):
        result = serialize_value(argparse.REMAINDER)
        assert result == {"__argparse__": "REMAINDER"}

    def test_circular_reference(self):
        lst: list[Any] = [1, 2]
        lst.append(lst)  # circular
        result = serialize_value(lst)
        assert result[2] == {"__circular_ref__": True}


class TestDeserializeValue:
    """Test deserialize_value function."""

    def test_primitives(self):
        assert deserialize_value(None) is None
        assert deserialize_value(True) is True
        assert deserialize_value(42) == 42
        assert deserialize_value("hello") == "hello"

    def test_containers(self):
        assert deserialize_value([1, 2, 3]) == [1, 2, 3]
        assert deserialize_value({"a": 1}) == {"a": 1}

    def test_set(self):
        result = deserialize_value({"__set__": [1, 2, 3]})
        assert result == {1, 2, 3}

    def test_frozenset(self):
        result = deserialize_value({"__frozenset__": [1, 2]})
        assert result == frozenset([1, 2])

    def test_bytes(self):
        result = deserialize_value({"__bytes__": "hello"})
        assert result == b"hello"

    def test_range(self):
        result = deserialize_value({"__range__": [1, 10, 2]})
        assert result == range(1, 10, 2)

    def test_argparse_suppress(self):
        result = deserialize_value({"__argparse__": "SUPPRESS"})
        assert result is argparse.SUPPRESS

    def test_argparse_remainder(self):
        result = deserialize_value({"__argparse__": "REMAINDER"})
        assert result == argparse.REMAINDER

    def test_non_serializable(self):
        result = deserialize_value({"__repr__": "<obj>", "__serializable__": False})
        assert result is None


class TestRoundTrip:
    """Test serialize -> deserialize round trip."""

    @pytest.mark.parametrize(
        "value",
        [
            None,
            True,
            False,
            0,
            42,
            -1,
            3.14,
            "",
            "hello",
            [],
            [1, 2, 3],
            {},
            {"a": 1, "b": [2, 3]},
            b"bytes",
            range(10),
            range(1, 10, 2),
        ],
    )
    def test_round_trip(self, value):
        serialized = serialize_value(value)
        deserialized = deserialize_value(serialized)
        assert deserialized == value
