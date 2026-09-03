File Directory
--------------
- `.git/`: Git repository data (history). Don’t edit directly.
- `.github/`: GitHub CI/workflow configs (used only if GitHub Actions are enabled).
- `.gitignore`: Files/folders Git should ignore (temp files, caches).
- `chapters.json`: Master list of chapter names and URLs the scraper visits. Edit to add/remove chapters, update events page urls, etc.
- `README.md`: This file — project overview and quick handoff commands.
- `requirements.txt`: Python packages needed to run the scraper. Install with `pip install -r requirements.txt`.
- `scrape_events.py`: Main scraper. Uses Playwright + BeautifulSoup to extract events and write `docs/` outputs.
- `run_scraper.bat`: Windows wrapper to run the full scraper, append logs, and commit outputs on success.
- `rerun_chapter.ps1`: PowerShell helper to rerun a single chapter (sets `SCRAPE_BATCH_SIZE=1`).
- `list_debug_chapters.ps1`: Prints chapter indices for single-chapter reruns.
- `report_failed_chapters.py`: Lists failed chapters from `docs/scrape-status.json` and suggests rerun indices.
- `temp_scan_failures.py`: Ad-hoc log analysis to find repeatedly failing chapters.
- `scraper-task-log.txt`: Cumulative run log (first place to inspect run timestamps and errors).
- `rerun-output.txt`: Capture of the last single-chapter rerun output.
- `docs/`: Output served/checked into the site.
	- `docs/events.json`: Aggregated event data consumed by the site.
	- `docs/scrape-status.json`: Per-chapter status, `last_updated`, and `total_events`.
	- `docs/index.html`: Static HTML front-end that reads `events.json`.
	- `docs/fonts/` and image assets: Visual assets for `index.html`. Visual assets used by index.html for SMPS branding on website (not required to run scraper).
- `__pycache__/`: Python bytecode cache (ignore).

PROJECT OVERVIEW
Purpose
-------
Aggregator that scrapes upcoming events from SMPS chapter sites and produces a single `docs/events.json` used by the static site in `docs/index.html`.

Quick contact
-------------
Dylan DeZeeuw — dadezeeuw@psara.com

Prerequisites
-------------
- Windows (instructions below) or any OS with Python 3.9+
- Git
- Python packages listed in `requirements.txt`
- Playwright browsers installed (see commands below)

Install (one-time)
------------------
Open a terminal in the repository root and run:

```powershell
python -m pip install -r requirements.txt
python -m playwright install
```

Run the full scraper
--------------------
- Use the provided batch wrapper (recommended on Windows). It logs runs, commits, and pushes outputs:

```powershell
.\run_scraper.bat
```

- Or run the scraper directly (no auto-commit):

```powershell
python -u scrape_events.py
```

Rerun a single chapter
----------------------
1. Find the chapter index used for single-chapter reruns:

```powershell
.\list_debug_chapters.ps1
```

2. Rerun that chapter (saves output to `rerun-output.txt`):

```powershell
.\rerun_chapter.ps1 -Index <N>
```

Check failures and triage
------------------------
- Quick machine-readable failure report:

```powershell
python report_failed_chapters.py
```

- Options:
	- `--json` to print JSON
	- `--csv <file>` to write CSV

- Useful files to inspect:
	- `docs/scrape-status.json` — per-chapter status, `last_updated`, `total_events`
	- `scraper-task-log.txt` — full run logs and debug output
	- `rerun-output.txt` — last single-chapter run output

Verify outputs
--------------
- `docs/events.json` — aggregated events consumed by the site
- `docs/scrape-status.json` — scrape metadata and per-chapter results
- `docs/index.html` — static page that displays events

Common troubleshooting
----------------------
- "Too Many Requests" / Cloudflare: wait 10–30 minutes and rerun the chapter; consider increasing `SCRAPE_DELAY_MIN_SECONDS` / `SCRAPE_DELAY_MAX_SECONDS` environment vars within 'scrape_events.py' 
- Playwright errors: ensure browsers are installed with `python -m playwright install` and that the Python environment matches `requirements.txt`.
- Network/load failures: rerun single chapter with `rerun_chapter.ps1` and inspect `rerun-output.txt`.

Useful environment variables
---------------------------
- `SCRAPE_BATCH_SIZE` — how many chapters to process in one run (default: all)
- `SCRAPE_BATCH_INDEX` — which batch index to run (useful for reruns)
- `SCRAPE_DELAY_MIN_SECONDS` / `SCRAPE_DELAY_MAX_SECONDS` — delay between chapters

Maintenance notes
-----------------
- `run_scraper.bat` appends to `scraper-task-log.txt` and commits `docs/events.json` + `docs/scrape-status.json` on success.
- Use `report_failed_chapters.py` to get rerun indices for failed chapters.

