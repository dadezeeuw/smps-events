from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, date
import re
import json

with open("chapters.json", "r", encoding="utf-8") as f:
    chapters = json.load(f)

date_pattern = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$")
time_pattern = re.compile(
    r"^\d{1,2}:\d{2}\s?[AP]M(?:\s?[A-Z]{2,4})?\s?(to|-|\u2013)\s?\d{1,2}:\d{2}\s?[AP]M(?:\s?[A-Z]{2,4})?$",
    re.IGNORECASE
)

today = date.today()
all_events = []
skip_lines = {
    "Register Now",
    "Read More",
    "View Details",
    "View Details \u25ba",
    "Venue website",
    "View Current Registrants",
}
footer_lines = {
    "Connect",
    "Follow us",
    "Signup for our Newsletter",
    "Join Our Mailing List",
    "Additional Event Information",
}
location_pattern = re.compile(
    r"(^\d+|"
    r"\b(ave|avenue|blvd|boulevard|circle|court|ct|drive|dr|lane|ln|parkway|pkwy|"
    r"place|pl|road|rd|street|st|suite|ste|way)\b|"
    r"\b[A-Z]{2}\s+\d{5}\b|"
    r"^https?://)",
    re.IGNORECASE
)
virtual_pattern = re.compile(r"\b(virtual|online|webinar|zoom|remote|microsoft\s+teams|ms\s+teams)\b", re.IGNORECASE)

def make_sort_date(date_text):
    try:
        return datetime.strptime(date_text, "%B %d, %Y").strftime("%Y-%m-%d")
    except:
        return ""

def make_date(date_text):
    try:
        return datetime.strptime(date_text, "%B %d, %Y").date()
    except:
        return None

def clean_event_segment(segment):
    cleaned = []

    for line in segment:
        if line in footer_lines:
            break

        if line in skip_lines:
            continue

        cleaned.append(line)

    return cleaned

def split_location_description(segment):
    cleaned = clean_event_segment(segment)

    if not cleaned:
        return "", ""

    location_lines = [cleaned[0]]
    description_lines = []

    for line in cleaned[1:]:
        if location_pattern.search(line):
            location_lines.append(line)
        else:
            description_lines.append(line)

    return ", ".join(location_lines), " ".join(description_lines)

def is_virtual_event(title, location, description):
    searchable_text = f"{title} {location} {description}"
    return bool(virtual_pattern.search(searchable_text))

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="America/New_York",
    )
    page = context.new_page()

    for chapter in chapters:
        print(f"\nScraping: {chapter['chapter']}")

        try:
            page.goto(chapter["url"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            html = page.content()
        except Exception as e:
            print(f"Failed to load {chapter['chapter']}: {e}")
            continue

        soup = BeautifulSoup(html, "lxml")

        text = soup.get_text("\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        print(f"Loaded {len(lines)} lines from {chapter['chapter']}")
        print("First 80 lines:")
        for debug_line in lines[:80]:
            print(debug_line)

        if "Cloudflare" in lines or "Just a moment..." in lines:
            print(f"Cloudflare challenge detected for {chapter['chapter']}; waiting for verification.")
            page.wait_for_timeout(10000)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text("\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            if "Cloudflare" in lines or "Just a moment..." in lines:
                print(f"Cloudflare still blocking {chapter['chapter']}; skipping for now.")
                continue

        event_links = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href")

            if href and "meetinginfo.php?id=" in href:
                full_url = urljoin(chapter["url"], href)

                if full_url not in seen:
                    seen.add(full_url)
                    event_links.append(full_url)

        event_link_index = 0
        date_indexes = [i for i, line in enumerate(lines) if date_pattern.match(line)]

        for i, line in enumerate(lines):
            if date_pattern.match(line):
                title = lines[i - 1] if i > 0 else ""
                date = line
                time = lines[i + 1] if i + 1 < len(lines) else ""
                event_date = make_date(date)
                sort_date = make_sort_date(date)

                if not time_pattern.match(time):
                    print(f"Date found but time rejected: {date} | next line: {time}")
                    continue

                detail_url = event_links[event_link_index] if event_link_index < len(event_links) else ""
                event_link_index += 1

                if event_date and event_date < today:
                    print(f"Skipping past event: {date} | {title}")
                    continue

                current_date_index = date_indexes.index(i)
                next_date_index = date_indexes[current_date_index + 1] if current_date_index + 1 < len(date_indexes) else len(lines)
                segment_end = next_date_index - 1 if next_date_index < len(lines) else len(lines)
                segment = lines[i + 2:segment_end]
                location, description = split_location_description(segment)

                is_virtual = is_virtual_event(title, location, description)

                all_events.append({
                    "chapter": chapter["chapter"],
                    "state": chapter.get("state", ""),
                    "region": chapter.get("region", ""),
                    "title": title,
                    "date": date,
                    "sort_date": sort_date,
                    "time": time,
                    "location": location,
                    "description": description,
                    "is_virtual": is_virtual,
                    "detail_url": detail_url
                })

    context.close()
    browser.close()

all_events.sort(key=lambda event: event.get("sort_date", ""))

if len(all_events) == 0:
    print("ERROR: No events found. Not overwriting events.json.")
    raise SystemExit(1)

with open("docs/events.json", "w", encoding="utf-8") as f:
    json.dump(all_events, f, indent=2)

print(f"\nSaved {len(all_events)} total events")
