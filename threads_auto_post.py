import os
import sys
import json
import csv
import requests
import schedule
import time
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
USER_ID      = os.getenv("THREADS_USER_ID")
POST_HOUR    = int(os.getenv("POST_HOUR", "21"))
POST_MINUTE  = int(os.getenv("POST_MINUTE", "0"))

BASE_DIR   = os.path.dirname(__file__)
POSTS_FILE = os.path.join(BASE_DIR, "posts.json")
LOG_FILE   = os.path.join(BASE_DIR, "post_log.csv")

with open(POSTS_FILE, "r", encoding="utf-8") as f:
    POSTS_DATA = json.load(f)

post_index = {"A": 0, "B": 0, "C": 0}


def get_post_type_for_today(forced_type: str = None) -> str:
    if forced_type:
        return forced_type
    day = datetime.now().strftime("%a")
    return POSTS_DATA["schedule"].get(day, "A")


def get_next_post(post_type: str) -> dict:
    posts = POSTS_DATA["posts"][post_type]
    idx = post_index[post_type] % len(posts)
    post_index[post_type] += 1
    return posts[idx]


def create_threads_post(text: str) -> Optional[str]:
    url = f"https://graph.threads.net/v1.0/{USER_ID}/threads"
    res = requests.post(url, params={"media_type": "TEXT", "text": text, "access_token": ACCESS_TOKEN})
    if res.status_code == 200:
        return res.json().get("id")
    print(f"[ERROR] メディア作成失敗: {res.status_code} {res.text}")
    return None


def publish_threads_post(creation_id: str) -> Optional[str]:
    url = f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish"
    res = requests.post(url, params={"creation_id": creation_id, "access_token": ACCESS_TOKEN})
    if res.status_code == 200:
        return res.json().get("id")
    print(f"[ERROR] 公開失敗: {res.status_code} {res.text}")
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
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 投稿開始: {post['id']} - {post['title']}")

    creation_id = create_threads_post(post["body"])
    if not creation_id:
        return

    published_id = publish_threads_post(creation_id)
    if published_id:
        save_post_log(published_id, post_type, post)
        print(f"[OK] 投稿完了: {post['title']} (ID: {published_id})")
    else:
        print(f"[NG] 投稿失敗: {post['title']}")


def main():
    forced_type = None
    for arg in sys.argv[1:]:
        if arg.startswith("--type="):
            forced_type = arg.split("=")[1].upper()

    if "--once" in sys.argv:
        post_today(forced_type)
        return

    post_time = f"{POST_HOUR:02d}:{POST_MINUTE:02d}"
    print(f"Threads自動投稿スケジューラー起動 - 毎日 {post_time} に投稿")
    schedule.every().day.at(post_time).do(post_today, forced_type)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
