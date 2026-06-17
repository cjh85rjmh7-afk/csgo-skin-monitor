#!/usr/bin/env python3
"""CS:GO / CS2 skin monitor.

Fetches the full Skinport item list in a single API call, finds skins that are
priced meaningfully below their suggested market price, and posts a Discord
notification for each new underpriced listing.

No auto-buy. Purely a notifier. Buying is done manually via the Skinport link.

Skinport /v1/items facts (see https://docs.skinport.com/items):
  * No auth required.
  * Rate limit: 8 requests / 5 minutes. Response is cached for 5 minutes,
    so calling more than once per 5 min only wastes quota and returns the
    same data. This script makes exactly ONE request per run.
  * 'Accept-Encoding: br' (Brotli) is REQUIRED for this endpoint.
  * min_price / suggested_price may be null (e.g. nothing currently listed).
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
SEEN_PATH = BASE_DIR / "seen.json"

SKINPORT_ITEMS_URL = "https://api.skinport.com/v1/items"


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        print(f"WARN: {path.name} is not valid JSON ({e}); using default.")
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_items(currency, app_id=730):
    """Return {market_hash_name: item_dict} for the whole market in one call."""
    resp = requests.get(
        SKINPORT_ITEMS_URL,
        params={"app_id": app_id, "currency": currency, "tradable": 0},
        # Brotli encoding is required by this endpoint. requests advertises
        # gzip/deflate by default; if the 'brotli' package is installed it will
        # also advertise br and transparently decompress. We set the header
        # explicitly to satisfy the API requirement.
        headers={"Accept-Encoding": "br"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return {item["market_hash_name"]: item for item in data}


def send_discord(webhook_url, embed):
    resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
    # Discord returns 204 on success.
    if resp.status_code == 429:
        retry = resp.json().get("retry_after", 1)
        time.sleep(float(retry) + 0.5)
        resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
    resp.raise_for_status()


def build_embed(skin_name, min_price, ref_price, discount, currency, link, quantity):
    pct = round(discount * 100)
    return {
        "title": f"\U0001F3AE {skin_name}",
        "url": link,
        "color": 0x2ECC71 if pct >= 30 else 0xF1C40F,
        "fields": [
            {"name": "\U0001F4B0 Price", "value": f"{min_price:.2f} {currency}", "inline": True},
            {"name": "\U0001F4C9 Discount", "value": f"{pct}% under market", "inline": True},
            {"name": "\U0001F4CA Market price", "value": f"{ref_price:.2f} {currency}", "inline": True},
            {"name": "\U0001F4E6 Listings", "value": str(quantity), "inline": True},
        ],
        "footer": {"text": "Skinport monitor • buy manually via link"},
    }


def fallback_link(market_hash_name):
    # Used only if the item dict has no item_page (it normally does).
    return "https://skinport.com/market/730?search=" + quote(market_hash_name)


def main():
    config = load_json(CONFIG_PATH, None)
    if config is None:
        print("ERROR: config.json not found or invalid.")
        sys.exit(1)

    webhook_env = config.get("discord_webhook_env", "DISCORD_WEBHOOK")
    webhook_url = os.environ.get(webhook_env)
    if not webhook_url:
        print(f"ERROR: environment variable {webhook_env} is not set.")
        sys.exit(1)

    currency = config.get("currency", "EUR")
    default_discount = config.get("discount_threshold", 0.20)
    skins = config.get("skins", [])
    if not skins:
        print("Nothing to monitor: config 'skins' is empty.")
        return

    try:
        items = fetch_items(currency, app_id=config.get("app_id", 730))
    except requests.RequestException as e:
        print(f"ERROR fetching Skinport items: {e}")
        sys.exit(1)

    print(f"Fetched {len(items)} items from Skinport.")

    seen = load_json(SEEN_PATH, {})
    alerts = 0

    for skin in skins:
        mhn = skin.get("market_hash_name") or skin.get("name")
        item = items.get(mhn)
        if not item:
            print(f"  - not on market: {mhn}")
            continue

        min_price = item.get("min_price")
        ref_price = item.get("suggested_price")
        if min_price is None or ref_price is None or ref_price <= 0:
            continue

        discount = 1 - (min_price / ref_price)
        max_price = skin.get("max_price", float("inf"))
        min_discount = skin.get("min_discount", default_discount)

        if min_price > max_price or discount < min_discount:
            continue

        # Dedupe: alert again only if the cheapest price changed.
        # Round to cents so float noise doesn't re-trigger.
        price_key = f"{min_price:.2f}"
        if seen.get(mhn) == price_key:
            continue

        link = item.get("item_page") or fallback_link(mhn)
        embed = build_embed(
            skin.get("name", mhn), min_price, ref_price, discount,
            currency, link, item.get("quantity", 0),
        )
        try:
            send_discord(webhook_url, embed)
            seen[mhn] = price_key
            alerts += 1
            print(f"  ALERT {mhn}: {min_price:.2f} {currency} "
                  f"({round(discount*100)}% off)")
        except requests.RequestException as e:
            print(f"  WARN: failed to send Discord alert for {mhn}: {e}")

    save_json(SEEN_PATH, seen)
    print(f"Done. {alerts} new alert(s) sent.")


if __name__ == "__main__":
    main()
