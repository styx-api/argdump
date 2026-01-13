"""Deserialize dict/JSON back to argparse parsers."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Set, Type, Union

from ._types import UnresolvableTypeError, resolve_type
from ._values import deserialize_value
from .models import (
    ActionInfo,
    ActionType,
    ArgumentGroup,
    FileTypeInfo,
    MutualExclusionGroup,
    ParserInfo,
    TypeInfo,
)

# Formatter class lookup
_FORMATTER_CLASSES: Dict[str, Type[argparse.HelpFormatter]] = {
    "HelpFormatter": argparse.HelpFormatter,
    "RawDescriptionHelpFormatter": argparse.RawDescriptionHelpFormatter,
    "RawTextHelpFormatter": argparse.RawTextHelpFormatter,
    "ArgumentDefaultsHelpFormatter": argparse.ArgumentDefaultsHelpFormatter,
}

if hasattr(argparse, "MetavarTypeHelpFormatter"):
    _FORMATTER_CLASSES["MetavarTypeHelpFormatter"] = argparse.MetavarTypeHelpFormatter

# Action type mappings
_ACTION_TYPE_MAP: Dict[ActionType, str] = {
    ActionType.STORE: "store",
    ActionType.STORE_CONST: "store_const",
    ActionType.STORE_TRUE: "store_true",
    ActionType.STORE_FALSE: "store_false",
    ActionType.APPEND: "append",
    ActionType.APPEND_CONST: "append_const",
    ActionType.COUNT: "count",
    ActionType.HELP: "help",
    ActionType.VERSION: "version",
    ActionType.EXTEND: "extend",
}

# Actions with restricted kwargs
_NO_NARGS_ACTIONS: Set[ActionType] = {
    ActionType.STORE_TRUE,
    ActionType.STORE_FALSE,
    ActionType.COUNT,
    ActionType.APPEND_CONST,
    ActionType.STORE_CONST,
}

_NO_TYPE_ACTIONS: Set[ActionType] = {
    ActionType.STORE_TRUE,
    ActionType.STORE_FALSE,
    ActionType.COUNT,
    ActionType.STORE_CONST,
    ActionType.APPEND_CONST,
}

_CONST_ACTIONS: Set[ActionType] = {
    ActionType.STORE_CONST,
    ActionType.APPEND_CONST,
}


# --- Type conversion helpers ---


def _action_type_to_argparse(
    action_type: Union[ActionType, str],
) -> Union[str, Type[argparse.Action]]:
    """Convert ActionType to argparse action string/class."""
    if isinstance(action_type, str):
        return action_type

    if action_type in _ACTION_TYPE_MAP:
        return _ACTION_TYPE_MAP[action_type]

    if action_type == ActionType.BOOLEAN_OPTIONAL:
        if hasattr(argparse, "BooleanOptionalAction"):
            return argparse.BooleanOptionalAction
        raise ValueError("BooleanOptionalAction requires Python 3.9+")

    # ActionType is str-based, so .value is str
    return action_type.value


def _convert_action_info(data: Dict[str, Any]) -> ActionInfo:
    """Convert dict to ActionInfo with proper nested types."""
    data = data.copy()

    if "action_type" in data and isinstance(data["action_type"], str):
        data["action_type"] = ActionType.from_string(data["action_type"])

    if data.get("type_info") and isinstance(data["type_info"], dict):
        data["type_info"] = TypeInfo(**data["type_info"])

    if data.get("file_type_info") and isinstance(data["file_type_info"], dict):
        data["file_type_info"] = FileTypeInfo(**data["file_type_info"])

    if data.get("subparsers"):
        data["subparsers"] = {
            name: _convert_parser_info(sub) if isinstance(sub, dict) else sub
            for name, sub in data["subparsers"].items()
        }

    return ActionInfo(**data)


def _convert_parser_info(data: Dict[str, Any]) -> ParserInfo:
    """Convert dict to ParserInfo with proper nested types."""
    data = data.copy()

    # Remove metadata markers (not part of ParserInfo)
    data.pop("$schema", None)
    data.pop("$env", None)

    # Extract nested lists for separate processing
    actions: List[Any] = data.pop("actions", [])
    groups: List[Any] = data.pop("argument_groups", [])
    mutex_groups: List[Any] = data.pop("mutually_exclusive_groups", [])

    info = ParserInfo(**data)

    info.actions = [_convert_action_info(a) if isinstance(a, dict) else a for a in actions]
    info.argument_groups = [ArgumentGroup(**g) if isinstance(g, dict) else g for g in groups]
    info.mutually_exclusive_groups = [
        MutualExclusionGroup(**g) if isinstance(g, dict) else g for g in mutex_groups
    ]

    return info


# --- Kwargs builders ---


def _build_action_kwargs(action_info: ActionInfo, strict: bool) -> Dict[str, Any]:
    """Build kwargs dict for add_argument() call."""
    kwargs: Dict[str, Any] = {}

    _add_action_type_kwarg(kwargs, action_info)
    _add_dest_kwarg(kwargs, action_info)
    _add_nargs_kwarg(kwargs, action_info)
    _add_const_kwarg(kwargs, action_info)
    _add_default_kwarg(kwargs, action_info)
    _add_type_kwarg(kwargs, action_info, strict)
    _add_choices_kwarg(kwargs, action_info)
    _add_required_kwarg(kwargs, action_info)
    _add_help_kwarg(kwargs, action_info)
    _add_metavar_kwarg(kwargs, action_info)
    _add_version_kwarg(kwargs, action_info)
    _add_deprecated_kwarg(kwargs, action_info)

    return kwargs


def _add_action_type_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add action type to kwargs if not default store."""
    if action_info.action_type not in (ActionType.STORE, ActionType.UNKNOWN):
        kwargs["action"] = _action_type_to_argparse(action_info.action_type)


