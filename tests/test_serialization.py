"""Tests for serialization (dump/dumps)."""

import argparse
import json
import sys
from pathlib import Path

import pytest

import argdump


class TestBasicSerialization:
    """Test basic dump/dumps functionality."""

    def test_empty_parser(self):
        parser = argparse.ArgumentParser()
        data = argdump.dump(parser)

        assert isinstance(data, dict)
        assert len(data["actions"]) >= 1  # at least help

    def test_simple_parser(self, simple_parser):
        data = argdump.dump(simple_parser)

        assert data["prog"] == "simple"
        assert data["description"] == "A simple test parser"

        actions_by_dest = {a["dest"]: a for a in data["actions"]}

        assert actions_by_dest["input"]["option_strings"] == []
        assert actions_by_dest["output"]["default"] == "out.txt"
        assert actions_by_dest["verbose"]["action_type"] == "count"

    def test_dumps_produces_valid_json(self, simple_parser):
        json_str = argdump.dumps(simple_parser)
        data = json.loads(json_str)
        assert data["prog"] == "simple"

    def test_dumps_indent(self, simple_parser):
        json_str = argdump.dumps(simple_parser, indent=2)
        assert "\n" in json_str
        assert "  " in json_str


class TestActionTypes:
    """Test serialization of all action types."""

    def test_store(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name", type=str)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "name")
        assert action["action_type"] == "store"
        assert action["type_info"]["name"] == "str"

    def test_store_const(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--enable", action="store_const", const=True)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "enable")
        assert action["action_type"] == "store_const"
        assert action["const"] is True

    def test_store_true_false(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--yes", action="store_true")
        parser.add_argument("--no", action="store_false")
        data = argdump.dump(parser)

        actions = {a["dest"]: a for a in data["actions"]}
        assert actions["yes"]["action_type"] == "store_true"
        assert actions["no"]["action_type"] == "store_false"

    def test_append(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--item", action="append")
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "item")
        assert action["action_type"] == "append"

    def test_count(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-v", action="count", default=0)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "v")
        assert action["action_type"] == "count"

    def test_version(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--version", action="version", version="1.0.0")
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["action_type"] == "version")
        assert action["version"] == "1.0.0"

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="extend requires 3.8+")
    def test_extend(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--items", action="extend", nargs="+")
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "items")
        assert action["action_type"] == "extend"

    @pytest.mark.skipif(sys.version_info < (3, 9), reason="BooleanOptionalAction requires 3.9+")
    def test_boolean_optional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--feature", action=argparse.BooleanOptionalAction)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "feature")
        assert action["action_type"] == "boolean_optional"


class TestTypeHandling:
    """Test type converter serialization."""

    def test_builtin_types(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--int-val", type=int)
        parser.add_argument("--float-val", type=float)
        parser.add_argument("--str-val", type=str)
        data = argdump.dump(parser)

        actions = {a["dest"]: a for a in data["actions"]}

        assert actions["int_val"]["type_info"]["name"] == "int"
        assert actions["int_val"]["type_info"]["builtin"] is True
        assert actions["float_val"]["type_info"]["name"] == "float"
        assert actions["str_val"]["type_info"]["name"] == "str"

    def test_file_type(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--input", type=argparse.FileType("r", encoding="utf-8"))
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "input")
        assert action["type_info"]["name"] == "FileType"
        assert action["file_type_info"]["mode"] == "r"
        assert action["file_type_info"]["encoding"] == "utf-8"

    def test_lambda_not_serializable(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--value", type=lambda x: int(x) * 2)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "value")
        assert action["type_info"]["name"] == "<lambda>"
        assert action["type_info"]["serializable"] is False

    def test_path_type(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=Path)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "path")
        assert action["type_info"]["name"] == "Path"
        assert action["type_info"]["module"] == "pathlib"


class TestNargs:
    """Test nargs serialization."""

    def test_nargs_int(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--coords", nargs=2)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "coords")
        assert action["nargs"] == 2

    def test_nargs_special(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--opt", nargs="?")
        parser.add_argument("files", nargs="*")
        parser.add_argument("required", nargs="+")
        data = argdump.dump(parser)

        actions = {a["dest"]: a for a in data["actions"]}
        assert actions["opt"]["nargs"] == "?"
        assert actions["files"]["nargs"] == "*"
        assert actions["required"]["nargs"] == "+"

    def test_nargs_remainder(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("args", nargs=argparse.REMAINDER)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "args")
        assert action["nargs"] == {"__argparse__": "REMAINDER"}


class TestGroups:
    """Test argument group serialization."""

    def test_argument_groups(self, parser_with_groups):
        data = argdump.dump(parser_with_groups)

        io_group = next(g for g in data["argument_groups"] if g["title"] == "I/O Options")
        assert io_group["description"] == "Input and output configuration"
        assert "input" in io_group["actions"]
        assert "output" in io_group["actions"]

    def test_mutex_groups(self, parser_with_groups):
        data = argdump.dump(parser_with_groups)

        assert len(data["mutually_exclusive_groups"]) == 1
        mutex = data["mutually_exclusive_groups"][0]
        assert mutex["required"] is True
        assert set(mutex["actions"]) == {"json", "xml", "csv"}


class TestSubparsers:
    """Test subparser serialization."""

    def test_basic_subparsers(self, parser_with_subparsers):
        data = argdump.dump(parser_with_subparsers)

        subparsers_action = next(a for a in data["actions"] if a["action_type"] == "parsers")

        assert "run" in subparsers_action["subparsers"]
        assert "build" in subparsers_action["subparsers"]

        run_info = subparsers_action["subparsers"]["run"]
        run_dests = {a["dest"] for a in run_info["actions"]}
        assert "target" in run_dests
        assert "dry_run" in run_dests

    def test_nested_subparsers(self):
        parser = argparse.ArgumentParser(prog="nested")
        subparsers = parser.add_subparsers(dest="cmd1")
        sub1 = subparsers.add_parser("level1")
        sub1_subs = sub1.add_subparsers(dest="cmd2")
        sub1_subs.add_parser("level2")

        data = argdump.dump(parser)

        cmd1_action = next(a for a in data["actions"] if a["action_type"] == "parsers")
        level1 = cmd1_action["subparsers"]["level1"]
        cmd2_action = next(a for a in level1["actions"] if a["action_type"] == "parsers")
        assert "level2" in cmd2_action["subparsers"]


class TestSpecialValues:
    """Test special value serialization."""

    def test_suppress_default(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--hidden", default=argparse.SUPPRESS)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "hidden")
        assert action["default"] == {"__argparse__": "SUPPRESS"}

    def test_suppress_help(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--internal", help=argparse.SUPPRESS)
        data = argdump.dump(parser)

        action = next(a for a in data["actions"] if a["dest"] == "internal")
        assert action["help"] is None

    def test_complex_defaults(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--list", default=[1, 2, 3])
        parser.add_argument("--dict", default={"key": "value"})
        data = argdump.dump(parser)

        actions = {a["dest"]: a for a in data["actions"]}
        assert actions["list"]["default"] == [1, 2, 3]
        assert actions["dict"]["default"] == {"key": "value"}
