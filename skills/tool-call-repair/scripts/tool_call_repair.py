#!/usr/bin/env python3
"""Validate-then-repair for LLM tool-call inputs. Standard library only.

Technique by Ahmad Awais (@MrAhmadAwais), published in the Command Code
"Tool Call Repairs" write-up: https://commandcode.ai/docs/harness-engineering/tool-call-repairs
This is an independent Python reimplementation of the documented method — none
of Command Code's proprietary source is used or included.

The idea: a strict tool schema filters out noise, but also filters out
*recoverable* noise from models that did not memorize your exact JSON contract.
So instead of preprocessing inputs before validation (which corrupts valid data
that merely looks broken), you:

  1. Validate the input as-is. If it passes, ship it untouched.
  2. On failure, walk the validator's own issue list. At each failing path, try
     a small ordered catalog of repairs until one makes that path valid.
  3. Validate again. Log `tool_input_repaired:<tool>` or, if still invalid,
     `tool_input_invalid:<tool>` and return a model-readable retry message.

The catalog is the finite, compositional set of mistakes open models make
(observed by Awais across deepseek-flash, deepseek-v4-pro, glm, qwen):

  - null-for-optional : {"timeoutMs": null}      -> key omitted
  - json-array-parse  : "[\"a\",\"b\"]"          -> ["a","b"]     (before bare-string-wrap)
  - empty-placeholder : {}  where array expected -> []
  - bare-string-wrap  : "foo" where array expected -> ["foo"]
  - path-autolink      : "/p/[notes.md](http://notes.md)" -> "/p/notes.md"  (DeepSeek chat-prior leak)

Ordering matters: json-array-parse must run before bare-string-wrap, or
'["a","b"]' becomes '[\'["a","b"]\']' (schema-valid, meaning lost).

Relational invariants (e.g. read_file's "offset requires limit") cannot be
fixed by per-field input repair, because each field is independently valid;
`fill_relational_defaults` handles those by extending semantics and surfacing
the choice back to the model WITHOUT an `Error:` prefix, so it self-corrects.
"""
from __future__ import annotations
import json, re
from typing import Any, Callable, Optional

# ---- lightweight schema validation (stdlib; the "validator complains first" step) ----

_JSON_TYPES = {
    "object": dict, "array": list, "string": str,
    "number": (int, float), "integer": int, "boolean": bool, "null": type(None),
}


def _type_ok(value: Any, typ: str) -> bool:
    if typ == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if typ == "boolean":
        return isinstance(value, bool)
    py = _JSON_TYPES.get(typ)
    return isinstance(value, py) if py else True


def _expected_types(prop_schema: dict) -> list[str]:
    t = prop_schema.get("type")
    if t is None:
        return []
    return [t] if isinstance(t, str) else list(t)


