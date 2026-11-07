# Competitor screen: free tier, installable as a plugin

Screened 2026-11-04 from live web pages (official pricing and docs first, third-party only where the official page would not render, and flagged). Nothing here was tested on a live account yet.

**Definition of free used here (generous):** anything a user can generate with and not pay for. That includes standing free plans, daily or weekly refills, one-time signup credits, promo credits, bonus credits for connecting a plugin, and free trials. Trials are included but treated with more suspicion, and a trial that needs a card on file is listed separately because a forgotten trial does cost money.

**Definition of installable:** an official MCP server or an official ChatGPT app. Community wrappers around a REST API do not count, since a ChatGPT user cannot install them.

## Verdict in one paragraph

About 60 products ship an official MCP or ChatGPT app. Read generously, around 25 of them let a free user generate something. The useful opponents split into three kinds. **Refills** you can run every day: Krea (100 units a day, LTX video), PixVerse (30 credits a day through its ChatGPT app), HeyGen (3 avatar videos a month), Tavus (5 minutes a month), Magnific (about 20 images a day, no video), Hugging Face (free inference, LTX and Qwen-Image). **One-time grants** that cover a handful of cases: Runway 125 credits, Pika 250 bonus credits, json2video 600 credits, Shotstack 10 minutes, Creatomate 50 credits, fal.ai promo credits, Replicate's free runs, OpenArt, Comfy Cloud's 5 runs, D-ID's 14-day trial. **Claims to verify**: Vivideo says free unlimited 1080p video, ImagineArt reportedly 100 credits a day. The big names mostly fail on the plugin route even where the website is free: Higgsfield, Kling, Hailuo, Vidu and Hedra give free generations on the web but charge for the MCP; Luma, LTX Studio, Leonardo, Synthesia and Google Flow have free allowances but no official plugin.

## Tier A: free refills (can run cases every day or every month)

| Product | Plugin | Free allowance | Card | What the suite can use it for |
|---|---|---|---|---|
| **Krea** | Official remote MCP `api.krea.ai/mcp` (OAuth); Claude Code, Codex, Cursor documented; ChatGPT unconfirmed | 100 compute units/day, refilled daily; about 2 LTX-2 videos and several images a day; commercial use included per pricing page | No | Full suite over several days. Same LTX family as our free tier, so the agent layer is the difference. **First opponent.** |
| **PixVerse** | Official ChatGPT app "PixVerse Plugin for OpenAI" (also Codex); local MCP uses paid API credits | Consumer free: 60 credits + 30/day, 540p, watermark | Not stated | Video cases via the ChatGPT app, a few per day. The MCP route is paid, so this one is app-only. |
| **HeyGen** | Official remote MCP and ChatGPT app | 3 watermarked videos/month, 1 min each, no free API credits | No | Talking-head cases only (S09-style portrait animation). MCP plan gating not stated. |
| **Tavus** | Official MCP and ChatGPT app | 5 min video generation/month, API included | No | Avatar cases; the ChatGPT app does not expose rendered video, MCP may. |
| **Magnific (ex-Freepik)** | Official MCP `mcp.magnific.com`, listed in the ChatGPT directory | About 20 in-house image generations/day; no video on free | Not stated | Picture cases only. |
| **Hugging Face** | Official MCP `huggingface.co/mcp` (custom connector) | Free account inference credits; LTX Video, Qwen-Image, FLUX Kontext via Spaces | No | Raw-model baseline on the same open models we use; queues vary. |
| **VEED** | Official MCP (endpoint not public) and ChatGPT app (third-party listing) | 50 AI credits/month, about 6 s of Fabric video, watermark | No | One short talking-video case a month, if the credits flow through the MCP (unstated). |
| **InVideo** | Official MCP and ChatGPT app, on every plan | 10 AI minutes/week, 4 watermarked exports/week, no generative models (stock footage script-to-video) | Not stated | Produces a video from a brief using stock. Fair opponent for "make me an ad" judged on intent, not on generation. |
| **Visla** | Official ChatGPT app | Free plan with base monthly credits, watermark, 1080p | Not stated | Narrated-video-from-text cases via the app. |
| **Canva** | ChatGPT app open to free users; AI Connector listed for Pro and up on canva.com | Free plan shares a monthly AI allowance; third parties say about 5 lifetime short clips | No | Picture and poster cases through the ChatGPT app; video not exposed over MCP. |

## Tier B: one-time grants (cover a few cases each)

