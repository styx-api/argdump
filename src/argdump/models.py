"""Data models for argparse serialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(Enum):
    """Argparse action types."""

    STORE = "store"
    STORE_CONST = "store_const"
    STORE_TRUE = "store_true"
    STORE_FALSE = "store_false"
    APPEND = "append"
    APPEND_CONST = "append_const"
    COUNT = "count"
    HELP = "help"
    VERSION = "version"
    PARSERS = "parsers"
    EXTEND = "extend"
    BOOLEAN_OPTIONAL = "boolean_optional"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> ActionType:
        """Convert string to ActionType, defaulting to UNKNOWN."""
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class TypeInfo:
    """Type converter information."""

    name: str
    module: str | None = None
    builtin: bool = False
    serializable: bool = True


@dataclass
class FileTypeInfo:
    """argparse.FileType parameters."""

    mode: str = "r"
    bufsize: int = -1
    encoding: str | None = None
    errors: str | None = None


@dataclass
class ActionInfo:
    """Serialized argparse Action."""

    option_strings: list[str]
    dest: str
    action_type: ActionType
    nargs: str | int | None = None
    const: Any = None
    default: Any = None
    type_info: TypeInfo | None = None
    file_type_info: FileTypeInfo | None = None
    choices: list[Any] | None = None
    required: bool = False
    help: str | None = None
    metavar: str | tuple[str, ...] | None = None
    version: str | None = None
    subparsers: dict[str, ParserInfo] | None = None
    subparsers_title: str | None = None
    subparsers_description: str | None = None
    subparsers_dest: str | None = None
    subparsers_required: bool = False
    custom_action_class: str | None = None


@dataclass
class MutualExclusionGroup:
    """Mutually exclusive argument group."""

    required: bool
    actions: list[str]


@dataclass
class ArgumentGroup:
    """Argument group for help organization."""

    title: str | None
    description: str | None
    actions: list[str]


@dataclass
class ParserInfo:
    """Complete serialized ArgumentParser."""

    prog: str | None = None
    description: str | None = None
    epilog: str | None = None
    usage: str | None = None
    add_help: bool = True
    allow_abbrev: bool = True
    formatter_class: str | None = None
    prefix_chars: str = "-"
    fromfile_prefix_chars: str | None = None
    argument_default: Any = None
    conflict_handler: str = "error"
    exit_on_error: bool = True

    actions: list[ActionInfo] = field(default_factory=list)
    argument_groups: list[ArgumentGroup] = field(default_factory=list)
    mutually_exclusive_groups: list[MutualExclusionGroup] = field(default_factory=list)
