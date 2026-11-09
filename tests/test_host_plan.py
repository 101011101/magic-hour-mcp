"""The host groups the beats into clips; the planner obeys, tracks the request and advises (user, 2026-11-07)."""

import json
import unittest
from copy import deepcopy
from pathlib import Path

from mcp_magichour import video_production as vp
from mcp_magichour.video_production_tool import plan_story

STORIES = Path(__file__).parent / "fixtures" / "stories"
B2_REQUEST = ('Make a 30-second 16:9 short film called Walk Anyway. Start on a title card for 2 seconds: white text "WALK ANYWAY". '
              '3. Close on both of them. He says out loud: "You came back." She smiles.')


def walk_anyway() -> dict:
    """B2 as the host wrote it in the dry run of 7 November: the line has its own beat, then the walk away."""
    story = json.loads((STORIES / "c4-walk-anyway-30.json").read_text())
    story.pop("variants", None)
    return story


def grouped(story: dict, clips: list[int]) -> dict:
    story = deepcopy(story)
    for beat, n in zip(story["beats"], clips):
        beat["clip"] = n
    return story


class HostGroupingTests(unittest.TestCase):
    def test_without_clip_numbers_the_split_rule_merges_and_says_so(self):
        story = walk_anyway()
        planned = plan_story(story)
        self.assertIn([4, 5], [c["beats"] for c in planned["clips"]])          # the line and the walk away in one call
        notes = [a["note"] for a in vp.advise(story, planned)]
        self.assertIn("grouping", notes)

    def test_the_hosts_clips_are_obeyed_exactly(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])                    # the line alone in clip 3
        planned = plan_story(story)
        self.assertTrue(planned["ok"], planned["problems"])
        self.assertEqual([c["beats"] for c in planned["clips"]], [[1], [2, 3], [4], [5], [6]])
        self.assertNotIn("grouping", [a["note"] for a in vp.advise(story, planned)])

    def test_bad_clip_numbers_are_problems(self):
        story = walk_anyway()
        self.assertTrue(vp.plan(grouped(story, [1, 2, 4, 5, 6, 7]), "manual")["problems"])   # skips 3
        self.assertTrue(vp.validate_story(grouped(story, [1, 1, 2, 3, 4, 5])))                # the card shares clip 1
        half = deepcopy(story)
        half["beats"][0]["clip"] = 1
        self.assertIn("set `clip` on every beat, or on none", vp.validate_story(half))


class SpokenLineTests(unittest.TestCase):
    def line_story(self, clips: list[int]) -> dict:
        story = grouped(walk_anyway(), clips)
        beat = story["beats"][3]
        beat["spoken"] = ["You came back."]
        return story

    def test_a_spoken_line_is_its_own_sentence_in_the_prompt_and_turns_the_sound_on(self):
        story = self.line_story([1, 2, 2, 3, 4, 5])
        story["audio"] = False
        planned = plan_story(story)
        clip = planned["clips"][2]
        self.assertIn('Said out loud on screen, once, word for word: "You came back."', clip["steps"][-1]["prompt"])
        self.assertTrue(clip["steps"][-1]["audio"])
        self.assertIn('Said on screen once, word for word: "You came back."', [l["want"] for l in planned["checklist"]])

    def test_a_spoken_line_with_another_beat_is_a_question_and_split_gives_it_its_own_clip(self):
        story = self.line_story([1, 2, 2, 3, 3, 4])
        asked = vp.questions(story, plan_story(story))
        line = next(q for q in asked if q["id"] == "line-4")
        self.assertIn("0 of 3", line["ask"])
        self.assertEqual(line["recommend"], "split")
        answered, problems = vp.apply_answers(story, {"line-4": "split"})
        self.assertEqual(problems, [])
        planned = plan_story(answered)
        self.assertIn([4], [c["beats"] for c in planned["clips"]])
        self.assertIn([5], [c["beats"] for c in planned["clips"]])
        self.assertEqual(vp.questions(answered, planned), [])


