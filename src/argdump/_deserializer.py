"""Deserialize dict/JSON back to argparse parsers."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

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

_FORMATTER_CLASSES: dict[str, type[argparse.HelpFormatter]] = {
    "HelpFormatter": argparse.HelpFormatter,
    "RawDescriptionHelpFormatter": argparse.RawDescriptionHelpFormatter,
    "RawTextHelpFormatter": argparse.RawTextHelpFormatter,
    "ArgumentDefaultsHelpFormatter": argparse.ArgumentDefaultsHelpFormatter,
}

if hasattr(argparse, "MetavarTypeHelpFormatter"):
    _FORMATTER_CLASSES["MetavarTypeHelpFormatter"] = argparse.MetavarTypeHelpFormatter


def _action_type_to_argparse(action_type: ActionType | str) -> str | type:
    """Convert ActionType to argparse action string/class."""
    if isinstance(action_type, str):
        return action_type

    mapping = {
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

    if action_type in mapping:
        return mapping[action_type]

    if action_type == ActionType.BOOLEAN_OPTIONAL:
        if hasattr(argparse, "BooleanOptionalAction"):
            return argparse.BooleanOptionalAction
        raise ValueError("BooleanOptionalAction requires Python 3.9+")

    return action_type.value


def _convert_action_info(data: dict) -> ActionInfo:
    """Convert dict to ActionInfo with proper nested types."""
    data = data.copy()

    if "action_type" in data and isinstance(data["action_type"], str):
        data["action_type"] = ActionType.from_string(data["action_type"])

    if data.get("type_info") and isinstance(data["type_info"], dict):
        data["type_info"] = TypeInfo(**data["type_info"])

    if data.get("file_type_info") and isinstance(data["file_type_info"], dict):
        data["file_type_info"] = FileTypeInfo(**data["file_type_info"])

    # Recursively convert subparsers
    if data.get("subparsers"):
        data["subparsers"] = {
            name: _convert_parser_info(sub) if isinstance(sub, dict) else sub
            for name, sub in data["subparsers"].items()
        }

    return ActionInfo(**data)


def _convert_parser_info(data: dict) -> ParserInfo:
    """Convert dict to ParserInfo with proper nested types."""
    data = data.copy()

    # Remove $schema if present (not part of ParserInfo)
    data.pop("$schema", None)

    actions = data.pop("actions", [])
    groups = data.pop("argument_groups", [])
    mutex_groups = data.pop("mutually_exclusive_groups", [])

    info = ParserInfo(**data)

    info.actions = [_convert_action_info(a) if isinstance(a, dict) else a for a in actions]

    info.argument_groups = [ArgumentGroup(**g) if isinstance(g, dict) else g for g in groups]

    info.mutually_exclusive_groups = [
        MutualExclusionGroup(**g) if isinstance(g, dict) else g for g in mutex_groups
    ]

    return info


# Actions that don't accept nargs/type/const
_NO_NARGS_ACTIONS = {
    ActionType.STORE_TRUE,
    ActionType.STORE_FALSE,
    ActionType.COUNT,
    ActionType.APPEND_CONST,
    ActionType.STORE_CONST,
}

_NO_TYPE_ACTIONS = {
    ActionType.STORE_TRUE,
    ActionType.STORE_FALSE,
    ActionType.COUNT,
    ActionType.STORE_CONST,
    ActionType.APPEND_CONST,
}


def _build_add_argument_kwargs(action_info: ActionInfo, *, strict: bool) -> dict[str, Any] | None:
    """Build kwargs for parser.add_argument()."""
    if action_info.action_type in (ActionType.HELP, ActionType.PARSERS):
        return None

    kwargs: dict[str, Any] = {}
    is_optional = bool(action_info.option_strings)

    # Action type
    if action_info.action_type not in (ActionType.STORE, ActionType.UNKNOWN):
        kwargs["action"] = _action_type_to_argparse(action_info.action_type)

    # Dest (for optionals)
    if is_optional:
        kwargs["dest"] = action_info.dest

    # nargs
    if action_info.action_type not in _NO_NARGS_ACTIONS and action_info.nargs is not None:
        nargs = deserialize_value(action_info.nargs)
        if nargs is not None:
            kwargs["nargs"] = nargs

    # const
    if (
        action_info.action_type in (ActionType.STORE_CONST, ActionType.APPEND_CONST)
        and action_info.const is not None
    ):
        kwargs["const"] = deserialize_value(action_info.const)

    # default
    if action_info.default is not None:
        kwargs["default"] = deserialize_value(action_info.default)

    # type
    if action_info.action_type not in _NO_TYPE_ACTIONS:
        try:
            type_func = resolve_type(
                action_info.type_info, action_info.file_type_info, strict=strict
            )
            if type_func is not None:
                kwargs["type"] = type_func
        except UnresolvableTypeError:
            if strict:
                raise

    # choices
    if action_info.choices is not None:
        kwargs["choices"] = action_info.choices

    # required
    if is_optional and action_info.required:
        kwargs["required"] = True

    # help
    if action_info.help is not None:
        kwargs["help"] = action_info.help

    # metavar
    if action_info.metavar is not None:
        kwargs["metavar"] = action_info.metavar

    # version
    if action_info.version is not None:
        kwargs["version"] = action_info.version

    return kwargs


def _add_action_to_parser(
    parser: argparse.ArgumentParser, action_info: ActionInfo, *, strict: bool
) -> argparse.Action | None:
    """Add an action to a parser."""
    # Skip auto-added help
    if action_info.action_type == ActionType.HELP:
        return None

    # Skip subparsers (handled separately)
    if action_info.action_type == ActionType.PARSERS:
        return None

    # Version needs special handling
    if action_info.action_type == ActionType.VERSION:
        version_kwargs: dict[str, Any] = {"action": "version"}
        if action_info.version:
            version_kwargs["version"] = action_info.version
        if action_info.help:
            version_kwargs["help"] = action_info.help
        return parser.add_argument(*action_info.option_strings, **version_kwargs)

    action_kwargs = _build_add_argument_kwargs(action_info, strict=strict)
    if action_kwargs is None:
        return None

    if action_info.option_strings:
        return parser.add_argument(*action_info.option_strings, **action_kwargs)
    else:
        return parser.add_argument(action_info.dest, **action_kwargs)


def deserialize_parser(info: ParserInfo | dict, *, strict: bool = True) -> argparse.ArgumentParser:
    """Reconstruct ArgumentParser from ParserInfo."""
    if isinstance(info, dict):
        info = _convert_parser_info(info)

    # Build parser kwargs
    kwargs: dict[str, Any] = {
        "add_help": info.add_help,
        "prefix_chars": info.prefix_chars,
        "conflict_handler": info.conflict_handler,
    }

    if info.prog:
        kwargs["prog"] = info.prog
    if info.description:
        kwargs["description"] = info.description
    if info.epilog:
        kwargs["epilog"] = info.epilog
    if info.usage:
        kwargs["usage"] = info.usage

    if hasattr(argparse.ArgumentParser, "allow_abbrev"):
        kwargs["allow_abbrev"] = info.allow_abbrev

    if info.formatter_class and info.formatter_class in _FORMATTER_CLASSES:
        kwargs["formatter_class"] = _FORMATTER_CLASSES[info.formatter_class]

    if info.fromfile_prefix_chars:
        kwargs["fromfile_prefix_chars"] = info.fromfile_prefix_chars

    if info.argument_default is not None:
        kwargs["argument_default"] = deserialize_value(info.argument_default)

    if sys.version_info >= (3, 9):  # noqa: UP036
        kwargs["exit_on_error"] = info.exit_on_error

    parser = argparse.ArgumentParser(**kwargs)

    # Track mutex group membership
    mutex_dests: dict[str, MutualExclusionGroup] = {}
    for mutex_group in info.mutually_exclusive_groups:
        for dest in mutex_group.actions:
            mutex_dests[dest] = mutex_group

    # Create mutex groups
    mutex_objects: dict[int, argparse._MutuallyExclusiveGroup] = {}
    for mutex_group in info.mutually_exclusive_groups:
        mutex_objects[id(mutex_group)] = parser.add_mutually_exclusive_group(
            required=mutex_group.required
        )

    # Add actions
    for action_info in info.actions:
        if action_info.action_type == ActionType.HELP:
            continue

        # Handle subparsers
        if action_info.action_type == ActionType.PARSERS and action_info.subparsers:
            subparsers_kwargs: dict[str, Any] = {
                "dest": action_info.subparsers_dest or action_info.dest,
            }
            if action_info.subparsers_title:
                subparsers_kwargs["title"] = action_info.subparsers_title
            if action_info.subparsers_description:
                subparsers_kwargs["description"] = action_info.subparsers_description

            subparsers_action = parser.add_subparsers(**subparsers_kwargs)

            if hasattr(subparsers_action, "required"):
                subparsers_action.required = action_info.subparsers_required

            for name, sub_info in action_info.subparsers.items():
                sub_parser = deserialize_parser(sub_info, strict=strict)
                subparsers_action.add_parser(
                    name,
                    parents=[sub_parser],
                    add_help=False,
                    description=sub_parser.description,
                )
            continue

        # Add to mutex group or regular parser
        if action_info.dest in mutex_dests:
            mutex_group = mutex_dests[action_info.dest]
            group_obj = mutex_objects[id(mutex_group)]
            action_kwargs = _build_add_argument_kwargs(action_info, strict=strict)
            if action_kwargs is not None:
                if action_info.option_strings:
                    group_obj.add_argument(*action_info.option_strings, **action_kwargs)
                else:
                    group_obj.add_argument(action_info.dest, **action_kwargs)
        else:
            _add_action_to_parser(parser, action_info, strict=strict)

    return parser


def load(data: dict, *, strict: bool = True) -> argparse.ArgumentParser:
    """Reconstruct parser from dictionary."""
    return deserialize_parser(data, strict=strict)


def loads(json_str: str, *, strict: bool = True) -> argparse.ArgumentParser:
    """Reconstruct parser from JSON string."""
    return deserialize_parser(json.loads(json_str), strict=strict)
