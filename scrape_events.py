from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import re
import json

with open("chapters.json", "r", encoding="utf-8") as f:
    chapters = json.load(f)

date_pattern = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4}$"
)

time_pattern = re.compile(
    r"^\d{1,2}(:\d{2})?\s*[AP]M\s*(to|-|–)\s*\d{1,2}(:\d{2})?\s*[AP]M$",
    re.IGNORECASE
)
all_events = []

def make_sort_date(date_text):
    date_text = date_text.replace(".", "")
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_text, fmt).strftime("%Y-%m-%d")
        except:
            pass
    return ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

    for chapter in chapters:
        print(f"\nScraping: {chapter['chapter']}")

        try:
            page.goto(chapter["url"], wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(8000)
            html = page.content()
        except Exception as e:
            print(f"Failed to load {chapter['chapter']}: {e}")
            continue

        soup = BeautifulSoup(html, "lxml")

        text = soup.get_text("\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        print(f"Found {len(lines)} lines for {chapter['chapter']}")
        for line in lines[:50]:
            print(line)
            
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
                print("\nDATE MATCH:", line)
                print("TITLE:", lines[i - 1] if i > 0 else "")
                print("TIME CANDIDATE:", lines[i + 1] if i + 1 < len(lines) else "")
                
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
if len(all_events) == 0:
    print("ERROR: No events found. Site may be blocking scraper. Not overwriting events.json.")
    raise SystemExit(1)
with open("docs/events.json", "w", encoding="utf-8") as f:
    json.dump(all_events, f, indent=2)
    
print("\nFINAL EVENT COUNT:", len(all_events))

print(f"\nSaved {len(all_events)} total events")
