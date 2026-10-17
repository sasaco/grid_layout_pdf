"""JSON-shaped metadata snapshots shared by the scene and layout boundaries.

Both boundaries accept the same contract, so neither depends on the other's
implementation: values are JSON-compatible, containers become recursively
immutable, and cycles are rejected.
"""

from collections.abc import Mapping
from math import isfinite
from types import MappingProxyType


def freeze_metadata(value):
    """Copy JSON-compatible values to recursively immutable containers."""
    return _freeze(value, set())


def json_value(value):
    """Copy frozen metadata into JSON containers without changing local values."""
    if isinstance(value, Mapping):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def _freeze(value, active: set[int]):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("metadata numbers must be finite")
        return value
    if isinstance(value, (Mapping, list, tuple)):
        identity = id(value)
        if identity in active:
            raise ValueError("metadata must not contain cycles")
        active.add(identity)
        try:
            if isinstance(value, Mapping):
                if any(not isinstance(key, str) for key in value):
                    raise ValueError("metadata keys must be strings")
                return MappingProxyType({
                    key: _freeze(item, active) for key, item in value.items()
                })
            return tuple(_freeze(item, active) for item in value)
        finally:
            active.remove(identity)
    raise ValueError(f"Unsupported metadata value: {type(value).__name__}")