| Product | Plugin | Grant | Card | Fit |
|---|---|---|---|---|
| **Runway** | Official remote MCP `mcp.runwayml.com/mcp` and ChatGPT app | 125 credits, never expire, limited models, watermark; about 25 s of Gen-4 Turbo | Not stated | 2 to 3 video cases. Whether free credits are spendable via MCP is unconfirmed. **Second opponent.** |
| **Pika** | Official MCP `mcp.pika.art/mcp` and ChatGPT plugin (2026-10-16) | 0 monthly credits; 250 bonus credits after the first plugin generation; all models | Not stated | If the first generation runs at zero balance, about 4 clips. One sign-up settles it. |
| **json2video** | Official MCP `mcp.json2video.com/mcp` | 600 credits, watermark, movies up to 60 s, non-commercial | No | Edit and assembly cases: join, trim, title, music. Built-in voices and images, no frontier video model. |
| **Shotstack** | Official MCP `mcp.shotstack.io` | 10 credits (10 min of render), 30-day expiry; AI generation (Seedance, Wan 3.0, Gemini Omni Flash) charges those credits | No | Edit cases plus a couple of generated clips. |
| **Creatomate** | Official MCP `api.creatomate.com/mcp` (ChatGPT dev mode, Claude) | 50 trial credits, full-featured | No | Template rendering; edit cases. |
| **fal.ai** | Official MCP `mcp.fal.ai` (OAuth), ChatGPT and Claude listed | Signup promo credits, amount unstated officially (third parties $1 to $20), expire | Unknown | Raw-model baseline with 1,000 models; a few cases while promo lasts. |
| **Replicate** | Official MCP `mcp.replicate.com/sse` | Limited free runs on a "try for free" set (minimax/video-01, flux, imagen); 1 req/s without a card | No | Raw-model baseline; a handful of cases. |
| **OpenArt** | Official MCP `mcp.openart.ai/mcp` | Small free balance (unstated); Seedance 2.5, Kling 4.0, Nano Banana | Not stated | One or two cases. |
| **Comfy Cloud** | Official MCP `cloud.comfy.org/mcp` | 5 free runs | Not stated | Five cases at most. |
| **D-ID** | Official MCP `docs.d-id.com/mcp` (direct API access); no ChatGPT app | 14-day trial, 3 minutes shared across video and API, heavy watermark | Not stated (third parties: no) | Talking-photo cases during the trial. Trial, so lower confidence. |
| **Clip Studio (clipstudio.ai)** | Official MCP | One free story part for new accounts | Not stated | One narrated-film case. |
| **Kleo** | Official MCP | 5 credits on connect | No | One short narrated piece. One-person project. |

## Tier C: free on the website, paid through the plugin (fails the plugin test, kept for reference)

| Product | Website free | Why it fails |
|---|---|---|
| Higgsfield | Free web generations (third parties: a few credits a day), 24 h "unlimited" MCP trial needed a card | Help centre: MCP requires an active paid subscription. Card-gated trial, so skeptical. Paid-tier reference later. |
| Kling | 66 free credits/day on the web | MCP and CLI consume paid credits only. |
| Hailuo / MiniMax | Trial of 300 credits for 3 days, for subscribers | MCP is local and needs a funded API key. |
| Vidu | Trial credits plus daily login credits on the web | MCP needs separately purchased API credits. |
| Hedra | Third parties claim 100 to 400 free credits | MCP and CLI require a subscription; plans page behind login. |
| Pollo AI | 20 free credits on the web | MCP publisher unverified; API credits are separate paid packs. |
| OpusClip | 1 free clip/day | MCP connector needs Pro. |
| Revid.ai | Free credits, no card | Rendering needs a paid plan. |
| VideoGen | Free plan, watermarked | API and MCP listed under Pro. Could still work free; unverified. |
| Akool, bitHuman | Free plans exist | API access needs Pro Max (Akool); free API access ended 2026-10-12 (bitHuman). |
| Leonardo | 150 tokens/day | No official MCP. |
| LTX Studio | 800 one-time credits | No official MCP. |
| Luma | Free plan referenced in licensing, not on pricing | No official MCP. |
| Google Veo / Flow | Flow: 50 credits/day, Veo 3.1 Lite and Fast | No official MCP or ChatGPT app. Strongest free allowance with no plugin. |
| Synthesia | 500 credits/month, 10 min, no download on free | No official MCP. |
| Captions | 60 to 200 lifetime credits, no generation on free | Official MCP page broken; generation excluded from free. |
| Pictory | 14-day trial, 720p, watermark | MCP credentials only through a paid API agreement. |
| Zapier | 100 tasks/month | No video generator of its own. |

## Tier D: paid only or no generation through the plugin