def _add_dest_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add dest to kwargs for optional arguments."""
    if action_info.is_optional:
        kwargs["dest"] = action_info.dest


def _add_nargs_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add nargs to kwargs if applicable."""
    if action_info.action_type in _NO_NARGS_ACTIONS:
        return
    if action_info.nargs is not None:
        nargs = deserialize_value(action_info.nargs)
        if nargs is not None:
            kwargs["nargs"] = nargs


def _add_const_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add const to kwargs for const actions."""
    if action_info.action_type in _CONST_ACTIONS and action_info.const is not None:
        kwargs["const"] = deserialize_value(action_info.const)


def _add_default_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add default to kwargs if present."""
    if action_info.default is not None:
        kwargs["default"] = deserialize_value(action_info.default)


def _add_type_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo, strict: bool) -> None:
    """Add type converter to kwargs if applicable."""
    if action_info.action_type in _NO_TYPE_ACTIONS:
        return
    try:
        type_func = resolve_type(action_info.type_info, action_info.file_type_info, strict=strict)
        if type_func is not None:
            kwargs["type"] = type_func
    except UnresolvableTypeError:
        if strict:
            raise


def _add_choices_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add choices to kwargs if present."""
    if action_info.choices is not None:
        kwargs["choices"] = action_info.choices


def _add_required_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add required to kwargs for optional arguments."""
    if action_info.is_optional and action_info.required:
        kwargs["required"] = True


def _add_help_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add help to kwargs if present."""
    if action_info.help is not None:
        kwargs["help"] = action_info.help


def _add_metavar_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add metavar to kwargs if present."""
    if action_info.metavar is not None:
        kwargs["metavar"] = action_info.metavar


