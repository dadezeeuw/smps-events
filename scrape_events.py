from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urljoin, urlparse
from datetime import datetime, date
import re
import json
import os
import random
import sys
import time as time_module

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

with open("chapters.json", "r", encoding="utf-8") as f:
    chapters = json.load(f)

try:
    with open("docs/events.json", "r", encoding="utf-8") as f:
        existing_events = json.load(f)
except FileNotFoundError:
    existing_events = []

date_pattern = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$")
time_pattern = re.compile(
    r"^\d{1,2}:\d{2}\s?[AP]M(?:\s?[A-Z]{2,4})?(?:(?:\s?(to|-|\u2013)\s?)\d{1,2}:\d{2}\s?[AP]M(?:\s?[A-Z]{2,4})?)?(?:\s?\([^)]+\))?$",
    re.IGNORECASE
)
colorado_time_pattern = re.compile(
    r"^\d{1,2}:\d{2}\s?[AP]M\s?-\s?\d{1,2}:\d{2}\s?[AP]M(?:\s?[A-Z]{2,4})?$",
    re.IGNORECASE
)
wichita_date_time_pattern = re.compile(
    r"^([A-Z][a-z]+)\s+(\d{1,2})\s+@\s+(.+)$"
)

today = date.today()
new_events = []
successful_chapters = set()
batch_size = max(1, int(os.getenv("SCRAPE_BATCH_SIZE", len(chapters))))
batch_count = max(1, (len(chapters) + batch_size - 1) // batch_size)
batch_index = int(os.getenv("SCRAPE_BATCH_INDEX", str(today.toordinal() % batch_count))) % batch_count
batch_start = batch_index * batch_size
batch_end = batch_start + batch_size
chapters_to_scrape = chapters[batch_start:batch_end]
delay_min = int(os.getenv("SCRAPE_DELAY_MIN_SECONDS", "20"))
delay_max = int(os.getenv("SCRAPE_DELAY_MAX_SECONDS", "60"))
if delay_min > delay_max:
    delay_min, delay_max = delay_max, delay_min
is_ci = os.getenv("GITHUB_ACTIONS") == "true"
scrape_status = {
    "last_updated": "",
    "total_events": 0,
    "batch": {
        "batch_index": batch_index,
        "batch_count": batch_count,
        "batch_size": batch_size,
        "chapters_in_batch": len(chapters_to_scrape),
        "total_chapters": len(chapters)
    },
    "chapters": []
}
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

def normalize_line(line):
    return (
        line
        .replace("\u00a0", " ")
        .replace("á", " ")
        .replace("Â", "")
        .strip()
    )

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

def make_colorado_date_from_url(url):
    query = parse_qs(urlparse(url).query)

    try:
        event_date = datetime(
            int(query["year"][0]),
            int(query["month"][0]),
            int(query["day"][0])
        ).date()
    except (KeyError, ValueError, IndexError):
        return None, "", "", ""

    date_text = event_date.strftime("%B %d, %Y")
    sort_date = event_date.strftime("%Y-%m-%d")
    detail_date_text = event_date.strftime("%A, %B %d, %Y")
    return event_date, date_text, sort_date, detail_date_text

def find_colorado_time(lines, detail_date_text):
    for i, line in enumerate(lines):
        if line == detail_date_text and i + 1 < len(lines):
            possible_time = lines[i + 1]

            if colorado_time_pattern.match(possible_time):
                return possible_time.replace(" - ", " to ")

    return ""

def find_colorado_category(lines, title):
    for i, line in enumerate(lines):
        if title and title in line:
            for next_line in lines[i + 1:i + 4]:
                if next_line.startswith("Category:"):
                    return next_line.replace("Category:", "", 1).strip()

    return ""

def parse_colorado_events(soup, lines, chapter):
    events_by_url = {}

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = a.get_text(" ", strip=True)

        if "task=icalrepeat.detail" not in href or "evid=" not in href:
            continue

        if not title or title.lower().startswith("export event"):
            continue

        detail_url = urljoin(chapter["url"], href)
        event_date, date_text, sort_date, detail_date_text = make_colorado_date_from_url(detail_url)

        if not event_date or event_date < today:
            continue

        existing = events_by_url.get(detail_url)

        if existing and len(existing["title"]) >= len(title):
            continue

        category = find_colorado_category(lines, title)
        description = f"Category: {category}" if category else ""
        time_text = find_colorado_time(lines, detail_date_text)

        events_by_url[detail_url] = {
            "chapter": chapter["chapter"],
            "state": chapter.get("state", ""),
            "region": chapter.get("region", ""),
            "title": title,
            "date": date_text,
            "sort_date": sort_date,
            "time": time_text or "TBD",
            "location": "See event details",
            "description": description,
            "is_virtual": is_virtual_event(title, "", description),
            "detail_url": detail_url
        }

    return list(events_by_url.values())

def parse_wichita_date_time(date_time_text):
    match = wichita_date_time_pattern.match(date_time_text)

    if not match:
        return None, "", "", ""

    month_text, day_text, time_text = match.groups()
    event_year = today.year

    try:
        event_date = datetime.strptime(
            f"{month_text} {day_text}, {event_year}",
            "%B %d, %Y"
        ).date()
    except ValueError:
        return None, "", "", ""

    date_text = event_date.strftime("%B %d, %Y")
    sort_date = event_date.strftime("%Y-%m-%d")
    normalized_time = time_text.replace(" - ", " to ")

    return event_date, date_text, sort_date, normalized_time

def parse_wichita_events(soup, lines, chapter):
    detail_urls_by_title = {}

    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = a.get("href", "")

        if not title or "/event/" not in href:
            continue

        detail_urls_by_title[title] = urljoin(chapter["url"], href)

    events = []

    for i, line in enumerate(lines):
        if i + 1 >= len(lines):
            continue

        event_date, date_text, sort_date, time_text = parse_wichita_date_time(lines[i + 1])

        if not event_date or event_date < today:
            continue

        title = line
        description = ""

        if i + 2 < len(lines) and lines[i + 2] != "View Details":
            description = lines[i + 2]

        events.append({
            "chapter": chapter["chapter"],
            "state": chapter.get("state", ""),
            "region": chapter.get("region", ""),
            "title": title,
            "date": date_text,
            "sort_date": sort_date,
            "time": time_text,
            "location": "See event details",
            "description": description,
            "is_virtual": is_virtual_event(title, "", description),
            "detail_url": detail_urls_by_title.get(title, chapter["url"])
        })

    return events

def save_scrape_status():
    scrape_status["last_updated"] = datetime.now().isoformat(timespec="seconds")
    scrape_status["total_events"] = len(all_events)

    with open("docs/scrape-status.json", "w", encoding="utf-8") as f:
        json.dump(scrape_status, f, indent=2)

def wait_between_chapters():
    if delay_max <= 0:
        return

    delay = random.randint(delay_min, delay_max)
    print(f"Waiting {delay} seconds before the next chapter...")
    time_module.sleep(delay)

print(
    f"Scraping batch {batch_index + 1} of {batch_count}: "
    f"{len(chapters_to_scrape)} of {len(chapters)} chapters"
)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=is_ci,
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

    for chapter_index, chapter in enumerate(chapters_to_scrape):
        print(f"\nScraping: {chapter['chapter']}")
        chapter_event_count = 0
        rejected_dates = 0
        skipped_past_events = 0

        try:
            page.goto(chapter["url"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            html = page.content()
        except Exception as e:
            print(f"Failed to load {chapter['chapter']}: {e}")
            scrape_status["chapters"].append({
                "chapter": chapter["chapter"],
                "state": chapter.get("state", ""),
                "region": chapter.get("region", ""),
                "url": chapter["url"],
                "status": "failed",
                "message": str(e),
                "events_found": 0,
                "lines_loaded": 0,
                "rejected_dates": 0,
                "skipped_past_events": 0
            })
            if chapter_index < len(chapters_to_scrape) - 1:
                wait_between_chapters()
            continue

        soup = BeautifulSoup(html, "lxml")

        text = soup.get_text("\n", strip=True)
        lines = [normalize_line(line) for line in text.split("\n") if normalize_line(line)]

        print(f"Loaded {len(lines)} lines from {chapter['chapter']}")
        print("First 80 lines:")
        for debug_line in lines[:80]:
            print(debug_line)

        if "Too Many Requests" in lines:
            print(f"Rate limited by StarChapter/Cloudflare for {chapter['chapter']}; preserving existing events.")
            scrape_status["chapters"].append({
                "chapter": chapter["chapter"],
                "state": chapter.get("state", ""),
                "region": chapter.get("region", ""),
                "url": chapter["url"],
                "status": "throttled",
                "message": "Too Many Requests.",
                "events_found": 0,
                "lines_loaded": len(lines),
                "rejected_dates": 0,
                "skipped_past_events": 0
            })
            if chapter_index < len(chapters_to_scrape) - 1:
                wait_between_chapters()
            continue

        if "Cloudflare" in lines or "Just a moment..." in lines:
            print(f"Cloudflare challenge detected for {chapter['chapter']}; waiting for verification.")
            page.wait_for_timeout(10000)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text("\n", strip=True)
            lines = [normalize_line(line) for line in text.split("\n") if normalize_line(line)]

            if "Too Many Requests" in lines:
                print(f"Rate limited by StarChapter/Cloudflare for {chapter['chapter']}; preserving existing events.")
                scrape_status["chapters"].append({
                    "chapter": chapter["chapter"],
                    "state": chapter.get("state", ""),
                    "region": chapter.get("region", ""),
                    "url": chapter["url"],
                    "status": "throttled",
                    "message": "Too Many Requests.",
                    "events_found": 0,
                    "lines_loaded": len(lines),
                    "rejected_dates": 0,
                    "skipped_past_events": 0
                })
                if chapter_index < len(chapters_to_scrape) - 1:
                    wait_between_chapters()
                continue

            if "Cloudflare" in lines or "Just a moment..." in lines:
                print(f"Cloudflare still blocking {chapter['chapter']}; skipping for now.")
                scrape_status["chapters"].append({
                    "chapter": chapter["chapter"],
                    "state": chapter.get("state", ""),
                    "region": chapter.get("region", ""),
                    "url": chapter["url"],
                    "status": "blocked",
                    "message": "Cloudflare challenge remained after retry.",
                    "events_found": 0,
                    "lines_loaded": len(lines),
                    "rejected_dates": 0,
                    "skipped_past_events": 0
                })
                if chapter_index < len(chapters_to_scrape) - 1:
                    wait_between_chapters()
                continue

        if chapter["chapter"] == "SMPS Colorado" or "smpscolorado.org" in chapter["url"] or "smpsc.memberclicks.net" in chapter["url"]:
            colorado_events = parse_colorado_events(soup, lines, chapter)
            new_events.extend(colorado_events)
            chapter_event_count = len(colorado_events)
            successful_chapters.add(chapter["chapter"])

            scrape_status["chapters"].append({
                "chapter": chapter["chapter"],
                "state": chapter.get("state", ""),
                "region": chapter.get("region", ""),
                "url": chapter["url"],
                "status": "success",
                "message": "Scraped successfully with Colorado MemberClicks parser.",
                "events_found": chapter_event_count,
                "lines_loaded": len(lines),
                "rejected_dates": 0,
                "skipped_past_events": 0
            })

            if chapter_index < len(chapters_to_scrape) - 1:
                wait_between_chapters()
            continue

        if chapter["chapter"] == "SMPS Wichita" or "smpswichita.org" in chapter["url"]:
            wichita_events = parse_wichita_events(soup, lines, chapter)
            new_events.extend(wichita_events)
            chapter_event_count = len(wichita_events)
            successful_chapters.add(chapter["chapter"])

            scrape_status["chapters"].append({
                "chapter": chapter["chapter"],
                "state": chapter.get("state", ""),
                "region": chapter.get("region", ""),
                "url": chapter["url"],
                "status": "success",
                "message": "Scraped successfully with Wichita WordPress parser.",
                "events_found": chapter_event_count,
                "lines_loaded": len(lines),
                "rejected_dates": 0,
                "skipped_past_events": 0
            })

            if chapter_index < len(chapters_to_scrape) - 1:
                wait_between_chapters()
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
                    rejected_dates += 1
                    continue

                detail_url = event_links[event_link_index] if event_link_index < len(event_links) else ""
                event_link_index += 1

                if event_date and event_date < today:
                    print(f"Skipping past event: {date} | {title}")
                    skipped_past_events += 1
                    continue

                current_date_index = date_indexes.index(i)
                next_date_index = date_indexes[current_date_index + 1] if current_date_index + 1 < len(date_indexes) else len(lines)
                segment_end = next_date_index - 1 if next_date_index < len(lines) else len(lines)
                segment = lines[i + 2:segment_end]
                location, description = split_location_description(segment)

                is_virtual = is_virtual_event(title, location, description)

                new_events.append({
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
                chapter_event_count += 1

        successful_chapters.add(chapter["chapter"])
        scrape_status["chapters"].append({
            "chapter": chapter["chapter"],
            "state": chapter.get("state", ""),
            "region": chapter.get("region", ""),
            "url": chapter["url"],
            "status": "success",
            "message": "Scraped successfully.",
            "events_found": chapter_event_count,
            "lines_loaded": len(lines),
            "rejected_dates": rejected_dates,
            "skipped_past_events": skipped_past_events
        })

        if chapter_index < len(chapters_to_scrape) - 1:
            wait_between_chapters()

    context.close()
    browser.close()

preserved_events = [
    event for event in existing_events
    if event.get("chapter", "") not in successful_chapters
]
all_events = preserved_events + new_events
all_events.sort(key=lambda event: event.get("sort_date", ""))

if len(all_events) == 0:
    print("ERROR: No events found. Not overwriting events.json.")
    save_scrape_status()
    raise SystemExit(1)

with open("docs/events.json", "w", encoding="utf-8") as f:
    json.dump(all_events, f, indent=2)

save_scrape_status()

print(f"\nSaved {len(all_events)} total events")
