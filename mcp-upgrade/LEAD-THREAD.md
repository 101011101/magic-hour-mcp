# The conversation with Runbo ("runs" on Slack), 3 November 2026

Verbatim, as pasted from Slack. "donuts" is us. Times are Slack's. Below the thread: the earlier feedback (31 October) that set up this one, and a line-by-line reading of what each demand means for the work.

## The thread

```
1.  runs — 12:03 PM
    150k
2.  add what models were used in the comparisons
3.  runs — 12:10 PM
    Do you think it makes more sense to build on top of the MCP so that users using our MCP or plugin and places like ChatGPT can get one hundred percent of the benefits of this video agent?
4.  runs — 11:07 PM
    @donuts i thought you were working 9-12 hour days
5.  donuts — 11:24 PM
    yes, that was yesterday
6.  today i had to finsih some other things
7.  but i do have the answers to your questions
8.  donuts — 11:24 PM
    in terms of this it is ltx-2.5 or minimax-h3 for video, qwen-image-2.1 or flux-2-klein for pictures, and qwen-edit for edits
9.  runs — 11:25 PM
    I'm not asking for it here.
10. donuts — 11:25 PM
    wait what
11. runs — 11:25 PM
    I said add what models were used in the comparisons.
12. donuts — 11:25 PM
    the gpt mcp used the same models
13. runs — 11:25 PM
    I mean in your link.
14. donuts — 11:26 PM
    like for the reasoning part of the agent loop?
15. gpt
16. runs — 11:26 PM
    I don't know how to make this more clear. You sent me this. I told you to add the models that are used. I need to know stuff like models, generation type.
17. time
18. donuts — 11:28 PM
    oh i see
19. ok ill add that rn
20. the average credits or so used is around 101 vs 104
21. runs — 11:28 PM
    Averages aren't what I'm looking for. Everything is at the video level.
22. donuts — 11:29 PM
    the video one is around 1090 vs 1080
23. runs — 11:29 PM
    I just want to see it in your link for each video, not here.
24. But that's not even the main question at hand. The main question at hand is the MCP one. This can be done the next time.
25. donuts — 11:30 PM
26. like this one?
27. donuts — 11:30 PM
    yes
28. i was gonna answer that
29. but
30. in general
31. runs — 11:30 PM
    Yes, for each generation I need the details next to it.
32. donuts — 11:30 PM
    i think it would make sense to build on top of the mcp
33. runs — 11:30 PM
    Then, why did we even go this direction in the first place? Didn't I mention the MCP earlier?
34. Okay, here's what I need you to do. I need it so users using the plug-in or MCP, whatever, in ChatGPT get all the benefits of this video agent that I specced out.
35. Tool calling, full video generation, us asking clarifying questions if and only if it's absolutely needed, and getting the full finished video regardless of the user's intent.
36. Work off the MCP repo.
37. donuts — 11:31 PM
    ok
38. donuts — 11:31 PM
    ok
39. to finish the thread above for the timing ball park, ill have claude add the rest of the details on the vercel thing
40. donuts — 11:33 PM
    when you say regardless of intent
41. like do you mean a garenteed output?
42. runs — 11:33 PM
    I just mean anything the user throws at you, film, ad, whatever.
43. It needs to do it. Needs to meet the intent.
44. I need this upgrade to the MCP fast and I need it to be high confidence and I need it to be on an ongoing basis as soon as you get significant improvements in. But I need you to be testing this rigorously to know if it's an actual improvement. So that means having a really strong benchmark. You can use any things you've already built for this. I just need to get in improvements fast. And not just benchmark against past generations. I need you to benchmark against all of the other plugins in this space.
45. donuts — 11:36 PM
    ok so to summarize ->
      * pivot to mcp upgrade
      * ensuring the update is worth updating
      * benchmark against other similar plugins
    General specs
      * works for all media (film, ad, etc) -> Meets user intent (user satisfaction first, less user retries the better)
      * can use whatever as long as in the free tier (+ conversational, tools etc)
    basically whatever the user wants to make it will make with its best ability within free tier and is better than similar plugins
46. runs — 11:38 PM
    Yes, but with a few exceptions. Most users will be free, but some users will be paid. Obviously, for those, we'll want a different treatment. And then I want incremental improvements, but they should all come with satisfactory proof that it is an improvement. And we want to make sure there's no regressions. So each time you test, don't just test one aspect, like full videos or anything. Test against your whole benchmark, which includes basic stuff like tool calling, stuff where just a simple tool call solves a problem, we want to do that. Not everything's going to be a full video. We should be smart also about the duration to provide users.
47. donuts — 11:39 PM
    when you say duration do you mean by like total response time to user or the video duration and such
48. runs — 11:39 PM
    Video duration, I just mean be smart about it.
49. donuts — 11:39 PM
    ok
50. runs — 11:40 PM
    I want an improvement by tomorrow afternoon that gets the MCP outputs from your last one first fully complete and then on par with yours, though it doesn't need to win each one. I want to be making improvements each day.
51. donuts — 11:42 PM
    i have a quiz at 5-7 i can get something around after that
52. runs — 11:44 PM
    ok
53. donuts — 11:44 PM
    for this comparions like benchmarks wise
54. against competitors
55. like whats the range of the competitors
56. id assume the best of the competitors would only be comparable to the premium tier of magic hour
57. runs — 11:45 PM
    If you're asking what competitors are there, that's for you to identify. I also don't know which ones are free. It's both free and available as plugins.
58. There might not actually be any free ones, but you should do a screen.
59. donuts — 11:45 PM
    like is the range a similar price range or
60. runs — 11:45 PM
    I'm saying free.
61. donuts — 11:45 PM
    ok
62. donuts — 11:50 PM
    Just to confirm our free tier vs. competitors' free tier
    and have ours better on completing whatever the user wants regardless of what is (diveristy + quality + keep the cost low on our end + better timing than competitors)
63. runs — 11:51 PM
    yes
```

