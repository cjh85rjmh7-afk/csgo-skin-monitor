# CS Skin Monitor

Private notifier for underpriced CS2 / CS:GO skins on **Skinport**. No auto-buy —
it just sends a Discord message when a skin's cheapest listing is X% below its
suggested market price. You buy manually via the link.

## How it works

1. One call to the Skinport bulk endpoint `GET /v1/items` returns *every* item
   with `min_price` (cheapest current listing) and `suggested_price` (reference).
2. For each skin in `config.json`, alert when **both** are true:
   - `min_price <= max_price` (your absolute budget), and
   - `discount >= min_discount`, where `discount = 1 - min_price / suggested_price`.
3. New underpriced listings are posted to Discord as an embed.
4. `seen.json` remembers the last alerted price per skin so you aren't pinged
   again until the cheapest price changes.

## Important: rate limit

The Skinport `/v1/items` endpoint allows **8 requests per 5 minutes** and the
response is **cached for 5 minutes**. Calling it more often returns identical
data and wastes quota. The workflow therefore runs **once every 5 minutes with a
single API call** — this is the fastest meaningful cadence. (This differs from a
short-interval listing sniper; Skinport's aggregated data simply doesn't update
faster than 5 min.) Brotli (`Accept-Encoding: br`) is required, which is why
`brotli` is in `requirements.txt`.

## Setup

1. Create a **private** GitHub repo and add these files.
2. Create a Discord webhook (Server Settings → Integrations → Webhooks) and copy
   its URL.
3. In the repo: **Settings → Secrets and variables → Actions → New secret**
   - Name: `DISCORD_WEBHOOK`
   - Value: the webhook URL
4. Edit `config.json` — set your skins, `max_price`, and `min_discount`.
   `market_hash_name` must match Skinport **exactly**, including the `★` prefix
   for knives and gloves (e.g. `★ Flip Knife | Tiger Tooth (Factory New)`).
5. Trigger the first run: **Actions → CS skin monitor → Run workflow**.
6. After a day, tune thresholds based on how many alerts you get.

## Local test run

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
python monitor_once.py
```

## config.json

| Field | Meaning |
|-------|---------|
| `discount_threshold` | Default min discount if a skin omits `min_discount`. |
| `currency` | Any Skinport-supported currency (EUR, USD, GBP, …). |
| `skins[].max_price` | Absolute price ceiling — ignore listings above this. |
| `skins[].min_discount` | Min discount vs suggested price (0.25 = 25%). |

## Files

```
monitor_once.py   core script (one API call, then Discord)
config.json       skins + thresholds
seen.json         auto-managed dedupe state (committed by the workflow)
requirements.txt  requests, brotli
.github/workflows/monitor.yml   cron every 5 min
```

## Notes / caveats

- `min_price` / `suggested_price` can be `null` (nothing listed) — skipped safely.
- `suggested_price` is Skinport's own reference, not a cross-market low. For a
  true arbitrage signal, compare against Buff163 / Steam separately.
- The workflow commits `seen.json` back to the repo. GitHub may disable scheduled
  workflows on repos with no activity for 60 days — push occasionally or re-enable.