def _add_version_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add version to kwargs if present."""
    if action_info.version is not None:
        kwargs["version"] = action_info.version


def _add_deprecated_kwarg(kwargs: Dict[str, Any], action_info: ActionInfo) -> None:
    """Add deprecated to kwargs if True (Python 3.13+)."""
    if action_info.deprecated:
        kwargs["deprecated"] = True


def _build_parser_kwargs(info: ParserInfo) -> Dict[str, Any]:
    """Build kwargs dict for ArgumentParser constructor."""
    kwargs: Dict[str, Any] = {
        "add_help": info.add_help,
        "prefix_chars": info.prefix_chars,
        "conflict_handler": info.conflict_handler,
    }

    # Optional string fields
    if info.prog:
        kwargs["prog"] = info.prog
    if info.description:
        kwargs["description"] = info.description
    if info.epilog:
        kwargs["epilog"] = info.epilog
    if info.usage:
        kwargs["usage"] = info.usage
    if info.fromfile_prefix_chars:
        kwargs["fromfile_prefix_chars"] = info.fromfile_prefix_chars

    # Formatter class
    if info.formatter_class and info.formatter_class in _FORMATTER_CLASSES:
        kwargs["formatter_class"] = _FORMATTER_CLASSES[info.formatter_class]

    # allow_abbrev (Python 3.5+)
    if hasattr(argparse.ArgumentParser, "allow_abbrev"):
        kwargs["allow_abbrev"] = info.allow_abbrev

    # argument_default
    if info.argument_default is not None:
        kwargs["argument_default"] = deserialize_value(info.argument_default)

    # exit_on_error (Python 3.9+)
    if sys.version_info >= (3, 9):
        kwargs["exit_on_error"] = info.exit_on_error

    # suggest_on_error (Python 3.14+)
    if sys.version_info >= (3, 14) and info.suggest_on_error:
        kwargs["suggest_on_error"] = info.suggest_on_error

    # color (Python 3.14+)
    if sys.version_info >= (3, 14) and not info.color:
        kwargs["color"] = info.color

    return kwargs


# --- Action addition helpers ---


def _add_version_action(
    parser: argparse.ArgumentParser, action_info: ActionInfo
) -> argparse.Action:
    """Add a version action to the parser."""
    kwargs: Dict[str, Any] = {"action": "version"}
    if action_info.version:
        kwargs["version"] = action_info.version
    if action_info.help:
        kwargs["help"] = action_info.help
    return parser.add_argument(*action_info.option_strings, **kwargs)


def _add_subparsers(parser: argparse.ArgumentParser, action_info: ActionInfo, strict: bool) -> None:
    """Add subparsers to the parser."""
    if not action_info.subparsers:
        return

    kwargs: Dict[str, Any] = {
        "dest": action_info.subparsers_dest or action_info.dest,
    }
    if action_info.subparsers_title:
        kwargs["title"] = action_info.subparsers_title
    if action_info.subparsers_description:
        kwargs["description"] = action_info.subparsers_description

    subparsers_action = parser.add_subparsers(**kwargs)

    if hasattr(subparsers_action, "required"):
        subparsers_action.required = action_info.subparsers_required

    # Get aliases mapping
    aliases_map = action_info.subparsers_aliases or {}

    for name, sub_info in action_info.subparsers.items():
        sub_parser = deserialize_parser(sub_info, strict=strict)

        # Build add_parser kwargs
        add_parser_kwargs: Dict[str, Any] = {
            "parents": [sub_parser],
            "add_help": False,
            "description": sub_parser.description,
        }

        # Add aliases if present
        if name in aliases_map:
            add_parser_kwargs["aliases"] = aliases_map[name]

        subparsers_action.add_parser(name, **add_parser_kwargs)


def _add_regular_action(
    target: Union[argparse.ArgumentParser, argparse._MutuallyExclusiveGroup],
    action_info: ActionInfo,
    strict: bool,
) -> Optional[argparse.Action]:
    """Add a regular (non-special) action to parser or mutex group."""
    kwargs = _build_action_kwargs(action_info, strict)

    if action_info.is_optional:
        return target.add_argument(*action_info.option_strings, **kwargs)
    else:
        return target.add_argument(action_info.dest, **kwargs)


# --- Main deserialization ---


def deserialize_parser(
    info: Union[ParserInfo, Dict[str, Any]], *, strict: bool = True
) -> argparse.ArgumentParser:
    """Reconstruct ArgumentParser from ParserInfo.

    Args:
        info: ParserInfo or dict representation of parser
        strict: If True, raise on unresolvable types; if False, skip them

    Returns:
        Reconstructed ArgumentParser instance
    """
    if isinstance(info, dict):
        info = _convert_parser_info(info)

    parser = argparse.ArgumentParser(**_build_parser_kwargs(info))

    # Build mutex group tracking
    mutex_membership = _build_mutex_membership(info.mutually_exclusive_groups)
    mutex_groups = _create_mutex_groups(parser, info.mutually_exclusive_groups)

    # Add all actions
    for action_info in info.actions:
        _add_action(parser, action_info, mutex_membership, mutex_groups, strict)

    return parser


def _build_mutex_membership(
    groups: List[MutualExclusionGroup],
) -> Dict[str, MutualExclusionGroup]:
    """Build mapping of dest -> mutex group."""
    membership: Dict[str, MutualExclusionGroup] = {}
    for group in groups:
        for dest in group.actions:
            membership[dest] = group
    return membership


def _create_mutex_groups(
    parser: argparse.ArgumentParser,
    groups: List[MutualExclusionGroup],
) -> Dict[int, argparse._MutuallyExclusiveGroup]:
    """Create mutex groups on parser and return id mapping."""
    mutex_objects: Dict[int, argparse._MutuallyExclusiveGroup] = {}
    for group in groups:
        mutex_objects[id(group)] = parser.add_mutually_exclusive_group(required=group.required)
    return mutex_objects


def _add_action(
    parser: argparse.ArgumentParser,
    action_info: ActionInfo,
    mutex_membership: Dict[str, MutualExclusionGroup],
    mutex_groups: Dict[int, argparse._MutuallyExclusiveGroup],
    strict: bool,
) -> None:
    """Add a single action to the parser."""
    # Skip auto-added help
    if action_info.action_type == ActionType.HELP:
        return

    # Version action
    if action_info.action_type == ActionType.VERSION:
        _add_version_action(parser, action_info)
        return

    # Subparsers
    if action_info.action_type == ActionType.PARSERS:
        _add_subparsers(parser, action_info, strict)
        return

    # Add to mutex group or directly to parser
    if action_info.dest in mutex_membership:
        group = mutex_membership[action_info.dest]
        mutex_group = mutex_groups[id(group)]
        _add_regular_action(mutex_group, action_info, strict)
    else:
        _add_regular_action(parser, action_info, strict)


# --- Public API ---


def load(data: Dict[str, Any], *, strict: bool = True) -> argparse.ArgumentParser:
    """Reconstruct parser from dictionary."""
    return deserialize_parser(data, strict=strict)


def loads(json_str: str, *, strict: bool = True) -> argparse.ArgumentParser:
    """Reconstruct parser from JSON string."""
    return deserialize_parser(json.loads(json_str), strict=strict)
