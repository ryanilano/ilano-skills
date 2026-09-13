---
name: tool-call-repair
description: "Repair malformed LLM tool-call inputs by validate-then-repair instead of failing the call. Use when an open or cheaper model (DeepSeek, Qwen, GLM, Kimi, local) keeps bouncing off strict tool/function schemas — null for an optional field, a stringified array, a bare string where an array is wanted, an empty {} placeholder, or a markdown auto-linked file path. Wrap a tool's input validation with this so recoverable noise is fixed at the exact failing path and the model gets a readable retry message when it truly can't be fixed. Technique by Ahmad Awais; stdlib-only Python."
---

# tool-call-repair

Do not fail a tool call on recoverable noise. Validate first; repair only where the schema actually disagreed.

```bash
python3 scripts/tool_call_repair.py '<schema-json>' '<data-json>'
```

Or import it:

```python
from tool_call_repair import repair_tool_input, fill_relational_defaults

out = repair_tool_input(tool_schema, model_supplied_args, tool_name="readFile", model="deepseek-v4-flash")
if out["status"] == "invalid":
    return out["message"]      # model-readable, no "Error:" prefix
run_tool(out["data"])          # valid or repaired input
```

## Why

A strict schema filters out noise, but it also filters out *recoverable* noise
from any model that did not memorize your exact JSON contract. Big commercial
models absorb that cost invisibly; open and cheap models pay it loudly and get
called "bad at tool calls." It's usually a harness problem, not a model problem.
Ahmad Awais showed DeepSeek V4 Pro beat a frontier model 6/10 on internal evals
once a repair layer handled its quirks.

## The catalogue (finite, compositional, ordered)

| Repair | Model sent | Schema wanted |
|---|---|---|
| null-for-optional | `{"timeoutMs": null}` | key omitted |
| json-array-parse | `"[\"a\",\"b\"]"` | `["a","b"]` |
| empty-placeholder | `{}` (array field) | `[]` |
| bare-string-wrap | `"foo"` | `["foo"]` |
| path-autolink | `"/p/[notes.md](http://notes.md)"` | `"/p/notes.md"` |

**Order matters:** json-array-parse runs before bare-string-wrap, or
`'["a","b"]'` becomes `['["a","b"]']` — schema-valid, meaning lost.

## Rules

1. **Valid inputs are never touched.** Parse as-is; only on failure walk the
   issue list and repair at the failing paths. Preprocessing-before-validation
   corrupts valid data that merely looks broken (e.g. file content that is
   itself JSON-shaped).
2. **Mark path fields** with `"format": "path"` in the schema (the `pathString()`
   equivalent) so the degenerate markdown-auto-link leak is caught. Real links
   like `[click](https://x.com)` pass through untouched.
3. **Relational invariants are not input repair.** For a mutually-dependent pair
   like read_file's offset/limit, use `fill_relational_defaults`: fill the
   intended default and surface the choice with NO `Error:` prefix, so the model
   self-corrects next turn.
4. **Telemetry is free.** The `log` field (`tool_input_repaired:<tool>` /
   `tool_input_invalid:<tool>`) lets you watch repair rates per (model, tool)
   and catch a regression before users do.

## Attribution

Technique and catalogue by **Ahmad Awais (@MrAhmadAwais)**, published in the
Command Code "Tool Call Repairs" write-up:
https://commandcode.ai/docs/harness-engineering/tool-call-repairs
This skill is an independent Python reimplementation of the documented method.
No Command Code proprietary source is used or included.

## Requirements

`python3`, standard library only. `scripts/test_tool_call_repair.py` runs
offline in under a second.
