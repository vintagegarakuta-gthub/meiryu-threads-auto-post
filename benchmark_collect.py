"""
ベンチマークアカウントの投稿URLからテキストを収集し、benchmark_posts.json に保存する。
使い方: python3 benchmark_collect.py <URL1> <URL2> ...
"""
import sys
import json
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_DIR       = os.path.dirname(__file__)
BENCHMARK_FILE = os.path.join(BASE_DIR, "benchmark_posts.json")

IGNORE_TEXTS = {
    "Log in or sign up for Threads",
    "See what people are talking about and join the conversation.",
    "Continue with Instagram",
    "Translate",
}


def fetch_post(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ))
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        elements = page.query_selector_all("span[dir='auto'], div[dir='auto']")
        seen, blocks = set(), []
        for el in elements:
            t = el.inner_text().strip()
            if len(t) > 20 and t not in seen and t not in IGNORE_TEXTS:
                seen.add(t)
                blocks.append(t)

        browser.close()

    # 最初の長いテキストブロックを本文とする
    body = next((b for b in blocks if len(b) > 40), "")
    return {
        "url":        url,
        "collected":  datetime.now().strftime("%Y-%m-%d"),
        "body":       body,
        "all_blocks": blocks[:10],
    }


def main():
    urls = sys.argv[1:]
    if not urls:
        print("使い方: python3 benchmark_collect.py <URL1> <URL2> ...")
        sys.exit(1)

    data = []
    if os.path.exists(BENCHMARK_FILE):
        with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    existing_urls = {p["url"] for p in data}

    for url in urls:
        if url in existing_urls:
            print(f"[SKIP] 取得済み: {url}")
            continue
        print(f"[取得中] {url}")
        post = fetch_post(url)
        if post["body"]:
            data.append(post)
            print(f"[OK] 取得完了: {post['body'][:60]}...")
        else:
            print(f"[NG] テキスト取得失敗: {url}")

    with open(BENCHMARK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n合計 {len(data)} 件を {BENCHMARK_FILE} に保存しました")


if __name__ == "__main__":
    main()
