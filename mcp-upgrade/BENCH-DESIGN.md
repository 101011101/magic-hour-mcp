# Designing the benchmark: what was discussed and what was decided

Summary of the 4 November 2026 design conversation. The wide design (nine axes, eight intentions, core / extended / long rings for competitors) is in VIDEO-BENCH.md. This file records the narrower, denser set that runs first, and why.

## 1. Who the users are

Short-form creators (TikTok, Reels, Shorts), YouTubers and podcasters, small business owners (product, menu, event, "we're open"), founders and marketers (launch, explainer, ad variants), storytellers (fiction shorts, animatics, music visuals), educators and explainers, news and commentary, personal (birthday, memorial, pet, travel), real estate and venues, musicians.

Two axes sort all of them: **fiction against non-fiction**, and **story or news against product or company**. The cell predicts what they bring: non-fiction users bring references, fiction users bring requirements.

## 2. The three test families

1. **Reference-bound.** The user attaches something that must survive into the video: a product (shape, label text, colour), a person (generated portraits only), a place, a logo and brand colours, a style image, a previous clip to continue. Each is a different failure.
2. **Fiction with requirements.** No images, but hard constraints: a described character, beats in order, a line of dialogue or on-screen text, duration and aspect, a specified ending. The agent invents the rest and keeps the constraints.
3. **Multi-clip consistency.** Two to four shots that must read as one character, product or place, then joined. Cuts across the first two families.

The generic no-constraint request is one smoke item, not a family. Research-to-fill-gaps only matters for non-fiction without references; kept as one explainer item because it is the only place invented facts can be caught.

## 3. How each family is measured

- **Reference adherence.** Judge sees the reference beside first, middle and last frame grabs; answers per attribute (label text, colour, shape, hair, clothing) and finally "would the owner recognise it". Objective checks first and free: OCR on the label frame, dominant-colour distance, duration and aspect from ffprobe.
- **Requirements adherence.** Each requirement is one test line, as the bench items already do. Objective lines by tool (duration, aspect, OCR text present, audio track present or absent). Subjective lines to the judge with frames (beat order, ending, mood).
- **Consistency.** One grab per clip; the judge compares every pair, lists differences, answers same or not. Score is the fraction of pairs judged same. Join quality separately: uniform aspect and resolution, no black frames at seams, continuous audio level, total duration in tolerance.
- **Research fill.** Transcribe the voice-over, read the on-screen text; nothing contradicts the brief, nothing specific invented without basis. Pass or fail.

Needed beyond what exists: the pairwise consistency check and the OCR step. Everything else is the current harness and judge.

## 4. The principle: few tests, each testing many things

Every test stacks several capabilities, and every check is its own pass line, so a failure still says which thing broke.

### Proposal A: four pillars (about 1,250 credits per side)

| Item | Inputs | Ask | Tests | Expected |
|---|---|---|---|---|
| A1 product spot | perfume bottle photo, one brand hex, tagline, date | 15 s vertical ad, three shots: bottle alone, hand using it in a bathroom, end card with tagline and date in the brand colour; no voice, light music | label, shape and colour survive; same bottle across three shots; hand-and-product; overlay legibility; brand colour; music bed; join; 9:16; 15 s | one file, 15 s ±1, three cuts, OCR reads tagline and date in the last 3 s, bottle recognisable in all three, end-card colour near the hex, audio present with no speech |
| A2 invented character | text only: tall woman, silver bob, red raincoat, yellow boots; beats: waits at a bus stop in rain, the bus passes, she laughs and walks; end on her back; 12 s 16:9; words "walk anyway" at the end | as stated | constraints with no visual anchor; invented details stable across shots; beat order; ending; on-screen text; duration and aspect | all shots show bob, coat, boots; beats in order; last frame her back; OCR reads the phrase; 12 s; 16:9 |
| A3 continue this clip | the generated portrait and the 6 s clip already made from it | continue 6 s more, she turns and walks out of frame, keep her look, return one 12 s clip | last frame as start frame; identity across the seam; the action; join; nothing regenerated needlessly | 12 s single file; first 6 s identical to the input; no jump at the seam; same hair and clothing; she exits; cost of one 6 s generation |
| A4 branded explainer | logo image, two hexes, "We sell heat pumps. Explain how one works." | 15 s landscape explainer, voice-over, captions, our colours, end on the logo | research fill; voice generated; captions match voice; logo unaltered; palette; pacing | transcript has two or three correct facts and no invented claims; captions match transcript; logo in the last 2 s; palette near the hexes; 15 s |

### Proposal B: two monsters (about 800 credits each per side)

- **B1 full product spot.** Bottle photo, the portrait as presenter, brand hex, four shots, voice-over, captions, end card with date. 30 s, 9:16. A1 + A3 + A4 in one.
- **B2 full fiction short.** Two described characters, four shots, one line of dialogue, a title card, must loop back to frame one. 30 s, 16:9. A2 plus dialogue and loop.

Cheaper on count. Worse attribution: one early failure muddies later lines. At 30 s on the free tier the chunk logic is tested whether wanted or not.

### Proposal C: four pillars plus a probe

Proposal A plus one follow-up turn on A1: "Make the end card 2 seconds longer and change the date to the 19th. Keep everything else." Tests context retention, edit without regeneration, text replacement, duration arithmetic. Expected 17 s, shots one and two byte-identical, new date legible, near-zero cost. Only place the conversational layer gets measured.

## 5. The decision (4 November)

Run the monsters on the current MCP first, with a canary and the probe. Reasoning: stage 1 already showed the MCP matches on single generations and fails at assembly (trim, join, pad, narration, chunking). B is built from those steps, so it fails exactly where the lead's deliverable has to fix things. Four pillars would mostly re-confirm stage 1 one step at a time.

Order and stop rule, per side:

1. **Canary: A3, the continuation.** About 150 credits. Touches the weak spot (last frame, join) cheaply. Stop if the MCP cannot take the frame or join.
2. **B1, the product spot.** About 800. Score every line even if the final file is wrong.
3. **Probe on B1.** Near zero. Only if B1 produced a file.
4. **B2, the fiction short.** About 800. Skip if B1 broke before the join; B2 breaks at the same place.

Worst case 150 spent. Full case about 1,750 per side; both sides run so the lead sees the gap on the same items. Competitors wait until the MCP side has a number and the user has done the sign-ups.

Blocker: the ledger is at 111,536 against a 111,600 cap. About 3,500 for both sides means a cap of 115,500 with a little room. The cap moves only on the user's word.

## 6. Materials on hand

Perfume bottle photo (V02), generated portrait (S09) and its 6 s clip, two-reference pair (S10), the zoo story and clips, the barber seed clip. To make: a logo image with two hexes.

## 7. Rules carried over

Free tier only; no retries; one attempt per item per side; same driver model on both sides; judge sees frames and source material, never the side's name; every pass line recorded with evidence; per-generation model, type, time and credits recorded beside each item.
