import os
import csv
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN   = os.getenv("THREADS_ACCESS_TOKEN")
BASE_DIR       = os.path.dirname(__file__)
LOG_FILE       = os.path.join(BASE_DIR, "post_log.csv")
ANALYTICS_FILE = os.path.join(BASE_DIR, "analytics.csv")

METRICS = ["views", "likes", "replies", "reposts", "quotes", "shares"]

ANALYTICS_FIELDS = ["date", "time", "post_id", "post_type", "post_key", "title",
                    "views", "likes", "replies", "reposts", "quotes", "shares", "fetched_at"]


def fetch_insights(post_id: str) -> dict:
    url = f"https://graph.threads.net/v1.0/{post_id}/insights"
    res = requests.get(url, params={"metric": ",".join(METRICS), "access_token": ACCESS_TOKEN})
    if res.status_code != 200:
        print(f"[ERROR] インサイト取得失敗 {post_id}: {res.status_code} {res.text}")
        return {}
    result = {}
    for item in res.json().get("data", []):
        name = item.get("name")
        values = item.get("values", [])
        result[name] = values[-1]["value"] if values else item.get("total_value", {}).get("value", 0)
    return result


def load_post_log() -> list:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_analytics() -> set:
    if not os.path.exists(ANALYTICS_FILE):
        return set()
    with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
        return {row["post_id"] for row in csv.DictReader(f)}


def run():
    posts = load_post_log()
    already_fetched = load_analytics()
    now = datetime.now()
    cutoff = now - timedelta(hours=24)

    targets = [
        p for p in posts
        if p["post_id"] not in already_fetched
        and datetime.strptime(f"{p['date']} {p['time']}", "%Y-%m-%d %H:%M") <= cutoff
    ]

    if not targets:
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] 分析対象なし")
        return

    file_exists = os.path.exists(ANALYTICS_FILE)
    with open(ANALYTICS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANALYTICS_FIELDS)
        if not file_exists:
            writer.writeheader()

        for p in targets:
            insights = fetch_insights(p["post_id"])
            if not insights:
                continue
            row = {**p, **{m: insights.get(m, 0) for m in METRICS}, "fetched_at": now.strftime("%Y-%m-%d %H:%M")}
            writer.writerow(row)
            print(f"[OK] {p['date']} {p['title']} - 閲覧:{insights.get('views',0)} いいね:{insights.get('likes',0)} 返信:{insights.get('replies',0)}")

    print(f"[完了] {len(targets)}件の分析を保存しました → {ANALYTICS_FILE}")


if __name__ == "__main__":
    run()
