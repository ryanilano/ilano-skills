#!/usr/bin/env python3
"""Offline tests for tool_call_repair. Stdlib only: python3 test_tool_call_repair.py"""
import unittest
from tool_call_repair import (
    validate, repair_tool_input, fill_relational_defaults,
    repair_json_array_parse, repair_bare_string_wrap, repair_path_autolink,
)

ARR = {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}},
       "required": ["paths"]}
OPT = {"type": "object", "properties": {"cmd": {"type": "string"}, "timeoutMs": {"type": "integer"}},
       "required": ["cmd"]}
PATH = {"type": "object", "properties": {"filePath": {"type": "string", "format": "path"}}, "required": ["filePath"]}


class ValidInputsUntouched(unittest.TestCase):
    def test_valid_ships_unchanged(self):
        data = {"paths": ["a", "b"]}
        out = repair_tool_input(ARR, data)
        self.assertEqual(out["status"], "ok")
        self.assertIs(out["data"], data)  # same object, not copied

    def test_valid_json_shaped_content_not_rewritten(self):
        # the bug Awais hit: preprocessing corrupted valid json-shaped strings
        schema = {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}
        out = repair_tool_input(schema, {"content": '["a","b"]'})
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["data"]["content"], '["a","b"]')


class ShapeRepairs(unittest.TestCase):
    def test_bare_string_wrap(self):
        out = repair_tool_input(ARR, {"paths": "src/index.ts"})
        self.assertEqual(out["status"], "repaired")
        self.assertEqual(out["data"]["paths"], ["src/index.ts"])

    def test_json_array_parse(self):
        out = repair_tool_input(ARR, {"paths": '["a","b"]'})
        self.assertEqual(out["status"], "repaired")
        self.assertEqual(out["data"]["paths"], ["a", "b"])

    def test_empty_placeholder(self):
        out = repair_tool_input(ARR, {"paths": {}})
        self.assertEqual(out["status"], "repaired")
        self.assertEqual(out["data"]["paths"], [])

    def test_null_for_optional_dropped(self):
        out = repair_tool_input(OPT, {"cmd": "ls", "timeoutMs": None})
        self.assertEqual(out["status"], "repaired")
        self.assertNotIn("timeoutMs", out["data"])

    def test_order_parse_before_wrap(self):
        # '["a","b"]' must parse to ["a","b"], NOT wrap to ['["a","b"]']
        v, ok = repair_json_array_parse('["a","b"]', ["array"])
        self.assertTrue(ok); self.assertEqual(v, ["a", "b"])
        v2, ok2 = repair_bare_string_wrap('["a","b"]', ["array"])
        self.assertTrue(ok2); self.assertEqual(v2, ['["a","b"]'])  # the wrong order, proven wrong


class PathAutolink(unittest.TestCase):
    def test_degenerate_autolink_unwrapped(self):
        v, ok = repair_path_autolink("/Users/x/proj/[notes.md](http://notes.md)", ["string"])
        self.assertTrue(ok); self.assertEqual(v, "/Users/x/proj/notes.md")

    def test_real_markdown_link_untouched(self):
        v, ok = repair_path_autolink("[click](https://x.com)", ["string"])
        self.assertFalse(ok)  # text != url-sans-protocol -> leave it

    def test_via_orchestrator(self):
        out = repair_tool_input(PATH, {"filePath": "/p/[a.md](http://a.md)"})
        self.assertEqual(out["data"]["filePath"], "/p/a.md")


class Relational(unittest.TestCase):
    def test_limit_alone_fills_offset(self):
        args, note = fill_relational_defaults({"limit": 30}, a="offset", b="limit",
                                              default_a=0, default_b=2000)
        self.assertEqual(args["offset"], 0)
        self.assertIn("offset", note); self.assertNotIn("Error:", note)

    def test_offset_alone_fills_limit(self):
        args, note = fill_relational_defaults({"offset": 10}, a="offset", b="limit",
                                              default_a=0, default_b=2000)
        self.assertEqual(args["limit"], 2000)

    def test_both_present_no_note(self):
        args, note = fill_relational_defaults({"offset": 1, "limit": 5}, a="offset", b="limit",
                                              default_a=0, default_b=2000)
        self.assertIsNone(note)


class Invalid(unittest.TestCase):
    def test_unrepairable_returns_model_message(self):
        out = repair_tool_input(ARR, {})  # missing required 'paths', cannot invent
        self.assertEqual(out["status"], "invalid")
        self.assertIn("paths", out["message"])
        self.assertNotIn("Error:", out["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