def validate(schema: dict, data: Any, _path: tuple = ()) -> list[dict]:
    """Return a list of issues. Each issue: {path, expected, kind, value}.

    kind is 'missing' (required key absent) or 'type' (wrong type). Covers the
    object/properties/required/array-items subset that tool schemas use.
    """
    issues: list[dict] = []
    types = _expected_types(schema)
    if types and not any(_type_ok(data, t) for t in types):
        issues.append({"path": _path, "expected": types, "kind": "type", "value": data})
        return issues  # wrong container type; deeper checks are meaningless

    # path fields (the pathString() equivalent): a valid string can still be a
    # degenerate auto-linked path. Flag it so the repair layer can unwrap it.
    if schema.get("format") == "path" and isinstance(data, str):
        m = _AUTOLINK.match(data)
        if m and m.group("text") == re.sub(r"^[a-z][a-z0-9+.\-]*://", "", m.group("url"), flags=re.I):
            issues.append({"path": _path, "expected": ["string"], "kind": "path-autolink", "value": data})

    if "object" in (types or ["object"]) and isinstance(data, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in data:
                issues.append({"path": _path + (key,), "expected": _expected_types(props.get(key, {})),
                               "kind": "missing", "value": None})
        for key, sub in props.items():
            if key in data:
                issues.extend(validate(sub, data[key], _path + (key,)))
    if isinstance(data, list) and "items" in schema:
        item_schema = schema["items"]
        for i, item in enumerate(data):
            issues.extend(validate(item_schema, item, _path + (i,)))
    return issues


# ---- pure repairs: (value, expected_types) -> (new_value, applied?) ----

_AUTOLINK = re.compile(r"^(?P<pre>.*?)\[(?P<text>[^\]]+)\]\((?P<url>[^)]+)\)(?P<post>.*)$")


def repair_null_for_optional(value, expected, required: bool):
    # a None on an OPTIONAL field is best expressed by omitting the key entirely
    if value is None and not required:
        return None, True  # caller removes the key on applied=True + sentinel
    return value, False


def repair_json_array_parse(value, expected):
    if "array" in expected and isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return value, False
        if isinstance(parsed, list):
            return parsed, True
    return value, False


def repair_empty_placeholder(value, expected):
    if "array" in expected and isinstance(value, dict) and not value:
        return [], True
    return value, False


def repair_bare_string_wrap(value, expected):
    # only after json-array-parse has had its turn
    if "array" in expected and isinstance(value, str):
        return [value], True
    return value, False


def repair_path_autolink(value, expected):
    """Unwrap only the degenerate DeepSeek case where a path was auto-linked:
    link text equals the url without its protocol. Real markdown links pass
    through untouched (text != url-sans-protocol)."""
    if "string" not in expected or not isinstance(value, str):
        return value, False
    m = _AUTOLINK.match(value)
    if not m:
        return value, False
    text, url = m.group("text"), m.group("url")
    url_no_proto = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", url, flags=re.I)
    if text == url_no_proto:
        return m.group("pre") + text + m.group("post"), True
    return value, False


# ordered catalog; json-array-parse strictly before bare-string-wrap
_SHAPE_REPAIRS: list[tuple[str, Callable]] = [
    ("json-array-parse", repair_json_array_parse),
    ("empty-placeholder", repair_empty_placeholder),
    ("bare-string-wrap", repair_bare_string_wrap),
    ("path-autolink", repair_path_autolink),
]


def _get(data, path):
    cur = data
    for p in path:
        cur = cur[p]
    return cur


def _set(data, path, value):
    cur = data
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = value


def _del(data, path):
    cur = data
    for p in path[:-1]:
        cur = cur[p]
    del cur[path[-1]]


def _required_at(schema: dict, path: tuple) -> bool:
    """Is the leaf named by `path` in its parent object's required list?"""
    if not path:
        return True
    parent = schema
    for p in path[:-1]:
        if isinstance(p, int):
            parent = parent.get("items", {})
        else:
            parent = parent.get("properties", {}).get(p, {})
    return path[-1] in parent.get("required", [])


def repair_tool_input(schema: dict, data: Any, tool_name: str = "tool",
                      model: Optional[str] = None) -> dict:
    """Validate-then-repair. Returns:
      {"data": <possibly repaired>, "status": "ok"|"repaired"|"invalid",
       "repairs": [{"path","repair"}...], "log": "tool_input_repaired:...",
       "message": <model-readable retry text, only when invalid>}
    Valid inputs are returned byte-for-byte unchanged.
    """
    import copy
    issues = validate(schema, data)
    if not issues:
        return {"data": data, "status": "ok", "repairs": [], "log": None}

    data = copy.deepcopy(data)
    applied: list[dict] = []
    for issue in issues:
        path = issue["path"]
        if issue["kind"] == "missing":
            continue  # a genuinely absent required field is not ours to invent
        try:
            value = _get(data, path)
        except (KeyError, IndexError, TypeError):
            continue
        expected = issue["expected"]

        # null-for-optional first (structural: remove the key)
        _, drop = repair_null_for_optional(value, expected, _required_at(schema, path))
        if drop:
            _del(data, path)
            applied.append({"path": list(path), "repair": "null-for-optional"})
            continue

        for name, fn in _SHAPE_REPAIRS:
            new_value, ok = fn(value, expected)
            if ok:
                _set(data, path, new_value)
                applied.append({"path": list(path), "repair": name})
                value = new_value
                # re-check this leaf; a value can need parse THEN nothing else
                if all(_type_ok(new_value, t) for t in expected):
                    break

    remaining = validate(schema, data)
    if not remaining:
        return {"data": data, "status": "repaired", "repairs": applied,
                "log": f"tool_input_repaired:{tool_name}"}

    return {"data": data, "status": "invalid", "repairs": applied,
            "log": f"tool_input_invalid:{tool_name}",
            "message": _retry_message(remaining)}


def _retry_message(issues: list[dict]) -> str:
    parts = []
    for i in issues:
        loc = "/".join(str(p) for p in i["path"]) or "(root)"
        if i["kind"] == "missing":
            parts.append(f"missing required field `{loc}`")
        else:
            parts.append(f"`{loc}` should be {' or '.join(i['expected'])}, got {type(i['value']).__name__}")
    return "Tool input could not be validated: " + "; ".join(parts) + "."


# ---- relational invariants: extend semantics, surface the choice, no Error: prefix ----

def fill_relational_defaults(args: dict, *, a: str, b: str,
                             default_a: Any, default_b: Any) -> tuple[dict, Optional[str]]:
    """For a mutually-dependent pair (e.g. offset/limit): if exactly one is
    present, fill the other with the intended default and return a plain note
    (NO `Error:` prefix, so the TUI does not paint it red and the model can
    self-correct next turn). Returns (args, note_or_None).

    Example (read_file):
        args, note = fill_relational_defaults(args, a="offset", b="limit",
                                              default_a=0, default_b=2000)
    """
    args = dict(args)
    has_a, has_b = a in args and args[a] is not None, b in args and args[b] is not None
    if has_a == has_b:
        return args, None
    if has_a and not has_b:
        args[b] = default_b
        return args, (f"Note: {b} was not provided; defaulted to {default_b}. "
                      f"To change it, retry with both {a} and {b}.")
    args[a] = default_a
    return args, (f"Note: {a} was not provided; defaulted to {default_a}. "
                  f"To change it, retry with both {a} and {b}.")


if __name__ == "__main__":
    import sys
    # demo: python3 tool_call_repair.py '<schema-json>' '<data-json>'
    if len(sys.argv) == 3:
        out = repair_tool_input(json.loads(sys.argv[1]), json.loads(sys.argv[2]))
        print(json.dumps(out, indent=2))
    else:
        print(__doc__)
