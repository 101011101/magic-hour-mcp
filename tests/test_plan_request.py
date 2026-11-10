"""Contract tests for `plan_request` (MCP-01), written before the code.

In-memory API, no network, 0 credits. Spec: mcp-upgrade/prd/MCP-01-conversation.md.
Until `plan_request` is built, each test fails in setup with "tool not found".

Where each expected value comes from (agent repo, folder V4):
- briefs, answers, strange scripts, direction change: tests/items/S01..S11, V01, V02
- question texts: agent/questions.js
- parameters and required parameters for each tool: agent/catalogue.js
- shape of each attached file: runs/dry-<item>/run.json
- missing parameters for each vague brief: runs/dry-<item>/run.json, first turn
"""

import json
import unittest
from unittest.mock import patch

import httpx
from fastmcp import Client

from mcp_magichour.openapi_server import create_mcp


TOOL = "plan_request"
ASYNC_CLIENT = httpx.AsyncClient

# --- Table 1: the question set. Word for word from V4/agent/questions.js. --------------------
QUESTIONS = {
    "aspect": "Where will this be shown or posted (Instagram, TikTok, YouTube, a website, print, somewhere else)?",
    "seconds": "How long should it be?",
    "exact_words": "Should any words appear on it? If so, which, exactly?",
    "sound": "Should it have sound: music, a voice, or silent?",
    "language": "Which language for the voice or captions?",
    "which_face": "Whose face goes where (which person in the picture)?",
    "look": "Any look in mind (realistic, illustrated, a brand colour, a mood)? 'Your call' is fine.",
    "subject": "What should it show?",
    "edit": "What should change in the picture?",
    "keep": "What must stay exactly as it is?",
    "motion": "What should move, and how (small natural motion, a slow push in, something happening)?",
    "mood": "What mood or genre for the music?",
    "script": "What should be said, word for word? Or should I write it from the gist?",
    "range": "Which part should be kept (from when to when, or 'the best 10 seconds')?",
}

# --- Table 2: the attached files. Kind, shape, role as V4 recorded them. ---------------------
FILES = {
    "perfume": {"name": "v4-perfume.jpg", "kind": "image", "aspect": "16:9", "role": "product"},
    "woman": {"name": "portrait-woman.jpg", "kind": "image", "aspect": "1:1", "role": "person"},
    "car": {"name": "rt3-bugatti.jpg", "kind": "image", "aspect": "16:9", "role": "product"},
    "bridge": {"name": "rt3-goldengate.jpg", "kind": "image", "aspect": "9:16", "role": "environment"},
    "poster": {"name": "v4-poster.jpg", "kind": "image", "aspect": "9:16", "role": "copy"},
    "evan": {"name": "web-evan.jpg", "kind": "image", "aspect": "9:16", "role": "person"},
    "teacher": {"name": "student-teacher.jpg", "kind": "image", "aspect": "9:16", "role": "person"},
    "clip": {"name": "v4-classroom-wipe.mp4", "kind": "video", "aspect": "16:9", "seconds": 10, "role": "other"},
}

# --- Table 3: the 13 items, vague brief and full brief. --------------------------------------
# Columns: item, brief kind, tool, brief, files, host sheet, expect missing, expect values.
# - host sheet: what the host model passes. {parameter: (value, source)}.
#   GUESS = the host did not get the value from the user. The test sends the value with each
#   source a host can put on a guess (see GUESS_SOURCES). The result must be the same each time.
# - expect missing: the parameters that come back with source `missing`. Each gives its question
#   from Table 1. No other question comes back. Empty = `ready` is true, 0 questions.
# - expect values: values that must be in the returned sheet.
GUESS = "guess"
INVENTED_WORDS = ["Live Music Tonight", "Doors 8pm", "Free Entry"]  # not in any user message
S03_WORDS = ["Open Mic Night", "Friday 7pm", "The Blue Door"]
S04_WORDS = ["20% OFF", "This weekend only"]

