# Submission: Hält das? (Agentic Hackathon Berlin, 27 Nov 2026)

**Repo:** https://github.com/kaiser-data/haelt-das
**Demo video:** `demo/out/haelt-das-m-calm-16x9.mp4` (63 s) · feed cut `demo/out/haelt-das-m-calm-4x5.mp4`
**Track:** Agentic Commerce · **Challenges entered:** idealo, Nebius, Norma

## One-liner
An agent that tells you what a product really costs per day, how long it will last, and whether someone is trying to
trick you, before you pay.

## Short description (for the form)
I bought a cordless drill with 4.7 stars; six weeks later it broke, and I found the same drill under other names.
Hält das? checks any listing (link, text, screenshot, or the page you are on via a browser side panel) the way an
experienced buyer would. It looks the product up on idealo, tests the specs against physics ("21V" is an 18V pack,
50,000 mAh cannot weigh 180 g, 2 TB for €16 is a fake-capacity drive), searches for the same product under other
brand names, collects failure reports in German, English and French, reads the official French durability index
for TVs and washing machines, checks green claims and certificates for clothing, and prints a *receipt from the
future*: the price per day (or per wear) over the life you can actually expect. A live Nebius Token Factory call
decides BUY, AVOID, BUY_ALTERNATIVE or ASK, with every reason tiered (A hard to fake, C cheap signal) and linked to a
source a human can check.

## idealo: Most Creative Use of the MCP
- **Unexpected:** idealo becomes the *reality check*: "not sold by any idealo shop" is itself a signal, and idealo's
  branded equivalents are the yardstick for cost per day. The comparison is per day of life, not sticker price.
- **Data that drives the result:** catalogue search (exact match and branded equivalents across the category),
  structured specs (spec plausibility and equivalence), offers and shop counts (established vs. throwaway),
  30-day price trend, consumable prices for running costs.
- **Meaningful:** cheap clones and rebrand cycles cost buyers money and create e-waste. Fakespot (Mozilla) shut down
  in July 2025; nothing replaced it.
- Tested on 10 products: fake-capacity USB stick → AVOID; "blood sugar" smartwatch → AVOID (FDA warning);
  €49 printer → AVOID (ink); no-name 21V drill → buy Bosch instead; Galaxy A56 → BUY.

## Nebius: model and use note (required)
Models called on Token Factory (names as listed there):
- `Qwen/Qwen3-30B-A3B-Instruct-2507`: read listing, rebrand names, classify failure reports, lifetime/consumables estimate, certificate check
- `google/gemma-3-27b-it`: read screenshots, image-vs-image clone check (vision)
- `Qwen/Qwen3-Embedding-8B`: de-duplicate failure reports across languages
- **`deepseek-ai/DeepSeek-V4-Pro-0813`: the decision.** `app/pipeline.py → verdict()` sends all evidence and
  returns `{verdict, headline, confidence, reasons[{text, tier, url}], better_alternative, missing_fact}`; the UI acts
  on that JSON. Fallback: `deepseek-ai/DeepSeek-V4.1-Flash-1017`.

Every call goes through `app/llm.py` and appears in the UI's call log (model, latency, tokens).
- **Routine case:** Samsung Galaxy A56 → BUY ("solid midrange with strong independent test record").
- **Incomplete / conflicting case:** LG OLED77B65LA → ASK: the official French durability index says 8.0/10, while
  user reports describe firmware and overheating failures after 3–6 weeks; the agent names what would decide it.
  Also: Bosch PSR 18 LI-2 → ASK (listing price and idealo model disagree; asks whether the kit includes two batteries).

## Norma: note (fill in after the checks)
- **Workspace:** <team name>
- **Policy:** "Every LLM call goes through `app/llm.py`" (no direct HTTP calls to model APIs elsewhere), so the call
  log the Nebius judges see is complete by construction. Plus: no hardcoded API keys; `httpx` only.
- **Finding we accepted:** <rule> in `app/pipeline.py` / `app/web.py`: untrusted web text (search snippets, listing
  pages) is passed into model prompts. That is the product's purpose; mitigations: JSON-only outputs, the decision
  model never executes tools, every claim must cite a URL, the UI escapes all model output.
- **Fixed:** <finding, file, before/after check>
- **Consistency example:** <where two authors / agents clashed>

## Data insight (bonus)
`data/FR_DURABILITY_INSIGHTS.md`: 1,968 official French durability indexes. The overall score is exactly
0.5 × repairability + 0.5 × reliability (R² 0.998); repairability and reliability correlate only weakly (ρ ≈ 0.33);
self-declared spare-part fields sit at the legal minimum for every model and carry no information.

## Honest limits
idealo Trial tier (no per-review data, so no per-review fake detection yet); life estimates are ranges; web evidence is
thin for brand-new products, where the agent answers ASK. AI voice in the video (Qwen3-TTS); footage is a real recording.
