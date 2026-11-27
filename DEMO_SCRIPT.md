# Demo video script: Hält das? (about 2:15, you speak)

Problem → solution → four use cases → close. About 340 spoken words. Every number is what the recorded run shows on
screen (fact-checked against `samples/batch/*.json` by Codex). Say "Hält das" roughly as *helt dass*.

## Setup (5 minutes before recording)

1. Server running (`.venv/bin/uvicorn app.server:app --port 8787`).
2. Chrome, window about 1440 × 900, zoom 110 %, bookmarks bar hidden (⌘⇧B), Do Not Disturb on.
3. Open **http://127.0.0.1:8787/?replay**. The header label reads *"Replay of a recorded live run · sped up"*, and
   the first step of each run names the recording. Every event comes from a real live run (idealo, Nebius, Tavily)
   recorded today, played back in ~10 s instead of ~2 min. Keep it visible; you say it once.
4. Record: ⌘⇧5 → *Record Selected Portion* → *Options* → Microphone = your mic. Or record the screen silently first
   and speak over it in QuickTime/iMovie, which is easier to get right.
5. Rehearse once. While a check runs, let the screen breathe; after the verdict, scroll slowly to the receipt.

## Script

| Time | Screen (what you do) | Say |
|---|---|---|
| **0:00** PROBLEM | Empty app | "A cordless drill: four point seven stars, almost two thousand reviews, forty euros. Stars and prices don't tell you how long something lasts. Cheap products come back under new brand names, specs get inflated, and 'eco' is just a word. Mozilla's Fakespot used to check reviews. It shut down in 2025." |
| **0:20** SOLUTION | Point at the input field and the chips | "Hält das? means *will it last?* It checks a listing before you pay: a link, a screenshot, or the shop page you're on. Will it last, what does it cost per day, and is someone tricking me? What you see are live runs we recorded today, replayed faster." |
| **0:40** CASE 1 · the rebrand | Click **No-name „21V" drill · €39.99** | (while the steps tick) "The drill. idealo has no shop selling this exact product. '21 volts' is really an 18-volt pack. The same tool shows up under eight other brand names, with early failure reports." |
| **0:55** | Verdict appears, then scroll to the receipt | "Verdict: buy the alternative. And this is the receipt from the future. Under these life estimates, the drill costs about 35 cents a day. The Bosch from idealo, 79 euros: two cents a day. Cheap is expensive." |
| **1:10** CASE 2 · the impossible spec | Click **„2 TB" USB stick · €15.99** | "Two terabytes for sixteen euros is eight euros per terabyte. Real flash memory costs several times that. Sticks like this fake their size and put your files at risk. Avoid." |
| **1:25** CASE 3 · conflicting evidence | Click **LG OLED TV · €1,799**; when it's done, point at the left column (Nebius calls) | "The hard case: an eighteen-hundred-euro TV. The official French durability index, declared by LG, gives this model eight out of ten. But owners of LG's B-series report processor failures, though none for this exact model. A live Nebius call weighs both, says *ask*, and names the one fact that would decide: does this model use the same board as the older ones? Every model call is logged here." |
| **1:50** CASE 4 · greenwashing | Click **„Eco" fast-fashion T-shirt · €7.99** | "A T-shirt from a made-up demo brand: 'sustainable', 'environmentally friendly production', 'climate-neutral shipping', and no certificate listed. All three claims: unproven. Verdict: ask. It never accuses a brand; it only repeats official registries. And it prints the cost per wear: three cents." |
| **2:05** CLOSE | Verdict area, or the installed app window | "Built today on the idealo MCP, Nebius Token Factory and Tavily: a website, a browser extension, and an app you can install. Every change went through a pull request that Norma checked before merge, written by two people and two coding agents. When Norma found issues, we fixed the cause, not the finding, and Norma also runs inside the agent's loop. Hält das? Know what lasts, before you pay." |

## Notes

- **TrendWave is a fictional demo brand.** Never name a real brand in the greenwashing case.
- Costs per day and per wear rest on estimated lifetimes; the receipt prints the range and the basis. Say "estimates".
- Optional extra shot (live, not replay): the browser extension on the toolbrothers drill page. Badge → side panel →
  verdict on the badge. Cut the wait.
- Live on stage (20:00): `?replay` is the safe path; run one chip live if there's time (~1–2 min per check).
- Public link for judges: replay only (see the README / submission); live checks run on the laptop.
- Norma facts you can say (check before recording): every PR checked by the Norma GitHub App before merge; PR #3 went
  6 → 2 → 1 → 1 → 0 issues; a second human author (Silvia's PR) only if it is merged by the time you record;
  Norma MCP in the agent loop (live_check clean, 5 fixes registered, PR #11); policies set in the Norma workspace.
