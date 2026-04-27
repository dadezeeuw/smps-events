<<<<<<< HEAD
@echo off
cd /d "C:\users\dadezeeuw\Documents\smps-events"

python scrape_events.py

if errorlevel 1 (
    echo Scraper failed. Not committing changes.
    exit /b 1
)

git add docs/events.json
git commit -m "Update scraped SMPS events"

=======
@echo off
cd /d "C:\users\dadezeeuw\Documents\smps-events"

python scrape_events.py

if errorlevel 1 (
    echo Scraper failed. Not committing changes.
    exit /b 1
)

git add docs/events.json
git commit -m "Update scraped SMPS events"

>>>>>>> 8a5918c7b5f5c13ce10933c5da3728aeb82cc922
git push