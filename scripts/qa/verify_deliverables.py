"""Verify chapter 1 outputs and DB state."""

import json
import sqlite3
from pathlib import Path

def verify():
    con = sqlite3.connect(r"F:\AI-Office\data\office.db")
    cur = con.cursor()
    pages = cur.execute("SELECT count(*) FROM manga_storyboard_pages WHERE chapter_id='mlc-chap-01'").fetchone()[0]
    panels = cur.execute("SELECT count(*) FROM manga_panels WHERE page_id LIKE 'mlc-chap-01%'").fetchone()[0]
    print(f"Database -> Pages: {pages}, Panels: {panels}")

    qa_report_path = Path(r"F:\AI-Office\data\manga\exports\manga_qa_report_ch01.json")
    with open(qa_report_path, "r", encoding="utf-8") as f:
        qa = json.load(f)
    print(f"QA Report -> Title: {qa['title']}, Total Pages: {qa['total_pages']}, Total Panels: {qa['total_panels']}, Passed: {qa['panels_passed']}, Failed: {qa['panels_failed']}")

    exports_dir = Path(r"F:\AI-Office\data\manga\exports")
    for item in sorted(exports_dir.iterdir()):
        if item.is_file():
            size_mb = item.stat().st_size / (1024 * 1024)
            print(f"File: {item.name:<40} {size_mb:>8.2f} MB")
        elif item.is_dir():
            count = len(list(item.glob("*.png")))
            print(f"Dir:  {item.name:<40} {count:>8} PNG pages")

if __name__ == "__main__":
    verify()
