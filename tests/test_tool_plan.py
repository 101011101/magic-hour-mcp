"""Contract tests for plan_tool_call (MCP-23, tool management)."""
import asyncio
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_magichour import tool_plan
from mcp_magichour.openapi_server import create_mcp

ROOT = Path(__file__).resolve().parents[1]


def tool_names(env: dict) -> set[str]:
    async def names():
        with patch.dict(os.environ, env):
            async with Client(create_mcp()) as client:
                return {t.name for t in await client.list_tools()}
    return asyncio.run(names())


class DataTests(unittest.TestCase):
    def test_every_sheet_tool_has_a_note(self):
        known = set(tool_plan.notes()["tools"]) | {"ai_voice_generator_create_audio"}
        for family, sheet in tool_plan.sheets()["families"].items():
            self.assertEqual([t for t in sheet["tools"] if t not in known], [], family)

    def test_every_row_has_options_a_default_and_evidence(self):
        for family, sheet in tool_plan.sheets()["families"].items():
            for row in sheet["rows"]:
                self.assertIn(row["kind"], ("deciding", "required"), row["id"])
                self.assertTrue(row["answers"] and row["default"] and row["why"], f"{family}.{row['id']}")

    def test_settings_name_free_models_only(self):
        free = {m.split(" ")[0] for ms in tool_plan.notes()["free_models"].values() if isinstance(ms, list) for m in ms}
        for family, sheet in tool_plan.sheets()["families"].items():
            for tool, s in sheet.get("settings", {}).items():
                if "model" in s:
                    self.assertIn(s["model"], free, f"{family}.{tool}")


class PlanTests(unittest.TestCase):
    def test_first_call_returns_the_sheet(self):
        out = tool_plan.plan("change_picture", "make this square", None)
        self.assertFalse(out["ready"])
        self.assertEqual(out["stage"], "fill_the_sheet")
        self.assertIn("keep_or_redraw", [r["id"] for r in out["rows"]])

    def test_unknown_family_and_row_are_errors(self):
        with self.assertRaises(ToolError):
            tool_plan.plan("films", "x", None)
        with self.assertRaises(ToolError):
            tool_plan.plan("change_picture", "x", {"nope": "keep"})

    def test_a_deciding_row_needs_one_of_its_options(self):
        with self.assertRaises(ToolError):
            tool_plan.plan("change_picture", "x", {"keep_or_redraw": "maybe"})

    def test_host_only_rows_are_never_questions(self):
        with self.assertRaises(ToolError):
            tool_plan.plan("faces", "put my face on this", {"photo_or_video": "ask"})

    def test_at_most_three_questions_the_rest_defaulted(self):
        out = tool_plan.plan("new_picture", "make me a picture", {"shape": "ask", "exact_words": "ask",
                             "several_sizes": "ask", "transparent": "ask", "meme_kind": "n/a"})
        self.assertFalse(out["ready"])
        self.assertEqual(len(out["questions"]), 3)
        self.assertEqual([d["id"] for d in out["defaulted"]], ["transparent"])
        self.assertTrue(all(q["if_skipped"] for q in out["questions"]))

    def test_square_from_the_users_words_gives_reframe_not_edit_image(self):
        """B12a: 'make this wide photo square' → keep, fill → reframe_media, with its notes."""
        out = tool_plan.plan("change_picture", "Make this wide photo square. Keep the whole sneaker.", {
            "keep_or_redraw": "keep", "shape_how": "blurred", "subject_place": "n/a", "words": "n/a",
            "on_object": "n/a", "bigger_or_fixed": "n/a", "colour_only": "n/a"})
        self.assertTrue(out["ready"])
        self.assertIn("reframe_media", out["tools"])
        self.assertIn("antitype", out["tools"]["reframe_media"])
        self.assertIn("reframe_media", out["decisions"][0]["instruction"])

    def test_your_call_uses_the_default_and_says_so(self):
        out = tool_plan.plan("sound", "a music bed", {"on_its_own": "on its own", "length": "your_call",
                                                     "mood": "your_call", "voices": "n/a"})
        length = next(d for d in out["decisions"] if d["id"] == "length")
        self.assertTrue(length["tell_the_user"])
        self.assertEqual(length["value"], "15 s.")

    def test_a_gap_is_reported(self):
        out = tool_plan.plan("change_video", "add music to this clip", {
            "keep_or_remake": "keep", "shape_how": "n/a", "range": "n/a", "new_ending": "n/a", "words": "n/a",
            "subtitle_language": "n/a", "has_speech": "n/a", "sound_on_video": "yes", "logo_or_card": "n/a"})
        self.assertIn("sound_on_video", out["gaps"])

    def test_faces_in_a_photo_plan_head_swap(self):
        out = tool_plan.plan("faces", "put my face on the astronaut", {
            "consent": "none", "photo_or_video": "photo", "which_person": "n/a", "which_part": "n/a", "headshot_look": "n/a"})
        self.assertIn("swap_head_in_photo", out["tools"])

    def test_plan_settings_are_free_tier(self):
        out = tool_plan.plan("new_picture", "a candle product shot", {
            "exact_words": "none", "shape": "1:1", "several_sizes": "one", "transparent": "no", "meme_kind": "n/a"})
        self.assertEqual(out["settings"]["generate_image"]["model"], "qwen-image-2.1")


class SwitchTests(unittest.TestCase):
    def test_off_by_default(self):
        env = {k: v for k, v in os.environ.items() if k != "MAGIC_HOUR_TOOL_PLAN"}
        with patch.dict(os.environ, env, clear=True):
            self.assertNotIn("plan_tool_call", tool_names({}))

    def test_on_registers_the_tool(self):
        self.assertIn("plan_tool_call", tool_names({"MAGIC_HOUR_TOOL_PLAN": "on"}))

    def test_the_server_offers_the_sheet_fields(self):
        async def schema():
            with patch.dict(os.environ, {"MAGIC_HOUR_TOOL_PLAN": "on"}):
                async with Client(create_mcp()) as client:
                    return next(t for t in await client.list_tools() if t.name == "plan_tool_call").inputSchema
        s = asyncio.run(schema())
        self.assertEqual(set(s["properties"]), {"family", "request", "answers"})
        self.assertIn("change_video", json.dumps(s["properties"]["family"]))


class IsolationTests(unittest.TestCase):
    """Tool management changes no video composition file (PRD, Isolation)."""
    PROTECTED = ["mcp_magichour/plan_request.py", "mcp_magichour/video_production.py",
                 "mcp_magichour/video_production_tool.py", "mcp_magichour/gates.py",
                 "mcp_magichour/media_tools.py", "mcp_magichour/openapi_policies.py"]

    def test_tool_plan_imports_nothing_from_video_composition(self):
        src = (ROOT / "mcp_magichour" / "tool_plan.py").read_text()
        for mod in ("plan_request", "video_production", "gates", "media_tools"):
            self.assertNotIn(f"from .{mod}", src)
            self.assertNotIn(f"import {mod}", src)

    def test_this_branch_changes_no_protected_file(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
        base = git("merge-base", "HEAD", "origin/video-production")
        if base.returncode:
            self.skipTest("no origin/video-production to compare with")
        changed = git("diff", "--name-only", base.stdout.strip()).stdout.split()
        self.assertEqual([f for f in self.PROTECTED if f in changed], [])


if __name__ == "__main__":
    unittest.main()