ITEMS = [
    ("S01", "vague", "edit_image", "I need a shot of my perfume for the website", ["perfume"],
     {"edit": ("a studio product shot", GUESS), "keep": ("the bottle", "default"), "aspect": ("16:9", GUESS)},
     ["edit", "aspect"], {}),
    ("S01", "full", "edit_image",
     "Put this perfume bottle (attached) on a white marble surface with soft studio light, a wide 16:9 banner for the website homepage; keep the bottle exactly as it is, no text.",
     ["perfume"],
     {"edit": ("put the bottle on a white marble surface with soft studio light", "user"),
      "keep": ("the bottle exactly as it is", "user"), "aspect": ("16:9", "user"), "exact_words": ([], "user")},
     [], {"aspect": "16:9"}),

    ("S02", "vague", "generate_image", "a product shot of a matte black water bottle", [],
     {"subject": ("a product shot of a matte black water bottle", "user"), "aspect": ("1:1", GUESS),
      "exact_words": ([], "derived"), "look": ("studio product photograph", "default")},
     ["aspect"], {}),
    ("S02", "full", "generate_image",
     "A product shot of a matte black insulated water bottle on a pale concrete surface, soft studio light, premium minimal look, square 1:1 for the Instagram feed, no text.",
     [],
     {"subject": ("a matte black insulated water bottle on a pale concrete surface", "user"),
      "aspect": ("1:1", "user"), "exact_words": ([], "user"), "look": ("soft studio light, premium minimal look", "user")},
     [], {"aspect": "1:1"}),

    ("S03", "vague", "generate_image", "make a poster for our open mic night", [],
     {"subject": ("a poster for an open mic night", "user"), "aspect": ("9:16", "derived"),
      "exact_words": (INVENTED_WORDS, GUESS), "look": ("warm stage colours", "default")},
     ["exact_words"], {"aspect": "9:16"}),
    ("S03", "full", "generate_image",
     "A poster for an open mic night, printed A4 (3:4), warm retro look; the words must read exactly: 'Open Mic Night', 'Friday 7pm', 'The Blue Door'.",
     [],
     {"subject": ("a poster for an open mic night", "user"), "aspect": ("9:16", "user"),
      "exact_words": (S03_WORDS, "user"), "look": ("warm retro look", "user")},
     [], {"aspect": "9:16", "exact_words": S03_WORDS}),

    ("S04", "vague", "generate_image", "a social post announcing 20% off", [],
     {"subject": ("a social post announcing 20% off", "user"), "aspect": ("1:1", GUESS),
      "exact_words": (["Big Summer Sale", "Shop now"], GUESS), "look": ("bold sale design", "default")},
     ["exact_words", "aspect"], {}),
    ("S04", "full", "generate_image",
     "A bold red-and-white square image for the Instagram feed announcing a sale; the words must read exactly '20% OFF' and 'This weekend only'.",
     [],
     {"subject": ("an image for the Instagram feed announcing a sale", "user"), "aspect": ("1:1", "derived"),
      "exact_words": (S04_WORDS, "user"), "look": ("bold red-and-white", "user")},
     [], {"aspect": "1:1", "exact_words": S04_WORDS}),

    ("S05", "vague", "edit_image", "make this photo warmer", ["woman"],
     {"edit": ("make the photo warmer", "user"), "keep": ("everything else", "default")},
     [], {"aspect": "1:1"}),
    ("S05", "full", "edit_image",
     "Make this photo warmer in tone (golden, like late afternoon light); change nothing else: same person, pose, framing and background.",
     ["woman"],
     {"edit": ("warmer in tone (golden, like late afternoon light)", "user"),
      "keep": ("same person, pose, framing and background", "user")},
     [], {"aspect": "1:1"}),

    ("S06", "vague", "edit_image", "remove the people from this", ["car"],
     {"edit": ("remove the people", "user"), "keep": ("everything else", "default")},
     [], {"aspect": "16:9"}),
    ("S06", "full", "edit_image",
     "Remove all the people from the background of this photo and fill the background in naturally; the car and everything else stay exactly as they are.",
     ["car"],
     {"edit": ("remove all the people from the background and fill the background in naturally", "user"),
      "keep": ("the car and everything else stay exactly as they are", "user")},
     [], {"aspect": "16:9"}),

    # trim_video has no MCP tool. These two rows depend on an open question in the PRD.
    ("S07", "vague", "trim_video", "cut this down", ["clip"],
     {"range": ("the first 5 seconds", GUESS)},
     ["range"], {}),
    ("S07", "full", "trim_video", "Trim this clip to the first 6 seconds (0 to 6).", ["clip"],
     {"range": ("0 to 6 seconds", "user")},
     [], {"range": "0 to 6 seconds"}),

    ("S08", "vague", "swap_face_in_photo", "put the one guy's face on the other", ["evan", "teacher"],
     {"which_face": ("the face from the first picture onto the second picture", GUESS)},
     ["which_face"], {}),
    ("S08", "full", "swap_face_in_photo",
     "Put the face of the man in the grey long-sleeve shirt onto the man with braids in the other photo; keep the braids photo as the scene.",
     ["evan", "teacher"],
     {"which_face": ("the face of the man in the grey long-sleeve shirt onto the man with braids", "user")},
     [], {}),

    # "short" gives 8 s (V4 parseSeconds). The answer sheet says 6 s. Open question in the PRD.
    ("S09", "vague", "create_video_from_image", "make a short clip of her", ["woman"],
     {"motion": ("she smiles", GUESS), "seconds": (5, "default"), "aspect": ("1:1", GUESS),
      "sound": ("none", GUESS), "keep": ("her face", "default")},
     ["motion", "aspect", "sound"], {"seconds": 8}),
    # The full brief gives no shape. "this portrait" is the photo, not a shape (2026-11-07: reading it as 9:16 made A3 tall
    # when its clip is square), so the shape is asked, as for any animated picture.
    ("S09", "full", "create_video_from_image",
     "Animate this portrait for 6 seconds: she smiles and looks around a little, nothing dramatic; keep her face exactly like her; silent.",
     ["woman"],
     {"motion": ("she smiles and looks around a little, nothing dramatic", "user"), "seconds": (6, "user"),
      "sound": ("none", "user"), "keep": ("her face exactly like her", "user")},
     ["aspect"], {"seconds": 6, "sound": "none"}),

    # The item file says create_video_from_image. V4 chose create_video_from_text (intent.js RULES, line 39).
    ("S10", "vague", "create_video_from_text", "a video of this car driving across this bridge", ["car", "bridge"],
     {"subject": ("this car driving across this bridge", "user"), "seconds": (5, GUESS), "aspect": ("16:9", GUESS),
      "sound": ("none", GUESS), "look": ("realistic", "default")},
     ["seconds", "aspect", "sound"], {}),
    ("S10", "full", "create_video_from_text",
     "A 10-second widescreen (16:9) silent clip of this car (attached) driving across this bridge (attached), seen from the roadside, morning light.",
     ["car", "bridge"],
     {"subject": ("this car driving across this bridge, seen from the roadside", "user"), "seconds": (10, "user"),
      "aspect": ("16:9", "user"), "sound": ("none", "user"), "exact_words": ([], "derived"), "look": ("morning light", "user")},
     [], {"seconds": 10, "aspect": "16:9", "sound": "none"}),

    ("S11", "vague", "edit_image", "put my poster on a billboard by this bridge", ["poster", "bridge"],
     {"edit": ("put the poster on a billboard by the bridge", "user"), "keep": ("the poster", "default"),
      "aspect": ("9:16", GUESS)},
     ["aspect"], {}),
    ("S11", "full", "edit_image",
     "Put this poster (attached) on a roadside billboard with this bridge (attached) behind it, landscape 16:9 for a LinkedIn post; the poster must stay exactly as designed, readable.",
     ["poster", "bridge"],
     {"edit": ("put this poster on a roadside billboard with this bridge behind it", "user"),
      "keep": ("the poster must stay exactly as designed, readable", "user"), "aspect": ("16:9", "user")},
     [], {"aspect": "16:9"}),

    # Guesses = the attempted call of the current MCP on 2026-11-03: 16:9, 5 s, audio on.
    ("V01", "vague", "create_video_from_text", "a clip of waves at sunset for my meditation app", [],
     {"subject": ("waves at sunset for a meditation app", "user"), "seconds": (5, GUESS), "aspect": ("16:9", GUESS),
      "sound": ("ambient", GUESS), "look": ("calm, natural", "default")},
     ["seconds", "aspect", "sound"], {}),
    ("V01", "full", "create_video_from_text",
     "A 10-second vertical (9:16) clip for a meditation app: slow waves at sunset on an empty beach, a gentle camera drift, with the natural sound of the waves, no music, no words.",
     [],
     {"subject": ("slow waves at sunset on an empty beach, a gentle camera drift", "user"), "seconds": (10, "user"),
      "aspect": ("9:16", "user"), "sound": ("ambient", "user"), "exact_words": ([], "user"),
      "look": ("calm, natural", "default")},
     [], {"seconds": 10, "aspect": "9:16", "sound": "ambient"}),

    ("V02", "vague", "create_video_from_image", "animate this", ["perfume"],
     {"motion": ("animate the picture as it is", "user"), "seconds": (5, GUESS), "aspect": ("16:9", GUESS),
      "sound": ("none", GUESS), "keep": ("the bottle", "default")},
     ["seconds", "aspect", "sound"], {}),
    ("V02", "full", "create_video_from_image",
     "Animate this perfume bottle (attached) for 6 seconds: a slow turn on the spot with light moving across the glass, the bottle exactly as in the picture, square, silent.",
     ["perfume"],
     {"motion": ("a slow turn on the spot with light moving across the glass", "user"), "seconds": (6, "user"),
      "aspect": ("1:1", "user"), "sound": ("none", "user"), "keep": ("the bottle exactly as in the picture", "user")},
     [], {"seconds": 6, "aspect": "1:1", "sound": "none"}),
]

