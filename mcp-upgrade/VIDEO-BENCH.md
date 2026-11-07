# Video benchmark: cases, prompts, intentions, budget

Drafted 2026-11-04. Scope: video generation only, free tier against free tier, driven through each product's plugin by the same host model. Reuses the case bank already built (V2/bench/v1 groups D, H, I, J and the V4 stage items), so nothing here needs new materials.

## 1. What varies in a video request

Every real request is a point in this space. The benchmark should cover each axis at least twice, not every combination.

| Axis | Values seen in real asks |
|---|---|
| Input | text only · one user picture · several user pictures · a user's own clip (edit, not generation; out of scope here) |
| Output kind | single shot · animate a photo · product or service ad · reel from photos · multi-scene story · explainer · event promo · mood piece · loop · talking portrait · fact piece about a real thing |
| Shape | 16:9 · 9:16 · 1:1 |
| Length | 5 to 8 s (one clip) · 10 to 15 s (two or three clips) · 20 to 45 s (chained clips, the only place chunking matters) |
| Sound | silent · ambient · music bed · voice-over with given words · voice-over the agent writes |
| Text on screen | none · an exact title or end card · date and venue · captions per scene |
| Continuity | none · same character or product across scenes · last-frame chaining |
| Clarity | vague one-liner with an answer sheet · full brief · a follow-up tweak on a previous result |
| Outside knowledge | none · needs research (a real event, a real place, a URL) |

## 2. User intentions behind the asks

What the user actually wants, which the judge scores, is one of a short list:

1. **Make my picture move** without changing what is in it (face, product, framing preserved).
2. **Show my product well** for a feed or story, in the right shape, with my words on it.
3. **Tell a small story** that holds together across scenes: same character, same place, an ending.
4. **Explain or inform** with a voice that says accurate things, in a length people will watch.
5. **Set a mood** with no words: pacing, sound, loop that does not jump.
6. **Promote an event or business** with the date, name and place correct and readable.
7. **Fit a destination**: TikTok, Reels, YouTube, a website header, a phone wallpaper. Shape and length follow from this even when unsaid.
8. **Fix one thing** on the last result without redoing the rest.

Cross-cutting: be asked at most a couple of questions, only when the answer changes the output; get a finished file, not advice; not pay more than needed; not wait long.

## 3. The case set

Three rings. Every competitor runs the core. Those with a refill or a decent grant run the extended ring. Only sides with real budget run the long ring.

### Core ring (4 cases, about 28 s of video, fits a 125-credit Runway grant)

| Id | Kind | Vague ask (first turn) | Answer sheet | Full brief | Materials | Scores |
|---|---|---|---|---|---|---|
| C1 (= S09) | Talking portrait, picture in | "make a short clip of her" | motion: smiles, looks around, nothing dramatic · 6 s · silent | Animate this portrait for 6 seconds, keep her face exactly like her, silent | portrait-woman.jpg | face preserved, 6 s, silent, no destination assumed |
| C2 (= V01) | One shot from text, destination given | "a clip of waves at sunset for my meditation app" | TikTok · 10 s · gentle wave sound | 10 s vertical slow waves at sunset, empty beach, camera drift, natural sound, no music, no words | none | 9:16, 10 s, ambient audio present, no text |
| C3 (= V02) | Product picture to video, shape word | "animate this perfume bottle" | square · 6 s · silent | Animate the attached bottle 6 s, slow turn, square, silent | perfume-bottle.jpg | 1:1 output, bottle preserved, 6 s |
| C4 (= H44b-style) | Event promo with exact text | "an ad for our neon night" | 8 s · vertical · date 12 Sep 2026, The Foundry, Leeds · countdown open | 8 s 9:16 ad for Neon Night, start with a 3-2-1, end with date and venue readable | none | text exact and legible, 9:16, 8 s, no real brand |

### Extended ring (8 cases, about 90 s of video)

| Id | Kind | Vague ask | Key answers | Why it is here |
|---|---|---|---|---|
| E1 (= D20a) | Reel from five café photos, in order, music | "make a reel from these" | 10 s · vertical · relaxed music · order kept | several inputs, order, music, shape fitting of mixed photos |
| E2 (= H40a) | Product ad from a user photo | "a short ad for my bottle" | 15 s · 9:16 · studio look · mellow music · product name on the end card | product fidelity across 2 to 3 clips, end card text |
| E3 (= I47a) | Explainer with given voice-over | "an explainer of a seed sprouting with this voice-over: …" | 8 s · 16:9 · exact words | timed narration against picture, exact words |
| E4 (= I45a) | Two-character story, three scenes | "a short silent film about two people meeting in the rain" | 15 s · 16:9 · described characters | continuity of characters across cuts, the chunking seam |
| E5 (= D21a) | Seamless loop | "a calm lake loop for my website header" | 6 s · 16:9 · silent · must loop | loop test is measurable (first vs last frame) |
| E6 (= D23a) | Title card then footage | "a clip that opens on a title card saying exactly …" | 6 s · 16:9 · silent | exact text first, then motion; tests whether text is rendered or hallucinated |
| E7 (= H42b) | Local business promo, no photo | "a promo for Northside Gym" | 10 s · 9:16 · welcoming not hardcore · name on screen | taste judgement from a vague brief, fictional brand |
| E8 (= S10) | Two references in one clip | "a clip with my car at the Golden Gate" | 10 s · 16:9 · both pictures used | multi-reference handling, which most free models cannot do |

