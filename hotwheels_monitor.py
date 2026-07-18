"""
Amazon Hot Wheels Restock Monitor - Kay Kay Overseas Corporation Store
GitHub Actions Version (ek scan karke exit ho jata hai; cron isko baar baar chalata hai)
------------------------------------------------------------------------
BOT_TOKEN aur CHAT_ID environment variables se aate hain (GitHub Secrets se),
hardcode nahi kiye gaye taaki repo public hone par bhi safe rahe.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import random
import os
from datetime import datetime

# ============ CONFIG ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

SELLER_ID = "A2GTG1HPYW8M2P"  # Kay Kay Overseas Corporation Store
SEARCH_URLS = [
    f"https://www.amazon.in/s?k=hot+wheels&rh=p_6%3A{SELLER_ID}",
]

STATE_FILE = "seen_products.json"
# =================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


def now():
    return datetime.now().strftime("%H:%M:%S")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[{now()}] BOT_TOKEN/CHAT_ID missing, skipping Telegram send.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code != 200:
            print(f"[{now()}] Telegram send failed: {r.text}")
    except Exception as e:
        print(f"[{now()}] Telegram error: {e}")


def fetch_products(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    except Exception as e:
        print(f"[{now()}] Request failed: {e}")
        return []

    if resp.status_code == 503 or "captcha" in resp.text.lower():
        print(f"[{now()}] ⚠️ Amazon CAPTCHA/block mila.")
        return []

    if resp.status_code != 200:
        print(f"[{now()}] Unexpected status: {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    cards = soup.select('div[data-component-type="s-search-result"]')
    for card in cards:
        asin = card.get("data-asin", "").strip()
        if not asin:
            continue

        title_tag = card.select_one("h2 a span") or card.select_one("h2 span")
        title = title_tag.get_text(strip=True) if title_tag else "Unknown title"

        link_tag = card.select_one("h2 a")
        link = f"https://www.amazon.in{link_tag['href']}" if link_tag else f"https://www.amazon.in/dp/{asin}"

        text_blob = card.get_text(" ", strip=True).lower()
        out_of_stock = "currently unavailable" in text_blob or "out of stock" in text_blob

        price_tag = card.select_one("span.a-price > span.a-offscreen")
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        results.append({
            "asin": asin,
            "title": title,
            "link": link,
            "price": price,
            "in_stock": not out_of_stock,
        })

    return results


def run_once():
    state = load_state()
    all_products = []

    for url in SEARCH_URLS:
        all_products.extend(fetch_products(url))
        time.sleep(random.uniform(2, 4))

    if not all_products:
        print(f"[{now()}] Koi product nahi mila is scan me (block ho sakta hai ya listing empty).")
        return

    changed = False
    for p in all_products:
        asin = p["asin"]
        prev = state.get(asin)

        if prev is None:
            state[asin] = {"title": p["title"], "in_stock": p["in_stock"], "price": p["price"]}
            changed = True
            msg = (
                f"🆕 <b>Naya Hot Wheels listing mila!</b>\n\n"
                f"{p['title']}\n"
                f"💰 {p['price']}\n"
                f"📦 {'In Stock' if p['in_stock'] else 'Out of Stock'}\n"
                f"🔗 {p['link']}"
            )
            print(f"[{now()}] NEW: {p['title']}")
            send_telegram(msg)

        elif (not prev["in_stock"]) and p["in_stock"]:
            state[asin]["in_stock"] = True
            changed = True
            msg = (
                f"🔥 <b>RESTOCK ALERT!</b>\n\n"
                f"{p['title']}\n"
                f"💰 {p['price']}\n"
                f"🔗 {p['link']}"
            )
            print(f"[{now()}] RESTOCK: {p['title']}")
            send_telegram(msg)

        elif prev["in_stock"] and not p["in_stock"]:
            state[asin]["in_stock"] = False
            changed = True

    if changed:
        save_state(state)
        print(f"[{now()}] State updated.")
    else:
        print(f"[{now()}] Koi change nahi mila.")


if __name__ == "__main__":
    print("=== Hot Wheels Monitor - Single Scan (GitHub Actions) ===")
    run_once()
