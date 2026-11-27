# Hält das? ("Will it last?")

What a product really costs per day, how long it lasts, and whether someone is trying to trick you.

Give it a listing (a link, a pasted description, or a screenshot from Amazon, Temu, an Instagram ad). An agent checks it
the way an experienced buyer would and returns a verdict with a *receipt from the future*: the price per day over the
life you can actually expect.

## What it checks
- **Is it sold by real shops?** Exact match and branded equivalents, shop count and price (idealo).
- **Do the specs add up?** Physics and market rules: "21V" is 18V nominal, mAh vs weight, €/TB for flash, lumen vs price.
- **Same product, other names?** Look-alike listings and brand names (web search + vision comparison).
- **Does it break?** Failure reports in German, English and French, classified and de-duplicated.
- **Official durability index** for TVs and washing machines sold in France (data.gouv.fr, indice de durabilité).
- **What does it cost per day?** Price plus running costs over an evidence-based life range.
- **Verdict:** BUY, AVOID, BUY_ALTERNATIVE or ASK. Every reason carries an evidence tier (A hard to fake, B filtered
  user reports, C cheap signals) and a source link.

## API for agents
- `POST /api/check`: check a listing. JSON body with one of
  `{"text": "<listing text>"}`, `{"url": "<product page URL>"}` or `{"image": "<data: URL of a screenshot>"}`.
  The response is a Server-Sent Events stream (`text/event-stream`); each event is a JSON object with a `type`
  (`step`, `calls`, `verdict`, `saved`, `error`), and the stream ends with `{"type": "end"}`. The `verdict` event's
  `data` holds `verdict`, `headline`, `confidence` and `reasons` (each with `text`, evidence `tier` and source `url`).
  A live check takes 30 to 90 seconds. On the public demo it only replays recorded runs for the example listings.
- `POST /api/replay`: same input and output, replays a recorded run.
- OpenAPI description: [/openapi.json](/openapi.json). API catalog: [/.well-known/api-catalog](/.well-known/api-catalog).
- Agent skill: [/.well-known/agent-skills/haelt-das/SKILL.md](/.well-known/agent-skills/haelt-das/SKILL.md).

## Limits
- Life estimates are ranges from evidence plus model judgement, not measurements.
- When evidence is thin the verdict is **ASK**, naming the missing fact.
- Country of origin is never a signal; throwaway brands are.

Source code: https://github.com/kaiser-data/haelt-das
