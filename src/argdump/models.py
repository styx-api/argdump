"""Data models for argparse serialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class ActionType(str, Enum):
    """Argparse action types.

    Inherits from str for better type inference and direct string comparison.
    """

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
    def from_string(cls, value: str) -> "ActionType":
        """Convert string to ActionType, defaulting to UNKNOWN."""
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class TypeInfo:
    """Type converter information."""

    name: str
    module: Optional[str] = None
    builtin: bool = False
    serializable: bool = True


@dataclass
class FileTypeInfo:
    """argparse.FileType parameters."""

    mode: str = "r"
    bufsize: int = -1
    encoding: Optional[str] = None
    errors: Optional[str] = None


@dataclass
class ActionInfo:
    """Serialized argparse Action."""

    option_strings: List[str]
    dest: str
    action_type: ActionType
    nargs: Union[str, int, None] = None
    const: Any = None
    default: Any = None
    type_info: Optional[TypeInfo] = None
    file_type_info: Optional[FileTypeInfo] = None
    choices: Optional[List[Any]] = None
    required: bool = False
    help: Optional[str] = None
    metavar: Union[str, Tuple[str, ...], None] = None
    deprecated: bool = False
    version: Optional[str] = None
    subparsers: Optional[Dict[str, "ParserInfo"]] = None
    subparsers_title: Optional[str] = None
    subparsers_description: Optional[str] = None
    subparsers_dest: Optional[str] = None
    subparsers_required: bool = False
    subparsers_aliases: Optional[Dict[str, List[str]]] = None  # name -> aliases
    custom_action_class: Optional[str] = None

    @property
    def is_optional(self) -> bool:
        """Whether this is an optional (flag) argument."""
        return bool(self.option_strings)

    @property
    def is_positional(self) -> bool:
        """Whether this is a positional argument."""
        return not self.option_strings


@dataclass
class MutualExclusionGroup:
    """Mutually exclusive argument group."""

    required: bool
    actions: List[str]


@dataclass
class ArgumentGroup:
    """Argument group for help organization."""

    title: Optional[str]
    description: Optional[str]
    actions: List[str]


@dataclass
class ParserInfo:
    """Complete serialized ArgumentParser."""

    prog: Optional[str] = None
    description: Optional[str] = None
    epilog: Optional[str] = None
    usage: Optional[str] = None
    add_help: bool = True
    allow_abbrev: bool = True
    formatter_class: Optional[str] = None
    prefix_chars: str = "-"
    fromfile_prefix_chars: Optional[str] = None
    argument_default: Any = None
    conflict_handler: str = "error"
    exit_on_error: bool = True
    # Python 3.14+
    suggest_on_error: bool = False
    color: bool = True

    actions: List[ActionInfo] = field(default_factory=list)
    argument_groups: List[ArgumentGroup] = field(default_factory=list)
    mutually_exclusive_groups: List[MutualExclusionGroup] = field(default_factory=list)

    def get_action_by_dest(self, dest: str) -> Optional[ActionInfo]:
        """Find an action by its destination name."""
        for action in self.actions:
            if action.dest == dest:
                return action
        return None
