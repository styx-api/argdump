"""Serialize argparse parsers to dict/JSON."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from argdump._schema import SCHEMA_URL_V1

from .models import (
    ActionType,
    TypeInfo,
    ActionInfo,
    MutualExclusionGroup,
    ArgumentGroup,
    ParserInfo,
)
from ._types import type_info_from_callable, file_type_info_from_instance
from ._values import serialize_value


# Map argparse internal class names to ActionType
_ACTION_CLASS_MAP: dict[str, ActionType] = {
    "_StoreAction": ActionType.STORE,
    "_StoreConstAction": ActionType.STORE_CONST,
    "_StoreTrueAction": ActionType.STORE_TRUE,
    "_StoreFalseAction": ActionType.STORE_FALSE,
    "_AppendAction": ActionType.APPEND,
    "_AppendConstAction": ActionType.APPEND_CONST,
    "_CountAction": ActionType.COUNT,
    "_HelpAction": ActionType.HELP,
    "_VersionAction": ActionType.VERSION,
    "_SubParsersAction": ActionType.PARSERS,
    "_ExtendAction": ActionType.EXTEND,
    "BooleanOptionalAction": ActionType.BOOLEAN_OPTIONAL,
}


def _classify_action(action: argparse.Action) -> tuple[ActionType, str | None]:
    """Determine ActionType for an action."""
    class_name = type(action).__name__

    if class_name in _ACTION_CLASS_MAP:
        return _ACTION_CLASS_MAP[class_name], None

    # Check inheritance
    for base_name, action_type in _ACTION_CLASS_MAP.items():
        for base in type(action).__mro__:
            if base.__name__ == base_name:
                return action_type, class_name

    return ActionType.UNKNOWN, class_name


def _serialize_action(action: argparse.Action) -> ActionInfo:
    """Convert an argparse Action to ActionInfo."""
    action_type, custom_class = _classify_action(action)

    # Extract type info
    type_info = None
    file_type_info = None

    if action.type is not None:
        if isinstance(action.type, argparse.FileType):
            file_type_info = file_type_info_from_instance(action.type)
            type_info = TypeInfo(name="FileType", module="argparse", serializable=True)
        else:
            type_info = type_info_from_callable(action.type)

    info = ActionInfo(
        option_strings=list(action.option_strings),
        dest=action.dest,
        action_type=action_type,
        nargs=serialize_value(action.nargs) if action.nargs is not None else None,
        const=serialize_value(action.const),
        default=serialize_value(action.default),
        type_info=type_info,
        file_type_info=file_type_info,
        choices=list(action.choices) if action.choices is not None else None,
        required=getattr(action, "required", False),
        help=action.help if action.help != argparse.SUPPRESS else None,
        metavar=action.metavar,
        custom_action_class=custom_class,
    )

    # Version action
    if action_type == ActionType.VERSION:
        info.version = getattr(action, "version", None)

    # Subparsers
    if action_type == ActionType.PARSERS:
        info.subparsers = {}
        info.subparsers_title = getattr(action, "_group_title", None)
        info.subparsers_description = getattr(action, "_description", None)
        info.subparsers_dest = action.dest
        info.subparsers_required = getattr(action, "required", False)

        parser_map = getattr(action, "_name_parser_map", {}) or getattr(
            action, "choices", {}
        ) or {}
        for name, subparser in parser_map.items():
            info.subparsers[name] = serialize_parser(subparser)

    return info


def serialize_parser(parser: argparse.ArgumentParser) -> ParserInfo:
    """Serialize an ArgumentParser to ParserInfo."""
    formatter_class: str | None = None
    if parser.formatter_class is not None:
        formatter_class = getattr(parser.formatter_class, "__name__", None)

    info = ParserInfo(
        prog=parser.prog,
        description=parser.description,
        epilog=parser.epilog,
        usage=parser.usage,
        add_help=parser.add_help,
        allow_abbrev=getattr(parser, "allow_abbrev", True),
        formatter_class=formatter_class,
        prefix_chars=parser.prefix_chars,
        fromfile_prefix_chars=parser.fromfile_prefix_chars,
        argument_default=serialize_value(parser.argument_default),
        conflict_handler=parser.conflict_handler,
    )

    if hasattr(parser, "exit_on_error"):
        info.exit_on_error = parser.exit_on_error

    # Map action id -> dest for group tracking
    action_to_dest: dict[int, str] = {}

    for action in parser._actions:
        action_info = _serialize_action(action)
        info.actions.append(action_info)
        action_to_dest[id(action)] = action.dest

    # Argument groups
    for group in parser._action_groups:
        info.argument_groups.append(
            ArgumentGroup(
                title=group.title,
                description=group.description,
                actions=[
                    action_to_dest[id(a)]
                    for a in group._group_actions
                    if id(a) in action_to_dest
                ],
            )
        )

    # Mutex groups
    for mutex_group in parser._mutually_exclusive_groups:
        info.mutually_exclusive_groups.append(
            MutualExclusionGroup(
                required=mutex_group.required,
                actions=[
                    action_to_dest[id(a)]
                    for a in mutex_group._group_actions
                    if id(a) in action_to_dest
                ],
            )
        )

    return info


class _Encoder(json.JSONEncoder):
    """JSON encoder for dataclasses and enums."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        return super().default(o)


def dump(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Serialize parser to dictionary."""
    info = serialize_parser(parser)
    # JSON round-trip for consistent enum/dataclass handling
    data = json.loads(json.dumps(info, cls=_Encoder))
    # Put $schema first
    return {"$schema": SCHEMA_URL_V1, **data}


def dumps(parser: argparse.ArgumentParser, **json_kwargs: Any) -> str:
    """Serialize parser to JSON string."""
    return json.dumps(dump(parser), **json_kwargs)