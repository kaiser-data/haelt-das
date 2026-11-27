-- Every product check the agent runs: input, evidence, verdict and the Nebius calls behind it.
create table if not exists public.checks (
  id            uuid primary key default gen_random_uuid(),
  created_at    timestamptz not null default now(),
  input_kind    text not null check (input_kind in ('url', 'text', 'image', 'page')),
  input_ref     text,                       -- URL or first 300 chars of text; screenshots are not stored
  title         text,
  brand         text,
  category      text,
  price_eur     numeric,
  verdict       text check (verdict in ('BUY', 'AVOID', 'BUY_ALTERNATIVE', 'ASK')),
  confidence    text,
  headline      text,
  cost_per_day  numeric,                    -- mid estimate for the checked product
  life_low_y    numeric,
  life_high_y   numeric,
  n_spec_flags  int,
  n_failures    int,
  n_brands      int,
  claim         jsonb,
  idealo        jsonb,
  spec_flags    jsonb,
  clones        jsonb,
  lifetime      jsonb,
  cost          jsonb,
  verdict_full  jsonb,
  nebius_calls  jsonb
);
create index if not exists checks_created_at_idx on public.checks (created_at desc);
create index if not exists checks_brand_idx on public.checks (lower(brand));

-- The backend writes with the service-role key; the public (anon) key may only read verdict summaries.
alter table public.checks enable row level security;
create policy "public can read checks" on public.checks for select to anon using (true);