class ChosenReferenceTests(unittest.TestCase):
    def test_a_file_the_host_made_is_the_clips_reference(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        story["beats"][4]["reference"] = {"kind": "file", "file": "api-assets/x/frame-with-words.png"}
        clip = plan_story(story)["clips"][3]
        self.assertEqual(clip["reference"], {"kind": "file", "subject": "reference", "file": "api-assets/x/frame-with-words.png", "chosen": True})
        self.assertEqual(clip["steps"][-1]["model"], "minimax-h3")
        self.assertIn("@reference", clip["steps"][-1]["prompt"])

    def test_a_picture_reference_needs_a_subject_with_a_picture(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        story["beats"][1]["reference"] = {"kind": "picture", "subject": "woman"}
        self.assertTrue(any("reference picture" in p for p in vp.validate_story(story)))


class QuestionTests(unittest.TestCase):
    def words_story(self) -> dict:
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        story["beats"][4]["exact_words"] = ["walk anyway"]      # over the walk away, as in A2
        return story

    def test_words_over_a_scene_are_a_question_with_four_options(self):
        story = self.words_story()
        q = next(q for q in vp.questions(story, plan_story(story)) if q["id"] == "words-5")
        self.assertEqual(set(q["options"]), {"card", "model", "still", "accept"})
        self.assertEqual(q["recommend"], "card")

    def test_card_puts_the_words_on_a_drawn_card_after_the_beat(self):
        answered, _ = vp.apply_answers(self.words_story(), {"words-5": "card"})
        planned = plan_story(answered)
        self.assertTrue(planned["ok"], planned["problems"])
        self.assertEqual(sum(c["seconds"] for c in planned["clips"]), 30)            # 2 s taken from the beat
        card = planned["clips"][4]
        self.assertEqual((card["kind"], card["made_by"], card["steps"][0]["words"]), ("card", "code", ["walk anyway"]))
        self.assertNotIn("walk anyway", planned["clips"][3]["steps"][-1]["prompt"])  # not asked of the video model
        self.assertEqual(vp.questions(answered, planned), [])

    def test_model_routes_the_clip_to_minimax_and_asks_for_the_words(self):
        answered, _ = vp.apply_answers(self.words_story(), {"words-5": "model"})
        clip = plan_story(answered)["clips"][3]
        self.assertEqual(clip["steps"][-1]["model"], "minimax-h3")
        self.assertIn('Show the words "walk anyway"', clip["steps"][-1]["prompt"])

    def test_still_starts_the_clip_from_a_picture_with_the_words(self):
        answered, _ = vp.apply_answers(self.words_story(), {"words-5": "still"})
        clip = plan_story(answered)["clips"][3]
        self.assertEqual(clip["reference"]["kind"], "scene_still")
        self.assertEqual([s["tool"] for s in clip["steps"]], ["generate_image", "create_video_from_image"])
        self.assertIn('exactly "walk anyway"', clip["steps"][0]["prompt"])

    def test_colour_codes_become_colour_words(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        story["setting"] += " Brand colours #0E7C86 and #F28C28."
        q = next(q for q in vp.questions(story, plan_story(story)) if q["id"] == "colour-codes")
        self.assertIn("#0E7C86 as teal", q["options"]["words"])
        answered, _ = vp.apply_answers(story, {"colour-codes": "words"})
        self.assertNotRegex(answered["setting"], r"#[0-9A-Fa-f]{6}")
        self.assertIn("teal", answered["setting"])
        self.assertEqual(vp.questions(answered, plan_story(answered)), [])

    def test_in_scene_words_are_best_effort_with_no_question(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        story["beats"][1]["in_scene_words"] = ["BUS 12"]
        planned = plan_story(story)
        self.assertEqual(vp.questions(story, planned), [])
        self.assertIn('The words "BUS 12" are part of the picture', planned["clips"][1]["steps"][-1]["prompt"])
        self.assertTrue(any("best effort" in l["want"] for l in planned["checklist"]))


class AdviceTests(unittest.TestCase):

    def test_what_the_request_asks_for_is_tracked(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        missing = [a["warning"] for a in vp.advise(story, plan_story(story), B2_REQUEST) if a["note"] == "not-carried"]
        self.assertTrue(any("You came back." in m for m in missing))                 # no beat carries the line yet
        story["beats"][3]["spoken"] = ["You came back."]
        missing = [a["warning"] for a in vp.advise(story, plan_story(story), B2_REQUEST) if a["note"] == "not-carried"]
        self.assertEqual(missing, [])

    def test_advice_never_changes_the_plan(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 3, 4])
        planned = plan_story(story)
        before = json.dumps(planned, sort_keys=True)
        vp.advise(story, planned, B2_REQUEST)
        self.assertEqual(json.dumps(planned, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()


class DrawnCardTests(unittest.TestCase):
    def test_a_card_with_a_background_is_drawn_exactly(self):
        import shutil
        import tempfile
        from mcp_magichour import media_tools
        if not media_tools.have_captions() or not media_tools.have_ffmpeg():
            self.skipTest("needs Pillow and ffmpeg")
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            png = media_tools.draw_card(["MOCKUP FRAGRANCE", "Available 12 December"], "#3B1F6B", (480, 854), Path(folder) / "card.png")
            self.assertEqual(Image.open(png).getpixel((5, 5)), (0x3B, 0x1F, 0x6B))
            video = media_tools.still_video(png, 4, Path(folder) / "card.mp4")
            self.assertAlmostEqual(media_tools.probe(video)["seconds"], 4, delta=0.2)

    def test_the_plan_needs_no_call_for_a_drawn_card(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        story["beats"][0]["background"] = "#000000"
        clip = plan_story(story)["clips"][0]
        self.assertEqual((clip["made_by"], clip["steps"][0]["credits"]), ("code", 0))


class ToolFlowTests(unittest.TestCase):
    def test_an_open_question_holds_the_plan_and_the_answer_releases_it(self):
        import asyncio
        from fastmcp import Client, FastMCP
        from mcp_magichour.video_production_tool import register_video_production

        mcp = FastMCP("t")
        register_video_production(mcp)
        story = QuestionTests().words_story()
        for b in story["beats"]:
            b.pop("clip", None)          # the host did not group: the answer must keep the clips as they are

        async def go():
            async with Client(mcp) as client:
                first = (await client.call_tool("plan_video_production", {"story": story, "request": B2_REQUEST})).data
                second = (await client.call_tool("plan_video_production", {"story": story, "request": B2_REQUEST,
                                                                              "answers": {"words-5": "card"}})).data
                return first, second
        first, second = asyncio.run(go())
        self.assertIn("words-5", [q["id"] for q in first["questions"]])
        self.assertNotIn("production", first)
        self.assertNotIn("questions", second)
        self.assertTrue(second["production"])
        self.assertIn("code", [c.get("made_by") for c in second["clips"]])


class FixesFromTheDryRunTests(unittest.TestCase):
    """The question-flow dry run of 7 November found these."""

    def test_the_answers_model_wins_over_another_beats_model(self):
        story = QuestionTests().words_story()
        story["beats"][4]["clip"] = 4          # the words beat shares clip 4 with the line beat
        story["beats"][5]["clip"] = 5
        story["beats"][3]["model"] = "ltx-2.5"  # A2: the host had put ltx-2.5 on the first beat of the clip
        answered, _ = vp.apply_answers(story, {"words-5": "model"})
        clip = next(c for c in plan_story(answered)["clips"] if 5 in c["beats"])
        self.assertEqual(clip["steps"][-1]["model"], "minimax-h3")

    def test_a_model_that_cannot_take_the_picture_is_a_problem(self):
        story = json.loads((STORIES / "c5-fragrance-30.json").read_text())
        story.pop("variants", None)
        story["beats"][0]["model"] = "ltx-2.5"   # B1: the bottle's picture on ltx-2.5
        problems = plan_story(story)["problems"]
        self.assertTrue(any("cannot take a picture reference" in p for p in problems), problems)

    def test_a_card_can_hold_the_users_picture_unchanged(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        story["beats"][5] = {"seconds": 2, "kind": "card", "clip": 5, "text": "The logo, unchanged.", "picture": "https://example.com/logo.png", "background": "#FFFFFF"}
        planned = plan_story(story)
        self.assertTrue(planned["ok"], planned["problems"])
        card = planned["clips"][-1]
        self.assertEqual((card["made_by"], card["steps"][0]["tool"], card["steps"][0]["credits"]), ("code", "hold_picture", 0))

    def test_fit_picture_keeps_the_picture_unchanged_inside_the_frame(self):
        import tempfile
        from mcp_magichour import media_tools
        if not media_tools.have_captions():
            self.skipTest("needs Pillow")
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            logo = Path(folder) / "logo.png"
            Image.new("RGB", (400, 200), (14, 124, 134)).save(logo)
            out = media_tools.fit_picture(logo, "#FFFFFF", (854, 480), Path(folder) / "card.png")
            frame = Image.open(out)
            self.assertEqual(frame.size, (854, 480))
            self.assertEqual(frame.getpixel((427, 240)), (14, 124, 134))   # the logo's colour, unchanged, at the centre
            self.assertEqual(frame.getpixel((5, 5)), (255, 255, 255))


class HeldPictureUrlTests(unittest.TestCase):
    def test_a_held_picture_needs_a_url(self):
        story = grouped(walk_anyway(), [1, 2, 2, 3, 4, 5])
        story["beats"][5] = {"seconds": 2, "kind": "card", "clip": 5, "text": "The logo.", "picture": "api-assets/x/logo.png"}
        self.assertTrue(any("must be the picture's URL" in p for p in vp.validate_story(story)))
