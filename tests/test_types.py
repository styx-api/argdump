"""Tests for type introspection and resolution."""

import argparse
from pathlib import Path

import pytest

from argdump._types import (
    UnresolvableTypeError,
    file_type_info_from_instance,
    resolve_type,
    type_info_from_callable,
)
from argdump.models import FileTypeInfo, TypeInfo


class TestTypeInfoFromCallable:
    """Test type_info_from_callable function."""

    def test_none(self):
        assert type_info_from_callable(None) is None

    def test_builtin_int(self):
        info = type_info_from_callable(int)
        assert info is not None
        assert info.name == "int"
        assert info.builtin is True
        assert info.serializable is True

    def test_builtin_float(self):
        info = type_info_from_callable(float)
        assert info is not None
        assert info.name == "float"
        assert info.builtin is True

    def test_builtin_str(self):
        info = type_info_from_callable(str)
        assert info is not None
        assert info.name == "str"
        assert info.builtin is True

    def test_builtin_ascii(self):
        info = type_info_from_callable(ascii)
        assert info is not None
        assert info.name == "ascii"
        assert info.builtin is True

    def test_builtin_open(self):
        info = type_info_from_callable(open)
        assert info is not None
        assert info.name == "open"
        assert info.builtin is True
        assert info.serializable is False

    def test_file_type(self):
        file_type = argparse.FileType("r")
        info = type_info_from_callable(file_type)
        assert info is not None
        assert info.name == "FileType"
        assert info.module == "argparse"
        assert info.serializable is True

    def test_lambda(self):
        info = type_info_from_callable(lambda x: x)
        assert info is not None
        assert info.name == "<lambda>"
        assert info.serializable is False

    def test_stdlib_type(self):
        info = type_info_from_callable(Path)
        assert info is not None
        assert info.name == "Path"
        # Module may be 'pathlib' or 'pathlib._local' depending on Python version
        assert info.module is not None
        assert info.module.startswith("pathlib")
        assert info.serializable is True

    def test_custom_function(self):
        def my_converter(x: str) -> int:
            return int(x) * 2

        info = type_info_from_callable(my_converter)
        assert info is not None
        assert info.name == "my_converter"
        assert info.serializable is True


class TestFileTypeInfoFromInstance:
    """Test file_type_info_from_instance function."""

    def test_default_file_type(self):
        file_type = argparse.FileType()
        info = file_type_info_from_instance(file_type)
        assert info.mode == "r"
        assert info.bufsize == -1
        assert info.encoding is None
        assert info.errors is None

    def test_file_type_with_options(self):
        file_type = argparse.FileType("w", encoding="utf-8", errors="strict")
        info = file_type_info_from_instance(file_type)
        assert info.mode == "w"
        assert info.encoding == "utf-8"
        assert info.errors == "strict"

    def test_binary_file_type(self):
        file_type = argparse.FileType("rb")
        info = file_type_info_from_instance(file_type)
        assert info.mode == "rb"


class TestResolveType:
    """Test resolve_type function."""

    def test_none(self):
        assert resolve_type(None) is None

    def test_builtin_int(self):
        type_info = TypeInfo(name="int", builtin=True)
        result = resolve_type(type_info)
        assert result is int

    def test_builtin_float(self):
        type_info = TypeInfo(name="float", builtin=True)
        result = resolve_type(type_info)
        assert result is float

    def test_builtin_str(self):
        type_info = TypeInfo(name="str", builtin=True)
        result = resolve_type(type_info)
        assert result is str

    def test_file_type_basic(self):
        type_info = TypeInfo(name="FileType", module="argparse", serializable=True)
        result = resolve_type(type_info)
        assert isinstance(result, argparse.FileType)

    def test_file_type_with_info(self):
        type_info = TypeInfo(name="FileType", module="argparse", serializable=True)
        file_info = FileTypeInfo(mode="w", encoding="utf-8")
        result = resolve_type(type_info, file_info)
        assert isinstance(result, argparse.FileType)

    def test_stdlib_path(self):
        type_info = TypeInfo(name="Path", module="pathlib", serializable=True)
        result = resolve_type(type_info)
        assert result is Path

    def test_non_serializable_strict(self):
        type_info = TypeInfo(name="<lambda>", serializable=False)
        with pytest.raises(UnresolvableTypeError):
            resolve_type(type_info, strict=True)

    def test_non_serializable_non_strict(self):
        type_info = TypeInfo(name="<lambda>", serializable=False)
        result = resolve_type(type_info, strict=False)
        assert result is None

    def test_open_strict(self):
        type_info = TypeInfo(name="open", builtin=True, serializable=False)
        with pytest.raises(UnresolvableTypeError):
            resolve_type(type_info, strict=True)

    def test_open_non_strict(self):
        type_info = TypeInfo(name="open", builtin=True, serializable=False)
        result = resolve_type(type_info, strict=False)
        assert result is None

    def test_dict_input(self):
        type_info = {"name": "int", "builtin": True, "serializable": True}
        result = resolve_type(type_info)
        assert result is int

    def test_import_error_strict(self):
        type_info = TypeInfo(name="NonExistent", module="nonexistent.module", serializable=True)
        with pytest.raises(UnresolvableTypeError):
            resolve_type(type_info, strict=True)

    def test_import_error_non_strict(self):
        type_info = TypeInfo(name="NonExistent", module="nonexistent.module", serializable=True)
        result = resolve_type(type_info, strict=False)
        assert result is None


class TestRoundTrip:
    """Test type info extraction -> resolution round trip."""

    @pytest.mark.parametrize("type_func", [int, float, str, bool, complex, bytes, bytearray])
    def test_builtin_round_trip(self, type_func):
        info = type_info_from_callable(type_func)
        assert info is not None
        resolved = resolve_type(info)
        assert resolved is type_func

    def test_path_round_trip(self):
        info = type_info_from_callable(Path)
        assert info is not None
        resolved = resolve_type(info)
        assert resolved is Path

    def test_file_type_round_trip(self):
        original = argparse.FileType("r", encoding="utf-8")
        type_info = type_info_from_callable(original)
        file_info = file_type_info_from_instance(original)

        resolved = resolve_type(type_info, file_info)
        assert isinstance(resolved, argparse.FileType)
