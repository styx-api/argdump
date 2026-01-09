"""Tests for deserialization (load/loads)."""

import argparse
import sys

import pytest

import argdump
from argdump import UnresolvableTypeError


class TestBasicDeserialization:
    """Test basic load/loads functionality."""

    def test_round_trip_simple(self, simple_parser):
        data = argdump.dump(simple_parser)
        restored = argdump.load(data)

        assert restored.prog == simple_parser.prog
        assert restored.description == simple_parser.description

    def test_round_trip_parse_args(self, simple_parser):
        data = argdump.dump(simple_parser)
        restored = argdump.load(data)

        args = restored.parse_args(["test.txt", "-o", "result.txt", "-v", "-v"])

        assert args.input == "test.txt"
        assert args.output == "result.txt"
        assert args.verbose == 2

    def test_loads_from_json(self, simple_parser):
        json_str = argdump.dumps(simple_parser)
        restored = argdump.loads(json_str)

        args = restored.parse_args(["input.txt"])
        assert args.input == "input.txt"


class TestTypeReconstruction:
    """Test type converter reconstruction."""

    def test_builtin_types(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int)
        parser.add_argument("--ratio", type=float)

        restored = argdump.load(argdump.dump(parser))
        args = restored.parse_args(["--count", "42", "--ratio", "3.14"])

        assert args.count == 42
        assert isinstance(args.count, int)
        assert args.ratio == 3.14
        assert isinstance(args.ratio, float)

    def test_file_type(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--input", type=argparse.FileType("r"))

        restored = argdump.load(argdump.dump(parser))

        input_action = next(a for a in restored._actions if getattr(a, "dest", None) == "input")
        assert isinstance(input_action.type, argparse.FileType)

    def test_lambda_strict_fails(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--value", type=lambda x: x.upper())

        with pytest.raises(UnresolvableTypeError):
            argdump.load(argdump.dump(parser), strict=True)

    def test_lambda_non_strict(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--value", type=lambda x: x.upper())

        restored = argdump.load(argdump.dump(parser), strict=False)
        args = restored.parse_args(["--value", "test"])
        assert args.value == "test"  # No transformation


class TestChoices:
    """Test choices reconstruction."""

    def test_choices_valid(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--format", choices=["json", "csv", "xml"])

        restored = argdump.load(argdump.dump(parser))
        args = restored.parse_args(["--format", "json"])
        assert args.format == "json"

    def test_choices_invalid(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--format", choices=["json", "csv", "xml"])

        restored = argdump.load(argdump.dump(parser))
        with pytest.raises(SystemExit):
            restored.parse_args(["--format", "yaml"])


class TestGroups:
    """Test group reconstruction."""

    def test_mutex_groups(self, parser_with_groups):
        restored = argdump.load(argdump.dump(parser_with_groups))

        # Single option works
        args = restored.parse_args(["-i", "in.txt", "-o", "out.txt", "--json"])
        assert args.json is True

        # Multiple mutex options fail
        with pytest.raises(SystemExit):
            restored.parse_args(["-i", "in.txt", "-o", "out.txt", "--json", "--xml"])


class TestSubparsers:
    """Test subparser reconstruction."""

    def test_subparsers(self, parser_with_subparsers):
        restored = argdump.load(argdump.dump(parser_with_subparsers))

        args = restored.parse_args(["run", "target1", "--dry-run"])
        assert args.command == "run"
        assert args.target == "target1"
        assert args.dry_run is True

        args = restored.parse_args(["build", "--release", "-j", "8"])
        assert args.command == "build"
        assert args.release is True
        assert args.jobs == 8


class TestParserSettings:
    """Test parser configuration reconstruction."""

    def test_formatter_class(self):
        for formatter in [
            argparse.RawDescriptionHelpFormatter,
            argparse.RawTextHelpFormatter,
            argparse.ArgumentDefaultsHelpFormatter,
        ]:
            parser = argparse.ArgumentParser(formatter_class=formatter)
            restored = argdump.load(argdump.dump(parser))
            assert restored.formatter_class == formatter

    def test_prefix_chars(self):
        parser = argparse.ArgumentParser(prefix_chars="-+")
        parser.add_argument("-v", action="count", default=0)
        parser.add_argument("+d", action="store_true")

        restored = argdump.load(argdump.dump(parser))
        assert restored.prefix_chars == "-+"

    @pytest.mark.skipif(sys.version_info < (3, 9), reason="exit_on_error requires 3.9+")
    def test_exit_on_error(self):
        parser = argparse.ArgumentParser(exit_on_error=False)
        restored = argdump.load(argdump.dump(parser))
        assert restored.exit_on_error is False


class TestIntegration:
    """Integration tests with realistic CLI patterns."""

    def test_git_like_cli(self):
        parser = argparse.ArgumentParser(prog="mygit")
        parser.add_argument("--version", action="version", version="1.0.0")
        parser.add_argument("-C", dest="workdir")

        subparsers = parser.add_subparsers(dest="command")

        clone = subparsers.add_parser("clone")
        clone.add_argument("repository")
        clone.add_argument("directory", nargs="?")
        clone.add_argument("--depth", type=int)
        clone.add_argument("--branch", "-b")

        commit = subparsers.add_parser("commit")
        commit.add_argument("-m", "--message", required=True)
        commit.add_argument("-a", "--all", action="store_true")

        restored = argdump.load(argdump.dump(parser))

        args = restored.parse_args(
            ["-C", "/repo", "clone", "https://github.com/user/repo", "--depth", "1"]
        )
        assert args.workdir == "/repo"
        assert args.command == "clone"
        assert args.repository == "https://github.com/user/repo"
        assert args.depth == 1

        args = restored.parse_args(["commit", "-m", "Initial commit", "-a"])
        assert args.command == "commit"
        assert args.message == "Initial commit"
        assert args.all is True

    def test_data_processing_cli(self):
        parser = argparse.ArgumentParser(prog="dataproc")

        parser.add_argument("input", nargs="+")
        parser.add_argument("-o", "--output", default="output.csv")
        parser.add_argument("--format", choices=["csv", "json"], default="csv")
        parser.add_argument("--filter", action="append", default=[])
        parser.add_argument("-j", "--jobs", type=int, default=1)

        log_mutex = parser.add_mutually_exclusive_group()
        log_mutex.add_argument("-v", "--verbose", action="count", default=0)
        log_mutex.add_argument("-q", "--quiet", action="store_true")

        restored = argdump.load(argdump.dump(parser))

        args = restored.parse_args(
            [
                "data1.csv",
                "data2.csv",
                "-o",
                "result.json",
                "--format",
                "json",
                "--filter",
                "col1 > 0",
                "--filter",
                "col2 != null",
                "-j",
                "4",
                "-vvv",
            ]
        )

        assert args.input == ["data1.csv", "data2.csv"]
        assert args.output == "result.json"
        assert args.format == "json"
        assert args.filter == ["col1 > 0", "col2 != null"]
        assert args.jobs == 4
        assert args.verbose == 3
