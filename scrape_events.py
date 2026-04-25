from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import re
import json

with open("chapters.json", "r", encoding="utf-8") as f:
    chapters = json.load(f)

date_pattern = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$")
time_pattern = re.compile(r"^\d{1,2}:\d{2} [AP]M to \d{1,2}:\d{2} [AP]M$")

all_events = []

def make_sort_date(date_text):
    try:
        return datetime.strptime(date_text, "%B %d, %Y").strftime("%Y-%m-%d")
    except:
        return ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for chapter in chapters:
        print(f"\nScraping: {chapter['chapter']}")

        page.goto(chapter["url"], wait_until="networkidle")
        html = page.content()
        soup = BeautifulSoup(html, "lxml")

        text = soup.get_text("\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        event_links = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href")
            label = a.get_text(strip=True)

            if href and "meetinginfo.php?id=" in href:
                full_url = urljoin(chapter["url"], href)

                if full_url not in seen:
                    seen.add(full_url)
                    event_links.append(full_url)

        event_link_index = 0

        for i, line in enumerate(lines):
            if date_pattern.match(line):
                title = lines[i - 1] if i > 0 else ""
                date = line
                time = lines[i + 1] if i + 1 < len(lines) else ""
                location = lines[i + 2] if i + 2 < len(lines) else ""
                description = lines[i + 3] if i + 3 < len(lines) else ""

                if time_pattern.match(time):
                    detail_url = event_links[event_link_index] if event_link_index < len(event_links) else chapter["url"]
                    event_link_index += 1

                    all_events.append({
                        "chapter": chapter["chapter"],
                        "title": title,
                        "date": date,
                        "sort_date": make_sort_date(date),
                        "time": time,
                        "location": location,
                        "description": description,
                        "detail_url": detail_url
                    })

    browser.close()

all_events.sort(key=lambda event: event.get("sort_date", ""))

with open("docs/events.json", "w", encoding="utf-8") as f:
    json.dump(all_events, f, indent=2)

print(f"\nSaved {len(all_events)} total events")
