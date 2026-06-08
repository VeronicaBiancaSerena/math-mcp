"""A deliberately small JSON-Schema-subset validator.

The registry's ``payload_schema`` entries use only a fixed subset of JSON Schema
(``type``, ``required``, ``properties``, ``additionalProperties``, ``items``,
``enum``, ``maxLength``, ``maxItems``, ``minimum``, ``maximum``). This module checks a
payload against that subset. It is the first, cheap gate in the dispatcher and the
oracle that conformance tests use to confirm every ``example_payload`` is valid.

It is *not* a replacement for the per-operation Pydantic validation that handlers run;
agents may craft payloads the schema accepts but a handler still rejects.
"""

from __future__ import annotations

from typing import Any

_TYPE_CHECKS: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def _type_ok(value: Any, type_name: str) -> bool:
    expected = _TYPE_CHECKS.get(type_name)
    if expected is None:
        return True
    # bool is a subclass of int; keep them distinct.
    if type_name == "integer" and isinstance(value, bool):
        return False
    if type_name == "number" and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def validate_payload(
    payload: Any,
    schema: dict[str, Any],
    path: str = "payload",
    *,
    reject_additional: bool = True,
    enforce_required: bool = True,
) -> list[str]:
    """Return a list of human-readable validation errors (empty == valid).

    ``reject_additional`` controls whether unknown object keys are flagged. The
    conformance oracle keeps the default (``True``, honoring ``additionalProperties: false``
    exactly). The runtime dispatch gate passes ``False`` so that harmless extra fields —
    and the deliberate ``payload.domains`` misplacement that the discrete handler turns
    into a migration hint (guide §24.5) — still reach the handler.

    ``enforce_required`` controls the ``required`` list. The oracle keeps it ``True``; the
    runtime gate passes ``False`` and leaves required-field checking to the handlers,
    because several operations accept *either* ``expression`` *or* ``expr_ast`` (an OR the
    flat schema subset cannot express). The gate still enforces type / enum / bounds /
    lengths — exactly where handlers are intentionally lenient.
    """
    errors: list[str] = []
    _validate(payload, schema, path, errors, reject_additional, enforce_required)
    return errors


def _validate(
    value: Any,
    schema: dict[str, Any],
    path: str,
    errors: list[str],
    reject_additional: bool = True,
    enforce_required: bool = True,
) -> None:
    type_name = schema.get("type")
    if type_name is not None and not _type_ok(value, type_name):
        errors.append(f"{path}: expected type {type_name}, got {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")

    if type_name == "string" and isinstance(value, str):
        max_len = schema.get("maxLength")
        if max_len is not None and len(value) > max_len:
            errors.append(f"{path}: string length {len(value)} exceeds maxLength {max_len}")

    if type_name == "integer" and isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} above maximum {schema['maximum']}")

    if type_name == "array" and isinstance(value, list):
        max_items = schema.get("maxItems")
        if max_items is not None and len(value) > max_items:
            errors.append(f"{path}: array length {len(value)} exceeds maxItems {max_items}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                _validate(
                    item, item_schema, f"{path}[{i}]", errors, reject_additional, enforce_required
                )

    if type_name == "object" and isinstance(value, dict):
        properties: dict[str, Any] = schema.get("properties", {})
        if enforce_required:
            for required in schema.get("required", []):
                if required not in value:
                    errors.append(f"{path}: missing required field '{required}'")
        additional = schema.get("additionalProperties", True)
        for key, sub in value.items():
            if key in properties:
                _validate(
                    sub, properties[key], f"{path}.{key}", errors, reject_additional,
                    enforce_required,
                )
            elif isinstance(additional, dict):
                _validate(
                    sub, additional, f"{path}.{key}", errors, reject_additional, enforce_required
                )
            elif additional is False and reject_additional:
                errors.append(f"{path}: unexpected field '{key}'")
