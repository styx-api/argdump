"""Shared test fixtures for argdump."""

import argparse

import pytest


@pytest.fixture
def simple_parser():
    """Basic parser with common argument types."""
    parser = argparse.ArgumentParser(prog="simple", description="A simple test parser")
    parser.add_argument("input", help="Input file")
    parser.add_argument("-o", "--output", default="out.txt", help="Output file")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    return parser


@pytest.fixture
def complex_parser():
    """Parser exercising many argparse features."""
    parser = argparse.ArgumentParser(
        prog="complex",
        description="A complex parser",
        epilog="This is the epilog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("mode", choices=["run", "test", "build"])
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--items", nargs="+", type=str)
    parser.add_argument("--optional-item", nargs="?", const="default_const")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-cache", action="store_false", dest="cache")
    parser.add_argument("--json", action="store_const", const="json", dest="format")
    parser.add_argument("--csv", action="store_const", const="csv", dest="format")
    parser.add_argument("--include", action="append", default=[])

    return parser


@pytest.fixture
def parser_with_groups():
    """Parser with argument groups and mutual exclusion."""
    parser = argparse.ArgumentParser(prog="grouped")

    io_group = parser.add_argument_group("I/O Options", "Input and output configuration")
    io_group.add_argument("-i", "--input", required=True)
    io_group.add_argument("-o", "--output", required=True)

    format_group = parser.add_mutually_exclusive_group(required=True)
    format_group.add_argument("--json", action="store_true")
    format_group.add_argument("--xml", action="store_true")
    format_group.add_argument("--csv", action="store_true")

    return parser


@pytest.fixture
def parser_with_subparsers():
    """Parser with subcommands."""
    parser = argparse.ArgumentParser(prog="cli")
    parser.add_argument("--config", type=str)

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser("run", help="Run the task")
    run_parser.add_argument("target", help="Target to run")
    run_parser.add_argument("--dry-run", action="store_true")

    build_parser = subparsers.add_parser("build", help="Build the project")
    build_parser.add_argument("--release", action="store_true")
    build_parser.add_argument("--jobs", "-j", type=int, default=4)

    return parser