### Long ring (3 cases, 85 to 110 s of video, ours and the Magic Hour MCPs; Krea over several days)

| Id | Kind | Why |
|---|---|---|
| L1 (= V03) | 45 s zoo ad, three animals, voice-over, logo end card | the chunking, chaining, narration and end-card test; already judged on both Magic Hour sides |
| L2 (= R01) | 20 s reel about the latest big rocket launch | research step; facts in the voice-over must be true today |
| L3 (= P01, film part only) | 20 to 30 s perfume launch film ending on a logo | product continuity across scenes plus a designed end card; the still and poster parts are out of scope for the video bench |

### Conversation layer (on ours and the Magic Hour MCPs only)

Every case is run vague-first with the answer sheet, as in stage 1, so the questions asked are scored. Add two follow-up tweaks from group J on top of C4 and E2: "make it 2 seconds shorter" and "change the end card to say … instead". These measure whether the result can be edited without a full regeneration, which no competitor's free plugin is expected to manage.

## 4. What gets measured per case

- Intention checklist from the user's own words (yes / partly / no per item; "got what they wanted" = no "no" and ≥ 80).
- Questions asked: count, and whether each was needed (its answer changed the output).
- Finished file returned (yes / no / advice instead).
- Shape and length as asked, measured from the file, with the free-tier rounding noted.
- Sound as asked: present, absent, level, speech transcript where there is a voice-over.
- Text on screen: exact match, legible.
- Continuity on multi-clip cases: same subject across cuts (frame pairs at the seams).
- Cost in the product's credits and in dollars at its list price; our side in Magic Hour credits.
- Wall-clock from request to file.
- Quality, separately: a 1 to 5 look-and-sound score so a stronger free model does not hide a weaker agent.
- Verdict per case: clear win, comparable, could not do.

## 5. Budget

Magic Hour free-tier cost per ring (from stage-1 measurements: single clips 144 to 240 credits, 15 s two-clip pieces about 400, the zoo ad 1,090):

| Ring | Cases | Credits per side (approx.) |
|---|---|---|
| Core | 4 | 650 |
| Extended | 8 | 2,400 |
| Long | 3 | 2,700 |
| Follow-ups | 2 | 300 |
| **Total** | **17** | **about 6,000 per Magic Hour side** |

Sides on Magic Hour: ours (reference), the current MCP (baseline, partly already run), the upgraded MCP (the thing being proven). Stage-1 results already cover C1 to C3, E8 and L1 on ours and the baseline, so the new spend for those two sides is roughly 3,500 each; the upgraded MCP needs the full 6,000 each time it is re-proven, which is why the core ring exists as the cheap daily regression check and the full set is the weekly or pre-ship run.

Competitor coverage under their free allowances:

| Competitor | Can run | Notes |
|---|---|---|
| Krea | core in 2 days, extended over about a week, long ring maybe | 100 units a day, ~2 videos |
| Runway | core | 125 credits once, ~25 s of Gen-4 Turbo |
| Pika | core, if the 250 bonus lands | unverified at zero balance |
| OpenArt, Comfy Cloud | 2 to 5 core cases | small grants |
| fal.ai, Replicate, Hugging Face | core as raw-model baselines | no agent; the host model writes the prompt |
| HeyGen, Tavus, D-ID | C1 only | avatar products |
| Clip Studio, Kleo | L1 only | one story each |
| PixVerse | core, by hand in ChatGPT | later |

## 6. Rules carried over

- Free tier only on our side; the competitor's free allowance is its own cap.
- No retries. A failed step is a failed case.
- No synthetic video of identifiable real people; fictional brands, venues and names throughout (Ridgeview Zoo, Northside Gym, Noctis, Neon Night at The Foundry).
- Same host model and effort for every side. The same judge and checklist for every side.
- Record the allowance before and after each competitor run, since most grants are one-time.

## 7. Open choices

- Whether the core ring is 4 or 5 cases: adding E1 (reel from photos) to the core would test multi-input handling on every competitor but pushes Runway past its grant.
- Whether the raw-model hosts get a fixed prompt (fair to them, less realistic) or the host model's own prompt (realistic, noisier).
- Whether L3 keeps the still and poster deliverables as a separate campaign bench later.
