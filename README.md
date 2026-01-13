# argdump

Serialize and deserialize Python [argparse](https://docs.python.org/3/library/argparse.html) parsers.

## Installation

```bash
pip install argdump
```

## Usage

```python
import argparse
import argdump

# Create a parser
parser = argparse.ArgumentParser(prog="mytool")
parser.add_argument("input")
parser.add_argument("-v", "--verbose", action="count", default=0)
parser.add_argument("--format", choices=["json", "csv"])

# Serialize
data = argdump.dump(parser)       # dict
json_str = argdump.dumps(parser)  # JSON string

# Deserialize
restored = argdump.load(data)
restored = argdump.loads(json_str)

# Use normally
args = restored.parse_args(["input.txt", "-vvv", "--format", "json"])
```

## JSON Schema

A JSON Schema for validating serialized output is available at [`docs/schema-v1.json`](docs/schema-v1.json).

## Features

- All standard actions (store, append, count, etc.)
- Subparsers with aliases
- Mutual exclusion and argument groups
- Type converters (builtins, FileType, importable functions)
- Choices, defaults, metavar, help text
- Environment metadata (`$env`) for reproducibility

## Options

```python
# Exclude environment metadata
argdump.dump(parser, include_env=False)

# Non-strict mode: skip unresolvable types instead of raising
argdump.load(data, strict=False)
```

## Limitations

Lambdas and closures cannot be serialized. Use `strict=False` to skip them:

```python
parser.add_argument("--value", type=lambda x: int(x) * 2)

argdump.load(argdump.dump(parser), strict=False)  # type becomes None
argdump.load(argdump.dump(parser), strict=True)   # raises UnresolvableTypeError
```

## License

MIT