Black Forest Labs, Picsart, getimg, Everygen, varg, WaveSpeed, Motion, Artlist, Figma Weave, Photoroom, Recraft (API billed separately), ReelsFarm, MakeAIVideo (7-day trial, card required), Adobe Firefly (MCP has no generation), OpenAI Sora (discontinued 2026).

## Claims to verify with a sign-up

- **Vivideo**: own site claims "free forever, unlimited AI video, 1080p, no watermark" with an official MCP in the registry. If true it is the strongest free opponent in the list. Verify before believing.
- **ImagineArt**: one third-party test reports 100 free credits/day through the official MCP; the pricing page lists only a $5 plan.
- **Ideogram**: free plan replaced by pay-as-you-go around 2026-10-19, FAQ still mentions weekly free credits for Google, Apple and Microsoft sign-ins. Images only. Official MCP, ChatGPT Plus and Pro connectors.
- **Krikey, VideoZero, Genra, AI Video Maker (InfoseekAI)**: ChatGPT apps seen in directories, pricing not checked.

## Our own row, for the same columns

| | Magic Hour |
|---|---|
| Plugin | Hosted MCP `mcp.magichour.ai` (OAuth, asks for the API key); docs MCP at `docs.magichour.ai/mcp`. No ChatGPT directory listing found; connects as a custom connector. |
| Free tier | Free plan exists. Pricing page does not state the allowance; a docs example uses 400 starter credits plus 100 per day. Free-flagged models at 480p video and 640px stills (ltx-2.5, minimax-h3, qwen-image-2.1, flux-2-klein, qwen-edit, krea-2, flux-schnell, z-image-turbo). Watermark and commercial use tied to a credit-pack purchase per the billing docs. |
| Card required | Not stated. |
| Cheapest paid | Creator, $19/month or $12 annual, 12,000 credits. |

Our 20-case suite cost about 2,000 credits on Magic Hour's free models (101 per case on average, 1,090 for the zoo ad). Read each competitor's allowance against that: Krea covers the suite over several days, Runway covers two or three cases, the one-time grants cover a handful each.

## What this means for the benchmark

1. **First opponents:** Krea (refill, same model family) and Runway (one-time, the best-known name with a ChatGPT app).
2. **Second wave:** PixVerse and Pika through ChatGPT apps, HeyGen for the portrait cases, json2video and Shotstack for the edit cases, Replicate, fal.ai and Hugging Face as raw-model baselines with no agent layer.
3. **Verify the two "free unlimited" claims** (Vivideo, ImagineArt) with one account each before planning around them.
4. **Paid reference, later:** Higgsfield and Kling, when the paid-user treatment is specified.
5. **Report Tier C and D on the page** with the reason, since the lead expected the free column to be nearly empty and this is the evidence that it is not empty but shallow.
6. **Budget the allowances.** Several grants are one-time, so decide the case order per competitor before the first run and log the balance before and after.

## What a person has to do

- Sign up for each Tier A and B product you want, and connect each MCP or ChatGPT app once. I cannot create accounts or sign in.
- Decide per product whether the harness drives the MCP directly (reproducible, same as the Magic Hour run) or the ChatGPT app (what a ChatGPT user actually sees; PixVerse and Visla are app-only).
- Avoid any trial that asks for a card unless you set a reminder to cancel.

## Method and caveats

- Sources: official pricing and docs pages where they rendered; the MCP registry, PulseMCP, Glama, mcp.so, mcp.film, the Claude connectors directory and the ChatGPT app directory for discovery; third-party pricing checks only where the official page returned 403 or was JavaScript-only (Higgsfield, Kling, Hailuo, Vidu, LTX, Ideogram, PixVerse, Magnific, Canva help, HeyGen MCP overview).
- Card-required status is unstated on almost every official page; the sign-up form is the only reliable check.
- Pricing moved during 2026 (Pika zeroed its free credits in September, Ideogram in October, HeyGen cut free API credits in February, Sora shut down, Freepik became Magnific in April). Re-check before quoting numbers externally.

## Video generation only (added 2026-11-04, after the decision to focus on video)

Filter: the free plugin route must produce AI-generated video from text or a picture. Stock-footage assembly (InVideo, Visla, Creatomate), image-only free tiers (Magnific, Ideogram) and edit-only servers drop out. Avatar and talking-photo generators are kept but marked, since only the portrait cases use them.