## The earlier feedback that led here (31 October 2026)

> What you built is really narrow. It's missing at least these categories: Conversational, Non-film use cases, Tool calling, Multi-turn editing with retained context. I think u overindexed on one narrow slice of "film" like videos. But what if user just wants to face swap/character swap, or generate an ad, or generate an image. Conversation is also an important piece because sometimes the user will say like make X, but more information is needed to know exactly what they're looking for, so the agent actually needs to ask questions as well. Some of these pieces were in the original repo. Your examples have also been too narrow. I've only seen basically two examples, and just one video doesn't cut it. You also made the mistake of using paid models. The past generation cost of your videos was almost 10,000 credits, which is an entire month of a creator's usage, which just isn't feasible at all. So, you need a prototype on the free models only. Also, you should be creating a benchmark of test sets that you run every time. I haven't seen anything like that.

V4 was the answer to that message: free models only, a tool catalogue, a question bank, 20 test items with vague and full briefs, and the head-to-head against the MCP. The 3 November thread is the lead looking at that result and redirecting it into the MCP.

## Reading, line by line

| Lines | What was said | What it means for the work |
|---|---|---|
| 1 | "150k" | Unexplained. Not a credit figure we recognise (our whole ledger is 111,536). Ask. |
| 2, 11–31 | Add the models used, per generation, on the page | On the Vercel page, beside every item: model, generation type (text-to-video, image-to-video, edit, still), time, credits. Not averages, not in Slack. Still owed. |
| 3, 32–36 | Build on top of the MCP; work off the MCP repo | The pivot. V4 becomes the reference implementation to port from. |
| 34–35, 42–43 | Users in ChatGPT get the whole agent: tool calling, full video, questions only when needed, a finished file for any intent | The general spec. See MCP-UPGRADE-SPEC.md §3. |
| 44 | Fast, high confidence, ongoing, rigorous benchmark, against other plugins | Daily improvements, each with proof on the whole suite, plus a competitor screen. |
| 46 | Free first, paid later; no regressions; test the whole benchmark including simple tool calls; be smart about duration | Tier is a parameter. Regression rule: whole suite each run. Duration chosen for the ask, not maximal. |
| 50 | By tomorrow afternoon: MCP outputs from the last comparison fully complete, then on par with ours | The first deliverable, due the afternoon of 4 November 2026. Complete first, par second. |
| 57–60 | Competitors are for us to identify; free and available as plugins; there may be none | COMPETITOR-SCREEN.md. Free tier against free tier. |
| 62–63 | Confirmed target: our free tier vs theirs, ours better on completing whatever the user wants: diversity, quality, low cost, better timing | The one-line target. |

## Still unanswered by the lead

- What "150k" refers to.
- Which host matters first: ChatGPT, Claude, or any MCP client.
- Whether card-on-file trials count as "free" for the competitor comparison.
