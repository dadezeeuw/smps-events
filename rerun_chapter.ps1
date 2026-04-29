param(
    [Parameter(Mandatory = $true)]
    [int]$Index,

    [string]$Output = "rerun-output.txt"
)

$env:SCRAPE_BATCH_SIZE = "1"
$env:SCRAPE_BATCH_INDEX = "$Index"
$env:SCRAPE_DELAY_MIN_SECONDS = "0"
$env:SCRAPE_DELAY_MAX_SECONDS = "0"

python scrape_events.py *> $Output

Write-Host "Saved scraper output to $Output"
Select-String -Path $Output -Pattern "Date found but time rejected|Failed to load|Cloudflare|Too Many Requests|Saved "
