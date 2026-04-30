@echo off
set LOG_FILE=C:\Users\dadezeeuw\Documents\smps-events\scraper-task-log.txt

echo =============================== >> "%LOG_FILE%"
echo Run started: %date% %time% >> "%LOG_FILE%"
echo Current directory before cd: %cd% >> "%LOG_FILE%"

cd /d "C:\users\dadezeeuw\Documents\smps-events" >> "%LOG_FILE%" 2>&1

echo Current directory after cd: %cd% >> "%LOG_FILE%"
where python >> "%LOG_FILE%" 2>&1
python --version >> "%LOG_FILE%" 2>&1

echo Starting scraper: %date% %time% >> "%LOG_FILE%"
python -u scrape_events.py >> "%LOG_FILE%" 2>&1
echo Scraper finished with code %errorlevel%: %date% %time% >> "%LOG_FILE%"

if errorlevel 1 (
    echo Scraper failed. Not committing changes. >> "%LOG_FILE%"
    echo Run failed: %date% %time% >> "%LOG_FILE%"
    exit /b 1
)

git status --short >> "%LOG_FILE%" 2>&1
git add docs/events.json docs/scrape-status.json >> "%LOG_FILE%" 2>&1
git commit -m "Update scraped SMPS events" >> "%LOG_FILE%" 2>&1
git push >> "%LOG_FILE%" 2>&1

echo Run finished: %date% %time% >> "%LOG_FILE%"
