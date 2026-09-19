# Giggles bot

A headless client for the Giggles video market, built from the app's own
backend paths. It is a play-money game: Aura cannot be withdrawn, and the
platform may ban automated accounts. The research and phased plan live in
`.claude/workspace/` (not published); this page covers running the code.

## Setup

1. Install: `make install` (adds `httpx` and the `giggles` console script).
2. Get the Supabase anon key from the app bundle (it is a public key, but it is
   per project so it is not checked in) and export it as `SUPABASE_ANON_KEY`.
3. Sign in and save a session under `giggles-data/` (gitignored):

   ```bash
   giggles login you@example.com
   giggles probe   # prints your profile; proves the bearer token works
   ```

   Alternatively capture the app's `Authorization: Bearer` header with a proxy
   and export it as `GIGGLES_ACCESS_TOKEN`. Every request is paced by
   `GIGGLES_MIN_INTERVAL_S` (default 1.5 s).

## Phase 0: learn the schema and the pricing model

Nothing in the bundle dump says what the responses look like, so the client
records every exchange to `giggles-data/raw/*.jsonl`, and the collector stores
post details, price graphs, and trade tapes in `giggles-data/snapshots.sqlite`.

```bash
giggles collect --minutes 120   # discover posts, poll each on a decaying cadence
giggles schema                  # key paths and types seen per endpoint
giggles analyze --price-path points:t,price --trade-path trades:t
```

`schema` tells you where the price points and trade timestamps live; pass
those paths to `analyze`, which classifies each post as bonding-curve (price
moves only on trades), engagement-indexed (price drifts without trades), or a
hybrid. That verdict decides which strategy is worth building next.

Measure the round trip once by hand: buy the minimum on any post, sell it
immediately, and feed the two ledger amounts to
{py:func}`giggles.analysis.round_trip_cost`. Every entry threshold in
{py:mod}`giggles.strategy` is expressed against that number.

## Free Aura

```bash
giggles faucets   # rewards claim, gift reveal, signup-trend claim
```

Run it daily from cron. A faucet reports `ok` when the backend answers 2xx;
confirm the Aura actually arrived from the ledger snapshot.

## Trading

{py:meth}`giggles.client.GigglesClient.invest` posts to the invest endpoint
but the body schema must be confirmed from a recorded in-app trade before it
is wired into a strategy. That, the Centrifugo live feed, and the card-market
arbitrage are the next phases.
