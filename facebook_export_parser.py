"""
Facebook Data Export Parser

How to get your export:
  1. Go to Facebook Settings → Your Facebook Information → Download Your Information
  2. Select format: JSON, date range: All time
  3. Download the ZIP and extract it
  4. Run: python facebook_export_parser.py --path /path/to/extracted/folder
"""

import json
import os
import argparse
from datetime import datetime
from pathlib import Path


def decode_text(text: str) -> str:
    """Facebook encodes UTF-8 text as latin-1 in JSON exports."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return text


def parse_timestamp(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_posts(export_dir: Path) -> list[dict]:
    posts = []
    posts_dir = export_dir / "your_facebook_activity" / "posts"
    if not posts_dir.exists():
        posts_dir = export_dir / "posts"

    for json_file in sorted(posts_dir.glob("your_posts*.json")) if posts_dir.exists() else []:
        data = load_json(json_file)
        if not data:
            continue
        items = data if isinstance(data, list) else data.get("status_updates", [])
        for item in items:
            post = {
                "timestamp": parse_timestamp(item.get("timestamp", 0)),
                "title": decode_text(item.get("title", "")),
                "text": "",
                "media": [],
            }
            data_field = item.get("data", [])
            for d in data_field:
                if "post" in d:
                    post["text"] = decode_text(d["post"])
            attachments = item.get("attachments", [])
            for att in attachments:
                for media in att.get("data", []):
                    if "media" in media:
                        m = media["media"]
                        post["media"].append({
                            "uri": m.get("uri", ""),
                            "description": decode_text(m.get("description", "")),
                        })
            posts.append(post)

    return posts


def parse_comments(export_dir: Path) -> list[dict]:
    comments = []
    candidates = [
        export_dir / "your_facebook_activity" / "comments_and_reactions" / "comments.json",
        export_dir / "comments_and_reactions" / "comments.json",
        export_dir / "comments" / "comments.json",
    ]

    data = None
    for path in candidates:
        data = load_json(path)
        if data:
            break

    if not data:
        return comments

    items = data if isinstance(data, list) else data.get("comments_v2", [])
    for item in items:
        comment = {
            "timestamp": parse_timestamp(item.get("timestamp", 0)),
            "title": decode_text(item.get("title", "")),
            "text": "",
        }
        for d in item.get("data", []):
            if "comment" in d:
                comment["text"] = decode_text(d["comment"].get("comment", ""))
        comments.append(comment)

    return comments


def print_posts(posts: list[dict]) -> None:
    print(f"\n{'='*60}")
    print(f"  POSTS ({len(posts)} total)")
    print(f"{'='*60}")
    for i, post in enumerate(posts, 1):
        print(f"\n[{i}] {post['timestamp']}")
        if post["title"]:
            print(f"    Title: {post['title']}")
        if post["text"]:
            print(f"    Text:  {post['text'][:300]}{'...' if len(post['text']) > 300 else ''}")
        for m in post["media"]:
            print(f"    Media: {m['uri']}")
            if m["description"]:
                print(f"           {m['description'][:100]}")


def print_comments(comments: list[dict]) -> None:
    print(f"\n{'='*60}")
    print(f"  COMMENTS ({len(comments)} total)")
    print(f"{'='*60}")
    for i, comment in enumerate(comments, 1):
        print(f"\n[{i}] {comment['timestamp']}")
        print(f"    On:   {comment['title']}")
        if comment["text"]:
            print(f"    Said: {comment['text'][:300]}{'...' if len(comment['text']) > 300 else ''}")


def export_to_json(posts: list[dict], comments: list[dict], output_path: Path) -> None:
    result = {"posts": posts, "comments": comments}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Parse your Facebook data export")
    parser.add_argument("--path", required=True, help="Path to extracted Facebook export folder")
    parser.add_argument("--output", help="Optional: save results to a JSON file")
    parser.add_argument("--posts-only", action="store_true", help="Show only posts")
    parser.add_argument("--comments-only", action="store_true", help="Show only comments")
    args = parser.parse_args()

    export_dir = Path(args.path)
    if not export_dir.exists():
        print(f"Error: folder not found: {export_dir}")
        return

    if not args.comments_only:
        posts = parse_posts(export_dir)
        print_posts(posts)
    else:
        posts = []

    if not args.posts_only:
        comments = parse_comments(export_dir)
        print_comments(comments)
    else:
        comments = []

    if args.output:
        export_to_json(posts, comments, Path(args.output))


if __name__ == "__main__":
    main()
