"""Serialize argparse parsers to dict/JSON."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ._schema import SCHEMA_URL_V1, get_environment_info
from ._types import file_type_info_from_instance, type_info_from_callable
from ._values import serialize_value
from .models import (
    ActionInfo,
    ActionType,
    ArgumentGroup,
    MutualExclusionGroup,
    ParserInfo,
    TypeInfo,
)

# Map argparse internal class names to ActionType
_ACTION_CLASS_MAP: Dict[str, ActionType] = {
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


# --- Action classification ---


def _classify_action(action: argparse.Action) -> Tuple[ActionType, Optional[str]]:
    """Determine ActionType for an action.

    Returns:
        Tuple of (action_type, custom_class_name or None)
    """
    class_name = type(action).__name__

    # Direct match
    if class_name in _ACTION_CLASS_MAP:
        return _ACTION_CLASS_MAP[class_name], None

    # Check inheritance chain
    for base in type(action).__mro__:
        if base.__name__ in _ACTION_CLASS_MAP:
            return _ACTION_CLASS_MAP[base.__name__], class_name

    return ActionType.UNKNOWN, class_name


# --- Type extraction ---


def _extract_type_info(
    action: argparse.Action,
) -> Tuple[Optional[TypeInfo], Optional[Any]]:
    """Extract type info and file type info from an action.

    Returns:
        Tuple of (type_info, file_type_info)
    """
    if action.type is None:
        return None, None

    if isinstance(action.type, argparse.FileType):
        file_type_info = file_type_info_from_instance(action.type)
        type_info = TypeInfo(name="FileType", module="argparse", serializable=True)
        return type_info, file_type_info

    return type_info_from_callable(action.type), None


# --- Action serialization ---


def _serialize_action(action: argparse.Action) -> ActionInfo:
    """Convert an argparse Action to ActionInfo."""
    action_type, custom_class = _classify_action(action)
    type_info, file_type_info = _extract_type_info(action)

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
        deprecated=getattr(action, "deprecated", False),  # Python 3.13+
        custom_action_class=custom_class,
    )

    # Handle action-specific attributes
    _add_version_info(info, action, action_type)
    _add_subparsers_info(info, action, action_type)

    return info


def _add_version_info(info: ActionInfo, action: argparse.Action, action_type: ActionType) -> None:
    """Add version string if this is a version action."""
    if action_type == ActionType.VERSION:
        info.version = getattr(action, "version", None)


def _add_subparsers_info(
    info: ActionInfo, action: argparse.Action, action_type: ActionType
) -> None:
    """Add subparser information if this is a subparsers action."""
    if action_type != ActionType.PARSERS:
        return

    info.subparsers = {}
    info.subparsers_title = getattr(action, "_group_title", None)
    info.subparsers_description = getattr(action, "_description", None)
    info.subparsers_dest = action.dest
    info.subparsers_required = getattr(action, "required", False)

    # Get parser map from either attribute
    parser_map: Dict[str, argparse.ArgumentParser] = (
        getattr(action, "_name_parser_map", {}) or getattr(action, "choices", {}) or {}
    )

    # Build reverse mapping to find aliases
    # _name_parser_map may have multiple names pointing to the same parser
    parser_to_names: Dict[int, List[str]] = {}
    for name, subparser in parser_map.items():
        parser_id = id(subparser)
        if parser_id not in parser_to_names:
            parser_to_names[parser_id] = []
        parser_to_names[parser_id].append(name)

    # Track which parsers we've already serialized
    serialized_parsers: Dict[int, str] = {}  # parser id -> canonical name
    info.subparsers_aliases = {}

    for name, subparser in parser_map.items():
        parser_id = id(subparser)

        if parser_id in serialized_parsers:
            # This is an alias - skip serializing again
            continue

        # This is the first (canonical) name for this parser
        serialized_parsers[parser_id] = name
        info.subparsers[name] = serialize_parser(subparser)

        # Record any aliases (other names pointing to same parser)
        all_names = parser_to_names[parser_id]
        aliases = [n for n in all_names if n != name]
        if aliases:
            info.subparsers_aliases[name] = aliases


# --- Parser serialization ---


def serialize_parser(parser: argparse.ArgumentParser) -> ParserInfo:
    """Serialize an ArgumentParser to ParserInfo."""
    info = _create_parser_info(parser)
    action_to_dest = _serialize_actions(parser, info)
    _serialize_argument_groups(parser, info, action_to_dest)
    _serialize_mutex_groups(parser, info, action_to_dest)
    return info


def _create_parser_info(parser: argparse.ArgumentParser) -> ParserInfo:
    """Create base ParserInfo from parser attributes."""
    formatter_class: Optional[str] = None
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

    # Python 3.9+
    if hasattr(parser, "exit_on_error"):
        info.exit_on_error = parser.exit_on_error

    # Python 3.14+
    if hasattr(parser, "suggest_on_error"):
        info.suggest_on_error = parser.suggest_on_error
    if hasattr(parser, "color"):
        info.color = parser.color

    return info


def _serialize_actions(parser: argparse.ArgumentParser, info: ParserInfo) -> Dict[int, str]:
    """Serialize all actions and return id->dest mapping."""
    action_to_dest: Dict[int, str] = {}

    for action in parser._actions:
        action_info = _serialize_action(action)
        info.actions.append(action_info)
        action_to_dest[id(action)] = action.dest

    return action_to_dest


def _serialize_argument_groups(
    parser: argparse.ArgumentParser,
    info: ParserInfo,
    action_to_dest: Dict[int, str],
) -> None:
    """Serialize argument groups."""
    for group in parser._action_groups:
        info.argument_groups.append(
            ArgumentGroup(
                title=group.title,
                description=group.description,
                actions=[
                    action_to_dest[id(a)] for a in group._group_actions if id(a) in action_to_dest
                ],
            )
        )


def _serialize_mutex_groups(
    parser: argparse.ArgumentParser,
    info: ParserInfo,
    action_to_dest: Dict[int, str],
) -> None:
    """Serialize mutually exclusive groups."""
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


# --- JSON encoding ---


class _Encoder(json.JSONEncoder):
    """JSON encoder for dataclasses and enums."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        return super().default(o)


# --- Public API ---


def dump(parser: argparse.ArgumentParser, *, include_env: bool = True) -> Dict[str, Any]:
    """Serialize parser to dictionary.

    Args:
        parser: The ArgumentParser to serialize
        include_env: Whether to include environment metadata (default True)

    Returns:
        Dictionary representation with $schema, optional $env, and parser data
    """
    info = serialize_parser(parser)
    # JSON round-trip for consistent enum/dataclass handling
    data: Dict[str, Any] = json.loads(json.dumps(info, cls=_Encoder))

    # Build output with $schema first
    result: Dict[str, Any] = {"$schema": SCHEMA_URL_V1}

    if include_env:
        env_info = get_environment_info()
        result["$env"] = json.loads(json.dumps(env_info, cls=_Encoder))

    result.update(data)
    return result


def dumps(parser: argparse.ArgumentParser, *, include_env: bool = True, **json_kwargs: Any) -> str:
    """Serialize parser to JSON string.

    Args:
        parser: The ArgumentParser to serialize
        include_env: Whether to include environment metadata (default True)
        **json_kwargs: Additional arguments passed to json.dumps (e.g. indent)

    Returns:
        JSON string representation
    """
    return json.dumps(dump(parser, include_env=include_env), **json_kwargs)
