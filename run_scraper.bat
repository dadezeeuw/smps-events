@echo off
cd /d "C:\users\dadezeeuw\Documents\smps-events"

set SCRAPE_BATCH_SIZE=12
set SCRAPE_DELAY_MIN_SECONDS=45
set SCRAPE_DELAY_MAX_SECONDS=90

python scrape_events.py

if errorlevel 1 (
    echo Scraper failed. Not committing changes.
    exit /b 1
)

git add docs/events.json docs/scrape-status.json
git commit -m "Update scraped SMPS events"

git push
