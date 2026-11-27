# Demo video script: Hält das? (about 2:20, you speak)

Problem → solution → four use cases → close. Every number below is what the recorded run shows on screen.
Say "Hält das" roughly as *helt dass*.

## Setup (5 minutes before recording)

1. Server running (`.venv/bin/uvicorn app.server:app --port 8787`).
2. Chrome, window about 1440 × 900, zoom 110 %, bookmarks bar hidden (⌘⇧B), Do Not Disturb on.
3. Open **http://127.0.0.1:8787/?replay**. The grey label top right reads *"Replay of a recorded live run · sped up"*:
   every event comes from a real live run (idealo, Nebius, Tavily) recorded today, played back in ~10 s instead of
   ~2 min. Keep the label visible and say it once (below).
4. Record: ⌘⇧5 → *Record Selected Portion* → *Options* → Microphone = your mic. Or record the screen silently first
   and speak over it in QuickTime/iMovie, which is easier to get right.
5. Rehearse once. While a check runs, let the screen breathe; after the verdict, scroll slowly to the receipt.

## Script

| Time | Screen (what you do) | Say |
|---|---|---|
| **0:00** PROBLEM | Empty app, or a shop page with a 4.7★ drill | "A cordless drill. Four point seven stars, almost two thousand reviews, forty euros. It breaks after a few weeks, and then you find the same drill under eight other brand names. That's the trick: when the reviews go bad, the product comes back with a new name. Stars and prices don't tell you what something really costs. Fakespot shut down in 2025, and nothing replaced it." |
| **0:25** SOLUTION | Point at the input field and the chips | "Hält das? means *will it last?* It checks any listing before you pay: a link, a screenshot, the shop page you're on, or a share from your phone. Three questions: will it last, what does it really cost per day, and is someone trying to trick me. Every reason links to a source you can open. For this video I'm replaying runs we recorded live today, sped up." |
| **0:45** CASE 1 · the rebrand | Click **No-name „21V" drill · €39.99** | (while the steps tick) "It reads the listing and asks idealo: no idealo shop sells this drill, which is a signal in itself. It checks the specs against physics: '21 volts' is really an 18-volt pack. It searches in German, English and French: the same drill under eight brand names, and owners whose chuck failed after four weeks." |
| **1:05** | Verdict appears, then scroll to the receipt | "Verdict: buy the alternative. And this is the receipt from the future: forty euros, but spread over the life you can actually expect, about 35 cents a day. The Bosch from idealo costs 79 euros, two cents a day. Cheap is expensive." |
| **1:20** CASE 2 · the impossible spec | Click **„2 TB" USB stick · €15.99** | "Some listings simply lie. Two terabytes for sixteen euros is eight euros per terabyte. Real flash memory costs several times that. These sticks report a size they don't have, and your files are gone once it's full. Avoid." |
| **1:35** CASE 3 · conflicting evidence | Click **LG OLED TV · €1,799**; when it's done, point at the left column (Nebius calls) | "The hard case: an eighteen-hundred-euro TV. The official French durability index gives this exact model eight out of ten. But owners of this TV series report processor failures, some after six weeks. A live Nebius call weighs both, and it doesn't guess. It says *ask*, and names the one fact that would decide: does the 2026 model use the same board as the older ones that failed? Every model call is logged here: model, time, tokens." |
| **2:00** CASE 4 · greenwashing | Click **„Eco" fast-fashion T-shirt · €7.99** | "Clothing. 'Sustainable', 'climate-neutral shipping', and no certificate anywhere. All three claims are flagged as unproven; under new EU rules, vague green claims need proof. It never accuses a brand on its own: it only repeats official registries and named sources. And for clothes it prints the cost per wear: three cents." |
| **2:20** CLOSE | Verdict area, or the installed app window | "Built today on the idealo MCP, Nebius Token Factory and Tavily. It runs as a website, a browser extension, and an app you can install. Two coding agents, and every pull request checked by Norma before merge. Hält das? Know what lasts, before you pay." |

## Notes

- **TrendWave is a fictional demo brand.** Never name a real brand in the greenwashing case.
- If the drill story is your own experience, say "Last year I bought…". If not, keep it as written. The video must
  not claim a personal story that didn't happen.
- Optional extra shot (live, not replay): the browser extension on the toolbrothers drill page. Badge → side panel →
  verdict on the badge. Cut the wait.
- Live on stage (20:00): use `?replay` as the safe path and run one chip live if there's time (~1–2 min per check).