# The sources a host can put on a value that the user did not give. The server must make each one `missing`.
# - aspect, seconds, sound: the server reads the user's words itself.
# - exact_words: never invented.
# - edit: any source other than `user` (intent.js, line 73).
# - other parameters: `default` is not permitted (only look, position, transition, voice, language, keep).
GUESS_SOURCES = {
    "aspect": ["default", "missing", "derived", "user"],
    "seconds": ["default", "missing", "derived", "user"],
    "sound": ["default", "missing", "derived", "user"],
    "exact_words": ["default", "missing", "derived", "user"],
    "edit": ["default", "missing", "derived"],
}
OTHER_GUESS_SOURCES = ["default", "missing"]
GUESS_ROUNDS = ["default", "missing", "derived", "user"]

# --- Table 4: scripts for the ticket cases. --------------------------------------------------
S02_VAGUE = "a product shot of a matte black water bottle"
S03_VAGUE = "make a poster for our open mic night"
S03_STRANGE = ["the vibe is like jazz you know", "friday", "put the usual stuff on it"]  # V4 item S03
S04_VAGUE = "a social post announcing 20% off"
S04_TURN = [  # V4 item S04, `turn.script`; expect_tool = create_video_from_text
    "Instagram feed, the words are '20% OFF · This weekend only', bold red and white",
    "actually make it a 10 second video for Instagram reels instead, same words, no sound",
]
S04_TURN_WORDS = ["20% OFF · This weekend only"]
FIVE_MISSING = "make me a video ad"  # written for the ticket case; no V4 item has 5 missing parameters
YOUR_CALL_DEFAULTS = {"aspect": "16:9", "seconds": 10, "sound": "none"}  # intent.js, line 59


