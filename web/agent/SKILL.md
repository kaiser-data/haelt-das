---
name: haelt-das
description: Check whether a product listing (link, text or screenshot) is worth buying - real shops, specs that add up, clones, failure reports, durability index and cost per day - and get a BUY / AVOID / BUY_ALTERNATIVE / ASK verdict with sources.
---

# Hält das? product check

Use this when a user asks whether a product is worth buying, whether a listing is fake or exaggerated, how long it will
last, or what it really costs per day.

## Call
`POST /api/check` on the site that served this file, with `Content-Type: application/json` and one of:

```json
{"text": "Akkuschrauber 21V 2 Akkus 39,99 €"}
{"url": "https://www.example-shop.de/product/123"}
{"image": "data:image/png;base64,..."}
```

## Read the answer
The response is a Server-Sent Events stream. Read `data:` lines as JSON until `{"type": "end"}`.
- `step` events report progress (`id`, `status`, `title`).
- The `verdict` event's `data` holds `verdict` (BUY, AVOID, BUY_ALTERNATIVE or ASK), `headline`, `confidence` and
  `reasons`, each with `text`, an evidence `tier` (A hard to fake, B filtered user reports, C cheap signals) and a
  source `url`.
- Other event types (`calls`, `saved`) are bookkeeping and can be ignored.
- An `error` event carries a `message`; tell the user instead of guessing a verdict.

A live check takes 30 to 90 seconds. On the public demo only the example listings are answered (recorded runs).

## Report to the user
Give the verdict first, then the two or three strongest reasons with their sources. Present life and cost-per-day as
ranges, never as a single exact number.