| Product | Kind | Free video allowance | Harness route | Verdict |
|---|---|---|---|---|
| **Krea** | General T2V / I2V (LTX-2) | ~2 videos/day, refills | OAuth token once | Run. First opponent. |
| **Runway** | General (Gen-4 Turbo) | 125 credits once, ~25 s of video | OAuth token once | Run. 2 to 3 cases. |
| **Pika** | General (Pika 2.5 + third-party models) | 250 bonus credits after first plugin generation | OAuth token once | Run if the first generation works at zero balance. |
| **OpenArt** | General (Seedance 2.5, Kling 4.0) | Small balance, unstated | OAuth token once | Run, expect 1 to 2 cases. |
| **Comfy Cloud** | General via workflows | 5 runs | OAuth token once | Run, 5 cases at most. |
| **Shotstack** | Assembly + AI clips (Seedance, Wan 3.0, Gemini Omni Flash) | 10 credits, 30 days | API key now | Run, a few clips plus the edit cases. |
| **fal.ai** | Raw model host | Promo credits, amount unstated | API key now | Run as a no-agent baseline. |
| **Replicate** | Raw model host (minimax/video-01 free) | Limited free runs | API token, probably | Run as a no-agent baseline. |
| **Hugging Face** | Raw model host (LTX Video Space) | Free inference, queued | HF token now | Run as a no-agent baseline on our own model family. |
| **Clip Studio (clipstudio.ai)** | Narrated multi-shot film | One story part | OAuth token once | One case, the zoo ad. |
| **Kleo** | Narrated animatic (Seedance 2.5) | 5 credits | OAuth token once | One case. |
| **HeyGen** | Avatar | 3 videos/month, 1 min | OAuth token once | Portrait cases only. |
| **Tavus** | Avatar / digital human | 5 min/month | API key now | Portrait cases only. |
| **D-ID** | Talking photo | 14-day trial, 3 min | API key | Portrait cases only, trial. |
| **VEED** | Talking video (Fabric) | ~6 s/month | Unclear | Too small; skip. |
| **PixVerse** | General T2V / I2V | 30/day (third parties say 60) + signup grant | ChatGPT app only, manual | Free and real, but hand-typed. Later. |
| **Krikey** | 3D cartoon animation | 20 credits once | ChatGPT app only, manual | Niche; skip. |
| **Canva** | Magic Media clips, 4 s silent | ~5 lifetime (third party) | ChatGPT app only, manual | Too small; skip. |
| **Vivideo** | General, claims unlimited | Claimed unlimited 1080p | Unknown until sign-up | Verify first. |
| **ImagineArt** | General | Claimed 100 credits/day | OAuth token once | Verify first. |
| **json2video** | Assembly with built-in AI images and voices | 600 credits | API key now | Only if its AI video elements count; verify. |

Out on the plugin test despite free web video: Higgsfield, Kling, Hailuo, Vidu, Hedra, Pollo (paid through the MCP); Google Flow, LTX Studio, Luma (no official plugin).

Count: **9 general video generators** can be run by the harness on a free account (Krea, Runway, Pika, OpenArt, Comfy Cloud, Shotstack, fal.ai, Replicate, Hugging Face), of which four are agent-style products and the rest are raw model hosts or assembly engines; **3 avatar generators** for the portrait cases (HeyGen, Tavus, D-ID); **2 one-case narrated-film tools** (Clip Studio, Kleo); **3 to verify** (Vivideo, ImagineArt, json2video); **1 free general generator that is manual only** (PixVerse).

## Open-model routes (recorded 2026-11-04, on hold)

- Decision: the benchmark covers free routes only for now. The open-model comparison is on hold.
- Open-model group: Krea (LTX-2), Hugging Face (Wan 2.2, CogVideoX-5B, LTX-Video), fal.ai (LTX-2.3). Our free tier uses the same family (`ltx-2.5`).
- Purpose: compare the same model class. The models are near equal, so the agent layer is the difference.
- Hugging Face
  - MCP: `https://huggingface.co/mcp`. Without sign-in: 4 search tools, no generation.
  - Generation: sign in, then add video Spaces in the MCP settings. Each Space becomes one tool.
  - Models: open models published as MCP Spaces only. Closed models are not available.
  - Quota (ZeroGPU): 5 GPU-minutes per day on a free account, 2 without an account, 40 on PRO. Reset: 24 hours after first use.
  - Per call: 60 seconds of GPU by default. Estimate: 3 to 5 clips per day.
  - Risks: community Spaces can be offline or queued. Clips are a few seconds long. No agent layer.
- Krea free plan: 100 units per day. LTX-2 19B, 5 seconds at 512p = 34 units, so 2 clips per day. Clip lengths: 5, 8, 10 seconds. Aspect: 16:9 or 9:16.
- fal.ai: no free plan. LTX-2.3 fast = $0.06 per second.
- Not verified: Krea unit cost (source: Krea blog). Hugging Face cap of 3 runs per day (source: forum post).
