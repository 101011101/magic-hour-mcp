"""plan_video_production through the MCP server, and the answer parsers of plan_request. No network, no credits."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.shared.exceptions import McpError

from mcp_magichour.openapi_server import create_mcp
from mcp_magichour.plan_request import QUESTIONS, parse_aspect, parse_seconds, parse_sound, plan_sheet
from mcp_magichour.video_production_tool import SPLIT_MAX_SECONDS, SPLIT_STRATEGY

STORIES = Path(__file__).parent / "fixtures" / "stories"
STORY_FIELDS = ("title", "aspect", "audio", "setting", "subjects", "beats")
ASYNC_CLIENT = httpx.AsyncClient


def story(prefix):
    full = json.loads(next(STORIES.glob(f"{prefix}-*.json")).read_text())
    return {key: full[key] for key in STORY_FIELDS}


def data(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(c.text for c in result.content if c.type == "text"))


class VideoProductionToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []

        def upstream(request):
            self.requests.append((request.method, str(request.url)))
            return httpx.Response(500, json={"message": "plan_video_production must not call the API"})

        transport = httpx.MockTransport(upstream)
        self.patches = [
            patch("httpx.AsyncClient", side_effect=lambda *a, **k: ASYNC_CLIENT(*a, **{**k, "transport": transport})),
            patch("mcp_magichour.openapi_server.build_api_client", side_effect=lambda: ASYNC_CLIENT(base_url="https://api.example.test", transport=transport)),
            patch("mcp_magichour.openapi_server.current_authorization_header", return_value="Bearer synthetic-test-token"),
            patch("mcp_magichour.oauth_compat.current_authorization_header", return_value="Bearer synthetic-test-token"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.caller = await self.enterAsyncContext(Client(create_mcp()))

    async def plan(self, prefix):
        return data(await self.caller.call_tool("plan_video_production", {"story": story(prefix)}))

    async def test_tool_is_listed_read_only_and_takes_a_story(self):
        tool = next(t for t in await self.caller.list_tools() if t.name == "plan_video_production")
        self.assertTrue(tool.annotations.readOnlyHint)
        self.assertEqual(tool.inputSchema["required"], ["story"])
        self.assertLessEqual(len(tool.description.encode()), 2048)

    async def test_walk_anyway_comes_back_as_ordered_clips_with_one_reference_each(self):
        p = await self.plan("c4")
        self.assertTrue(p["ok"])
        self.assertEqual((p["strategy"], p["max_seconds"]), (SPLIT_STRATEGY, SPLIT_MAX_SECONDS))
        self.assertTrue(p["needs_production"])
        self.assertEqual(p["seconds"], 30)
        self.assertEqual(p["join"], [c["n"] for c in p["clips"]])
        self.assertEqual(p["clips"][0]["kind"], "card")
        self.assertEqual(p["clips"][-1]["kind"], "card")
        for clip in p["clips"]:
            self.assertIn(clip["reference"]["kind"], ("none", "last_frame", "picture", "still"))
            self.assertLessEqual(clip["seconds"], SPLIT_MAX_SECONDS)
            self.assertTrue(all(n < clip["n"] for n in clip["depends_on"]))

    async def test_a_picture_goes_into_the_plan_as_the_one_named_reference(self):
        p = await self.plan("c5")
        first = p["clips"][0]
        self.assertEqual(first["reference"], {"kind": "picture", "subject": "bottle", "file": "bench-mockup-fragrance.png"})
        self.assertEqual(first["steps"][-1]["tool"], "create_video_from_text")
        self.assertIn("@bottle", first["steps"][-1]["prompt"])

    async def test_a_short_single_scene_says_it_does_not_need_production(self):
        self.assertFalse((await self.plan("c2"))["needs_production"])

    async def test_a_bad_story_comes_back_with_named_problems_and_no_clips(self):
        bad = story("c4")
        bad["beats"][0]["exact_words"] = []
        bad["beats"][1]["subjects"] = ["nobody"]
        p = data(await self.caller.call_tool("plan_video_production", {"story": bad}))
        self.assertFalse(p["ok"])
        self.assertEqual(p["clips"], [])
        self.assertIn("beat 1: a card needs exact_words, or `picture` (a picture to hold unchanged, such as a logo)", p["problems"])
        self.assertIn("beat 2: unknown subject nobody", p["problems"])

    async def test_a_story_with_a_wrong_shape_is_refused_by_the_schema(self):
        bad = story("c1")
        bad["aspect"] = "4:3"
        with self.assertRaises((ToolError, McpError)):
            await self.caller.call_tool("plan_video_production", {"story": bad})

    async def test_the_tool_makes_no_api_request(self):
        await self.plan("c4")
        await self.plan("c5")
        self.assertEqual(self.requests, [])


class ProductionRunTests(unittest.IsolatedAsyncioTestCase):
    """Make and join the clips of a plan against an in-memory API. The file steps (ffmpeg) are replaced."""

    async def asyncSetUp(self):
        self.posts, self.uploads, self.joined = [], [], []
        self.video_status = "complete"

        self.paths = []

        def upstream(request):
            path = request.url.path
            self.paths.append(path)
            if request.url.host == "storage.example.test":
                self.uploads.append(path)
                return httpx.Response(200)
            if request.url.host == "videos.magichour.ai":
                return httpx.Response(200, content=b"video-bytes")
            if path == "/v1/files/upload-urls":
                return httpx.Response(200, json={"items": [{"upload_url": "https://storage.example.test/frame.jpg", "file_path": "api-assets/test/frame.jpg"}]})
            if request.method == "POST":
                self.posts.append((path, json.loads(request.content)))
                return httpx.Response(200, json={"id": f"job-{len(self.posts)}", "credits_charged": 10 if "image-generator" in path else 144})
            if path.startswith("/v1/video-projects/"):
                done = self.video_status == "complete"
                return httpx.Response(200, json={"id": path.rsplit("/", 1)[1], "status": self.video_status,
                                                 "downloads": [{"url": f"https://videos.magichour.ai{path}/output.mp4"}] if done else []})
            if path.startswith("/v1/audio-projects/"):
                return httpx.Response(200, json={"id": "music", "status": "complete", "downloads": [{"url": "https://videos.magichour.ai/music/output.mp3"}]})
            if path.startswith("/v1/image-projects/"):
                return httpx.Response(200, json={"id": "still", "status": "complete", "downloads": [{"url": "https://images.example.test/still/output.png"}]})
            raise AssertionError(f"Unhandled mock request: {request.method} {path}")

        transport = httpx.MockTransport(upstream)
        self.films = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.kept = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {"MAGIC_HOUR_KEPT_DIR": str(self.kept)}))
        self.enterContext(patch.dict(os.environ, {"BLOB_READ_WRITE_TOKEN": ""}))
        self.enterContext(patch.dict(os.environ, {"MAGIC_HOUR_VOICE_OVER": "video"}))   # these tests cover the video-model narration; the cloner test sets its own

        def fake_join(files, out, audio=True, seconds=None, size=None):
            self.joined.append(([f.name for f in files], audio))
            out.write_bytes(b"film")
            return out

        for target, value in [
            ("httpx.AsyncClient", lambda *a, **k: ASYNC_CLIENT(*a, **{**k, "transport": transport})),
            ("mcp_magichour.openapi_server.build_api_client", lambda: ASYNC_CLIENT(base_url="https://api.example.test", transport=transport)),
            ("mcp_magichour.openapi_server.current_authorization_header", lambda: "Bearer synthetic-test-token"),
            ("mcp_magichour.oauth_compat.current_authorization_header", lambda: "Bearer synthetic-test-token"),
            ("mcp_magichour.media_tools.have_ffmpeg", lambda: True),
            ("mcp_magichour.media_tools.last_frame", lambda video, out: (out.write_bytes(b"frame"), out)[1]),
            ("mcp_magichour.media_tools.join", fake_join),
            ("mcp_magichour.media_tools.probe", lambda file: {"seconds": {"clip-1.mp4": 8.4, "clip-2.mp4": 18.4, "clip-3.mp4": 4.0}.get(file.name, 30.2), "width": self.film_size[0], "height": self.film_size[1], "audio": True}),
            ("mcp_magichour.media_tools.speech_spans", lambda audio, **k: [(0.2, 3.0), (4.0, 6.0), (7.0, 9.0), (10.0, 12.0)]),
            ("mcp_magichour.media_tools.add_sound", self.fake_add_sound),
            ("mcp_magichour.media_tools.draw_captions", self.fake_captions),
            ("mcp_magichour.media_tools.have_captions", lambda: True),
            ("mcp_magichour.media_tools.loudness_db", lambda file: -18.0),
            ("mcp_magichour.video_production_tool.FILMS_DIR", self.films),
            ("mcp_magichour.video_production_tool._transcribe", self.fake_transcribe),
        ]:
            p = patch(target, side_effect=value) if callable(value) else patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        self.caller = await self.enterAsyncContext(Client(create_mcp()))

    film_size = (854, 480)   # the size the fake probe reports; a 9:16 story sets it
    heard = None   # what the fake transcriber hears; None = no transcriber on the server

    async def fake_transcribe(self, audio):
        return self.heard

    def fake_add_sound(self, film, out, narration=None, parts=None, music=None, spoken=None, music_first=False, layers=None, music_swell=False):
        self.sound = {"narration": narration.name if narration else None, "music": music.name if music else None, "parts": parts,
                      "spoken": spoken, "music_first": music_first}
        out.write_bytes(b"film with sound")
        return {"lufs_before": -30.0, "lufs": -16.0, "speech": [], "layers": ["speech", "effects"]}

    def fake_captions(self, film, timed, out):
        self.captions = timed
        out.write_bytes(b"film with captions")
        return out

    async def call(self, name, **arguments):
        return data(await self.caller.call_tool(name, arguments))

    async def planned(self, prefix):
        return await self.call("plan_video_production", story=story(prefix))

    async def planned_with_voice(self):
        s = story("c5")
        lines = [["Some scents fade by noon.", "This one stays."], ["It starts soft."], ["One spray is enough."], ["Mockup Fragrance."]]
        for beat, says in zip(s["beats"], lines):
            beat["says"] = says
        s.update(narrator="a calm, warm woman's voice", music="soft piano", captions=True)
        self.film_size = (480, 858)
        return await self.call("plan_video_production", story=s)

    async def test_the_sound_tool_makes_one_narration_and_one_music_track(self):
        p = await self.planned_with_voice()
        self.assertIn("create_production_sound", p["how"])
        made = await self.call("create_production_sound", production=p["production"])
        (narration_path, narration), (music_path, music) = self.posts
        self.assertEqual((narration_path, narration["audio"], narration["model"]), ("/v1/text-to-video", True, "ltx-2.5"))
        self.assertEqual(narration["style"]["prompt"], p["sound"]["narration"]["prompt"])
        self.assertEqual((music_path, music["duration"], music["style"]), ("/v1/ai-music-generator", 32, {"prompt": "soft piano", "instrumental": True}))
        self.assertEqual((made["narration"], made["music"]), ("job-1", "job-2"))

    async def test_with_the_switch_on_and_a_sample_the_voice_cloner_reads_the_script(self):
        # MCP-11, 2026-11-08: the cloner read A4 exactly; the video model 2 in 8. Off in what we ship until upstream approves.
        with patch.dict(os.environ, {"MAGIC_HOUR_VOICE_OVER": "cloner"}):
            s = story("c5")
            for beat, says in zip(s["beats"], [["Some scents fade by noon."], ["It starts soft."], ["One spray is enough."], ["Mockup Fragrance."]]):
                beat["says"] = says
            s.update(narrator="a calm voice", captions=True, voice_sample="https://example.com/voice.mp3")
            self.film_size = (480, 858)
            p = await self.call("plan_video_production", story=s)
            self.assertEqual(p["sound"]["narration"]["tool"], "voice_cloner")
            made = await self.call("create_production_sound", production=p["production"])
            (path, body), = self.posts
            self.assertEqual(path, "/v1/ai-voice-cloner")
            self.assertEqual(body["assets"], {"audio_file_path": "https://example.com/voice.mp3"})
            self.assertEqual(body["style"]["prompt"], "Some scents fade by noon. It starts soft. One spray is enough. Mockup Fragrance.")
            self.assertIn("wait_for_audio_project", made["next"])
            film = await self.call("join_production_clips", production=p["production"], made={"1": "a", "2": "b", "3": "c"},
                                   sound={"narration": made["narration"]})
        self.assertEqual(self.sound["narration"], "narration")   # fetched as an audio project
        self.assertTrue(film["sound"]["narration"])

    async def test_a_narration_that_says_other_words_is_not_met(self):
        # A4, 8 November: the narration said made-up words and the speech check passed it.
        p = await self.planned_with_voice()
        self.heard = "What Van Holtz of TMO Experience called the Mewmaw"
        film = await self.call("join_production_clips", production=p["production"], made={"1": "a", "2": "b", "3": "c"},
                               sound={"narration": "n", "music": "m"})
        voice = next(c for c in film["checked"] if c["want"].startswith("Voice-over"))
        self.assertEqual(voice["result"], "no")
        self.assertIn("Van Holtz", voice["got"])
        self.assertIn(voice["want"], film["not_met"])

    async def test_a_narration_that_says_the_script_passes_the_word_check(self):
        p = await self.planned_with_voice()
        self.heard = "Some scents fade by noon. This one stays. It starts soft. One spray is enough. Mockup fragrance."
        film = await self.call("join_production_clips", production=p["production"], made={"1": "a", "2": "b", "3": "c"},
                               sound={"narration": "n", "music": "m"})
        voice = next(c for c in film["checked"] if c["want"].startswith("Voice-over"))
        self.assertEqual(voice["result"], "yes")
        self.assertIn("100%", voice["got"])
        self.assertEqual(film["sound"]["words_match"], 1.0)

    async def test_a_plan_with_no_sound_has_no_sound_to_make(self):
        p = await self.planned("c4")
        with self.assertRaises(ToolError):
            await self.call("create_production_sound", production=p["production"])
        self.assertEqual(self.posts, [])

    async def test_the_join_puts_each_part_of_the_narration_on_its_clip_and_draws_the_captions(self):
        p = await self.planned_with_voice()   # clips: [1], [2, 3], [4]
        made = {"1": "a", "2": "b", "3": "c"}
        with self.assertRaises(ToolError):   # the plan has sound: the join asks for it
            await self.call("join_production_clips", production=p["production"], made=made)
        film = await self.call("join_production_clips", production=p["production"], made=made, sound={"narration": "n", "music": "m"})
        self.assertEqual(film["sound"], {"narration": True, "music": True, "captions": True, "loudness_lufs": -16.0, "speech_seconds": 8.8})
        self.assertEqual((self.sound["narration"], self.sound["music"]), ("narration.mp4", "music"))
        self.assertEqual(len(self.sound["parts"]), 4)
        starts = [part["at"] for part in self.sound["parts"]]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(starts[0], 0.5)                       # 0.5 s after its clip starts
        self.assertAlmostEqual(starts[2] - starts[1], 9, 5)    # the second beat of clip 2 starts 9 s into that clip
        self.assertEqual([c["text"] for c in self.captions], ["Some scents fade by noon.", "This one stays.", "It starts soft.", "One spray is enough.", "Mockup Fragrance."])
        self.assertTrue(all(a["end"] <= b["start"] + 1e-6 for a, b in zip(self.captions, self.captions[1:])))
        self.assertFalse(any(self.joined[-1][1]))              # the clips themselves are silent
        self.assertEqual([c["result"] for c in film["checked"]], ["yes"] * len(film["checked"]))
        self.assertEqual(film["not_met"], [])
        self.assertTrue(any("looks the same" in line for line in film["unchecked"]))

    async def test_a_narration_with_no_speech_is_not_met(self):
        # B1, 7 November: the narration call came back silent and the join counted it as placed.
        p = await self.planned_with_voice()
        with patch("mcp_magichour.media_tools.speech_spans", lambda audio, **k: [(0.0, 0.3)]):
            film = await self.call("join_production_clips", production=p["production"], made={"1": "a", "2": "b", "3": "c"},
                                   sound={"narration": "n", "music": "m"})
        voice = next(c for c in film["checked"] if c["want"].startswith("Voice-over"))
        self.assertEqual(voice["result"], "no")
        self.assertIn("no voice was made", voice["got"])
        self.assertIn(voice["want"], film["not_met"])

    async def test_the_plan_carries_a_checklist_and_the_join_reports_what_is_not_met(self):
        p = await self.planned("c4")   # Walk Anyway: scene sound wanted, no narration
        self.assertIn("file", [line["id"] for line in p["checklist"]])
        self.assertIn("scene-sound", [line["id"] for line in p["checklist"]])
        with patch("mcp_magichour.media_tools.loudness_db", return_value=None):   # a film that came out silent
            film = await self.call("join_production_clips", production=p["production"], made={"1": "a", "2": "b", "3": "c", "4": "d"})
        self.assertIn("The scenes have their own sound (as the beats describe)", film["not_met"])
        self.assertEqual(next(c for c in film["checked"] if c["want"].startswith("One file"))["result"], "yes")

    async def test_the_plan_carries_the_production_and_the_rounds(self):
        p = await self.planned("c4")
        self.assertEqual(p["rounds"], [[1, 2, 4], [3]])
        self.assertTrue(p["production"])
        self.assertIn("join_production_clips", p["how"])
        self.assertEqual(self.posts, [])

    async def test_a_clip_with_no_reference_is_one_text_to_video_call_with_the_plan_prompt(self):
        p = await self.planned("c4")
        made = await self.call("create_production_clip", production=p["production"], clip=2)
        path, body = self.posts[0]
        self.assertEqual((path, len(self.posts)), ("/v1/text-to-video", 1))
        self.assertEqual((body["model"], body["resolution"], body["end_seconds"], body["aspect_ratio"], body["audio"]), ("ltx-2.5", "480p", 13, "16:9", True))
        self.assertEqual(body["style"]["prompt"], p["clips"][1]["steps"][-1]["prompt"])
        self.assertEqual((made["id"], made["clip"], made["credits_charged"]), ("job-1", 2, 144))

    async def test_a_clip_that_continues_starts_from_the_last_frame_of_the_finished_clip(self):
        p = await self.planned("c4")
        await self.call("create_production_clip", production=p["production"], clip=3, made={"2": "job-a"})
        path, body = self.posts[0]
        self.assertEqual(path, "/v1/image-to-video")
        self.assertEqual(body["assets"], {"image_file_path": "api-assets/test/frame.jpg"})
        self.assertEqual(self.uploads, ["/frame.jpg"])
        self.assertNotIn("aspect_ratio", body)

    async def test_a_clip_whose_source_is_missing_or_not_finished_makes_no_paid_call(self):
        p = await self.planned("c4")
        with self.assertRaises(ToolError):
            await self.call("create_production_clip", production=p["production"], clip=3)
        self.video_status = "rendering"
        with self.assertRaises(ToolError):
            await self.call("create_production_clip", production=p["production"], clip=3, made={"2": "job-a"})
        self.assertEqual(self.posts, [])

    async def test_a_card_is_a_still_and_then_a_clip_from_that_still(self):
        p = await self.planned("c4")
        made = await self.call("create_production_clip", production=p["production"], clip=1)
        self.assertEqual([path for path, _ in self.posts], ["/v1/ai-image-generator", "/v1/image-to-video"])
        self.assertIn("WALK ANYWAY", self.posts[0][1]["style"]["prompt"])
        self.assertEqual(self.posts[1][1]["assets"], {"image_file_path": "https://images.example.test/still/output.png"})
        self.assertEqual(made["credits_charged"], 154)

    async def test_a_picture_is_the_one_named_reference(self):
        p = await self.planned("c5")
        await self.call("create_production_clip", production=p["production"], clip=2)
        path, body = self.posts[0]
        self.assertEqual((path, body["model"]), ("/v1/text-to-video", "minimax-h3"))
        self.assertEqual(body["references"], [{"name": "presenter", "file_path": "bench-presenter.png"}])

    async def test_the_join_takes_every_finished_clip_in_story_order(self):
        p = await self.planned("c4")
        made = {"1": "a", "2": "b", "3": "c", "4": "d"}
        film = await self.call("join_production_clips", production=p["production"], made=made)
        self.assertEqual(self.joined, [(["clip-1.mp4", "clip-2.mp4", "clip-3.mp4", "clip-4.mp4"], [True] * 4)])
        self.assertRegex(film["download_url"], r"/films/[0-9a-f]{32}\.mp4$")
        self.assertTrue((self.films / film["download_url"].rsplit("/", 1)[1]).exists())
        self.assertEqual(film["clips"], 4)
        self.assertEqual(self.posts, [])
        with self.assertRaises(ToolError):
            await self.call("join_production_clips", production=p["production"], made={"1": "a", "2": "b"})

    async def test_an_upload_through_the_server_can_be_joined_and_framed(self):
        import base64
        up = await self.call("upload_media", file_name="clip.mp4", data_base64=base64.b64encode(b"user-clip").decode())
        self.assertEqual((up["file_path"], up["kind"], up["bytes"]), ("api-assets/test/frame.jpg", "video", 9))
        self.assertEqual(self.uploads, ["/frame.jpg"])
        self.paths.clear()
        film = await self.call("join_videos", videos=[up["file_path"], "proj-1"])
        self.assertEqual(self.joined, [(["source.jpg", "source.mp4"], True)])   # each file in its own folder, named by its type
        self.assertNotIn("/v1/video-projects/api-assets/test/frame.jpg", self.paths)
        self.assertRegex(film["download_url"], r"/films/[0-9a-f]{32}\.mp4$")
        frame = await self.call("get_last_frame", video=up["file_path"])
        self.assertEqual(frame["file_path"], "api-assets/test/frame.jpg")

    async def test_an_upload_by_url_is_downloaded_then_kept(self):
        up = await self.call("upload_media", file_name="jet.mp4", url="https://videos.magichour.ai/u/jet.mp4")
        self.assertEqual(up["kind"], "video")
        self.assertEqual(list(self.kept.iterdir())[0].read_bytes(), b"video-bytes")

    async def test_a_file_uploaded_around_the_server_fails_clearly_and_spends_nothing(self):
        for name, arguments in [("join_videos", {"videos": ["api-assets/acct/never-seen.mp4"]}),
                                ("get_last_frame", {"video": "api-assets/acct/never-seen.mp4"})]:
            with self.subTest(tool=name), self.assertRaisesRegex(ToolError, "upload_media"):
                await self.call(name, **arguments)
        self.assertFalse([p for p in self.paths if "never-seen" in p])
        self.assertEqual(self.posts, [])

    async def test_the_production_join_takes_the_users_own_clip_by_file_path(self):
        import base64
        p = await self.planned("c4")
        up = await self.call("upload_media", file_name="mine.mov", data_base64=base64.b64encode(b"mine").decode())
        await self.call("join_production_clips", production=p["production"], made={"1": up["file_path"], "2": "b", "3": "c", "4": "d"})
        self.assertEqual(self.joined[0][0], ["clip-1.mp4", "clip-2.mp4", "clip-3.mp4", "clip-4.mp4"])
        self.assertNotIn("/v1/video-projects/api-assets/test/frame.jpg", self.paths)

    def users_clip_story(self, file_path, **extra):
        return {"title": "My clip", "aspect": "16:9", "setting": "A sunny kitchen, soft daylight.", "captions": True,
                "beats": [{"seconds": 7, "text": "The user's own clip.", "source": file_path, "clip": 1,
                           "says": ["Make mornings easier.", "Prepare the night before."]}], **extra}

    async def test_a_voice_over_goes_on_the_users_own_clip(self):
        # MCP-14: the user's clip is a beat of its own (`source`); nothing is generated for it.
        import base64
        up = await self.call("upload_media", file_name="mine.mp4", data_base64=base64.b64encode(b"user-clip").decode())
        p = await self.call("plan_video_production", story=self.users_clip_story(up["file_path"]))
        clip = p["clips"][0]
        self.assertEqual((clip["made_by"], clip["kind"], clip["steps"][0]["credits"]), ("user", "source", 0))
        self.assertIn("source-1", [line["id"] for line in p["checklist"]])
        made = await self.call("create_production_clip", production=p["production"], clip=1)
        self.assertEqual((made["made_by"], made["credits_charged"]), ("user", 0))
        sound = await self.call("create_production_sound", production=p["production"])
        self.assertEqual([path for path, _ in self.posts], ["/v1/text-to-video"])   # the narration only, no clip
        self.paths.clear()
        film = await self.call("join_production_clips", production=p["production"], made={}, sound={"narration": sound["narration"]})
        self.assertEqual(self.joined[-1], (["clip-1.mp4"], [True]))   # the user's clip keeps its own sound
        self.assertFalse([path for path in self.paths if "api-assets" in path])   # read from the kept copy
        self.assertTrue(film["sound"]["narration"])

    async def test_speech_in_the_users_clip_is_never_lowered_unless_the_host_says_it_is_background(self):
        # 2026-11-13: the user's clip's own sound was lowered 10 dB as "effects", even when someone speaks in it.
        import base64
        up = await self.call("upload_media", file_name="mine.mp4", data_base64=base64.b64encode(b"user-clip").decode())
        for speech, kept in [(None, [(0.0, 8.4)]), (True, [(0.0, 8.4)]), (False, [])]:
            story = self.users_clip_story(up["file_path"], music="Soft piano.")
            story["beats"][0].pop("says")
            if speech is not None:
                story["beats"][0]["source_speech"] = speech
            p = await self.call("plan_video_production", story=story)
            sound = await self.call("create_production_sound", production=p["production"])
            film = await self.call("join_production_clips", production=p["production"], made={}, sound={"music": sound["music"]})
            self.assertEqual(self.sound["spoken"], kept, speech)
            self.assertEqual(film["sound"].get("user_clip_as_speech"), [1] if kept else None)

    async def test_a_voice_over_on_the_users_clip_warns_when_the_clip_may_have_speech(self):
        import base64
        up = await self.call("upload_media", file_name="mine.mp4", data_base64=base64.b64encode(b"user-clip").decode())
        p = await self.call("plan_video_production", story=self.users_clip_story(up["file_path"]))
        self.assertIn("voice-over-on-speech", [a["note"] for a in p["advice"]])
        story = self.users_clip_story(up["file_path"])
        story["beats"][0]["source_speech"] = False
        p = await self.call("plan_video_production", story=story)
        self.assertNotIn("voice-over-on-speech", [a["note"] for a in p["advice"]])

    async def test_a_voice_over_with_too_many_words_for_its_beat_is_warned_at_the_plan(self):
        # I46a, 2026-11-13: 12 words in a 4 s beat; the last words ran past the end of the film.
        story = {"title": "Jet", "aspect": "16:9", "setting": "An airfield at dawn.", "beats": [
            {"seconds": 4, "text": "A jet on the runway.", "clip": 1, "says": ["The F-35A Lightning II is powered by a single engine."]},
            {"seconds": 4, "text": "The jet takes off.", "clip": 1,
             "says": ["It is the conventional takeoff and landing version, built for normal runways."]}]}
        p = await self.call("plan_video_production", story=story)
        paced = [a["warning"] for a in p["advice"] if a["note"] == "voice-over-pace"]
        self.assertEqual(len(paced), 1)
        self.assertIn("Beat 2: the voice-over has 12 words for 4 s", paced[0])

    async def test_a_new_clip_continues_from_the_users_clip(self):
        # A3: the next clip starts from the last frame of the user's clip.
        import base64
        up = await self.call("upload_media", file_name="mine.mp4", data_base64=base64.b64encode(b"user-clip").decode())
        story = self.users_clip_story(up["file_path"])
        story["beats"][0].pop("says")
        story["beats"].append({"seconds": 5, "text": "She turns and walks out of frame.", "clip": 2, "link": "continues"})
        p = await self.call("plan_video_production", story=story)
        self.assertEqual(p["clips"][1]["reference"]["kind"], "last_frame")
        self.assertEqual(p["clips"][1]["depends_on"], [1])
        await self.call("create_production_clip", production=p["production"], clip=2, made={})
        (path, body), = self.posts
        self.assertEqual(path, "/v1/image-to-video")
        await self.call("join_production_clips", production=p["production"], made={"2": "job-1"})
        self.assertEqual(self.joined[-1], (["clip-1.mp4", "clip-2.mp4"], [True, False]))   # the new clip is silent

    async def test_the_users_clip_is_cut_to_source_start_and_end(self):
        # J50b: keep the first 5 s of the user's 8 s clip and make a new ending from the frame at 5 s.
        import base64
        cuts = []

        def fake_trim(source, out, start=0.0, end=None):
            cuts.append((source.name, start, end))
            out.write_bytes(b"part")
            return out

        up = await self.call("upload_media", file_name="mine.mp4", data_base64=base64.b64encode(b"user-clip").decode())
        story = self.users_clip_story(up["file_path"])
        story["beats"][0].pop("says")
        story["beats"][0].update(seconds=5, source_end=5)
        story["beats"].append({"seconds": 3, "text": "The plane lands on the desk.", "clip": 2, "link": "continues"})
        p = await self.call("plan_video_production", story=story)
        self.assertEqual(p["clips"][0]["steps"][0]["end"], 5)
        with patch("mcp_magichour.media_tools.trim", side_effect=fake_trim):
            await self.call("create_production_clip", production=p["production"], clip=2, made={})
            await self.call("join_production_clips", production=p["production"], made={"2": "job-1"})
        self.assertEqual(cuts, [("clip-1.mp4", 0.0, 5), ("clip-1.mp4", 0.0, 5)])   # the last frame and the join both use the cut
        self.assertEqual(self.joined[-1][0], ["clip-1-part.mp4", "clip-2.mp4"])
        bad = self.users_clip_story(up["file_path"])
        bad["beats"][0].update(source_start=4, source_end=2)
        self.assertFalse((await self.call("plan_video_production", story=bad))["ok"])

    async def test_a_source_beat_must_stand_alone_and_be_used_as_it_is(self):
        bad = self.users_clip_story("api-assets/x/mine.mp4")
        bad["beats"][0]["reference"] = {"kind": "none"}
        p = await self.call("plan_video_production", story=bad)
        self.assertFalse(p["ok"])
        two = self.users_clip_story("api-assets/x/mine.mp4")
        two["beats"].append({"seconds": 3, "text": "A second beat.", "clip": 1})
        p = await self.call("plan_video_production", story=two)
        self.assertFalse(p["ok"])
        self.assertEqual(self.posts, [])

    async def test_upload_needs_one_source_and_a_known_type(self):
        for arguments in [{"file_name": "a.mp4"}, {"file_name": "a.mp4", "url": "https://x.test/a.mp4", "data_base64": "eA=="},
                          {"file_name": "a.exe", "data_base64": "eA=="}, {"file_name": "a.mp4", "data_base64": "not base64!"}]:
            with self.subTest(arguments=arguments), self.assertRaises(ToolError):
                await self.call("upload_media", **arguments)
        self.assertEqual(self.uploads, [])

    async def test_without_ffmpeg_the_file_steps_say_so_and_spend_nothing(self):
        p = await self.planned("c4")
        with patch("mcp_magichour.media_tools.have_ffmpeg", return_value=False):
            for name, arguments in [("create_production_clip", {"clip": 3, "made": {"2": "a"}}), ("join_production_clips", {"made": {"1": "a"}})]:
                with self.subTest(tool=name), self.assertRaises(ToolError):
                    await self.call(name, production=p["production"], **arguments)
        self.assertEqual(self.posts, [])

    async def test_a_changed_production_value_is_refused(self):
        with self.assertRaises(ToolError):
            await self.call("create_production_clip", production="not-a-plan", clip=1)
        self.assertEqual(self.posts, [])


class AnswerParserTests(unittest.TestCase):
    def test_a_length_needs_a_unit_or_a_short_answer(self):
        self.assertEqual(parse_seconds("a 10-second clip"), 10)
        self.assertEqual(parse_seconds("for 6 seconds"), 6)
        self.assertEqual(parse_seconds("10"), 10)
        self.assertEqual(parse_seconds("about 15"), 15)
        self.assertEqual(parse_seconds("make a short clip of her"), 8)
        self.assertIsNone(parse_seconds("a social post announcing 20% off"))
        self.assertIsNone(parse_seconds("the words are 'Open 9 to 5 every day'"))

    def test_no_music_is_not_a_request_for_music(self):
        self.assertIsNone(parse_sound("Rain only. No music and no narrator."))
        self.assertEqual(parse_sound("with the natural sound of the waves, no music, no words"), "ambient")
        self.assertEqual(parse_sound("with music"), "music")
        self.assertEqual(parse_sound("no sound"), "none")
        self.assertEqual(parse_sound("a warm voice-over"), "narration")

    def test_a_platform_or_a_ratio_gives_the_shape(self):
        self.assertEqual(parse_aspect("Instagram story"), "9:16")
        self.assertEqual(parse_aspect("printed A4 (3:4)"), "9:16")
        self.assertEqual(parse_aspect("for YouTube"), "16:9")
        self.assertIsNone(parse_aspect("for my meditation app"))


class SheetRuleTests(unittest.TestCase):
    WAVES = "a clip of waves at sunset for my meditation app"

    def test_the_create_tool_argument_names_are_read_as_sheet_rows(self):
        result = plan_sheet([{"role": "user", "text": self.WAVES}], "create_video_from_text", [
            {"name": "style.prompt", "value": "Gentle ocean waves at sunset.", "source": "derived"},
            {"name": "end_seconds", "value": 5, "source": "default"},
            {"name": "aspect_ratio", "value": "16:9", "source": "default"},
            {"name": "audio", "value": True, "source": "default"},
            {"name": "model", "value": "ltx-2.5", "source": "default"},
        ])
        sheet = {row["name"]: row for row in result["params"]}
        self.assertEqual(sheet["subject"]["value"], "Gentle ocean waves at sunset.")
        self.assertNotIn("model", sheet)
        self.assertEqual([q["param"] for q in result["questions"]], ["seconds", "aspect", "sound"])

    def test_your_call_is_not_a_default_for_a_question_that_was_not_asked(self):
        asked = " ".join(QUESTIONS[name] for name in ("subject", "seconds", "aspect"))
        result = plan_sheet([
            {"role": "user", "text": self.WAVES}, {"role": "assistant", "text": asked},
            {"role": "user", "text": "Your call on what it shows, 10 seconds, for TikTok."},
        ], "create_video_from_text", [
            {"name": "subject", "value": "waves at sunset", "source": "derived"},
            {"name": "seconds", "value": 10, "source": "user"}, {"name": "aspect", "value": "9:16", "source": "user"},
            {"name": "sound", "value": None, "source": "missing"},
        ])
        sheet = {row["name"]: row for row in result["params"]}
        self.assertEqual((sheet["seconds"]["value"], sheet["aspect"]["value"]), (10, "9:16"))
        self.assertEqual(sheet["sound"]["source"], "missing")
        self.assertEqual(result["questions"], [{"param": "sound", "question": QUESTIONS["sound"]}])

    def test_a_file_name_is_not_read_as_a_shape(self):
        result = plan_sheet(
            [{"role": "user", "text": "make a short clip of her\n[Attached: portrait-woman.jpg — Magic Hour file_path: api-assets/x/y.jpg]"}],
            "create_video_from_image", [{"name": "motion", "value": None, "source": "missing"}],
            [{"name": "portrait-woman.jpg", "kind": "image", "aspect": "1:1"}])
        sheet = {row["name"]: row for row in result["params"]}
        self.assertEqual(sheet["aspect"]["source"], "missing")
        self.assertEqual(sheet["seconds"]["value"], 8)

    def test_a_length_from_an_earlier_message_is_kept_on_the_next_turn(self):
        result = plan_sheet([
            {"role": "user", "text": "make a short clip of her"},
            {"role": "assistant", "text": QUESTIONS["motion"] + " " + QUESTIONS["sound"]},
            {"role": "user", "text": "She smiles and looks around a little. Silent."},
        ], "create_video_from_image", [
            {"name": "motion", "value": "she smiles and looks around a little", "source": "user"},
            {"name": "sound", "value": "none", "source": "user"}, {"name": "seconds", "value": None, "source": "missing"},
            {"name": "aspect", "value": "1:1", "source": "user"},
        ], [{"name": "portrait-woman.jpg", "kind": "image", "aspect": "1:1"}])
        sheet = {row["name"]: row for row in result["params"]}
        self.assertEqual((sheet["seconds"]["value"], sheet["seconds"]["source"]), (8, "derived"))
        self.assertNotIn("seconds", [q["param"] for q in result["questions"]])

    def test_a_paraphrase_of_a_stated_edit_is_kept_and_an_unstated_edit_is_asked(self):
        car = [{"name": "car.jpg", "kind": "image"}]
        stated = plan_sheet([{"role": "user", "text": "remove the people from this"}], "edit_image", [
            {"name": "edit", "value": "Remove all people and fill their place with natural background.", "source": "derived"}], car)
        self.assertEqual(stated["questions"], [])
        unstated = plan_sheet([{"role": "user", "text": "I need a shot of my perfume for the website"}], "edit_image", [
            {"name": "edit", "value": "Create a product shot for a website", "source": "user"}], car)
        self.assertIn("edit", [q["param"] for q in unstated["questions"]])

    def test_an_open_look_or_optional_words_row_is_not_asked(self):
        result = plan_sheet([{"role": "user", "text": "remove the people from this"}], "edit_image", [
            {"name": "edit", "value": "remove the people", "source": "user"},
            {"name": "look", "value": None, "source": "missing"}, {"name": "exact_words", "value": None, "source": "missing"},
            {"name": "keep", "value": None, "source": "missing"}], [{"name": "car.jpg", "kind": "image"}])
        self.assertTrue(result["ready"])
        poster = plan_sheet([{"role": "user", "text": "make a poster for our open mic night"}], "generate_image", [
            {"name": "subject", "value": "a poster for our open mic night", "source": "user"},
            {"name": "look", "value": None, "source": "missing"}, {"name": "exact_words", "value": None, "source": "missing"}])
        self.assertEqual([q["param"] for q in poster["questions"]], ["exact_words"])

    def test_an_answer_about_sound_is_read_from_the_newest_message(self):
        result = plan_sheet([
            {"role": "user", "text": self.WAVES}, {"role": "assistant", "text": QUESTIONS["sound"]},
            {"role": "user", "text": "gentle ambient wave sound"},
        ], "create_video_from_text", [
            {"name": "subject", "value": "waves at sunset", "source": "derived"},
            {"name": "seconds", "value": 10, "source": "user"}, {"name": "aspect", "value": "9:16", "source": "user"},
        ])
        self.assertEqual({row["name"]: row["value"] for row in result["params"]}["sound"], "ambient")


if __name__ == "__main__":
    unittest.main()
