@echo off
cd /d "C:\users\dadezeeuw\Documents\smps-events"

python scrape_events.py

if errorlevel 1 (
    echo Scraper failed. Not committing changes.
    exit /b 1
)

git add docs/events.json
git commit -m "Update scraped SMPS events"

git push