"""
argdump - Serialize and deserialize argparse parsers.

Usage:
    import argparse
    import argdump

    parser = argparse.ArgumentParser(prog="mytool")
    parser.add_argument("input")
    parser.add_argument("-v", "--verbose", action="count", default=0)

    # Serialize
    data = argdump.dump(parser)      # -> dict
    json_str = argdump.dumps(parser) # -> JSON string

    # Deserialize
    restored = argdump.load(data)
    restored = argdump.loads(json_str)
"""

from ._deserializer import load, loads
from ._schema import EnvironmentInfo, get_environment_info
from ._serializer import dump, dumps
from ._types import UnresolvableTypeError

# Models (for type hints if needed)
from .models import (
    ActionInfo,
    ActionType,
    ArgumentGroup,
    FileTypeInfo,
    MutualExclusionGroup,
    ParserInfo,
    TypeInfo,
)

__version__ = "0.1.0"

__all__ = [
    # Primary API
    "dump",
    "dumps",
    "load",
    "loads",
    # Exceptions
    "UnresolvableTypeError",
    # Models
    "ActionType",
    "TypeInfo",
    "FileTypeInfo",
    "ActionInfo",
    "MutualExclusionGroup",
    "ArgumentGroup",
    "ParserInfo",
    "EnvironmentInfo",
    # Utilities
    "get_environment_info",
]
