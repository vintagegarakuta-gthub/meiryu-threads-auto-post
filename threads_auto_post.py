import os
import sys
import json
import csv
import time
import requests
from datetime import datetime
from typing import Optional

ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
USER_ID      = os.getenv("THREADS_USER_ID")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
POSTS_FILE = os.path.join(BASE_DIR, "posts.json")
LOG_FILE   = os.path.join(BASE_DIR, "post_log.csv")

with open(POSTS_FILE, "r", encoding="utf-8") as f:
    POSTS_DATA = json.load(f)


def get_posted_keys() -> dict:
    posted = {"A": [], "B": [], "C": []}
    if not os.path.exists(LOG_FILE):
        return posted
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ptype = row.get("post_type", "")
            pkey  = row.get("post_key", "")
            if ptype in posted and pkey:
                posted[ptype].append(pkey)
    return posted


def get_post_type_for_today(forced_type: str = None) -> str:
    if forced_type:
        return forced_type
    day = datetime.now().strftime("%a")
    return POSTS_DATA["schedule"].get(day, "A")


def get_next_post(post_type: str) -> Optional[dict]:
    posts = POSTS_DATA["posts"][post_type]
    if not posts:
        return None
    # 投稿済み件数を基準に順番に循環させる（同一投稿の無限リピートを防止）
    posted_count = len(get_posted_keys()[post_type])
    return posts[posted_count % len(posts)]


def create_threads_post(text: str) -> Optional[str]:
    url = f"https://graph.threads.net/v1.0/{USER_ID}/threads"
    res = requests.post(url, params={"media_type": "TEXT", "text": text, "access_token": ACCESS_TOKEN})
    if res.status_code == 200:
        return res.json().get("id")
    print(f"[ERROR] メディア作成失敗: {res.status_code} {res.text}")
    return None


def publish_threads_post(creation_id: str, max_retries: int = 3, retry_delay: int = 20) -> Optional[str]:
    url = f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish"
    for attempt in range(1, max_retries + 1):
        res = requests.post(url, params={"creation_id": creation_id, "access_token": ACCESS_TOKEN})
        if res.status_code == 200:
            return res.json().get("id")
        print(f"[ERROR] 公開失敗 (試行{attempt}/{max_retries}): {res.status_code} {res.text}")
        # Meta側のメディアコンテナ反映待ち（Media Not Found対策）
        if attempt < max_retries:
            time.sleep(retry_delay)
    return None


def save_post_log(post_id: str, post_type: str, post_meta: dict):
    now = datetime.now()
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "time", "post_id", "post_type", "post_key", "title"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date":      now.strftime("%Y-%m-%d"),
            "time":      now.strftime("%H:%M"),
            "post_id":   post_id,
            "post_type": post_type,
            "post_key":  post_meta["id"],
            "title":     post_meta["title"],
        })


def post_today(forced_type: str = None):
    post_type = get_post_type_for_today(forced_type)
    post = get_next_post(post_type)
    if not post:
        print(f"[ERROR] 投稿コンテンツがありません（タイプ: {post_type}）")
        sys.exit(1)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 投稿開始: {post['id']} - {post['title']}")

    creation_id = create_threads_post(post["body"])
    if not creation_id:
        sys.exit(1)

    time.sleep(15)  # Meta側のメディアコンテナ反映待ち（Media Not Found対策）
    published_id = publish_threads_post(creation_id)
    if published_id:
        save_post_log(published_id, post_type, post)
        print(f"[OK] 投稿完了: {post['title']} (ID: {published_id})")
    else:
        sys.exit(1)


def main():
    forced_type = None
    for arg in sys.argv[1:]:
        if arg.startswith("--type="):
            forced_type = arg.split("=")[1].upper()

    if "--once" in sys.argv:
        post_today(forced_type)
        return

    # ローカルスケジューラーモード
    from dotenv import load_dotenv
    import schedule
    import time
    load_dotenv()
    POST_HOUR   = int(os.getenv("POST_HOUR", "21"))
    POST_MINUTE = int(os.getenv("POST_MINUTE", "0"))
    post_time = f"{POST_HOUR:02d}:{POST_MINUTE:02d}"
    print(f"Threads自動投稿スケジューラー起動 - 毎日 {post_time} に投稿")
    schedule.every().day.at(post_time).do(post_today, forced_type)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
