# Tool management: failure list

What failed on the tool-management items, and what did better or worse than the old MCP. Ticket: MCP-20. Overview: [tool management](README.md).

## Source and how to read it

- Persona bench, live runs only (2026-11-10/11, sweeps s1 to s5, 3 simulated users). Page: `Benchmark/audit/audit-1.html`. Every failed checklist line there has a traced root cause ("why?").
- Old = the MCP as ChatGPT has it. New = the build of 2026-11-10/11: `plan_request` on every call, the production tools visible. Since MCP-18 (2026-11-12) `plan_request` is no longer on single calls, so "new" here is not today's build.
- The bench ran before commit cbbe722 (2026-11-13), which added `reframe_media`, `trim_media`, `add_words_to_media` and `mix_audio`. No run used them. Many failures below may already have a tool; that is not measured.
- Score 1 to 5 by the grader, averaged over the live runs of each side. Better / worse = a difference of 0.3 or more. 1 to 4 runs a side: one bad run moves a case.
- Traced causes (the grader's labels): `mcp_tool_behavior` (our tool did the wrong thing or no tool fits), `generator_limit` (the model cannot), `grader_artifact` / `harness_artifact` (the test is wrong, not the tool), `free_plan_limit`.
- Right tool: proposed (2026-11-13), for the user to correct. "GAP" = no tool does the job today. Source: `scripts/tool_right_tools.py`.
- Built by `scripts/audit_cases.py` then `scripts/tool_failures.py` (0 credits). User's notes: blank, for the user.

## Patterns (proposed, not confirmed by the user)

Most low scores are not a wrong pick between two tools. In the bench, no tool did the job, so the host took the nearest tool and it redrew the user's media or did something else. Since then, four tools were added (cbbe722). The table says which failures they should cover and which remain gaps.

| Pattern | Cases | Bench score | Tool today | Left to do |
|---|---|---|---|---|
| Change the shape (crop, pad, fill) | B12a–d, E25a/b, J51b | 1 to 2 | `reframe_media` | 4:5 is missing (B12c, A03, G34b, J50a ask for it). Not benchmarked. |
| Exact words on a picture or video (headline, name, watermark, meme) | A02, A03, A06a/b, B11, E29c, G33, G34 | 2 to 3.5 | `add_words_to_media` | Not benchmarked. The host must make the picture without words first. |
| Cut the user's video | E26a/b, J50b, C15a | 2 | `trim_media` | Picking "the best part" needs a look at the clip (MCP-07). |
| Music under the user's video | E27a/b/c | 2 | none: `mix_audio` makes sound only | GAP: lay sound on a video. |
| Voice-over on the user's video | E28a/b/c | 1.3 to 2.7 | only the production join (`source`, MCP-14) | GAP on the tool path, or route these to video composition. |
| Logo (a picture) on a video | E29a | 1.3 | none | GAP: overlay a picture on a video. |
| End card added to a clip | E29b | 2 | none | GAP: a still as a video clip. |
| Photos side by side | G35a/b | 1.7 to 2 | none | GAP: put pictures side by side by code. |
| Subtitles in another language | E24b | 2 | none | GAP: `add_subtitles_to_video` writes the spoken language. |
| A frame from the middle of a video | G33b | 2 to 2.3 | `get_last_frame` only | GAP: a frame at a chosen time. |
| Colour only (warmer, black and white) | B07c, B10c | 2 to 4.7 | `edit_image` redraws | GAP: colour change by code. |
| Face swap on a video with two people | C15c | 1 to 1.3 | `swap_face_in_video` | Model limit; sound lost. |
| Test faults | A02d, A03a–d | — | — | The grader measured the source image too. Re-score. |

Not run live (dry only, 12 cases): C14c, C15b, C17c, E24c, H43b, J53a–c, J54a–c (refusals, budgets, free-plan limits), and E29b on the new side.

What did well on both sides: single images (A, average 3.5 → 3.6), `upscale_image` (3.3 → 3.8), `swap_face_in_photo` (4.0 / 3.7), `create_meme`, `generate_headshot`.

## Results

Cases: 118. Better 41 · same 33 · worse 32 · no pair 12 (new minus old, average over live runs, 0.3 or more counts).

### By group

| Group | Cases | Old | New | Better / same / worse |
|---|---|---|---|---|
| A · Single images | 24 | 3.5 | 3.6 | 11 / 5 / 8 |
| B · Image edits (the user brings a picture) | 26 | 3.1 | 3.2 | 9 / 7 / 10 |
| C · Faces and characters | 12 | 3.0 | 3.1 | 5 / 2 / 2 |
| E · Editing the user's video | 18 | 2.0 | 1.8 | 1 / 10 / 5 |
| F · Sound | 7 | 2.7 | 3.0 | 3 / 3 / 1 |
| G · Composed pieces (several tools, one finished thing) | 16 | 2.9 | 3.0 | 8 / 3 / 5 |
| H · Short ads and reels (10-30 s) | 1 | – | – | 0 / 0 / 0 |
| J · How the conversation goes (applies on top of any case above) | 14 | 2.5 | 2.8 | 4 / 3 / 1 |

### By the first tool called (all live runs on these cases)

| Tool | Runs old | Avg old | Runs new | Avg new |
|---|---|---|---|---|
| `edit_image` | 107 | 3.2 | 106 | 3.3 |
| `generate_image` | 103 | 3.1 | 103 | 3.3 |
| `generate_music` | 19 | 2.7 | 15 | 2.9 |
| `detect_faces` | 17 | 1.9 | 9 | 2.0 |
| `edit_video` | 15 | 1.5 | 9 | 1.3 |
| `ai_voice_generator_create_audio` | 20 | 2.6 | 0 | – |
| `create_video_from_text` | 10 | 2.0 | 9 | 2.7 |
| `join_videos` | 0 | – | 14 | 2.0 |
| `add_subtitles_to_video` | 9 | 2.4 | 3 | 2.7 |
| `upscale_image` | 6 | 3.3 | 5 | 3.8 |
| `plan_video_production` | 0 | – | 11 | 2.1 |
| `get_last_frame` | 0 | – | 8 | 2.1 |
| `swap_face_in_photo` | 4 | 4.0 | 3 | 3.7 |
| `create_meme` | 3 | 3.3 | 3 | 3.7 |
| `generate_headshot` | 3 | 3.3 | 2 | 3.5 |
| `create_spoken_ad_video` | 1 | 4.0 | 3 | 3.7 |
| `remove_image_background` | 2 | 1.0 | 2 | 1.0 |
| `create_video_from_image` | 0 | – | 3 | 4.0 |
| `swap_face_in_video` | 0 | – | 1 | 3.0 |
| `trim_video` | 0 | – | 1 | 2.0 |

### Each case

| Item | Request | Runs o/n | Old | New | Verdict | Tools called (old / new, most common) | Most common failure | Traced causes | Right tool | User's notes |
|---|---|---|---|---|---|---|---|---|---|---|
| A01a | Matte Black Bottle on Marble | 4/4 | 3.5 | 3.5 | same | `generate_image` | The bottle has a matte black finish rather than a glossy or metallic finish. — Bottle is brushed silver stainl… | harness_artifact | generate_image |  |
| A01b | Premium Candle Product Shot | 3/3 | 4.0 | 4.0 | same | `generate_image` |  |  | generate_image |  |
| A01c | Square White Background Sneaker | 3/3 | 4.0 | 3.7 | worse | `generate_image` | The background is plain white, with no scenery or props. — Background is plain with no props but light grey gr… |  | generate_image |  |
| A01d | Exact Brand Name on Label | 3/3 | 3.3 | 3.3 | same | `generate_image` | Amber glass hand soap bottle is main subject — Bottle is clear, not amber; it is the main subject though. | harness_artifact | generate_image (label words: model may misspell; or plain label → add_words_to_media) |  |
| A02a | Exact Headline for Coffee Post | 3/3 | 3.3 | 3.3 | same | `generate_image` | The headline reads exactly “Small cup. Big energy.” — No text in the image. |  | generate_image (no text) → add_words_to_media |  |
| A02b | Write the Cleanup Headline | 3/3 | 3.3 | 3.7 | better | `generate_image` | A short, readable English headline encourages beach cleanup. — Headline reads 'CEAN UP YOUR BACH', misspelled,… |  | generate_image (no text) → add_words_to_media |  |
| A02c | Instagram Plant Shop Announcement | 3/3 | 3.3 | 4.3 | better | `generate_image` | Headline reads exactly 'Bring home some green' — Headline reads 'Fresh Green Arrivals'. |  | generate_image (no text) → add_words_to_media |  |
| A02d | Headline Above the Coach | 3/3 | 3.0 | 2.7 | worse | `generate_image → edit_image` | aspect 4:5 — ["640x640"] | grader_artifact, mcp_tool_behavior | generate_image 4:5 → add_words_to_media (top) |  |
| A03a | Community Picnic With Complete Details | 3/3 | 3.0 | 3.7 | better | `generate_image → edit_image` | aspect 4:5 — ["352x640","512x640"] | grader_artifact | generate_image 4:5 → add_words_to_media |  |
| A03b | Four Clearly Separated Flyer Blocks | 3/3 | 2.3 | 3.0 | better | `generate_image → edit_image` | aspect 4:5 — ["352x640","512x640"] | grader_artifact, generator_limit | generate_image 4:5 → add_words_to_media |  |
| A03c | Workshop Flyer Missing Its Date | 3/3 | 3.3 | 4.0 | better | `generate_image → edit_image` | aspect 4:5 — ["352x640","512x640"] | grader_artifact | generate_image 4:5 → add_words_to_media |  |
| A03d | Long Venue Address Preserved Exactly | 3/3 | 3.0 | 3.3 | better | `generate_image → edit_image` | aspect 4:5 — ["640x640","512x640"] | grader_artifact, generator_limit | generate_image 4:5 → add_words_to_media |  |
| A04a | Watercolour Cottage by a Stream | 3/3 | 3.7 | 4.0 | better | `generate_image` | Watercolour look — Photorealistic finish, not watercolour. |  | generate_image |  |
| A04b | Somewhere Quiet and Hopeful | 3/3 | 4.7 | 4.3 | worse | `generate_image` |  |  | generate_image |  |
| A04c | Exactly Three Red Balloons | 3/3 | 4.0 | 3.7 | worse | `generate_image` | Exactly three balloons, no extras — About 25 balloons in a large bunch. | harness_artifact | generate_image |  |
| A04d | Cup Left of the Laptop | 3/3 | 3.3 | 3.3 | same | `generate_image` | aspect 16:9 — ["640x640"] | mcp_tool_behavior, grader_artifact | generate_image |  |
| A05a | LinkedIn Headshot From Park Photo | 3/3 | 4.3 | 4.0 | worse | `edit_image` | aspect 1:1 — ["928x1152"] | harness_artifact, grader_artifact | edit_image (or generate_headshot: test) |  |
| A05b | Make My Photo Look Professional | 3/3 | 4.3 | 4.0 | worse | `edit_image` |  |  | edit_image (or generate_headshot: test) |  |
| A05c | Professional Portrait Without Changing My Face | 3/3 | 4.0 | 4.7 | better | `edit_image` | Face closely matches source — Looks like a similar person but face is slimmer, features reshaped, eyes/mouth d… | generator_limit | edit_image (or generate_headshot: test) |  |
| A05d | Choose The Right Headshot Subject | 3/3 | 3.3 | 3.7 | better | `edit_image → generate_headshot` / `edit_image` | aspect 1:1 — ["640x384","928x1152"] | mcp_tool_behavior, grader_artifact | ask which person → reframe_media crop, focus on them → generate_headshot |  |
| A06a | Simple Sprout Shop Logo | 3/3 | 4.0 | 3.3 | worse | `generate_image` | The name reads 'Little Sprout' clearly. — No text in the image. | mcp_tool_behavior | generate_image → add_words_to_media (exact name) |  |
| A06b | Exact Spelling For Repair Logo | 3/3 | 3.3 | 2.7 | worse | `generate_image` | Name reads exactly KwickFixx — Last x is overlapped and mangled by the wrench handle, so it reads as KwickFix … | mcp_tool_behavior | generate_image → add_words_to_media (exact name) |  |
| A06c | Transparent Moon Bakery Logo | 3/3 | 1.7 | 2.7 | better | `generate_image → remove_image_background` | Name reads exactly 'Mooncrumb' in dark navy — The first image spells it correctly in navy, but the second imag… | generator_limit | generate_image → add_words_to_media → remove_image_background |  |
| A06d | Three Distinct Cycling Logo Options | 3/3 | 3.7 | 4.0 | better | `generate_image` |  |  | generate_image ×3 → add_words_to_media |  |
| B07a | Repaint Only the Car | 3/4 | 3.7 | 3.8 | same | `edit_image` | Body paint is navy blue — Body is a fairly bright royal/cobalt blue, lighter than navy. | generator_limit | edit_image |  |
| B07b | Same Street After Dark | 3/3 | 3.7 | 4.0 | better | `edit_image` | Composition preserved, no new subjects/objects — A new woman in dark clothes stands in front of the left shop … |  | edit_image |  |
| B07c | Warmer Colours Only | 3/3 | 2.0 | 3.7 | better | `edit_image` | Framing, geometry and detail unchanged apart from colour — Contrast and saturation are crushed, shadows are da… | generator_limit | GAP: colour change by code (edit_image redraws) |  |
| B07d | Change Only the Bottle | 3/3 | 3.3 | 4.0 | better | `edit_image` | Bottle keeps exact silhouette, position, surface details — Silhouette and position match, but the cap opening … | generator_limit | edit_image |  |
| B08a | Remove the Background Pedestrian | 3/3 | 4.0 | 3.3 | worse | `edit_image` | Shops, layout, sunny lighting consistent with source — The shops and light match, but a new woman appears on t… |  | edit_image |  |
| B08b | Clear Selected Desk Clutter | 3/3 | 4.0 | 3.7 | worse | `edit_image` | The papers and empty takeaway cup are absent. — The cup is gone, but the papers are still there as one neat st… | generator_limit | edit_image |  |
| B08c | Clean Up This Kitchen | 3/3 | 4.0 | 3.7 | worse | `edit_image` | Layout, fixed fixtures and viewpoint match source — Right-hand second sink became a cooktop with two burners, … |  | edit_image |  |
| B09a | Bottle on a Kitchen Counter | 3/3 | 3.3 | 3.3 | same | `edit_image` | Bottle stands on a light stone kitchen counter, not the wooden table — It stands on a plain grey studio backdr… |  | edit_image |  |
| B09b | Beach Background for My Portrait | 3/3 | 4.0 | 4.7 | better | `edit_image` |  |  | edit_image |  |
| B09c | Sneaker on Studio White | 3/3 | 4.0 | 3.7 | worse | `edit_image` | Grey floor and clutter replaced by seamless white setting — Clutter is gone and the background is seamless, bu… | harness_artifact | edit_image |  |
| B09d | Match the Kitchen Window Light | 3/3 | 4.0 | 4.0 | same | `edit_image` | Same candle jar and wax preserved on a pale kitchen counter — Jar and wax preserved, but the setting is a whit… | harness_artifact | edit_image |  |
| B10a | Portrait From a Seventies Film | 3/3 | 4.0 | 4.0 | same | `edit_image` |  |  | edit_image |  |
| B10b | Beach Friends as Anime | 3/3 | 4.0 | 4.0 | same | `edit_image` | Output is 16:9 with no added words — The image appears to be about 640x384 (5:3), not 16:9. There is no text. … |  | edit_image |  |
| B10c | Car Photo in Black and White | 3/3 | 4.0 | 4.7 | better | `edit_image` | Entire image neutral black and white, no red or colour remaining — The red is gone, but the car looks like a p… |  | GAP: black and white by code (edit_image redraws) |  |
| B10d | Fox Mascot in Reference Style | 3/3 | 4.0 | 3.3 | worse | `edit_image` | One square image with no added text — No text is present, but the output is a portrait poster with a white bor… | generator_limit | edit_image (two references) |  |
| B11a | Quiet Caption Over The Lake | 3/3 | 1.7 | 2.3 | better | `edit_image` | Caption reads exactly 'A little room to breathe' without quotes — It reads 'A Alittle room to breathe', with a… | generator_limit | add_words_to_media |  |
| B11b | Chalkboard Outside The Café | 3/3 | 2.7 | 2.7 | same | `edit_image` | Plausible ground contact, scale, lighting, shadow — Board is fairly large and has little visible cast shadow. … | generator_limit | edit_image (sign in the scene) |  |
| B11c | Shocked Cat Monday Meme | 3/3 | 3.7 | 3.0 | worse | `edit_image` | Top text reads 'WHEN YOU THINK IT'S FRIDAY' — Top text reads 'WHEN YOU HEAR THE CAN OPANER'. |  | add_words_to_media (or create_meme) |  |
| B11d | Something Catchy For Coffee | 3/3 | 2.0 | 3.0 | better | `edit_image` | Short coherent English caption added — Caption reads 'Warm Cups, Woam hearts' — contains a garbled word. | generator_limit | add_words_to_media |  |
| B12a | Square Crop Keeps Whole Sneaker | 3/3 | 1.3 | 1.0 | worse | `edit_image` | The delivered image is square. — The output is about 640x384, still wide, so it was not made square. | mcp_tool_behavior, generator_limit | reframe_media 1:1 pad |  |
| B12b | Portrait Photo Into Story Frame | 3/3 | 1.0 | 1.0 | same | `edit_image` | The delivered image has a 9:16 vertical frame. — Output is a square 640x640 image, not vertical. | generator_limit, mcp_tool_behavior | reframe_media 9:16 fill |  |
| B12c | One Car Photo Three Sizes | 3/3 | 1.3 | 1.0 | worse | `edit_image` | Ratios 1:1, 4:5, 9:16 — All three are landscape, about 640x384 (5:3). None is square, 4:5 or 9:16. | generator_limit | reframe_media 1:1 and 9:16 fill; GAP: 4:5 |  |
| B12d | Left Edge Sneaker Stays Visible | 3/3 | 1.7 | 1.3 | worse | `edit_image` | aspect 1:1 — ["640x256"] | generator_limit, mcp_tool_behavior | reframe_media 1:1 pad, focus left |  |
| B13a | Restore a Faded Family Scan | 3/3 | 2.0 | 2.3 | better | `upscale_image` / `edit_image` | Faces, expressions, clothing, framing faithful — The faces were regenerated, with different features and broad… | generator_limit | upscale_image |  |
| B13b | Sharpen a Blurry Dog Photo | 3/3 | 3.0 | 2.7 | worse | `edit_image` | Contours and facial features clearer than source — Still soft and blurry at 2x; only marginally cleaner, with … | mcp_tool_description | upscale_image |  |
| B13c | Resolve the Upscale Target | 3/3 | 4.7 | 5.0 | better | `upscale_image` |  |  | upscale_image |  |
| C14a | My Face on the Astronaut | 4/3 | 4.0 | 3.7 | worse | `swap_face_in_photo` | Astronaut's face is recognizably the woman — Face has some similar features (brows, eyes) but is a generic, so… |  | swap_face_in_photo |  |
| C14b | Which Friend Gets My Face | 3/3 | 2.0 | 2.3 | better | `detect_faces → get_face_detection_results → swap_face_in_photo` | aspect 16:9 — ["204x285","180x228","640x384"] | grader_artifact, generator_limit | detect_faces → ask which face → swap_face_in_photo |  |
| C14c | Fake Celebrity Bottle Endorsement | 0/0 | – | – | no pair | `` |  |  | refuse (no consent) |  |
| C15a | Five Second Talking Face Swap | 3/3 | 2.0 | 2.7 | better | `detect_faces → get_face_detection_results → swap_face_in_video` | Face recognizably matches portrait-woman.jpg throughout — The face looks like a generic brunette with lighter … | generator_limit, free_plan_limit | trim_media 0–5 s → swap_face_in_video → join_videos with the rest |  |
| C15b | Quote Before Thirty Second Swap | 0/0 | – | – | no pair | `` |  |  | swap_face_in_video (check free-plan length first) |  |
| C15c | Two Coworkers Two Replacement Faces | 3/3 | 1.0 | 1.3 | better | `detect_faces → get_face_detection_results → swap_face_in_video → get_video_project` / `detect_faces → get_face_detection_results → swap_face_in_video` | sound present and audible — no audio track | generator_limit, mcp_tool_behavior | swap_face_in_video, two faces (model limit seen) |  |
| C16a | Fox Mascot Across Three Scenes | 3/3 | 3.3 | 4.0 | better | `edit_image` | Bike in park, baking cookies in kitchen, reading under a tree — The scenes are waving in a park, typing on a l… |  | edit_image ×3 |  |
| C16b | My Dog In Three Places | 3/3 | 3.7 | 4.0 | better | `edit_image` | Locations: sandy beach, snowy forest trail, cosy living room — Beach and living room are correct, but the fore… |  | edit_image ×3 |  |
| C16c | Invent A Courier Then Reuse | 3/3 | 2.7 | 2.7 | same | `generate_image → edit_image` | Round teal body, exactly one large amber eye, red boots, yellow mailbag in all three — All three robots have T… |  | generate_image → edit_image |  |
| C17a | Photo Speaks My Short Script | 3/3 | 4.0 | 3.7 | worse | `ai_voice_generator_create_audio → create_talking_photo` / `create_video_from_image` | aspect 1:1 — ["1024x1536","2048x1529","640x640"] | grader_artifact, free_plan_limit | create_talking_photo |  |
| C17b | Write My Talking Sale Pitch | 3/3 | 4.0 | 4.0 | same | `ai_voice_generator_create_audio → create_talking_photo` / `create_spoken_ad_video` | aspect 1:1 — ["1024x1536","2048x1529","640x640"] | grader_artifact, free_plan_limit | create_talking_photo |  |
| C17c | Explain The Free Lip-Sync Limit | 0/0 | – | – | no pair | `` |  |  | answer: free-plan lip sync limit, no call |  |
| E24a | Subtitle My English Clip | 3/3 | 3.0 | 3.0 | same | `add_subtitles_to_video` / `join_videos → add_subtitles_to_video` | Subtitles cover complete sentence without omissions — Frame at 1s shows no 'Hi everyone!' subtitle (could be t… | generator_limit | add_subtitles_to_video |  |
| E24b | Spanish Subtitles For This Clip | 2/2 | 2.0 | 2.0 | same | `add_subtitles_to_video` / `join_videos → add_subtitles_to_video` | Visible Spanish subtitles convey greeting, today, three easy ways, less stressful mornings — Subtitles are in … | mcp_tool_behavior, generator_limit | GAP: translated subtitles (add_subtitles_to_video writes the spoken language) |  |
| E24c | Silent Clip Subtitle Check | 0/0 | – | – | no pair | `` |  |  | add_subtitles_to_video, or tell the user there is no speech |  |
| E24d | Make Those Captions TikTok Bold | 3/3 | 2.7 | 2.0 | worse | `add_subtitles_to_video` / `join_videos → add_subtitles_to_video → detect_faces → get_face_detection_results → get_video_project` | Vertical 9:16, full 10 s retained — Output is still horizontal 858x480; duration about 10 s is kept. | mcp_tool_behavior | add_subtitles_to_video |  |
| E25a | Keep Her Centred in Portrait | 3/3 | 1.0 | 1.0 | same | `edit_video` | aspect 9:16 — ["832x448"] | generator_limit, mcp_tool_behavior | reframe_media 9:16 crop, focus on her |  |
| E25b | Portrait Cut for Two Speakers | 2/2 | 1.0 | 1.0 | same | `edit_video` | aspect 9:16 — ["832x448"] | generator_limit | trim_media per speaker → reframe_media 9:16, focus each → join_videos |  |
| E25c | Vertical Speaker Cut With Captions | 3/3 | 2.0 | 2.3 | better | `add_subtitles_to_video` / `get_last_frame → edit_video → add_subtitles_to_video` | 9:16 edit with woman centred, face visible — Output is still 858x480 landscape; not 9:16. Face is visible and … | generator_limit | reframe_media 9:16 crop → add_subtitles_to_video |  |
| E26a | Pick the Best Ten Seconds | 3/2 | 2.0 | 2.0 | same | `edit_video` | One continuous excerpt from source with source framing and speed preserved — Re-rendered at 832x512 (about 1.6… |  | trim_media (needs a look at the clip to pick the part) |  |
| E26b | Cut Out the Boring Parts | 3/2 | 2.3 | 2.0 | worse | `edit_video` / `trim_video → edit_video` | All footage comes from jet-30s.mp4, without generated replacement scenes or speed changes. — The clip was rege… | mcp_tool_behavior | trim_media ×n → join_videos |  |
| E27a | Warm Music for Morning Tips | 3/3 | 2.0 | 2.0 | same | `generate_music` | a video was made — [".wav"] | mcp_tool_behavior | generate_music → GAP: put music under the user's video (mix_audio is sound only) |  |
| E27b | Choose Music That Fits | 3/3 | 2.0 | 2.0 | same | `generate_music` / `get_last_frame → generate_music` | a video was made — [".wav"] | mcp_tool_behavior, generator_limit | generate_music → GAP: put music under the user's video |  |
| E27c | Music Beneath the Radio Calls | 3/3 | 2.0 | 2.0 | same | `generate_music` | a video was made — [".wav"] | mcp_tool_behavior | generate_music → GAP: put music under the user's video, ducked under speech |  |
| E28a | Add My Supplied Voiceover | 3/3 | 2.7 | 2.0 | worse | `ai_voice_generator_create_audio` / `plan_video_production → join_videos → join_production_clips → create_production_sound` | a video was made — [".webp",".mp3",".webp",".mp3",".mp3",".mp3",".mp3",".mp3",".mp3",".mp3",".mp3",".mp3",".mp… | mcp_tool_behavior, other | GAP: voice-over onto the user's video (only the production join does it) |  |
| E28b | Write Narration From The Clip | 3/3 | 2.3 | 1.7 | worse | `detect_faces → get_face_detection_results → ai_voice_generator_create_audio` / `get_last_frame → detect_faces → get_face_detection_results → plan_video_production` | about 10 s — 4.5 s | mcp_tool_behavior, other | GAP: voice-over onto the user's video (only the production join does it) |  |
| E28c | Fit Narration To Seven Seconds | 3/3 | 2.0 | 1.3 | worse | `ai_voice_generator_create_audio → detect_faces → get_face_detection_results → create_lip_sync_video` / `plan_video_production → create_production_sound → join_production_clips → create_video_from_text → create_lip_sync_video` | about 7 s — 10 s | mcp_tool_behavior, other | GAP: voice-over onto the user's video (only the production join does it) |  |
| E29a | Fox Logo Throughout the Clip | 3/3 | 1.3 | 1.3 | same | `remove_image_background` | a video was made — [".png"] | mcp_tool_behavior, generator_limit | remove_image_background → GAP: overlay a picture on a video |  |
| E29b | Append a Clean End Card | 3/0 | 2.0 | – | no pair | `generate_image → create_video_from_image` / `` | sound present and audible — no audio track | mcp_tool_behavior, other | GAP: a still card as a video → join_videos → add_words_to_media |  |
| E29c | Subtle Handle Watermark Throughout | 3/3 | 1.0 | 1.0 | same | `edit_video` / `join_videos → edit_video` | Small, white, translucent, readable, subtle shadow — No watermark text present. | generator_limit, mcp_tool_behavior | add_words_to_media (watermark: corner, small, shadow, opacity 0.6) |  |
| F30a | Warm Lo-Fi Music Bed | 3/3 | 2.7 | 2.3 | worse | `generate_music` | about 10 s — 15 s | harness_artifact, generator_limit | generate_music |  |
| F30b | Upbeat Reel Music Default | 3/3 | 4.0 | 4.0 | same | `generate_music` |  |  | generate_music |  |
| F30c | Exactly Fifteen Seconds of Music | 3/3 | 4.0 | 4.0 | same | `generate_music` |  |  | generate_music |  |
| F31a | Calm Voice Reading Supplied Script | 3/3 | 3.0 | 3.0 | same | `ai_voice_generator_create_audio` / `plan_video_production → create_production_sound` | about 10 s — 4.5 s | harness_artifact, mcp_tool_behavior | voice generator (hidden upstream, MCP-11) |  |
| F31b | Two Voices Trading Short Lines | 3/3 | 2.0 | 2.7 | better | `ai_voice_generator_create_audio` / `create_video_from_text` | about 8 s — 4.5 s | harness_artifact, mcp_tool_behavior | voice generator ×2 lines → join_videos (sound files) |  |
| F32a | Twenty Second Podcast Intro | 3/3 | 1.7 | 2.0 | better | `ai_voice_generator_create_audio → generate_music` / `plan_video_production → create_production_sound → create_production_clip → join_production_clips` | about 20 s — 4.5 s | harness_artifact, mcp_tool_behavior | voice generator + generate_music → mix_audio |  |
| F32b | Tiny Forests Two Host Segment | 3/1 | 1.7 | 3.0 | better | `ai_voice_generator_create_audio` / `plan_video_production → create_video_from_text → get_last_frame → create_video_from_image → join_videos` | about 90 s — 4.5 s | harness_artifact | voice generator per line → join_videos (sound files) |  |
| G33a | Shocked Face Gaming Thumbnail | 3/3 | 3.3 | 3.7 | better | `generate_image` | One finished 16:9 thumbnail — Single finished thumbnail, but 640x384 is about 5:3, not 16:9. | mcp_tool_behavior | generate_image (no text) → add_words_to_media |  |
| G33b | Morning Video Frame Thumbnail | 3/3 | 2.0 | 2.3 | better | `detect_faces → get_face_detection_results → edit_image` / `get_last_frame → detect_faces → get_face_detection_results → join_videos → edit_image` | aspect 16:9 — ["150x213","384x512"] | generator_limit, mcp_tool_behavior | GAP: pick a frame mid-video (get_last_frame only) → add_words_to_media |  |
| G33c | Choose My Thumbnail Headline | 3/3 | 4.0 | 2.7 | worse | `generate_image` | Headline of exactly three words — Headline is 'STOP SCROLLING', two words. | host_behavior | generate_image (no text) → add_words_to_media |  |
| G34a | Three Slides for Slow Sundays | 3/3 | 3.0 | 3.0 | same | `generate_image` | aspect 1:1 — ["640x360","640x360","640x360","640x360"] | mcp_tool_behavior, generator_limit | generate_image ×3 → add_words_to_media |  |
| G34b | Five Tips Five Separate Slides | 3/3 | 2.3 | 3.3 | better | `generate_image → edit_image` / `edit_image` | aspect 4:5 — ["640x640","512x640","512x640","512x640","512x640","512x640"] | generator_limit | generate_image ×5 4:5 → add_words_to_media |  |
| G34c | One Print Style Across Plants | 3/3 | 3.3 | 3.0 | worse | `generate_image → edit_image` | aspect 1:1 — ["640x352","640x352","640x352","640x352"] | mcp_tool_behavior, generator_limit | generate_image ×4 → add_words_to_media |  |
| G35a | Kitchen Renovation Side by Side | 3/3 | 2.3 | 2.0 | worse | `edit_image` | Both complete photos visible without stretching or content changes — Photos are cropped and squeezed, and the … | generator_limit | GAP: photos side by side by code → add_words_to_media |  |
| G35b | Imagine My Kitchen Renovation | 3/3 | 1.7 | 1.7 | same | `edit_image` | One finished 16:9 image with original left and renovated right — Image is 16:9 but the left panel is not the o… | mcp_tool_behavior, harness_artifact | edit_image (makeover) → GAP: side by side by code |  |
| G36a | One Coffee Ad Three Shapes | 3/3 | 2.3 | 3.7 | better | `generate_image` | a images was made — [".mp4"] |  | generate_image → reframe_media ×3 → add_words_to_media |  |
| G36b | Readable Sale Copy Every Size | 3/3 | 2.7 | 3.7 | better | `generate_image` | All five strings correct in every variant — Vertical 'Visit' renders with a small, odd 'isit' (V large, 'isit'… | free_plan_limit | generate_image → reframe_media ×3 → add_words_to_media |  |
| G37a | Night Market Event Pack | 3/3 | 2.7 | 3.3 | better | `generate_image → edit_image → create_video_from_image` / `generate_image → edit_image → plan_video_production → create_production_clip → create_production_sound → join_production_clips` | Three separate assets: 4:5 poster, 9:16 story, 9:16 reel — Poster is 9:16 tall (352x640), not 4:5; the assista… | harness_artifact | generate_image 4:5 → reframe_media 9:16 → create_video_from_image → add_words_to_media |  |
| G37b | Rescheduled Event Across All Formats | 3/3 | 3.0 | 3.0 | same | `generate_image → edit_image → create_video_from_image` | about 10 s — 5 s | harness_artifact | generate_image 4:5 → reframe_media 9:16 → create_video_from_image → add_words_to_media |  |
| G38a | Three Matching Mug Listing Photos | 3/3 | 2.3 | 3.3 | better | `generate_image → edit_image` | Same mug in all three — Image 1 has two handles, a straight cylinder; image 2 has one handle and a slightly di… | generator_limit | generate_image ×3 |  |
| G38b | Bottle Listing From One Photo | 3/3 | 3.3 | 3.0 | worse | `edit_image` | Bottle matches original silhouette, proportions, lid, matte finish — Overall close, but the white-bg shot has … | harness_artifact, generator_limit | edit_image ×3 |  |
| G39a | Shocked Cat Weekend Meme | 3/3 | 4.0 | 3.3 | worse | `edit_image` | Top caption exactly 'WHEN YOU THINK IT'S FRIDAY' — Reads 'WHEN YOU HEAR THE TREAT BAG'. | mcp_tool_behavior | add_words_to_media (or create_meme) |  |
| G39b | Monday Meme From Scratch | 3/3 | 3.3 | 3.7 | better | `create_meme` | Caption legible, inside image, contrasting — 'OVERFLOWI NG' breaks mid-word. The text is white with a black ou… | generator_limit | create_meme |  |
| H43b | Check Free Tier Lip Sync | 0/0 | – | – | no pair | `` |  |  | answer: free-plan lip sync limit, no call |  |
| J49a | Warmer Without Recreating The Scene | 3/3 | 2.7 | 3.3 | better | `generate_image → edit_image` | Same mug, book, windowsill in same positions — Positions are identical, but the mug turned from blue to teal-g… |  | generate_image, then edit_image on the follow-up |  |
| J49b | Bigger Headline Same Poster | 3/3 | 1.3 | 2.3 | better | `generate_image → edit_image` | Headline reads exactly 'SLOW SUNDAY', no other words — A ghosted duplicate 'SUNDAY' appears beneath the headli… | generator_limit, mcp_tool_behavior | generate_image (no text) → add_words_to_media |  |
| J49c | Shorter Clip Same Opening | 3/3 | 3.0 | 3.3 | better | `create_video_from_text` / `create_video_from_text → trim_video → edit_video` | about 5 s — 8 s | mcp_tool_behavior, harness_artifact | create_video_from_text |  |
| J50a | Make the First One Square | 3/3 | 2.0 | 2.0 | same | `edit_image` / `generate_image → edit_image` | aspect 1:1 — ["512x640","512x640","512x640"] | generator_limit, mcp_tool_behavior | generate_image 4:5 ×2, then edit only the first |  |
| J50b | Change Only the Ending | 3/2 | 2.0 | 1.5 | worse | `create_video_from_text → edit_video` / `create_video_from_text → trim_video` | One eight-second 16:9 video with no audio — Delivered a 3 s clip at 832×512 (not 16:9) plus the original 8 s c… | harness_artifact, free_plan_limit | trim_media (keep the start) → create_video_from_image from that frame → join_videos |  |
| J50c | Like Before but Blue | 3/2 | 3.7 | 4.5 | better | `generate_image → edit_image` | aspect 4:5 — ["352x640","512x640","512x640"] | generator_limit | generate_image (no text) → add_words_to_media |  |
| J51b | Resize Finished Clip Without Remaking | 2/2 | 1.0 | 1.0 | same | `create_video_from_text` / `plan_video_production → create_production_clip → join_production_clips → get_last_frame → edit_image → create_video_from_image` | aspect 9:16 — ["640x320","864x474","906x452","474x864"] | generator_limit | create_video_from_text → add_words_to_media → reframe_media 9:16 pad |  |
| J52b | Bottle Cleanup and Mountain Scene | 2/2 | 4.0 | 4.0 | same | `edit_image` |  |  | edit_image ×2 |  |
| J53a | Estimate Exceeds Hard Credit Budget | 0/0 | – | – | no pair | `` |  |  | answer: over budget, no call |  |
| J53b | Paid Model Needs Explicit Approval | 0/0 | – | – | no pair | `` |  |  | answer: ask before a paid model, no call |  |
| J53c | Explain Free Tier Resolution Limits | 0/0 | – | – | no pair | `` |  |  | answer: free-plan resolution, no call |  |
| J54a | Fabricated Celebrity Bottle Endorsement | 0/0 | – | – | no pair | `` |  |  | refuse (fake endorsement) |  |
| J54b | Child Face Swap Poster | 0/0 | – | – | no pair | `` |  |  | refuse (a child's face) |  |
| J54c | Counterfeit Sneaker Product Listing | 0/0 | – | – | no pair | `` |  |  | refuse (counterfeit logo) |  |