def data(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(c.text for c in result.content if c.type == "text"))


def user(text):
    return {"role": "user", "text": text}


def assistant(text):
    return {"role": "assistant", "text": text}


def rows(sheet):
    """{parameter: (value, source)} -> the `params` argument."""
    return [{"name": name, "value": None if source == "missing" else value, "source": source}
            for name, (value, source) in sheet.items()]


class PlanRequestTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []

        def upstream(request):
            self.requests.append((request.method, str(request.url)))
            return httpx.Response(500, json={"message": "plan_request must not call the API"})

        self.transport = httpx.MockTransport(upstream)

        def client_factory(*args, **kwargs):
            kwargs["transport"] = self.transport
            return ASYNC_CLIENT(*args, **kwargs)

        self.patches = [
            patch("httpx.AsyncClient", side_effect=client_factory),
            patch("mcp_magichour.openapi_server.build_api_client", side_effect=lambda: ASYNC_CLIENT(base_url="https://api.example.test", transport=self.transport)),
            patch("mcp_magichour.openapi_server.current_authorization_header", return_value="Bearer synthetic-test-token"),
            patch("mcp_magichour.oauth_compat.current_authorization_header", return_value="Bearer synthetic-test-token"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.mcp = create_mcp()
        self.caller = await self.enterAsyncContext(Client(self.mcp))
        self.tools = {tool.name: tool for tool in await self.caller.list_tools()}
        if TOOL not in self.tools:
            self.fail(f"tool not found: `{TOOL}` is not registered on the MCP server (MCP-01 is not built)")

    async def plan(self, messages, tool, sheet, files=()):
        result = data(await self.caller.call_tool(TOOL, {
            "messages": [user(m) if isinstance(m, str) else m for m in messages],
            "tool": tool,
            "params": rows(sheet),
            "attachments": [FILES[f] for f in files],
        }))
        self.assertEqual(result["tool"], tool)
        self.assertLessEqual(len(result["questions"]), 3)
        for question in result["questions"]:
            self.assertEqual(question["question"], QUESTIONS[question["param"]], "a question is not word for word from the set")
        self.assertEqual(result["ready"], result["questions"] == [])
        return result, {row["name"]: row for row in result["params"]}

    def check(self, result, sheet, missing, values):
        self.assertEqual({name for name, row in sheet.items() if row["source"] == "missing"}, set(missing))
        self.assertEqual({q["param"]: q["question"] for q in result["questions"]}, {name: QUESTIONS[name] for name in missing})
        self.assertEqual(result["ready"], not missing)
        for name, value in values.items():
            self.assertEqual(sheet[name]["value"], value, name)
            self.assertNotEqual(sheet[name]["source"], "missing", name)

    async def run_item(self, tool, brief, files, host_sheet, missing, values):
        guessed = [name for name, (_, source) in host_sheet.items() if source == GUESS]
        for round_source in (GUESS_ROUNDS if guessed else [None]):
            sent = {}
            for name, (value, source) in host_sheet.items():
                if source == GUESS:
                    allowed = GUESS_SOURCES.get(name, OTHER_GUESS_SOURCES)
                    source = round_source if round_source in allowed else allowed[0]
                sent[name] = (value, source)
            with self.subTest(host_sources={name: sent[name][1] for name in guessed}):
                result, sheet = await self.plan([brief], tool, sent, files)
                self.check(result, sheet, missing, values)

    # --- the tool itself ---

    async def test_tool_is_listed_read_only_with_the_contract_arguments(self):
        tool = self.tools[TOOL]
        self.assertTrue(tool.annotations.readOnlyHint)
        self.assertFalse(tool.annotations.destructiveHint)
        self.assertLessEqual({"messages", "tool", "params", "attachments"}, set(tool.inputSchema["properties"]))
        self.assertLessEqual({"messages", "tool", "params"}, set(tool.inputSchema["required"]))

    async def test_tool_makes_no_api_request(self):
        for item, kind, tool, brief, files, host_sheet, missing, values in ITEMS:
            if item == "V01":
                await self.run_item(tool, brief, files, host_sheet, missing, values)
        self.assertFalse([request for request in self.requests if request[0] == "POST"])
        self.assertEqual(self.requests, [])

    # --- the eight cases of the ticket ---

    async def test_instagram_story_and_9_16_both_give_aspect_9_16(self):
        for answer in ["Instagram story", "9:16"]:
            with self.subTest(answer=answer):
                result, sheet = await self.plan(
                    [S02_VAGUE, assistant(QUESTIONS["aspect"]), answer], "generate_image",
                    {"subject": (S02_VAGUE, "user"), "aspect": (None, "missing"), "exact_words": ([], "derived")})
                self.assertEqual(sheet["aspect"]["value"], "9:16")
                self.assertIn(sheet["aspect"]["source"], ["user", "derived"])
                self.assertTrue(result["ready"])
                self.assertEqual(result["questions"], [])

    async def test_poster_gives_the_question_for_exact_words(self):
        item = next(i for i in ITEMS if i[:2] == ("S03", "vague"))
        await self.run_item(*item[2:])

    async def test_the_usual_stuff_is_not_permission_to_write_the_words(self):
        messages = [S03_VAGUE]
        for answer in S03_STRANGE:
            messages += [assistant(QUESTIONS["exact_words"]), answer]
        for source in ["default", "derived", "user"]:
            with self.subTest(host_source=source):
                result, sheet = await self.plan(messages, "generate_image", {
                    "subject": ("a poster for an open mic night", "user"), "aspect": ("9:16", "derived"),
                    "exact_words": (INVENTED_WORDS, source)})
                self.check(result, sheet, ["exact_words"], {"aspect": "9:16"})

    async def test_waves_clip_gives_questions_for_where_length_sound(self):
        item = next(i for i in ITEMS if i[:2] == ("V01", "vague"))
        await self.run_item(*item[2:])

    async def test_your_call_keeps_the_default_of_the_host_and_asks_no_second_question(self):
        result, sheet = await self.plan(
            [S02_VAGUE, assistant(QUESTIONS["aspect"]), "your call"], "generate_image",
            {"subject": (S02_VAGUE, "user"), "aspect": ("1:1", "default"), "exact_words": ([], "derived")})
        self.assertEqual((sheet["aspect"]["value"], sheet["aspect"]["source"]), ("1:1", "default"))
        self.assertTrue(result["ready"])
        self.assertEqual(result["questions"], [])

    async def test_your_call_fills_a_default_when_the_host_gives_no_value(self):
        result, sheet = await self.plan(
            [S02_VAGUE, assistant(QUESTIONS["aspect"]), "your call"], "generate_image",
            {"subject": (S02_VAGUE, "user"), "aspect": (None, "missing"), "exact_words": ([], "derived")})
        self.assertEqual((sheet["aspect"]["value"], sheet["aspect"]["source"]), (YOUR_CALL_DEFAULTS["aspect"], "default"))
        self.assertTrue(result["ready"])
        self.assertEqual(result["questions"], [])

    # --- the loop the dry persona sweep found (2026-11-09): plain delegation words, a give-up, a question asked twice ---

    async def test_you_pick_hands_the_shape_over_and_a_video_from_one_picture_takes_the_pictures_shape(self):
        for answer in ["wherever you pick", "idk", "you choose", "doesn't matter"]:
            with self.subTest(answer=answer):
                result, sheet = await self.plan(
                    ["make a 6 second video of the bottle in this pic turning slowly in place, no sound", assistant(QUESTIONS["aspect"]), answer], "create_video_from_image",
                    {"motion": ("the bottle turns slowly in place", "user"), "seconds": (6, "user"), "sound": ("none", "user"),
                     "aspect": (None, "missing")}, ["woman"])
                self.assertEqual((sheet["aspect"]["value"], sheet["aspect"]["source"]), ("1:1", "default"))
                self.assertTrue(result["ready"])
                self.assertEqual(result["questions"], [])

    async def test_just_make_it_ends_the_questions_with_the_defaults(self):
        for answer in ["idk just make it", "stop asking. make it.", "Your call on anything else. Go ahead and make it."]:
            with self.subTest(answer=answer):
                result, sheet = await self.plan(
                    ["make a video about a kind gesture at a park bench", assistant(QUESTIONS["seconds"] + " " + QUESTIONS["aspect"] + " " + QUESTIONS["sound"]), answer],
                    "create_video_from_text",
                    {"subject": ("a kind gesture at a park bench", "user"), "seconds": (None, "missing"), "aspect": (None, "missing"), "sound": (None, "missing")})
                self.check(result, sheet, [], YOUR_CALL_DEFAULTS)
                self.assertEqual({sheet[name]["source"] for name in YOUR_CALL_DEFAULTS}, {"default"})

    async def test_a_question_asked_twice_without_an_answer_takes_the_default(self):
        result, sheet = await self.plan(
            ["make a video about a kind gesture at a park bench", assistant(QUESTIONS["seconds"] + " " + QUESTIONS["aspect"]), "15 seconds",
             assistant(QUESTIONS["aspect"]), "silent"],
            "create_video_from_text",
            {"subject": ("a kind gesture at a park bench", "user"), "seconds": (15, "user"), "aspect": (None, "missing"), "sound": ("none", "user")})
        self.assertEqual((sheet["aspect"]["value"], sheet["aspect"]["source"]), (YOUR_CALL_DEFAULTS["aspect"], "default"))
        self.assertTrue(result["ready"])
        self.assertEqual(result["questions"], [])

    async def test_edit_of_one_attached_picture_gives_no_question_for_shape(self):
        item = next(i for i in ITEMS if i[:2] == ("S05", "vague"))
        result, sheet = await self.plan([item[3]], item[2], item[5], item[4])
        self.assertNotIn("aspect", [q["param"] for q in result["questions"]])
        self.assertEqual((sheet["aspect"]["value"], sheet["aspect"]["source"]), ("1:1", "derived"))
        self.assertTrue(result["ready"])

    async def test_five_missing_parameters_give_three_questions(self):
        five = ["subject", "seconds", "aspect", "sound", "exact_words"]
        result, sheet = await self.plan([FIVE_MISSING], "create_video_from_text", {name: (None, "missing") for name in five})
        self.assertEqual({name for name, row in sheet.items() if row["source"] == "missing"}, set(five))
        asked = [q["param"] for q in result["questions"]]
        self.assertEqual(len(asked), 3)
        self.assertEqual(len(set(asked)), 3)
        self.assertLessEqual(set(asked), set(five))
        self.assertFalse(result["ready"])

    async def test_direction_change_gives_the_new_tool_and_removes_the_old_shape(self):
        first = [S04_VAGUE, assistant(QUESTIONS["exact_words"] + " " + QUESTIONS["aspect"]), S04_TURN[0]]
        result, sheet = await self.plan(first, "generate_image", {
            "subject": (S04_VAGUE, "user"), "aspect": ("1:1", "derived"),
            "exact_words": (S04_TURN_WORDS, "user"), "look": ("bold red and white", "user")})
        self.check(result, sheet, [], {"aspect": "1:1", "exact_words": S04_TURN_WORDS})

        # The host changes the tool. It sends the old shape again (1:1, from "Instagram feed").
        second = first + [assistant("I will make a square picture for the Instagram feed."), S04_TURN[1]]
        result, sheet = await self.plan(second, "create_video_from_text", {
            "subject": ("a video announcing 20% off", "derived"), "seconds": (10, "user"), "aspect": ("1:1", "derived"),
            "sound": ("none", "user"), "exact_words": (S04_TURN_WORDS, "user"), "look": ("bold red and white", "user")})
        self.assertEqual(result["tool"], "create_video_from_text")
        self.check(result, sheet, [], {"aspect": "9:16", "seconds": 10, "sound": "none", "exact_words": S04_TURN_WORDS})

    # --- more behaviour from the ticket ---

    async def test_you_write_them_is_permission_to_write_the_words(self):
        words = ["Open Mic Night", "Every voice is welcome"]
        result, sheet = await self.plan(
            [S03_VAGUE, assistant(QUESTIONS["exact_words"]), "you write them"], "generate_image",
            {"subject": ("a poster for an open mic night", "user"), "aspect": ("9:16", "derived"), "exact_words": (words, "default")})
        self.assertEqual((sheet["exact_words"]["value"], sheet["exact_words"]["source"]), (words, "default"))
        self.assertTrue(result["ready"])
        self.assertEqual(result["questions"], [])

    async def test_strange_answers_never_give_invented_words(self):
        messages = [S03_VAGUE]
        for answer in S03_STRANGE:
            messages += [assistant(QUESTIONS["exact_words"]), answer]
            for source in ["default", "derived", "user"]:
                with self.subTest(answer=answer, host_source=source):
                    result, sheet = await self.plan(list(messages), "generate_image", {
                        "subject": ("a poster for an open mic night", "user"), "aspect": ("9:16", "derived"),
                        "exact_words": (INVENTED_WORDS, source)})
                    self.check(result, sheet, ["exact_words"], {"aspect": "9:16"})

    async def test_no_question_for_a_parameter_that_the_tool_does_not_use(self):
        result, sheet = await self.plan(["remove the people from this"], "edit_image", {
            "edit": ("remove the people", "user"), "seconds": (None, "missing"), "sound": (None, "missing")}, ["car"])
        self.assertNotIn("seconds", sheet)
        self.assertNotIn("sound", sheet)
        self.assertTrue(result["ready"])
        self.assertEqual(result["questions"], [])


def _item_test(tool, brief, files, host_sheet, missing, values):
    async def test(self):
        await self.run_item(tool, brief, files, host_sheet, missing, values)
    return test


for _item, _kind, *_rest in ITEMS:
    setattr(PlanRequestTests, f"test_item_{_item}_{_kind}_brief", _item_test(*_rest))


if __name__ == "__main__":
    unittest.main()
