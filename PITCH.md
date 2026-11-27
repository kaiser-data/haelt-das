# Pitch: Hält das? (3 minutes, live demo)

**Setup before going on stage:** server running (`.venv/bin/uvicorn app.server:app --port 8787`), Chrome with the
extension loaded, two tabs open: (1) the toolbrothers 21V drill page, (2) http://127.0.0.1:8787. Pre-run one check
so the page is warm. Backup: the video `demo/out/haelt-das-m-calm-16x9.mp4`.

---

**0:00 Hook (story, no slides)**
"Last year I bought a cordless drill. 4.7 stars, almost two thousand reviews, forty euros. Six weeks later the chuck
broke. Then I found the same drill, same housing, same buttons, under five other brand names. The old names had
2.9 stars. The trick is simple: when the reviews go bad, the product comes back with a new name."

**0:25 What it is**
"Hält das? answers one question before you pay: will it last, and what does it really cost? It checks any listing
the way an experienced buyer would."

**0:35 Live demo 1: the browser extension (the wow)**
- Tab 1, the drill page. Point at the badge bottom right: "It appears on any product page."
- Click. Side panel opens, ticker runs. While it runs, narrate:
  "It reads the page's structured data, so the barcode, not a guess. It looks the product up on idealo:
  no idealo shop sells it. It tests the specs against physics: '21 volts' is an 18-volt pack. It searches the
  web in three languages for the same product under other names and for people whose drill broke."
- Badge turns colour: "AVOID / BUY ALTERNATIVE · €…/day". "And the verdict lands right on the shop page."

**1:20 The receipt from the future**
"This is the part I love. The sticker says forty euros. Spread over the life you can actually expect, the cheap
drill costs 73 cents a day. The Bosch costs two. Cheap is expensive."

**1:35 Why you can trust it (evidence tiers)**
"Every reason links to a source a human can open. Hard-to-fake evidence counts more than star ratings:
A is official data, independent tests, physics; C is the star average. And it never accuses on its own.
For clothing it checks green claims against official certificate registries and only repeats official lists."

**1:55 Nebius: uncertainty**
"Real evidence conflicts. This LG OLED has an official French durability index of 8.0, but users report
firmware failures after three weeks. A live Nebius Token Factory call decides, and here it says ASK, and names
the one fact that would change its mind. Every model call is in the log: four models, each with a job."

**2:15 Science bonus**
"We downloaded all 1,968 official French durability indexes. The overall score is exactly half repairability, half
reliability, and the two barely correlate: repairable is not reliable. That is why we check both."

**2:30 Why now / close**
"Fakespot shut down in 2025. Nothing replaced it, and fake reviews and rebrands are now free to produce.
Hält das? is the buyer who isn't fooled. Built today on idealo, Nebius Token Factory and Tavily, with every PR
checked by Norma.
Hält das? Know what lasts, before you pay."

---

## Likely judge questions
- **"How do you know it's the same product?"** Specs fingerprint plus image comparison by a vision model; we show
  matches as look-alikes with sources, never as proof.
- **"Isn't the life estimate made up?"** It is a range, pulled down by real failure reports and anchored on official
  indexes where they exist; the basis is printed on the receipt.
- **"What does idealo get?"** A new view on their data: cost per day of life instead of price today, and
  "not sold by any idealo shop" as a trust signal. Partner tier would add per-review fake detection in 6 markets.
- **"Defamation?"** We only repeat official listings and named sources, say "suspicious", never "fake", and treat
  country of origin as no signal at all.
- **"How do you keep agent-written code defensible?"** Two agents (Claude Code, Grok) on one repo, every change a PR
  checked by Norma before merge, Codex and Grok reviewing each other. The extension PR went 6 → 2 → 1 → 1 → 0 issues,
  each step a cause fixed, nothing deleted. 23 offline tests (`pytest -v`), one per demo listing.
