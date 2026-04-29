$targets = @(
    "*Colorado*",
    "*Wichita*",
    "*Northern New England*",
    "*Southeast Michigan*",
    "*Orange County*",
    "*San Francisco*"
)

$chapters = Get-Content chapters.json -Raw | ConvertFrom-Json

for ($i = 0; $i -lt $chapters.Count; $i++) {
    foreach ($target in $targets) {
        if ($chapters[$i].chapter -like $target) {
            "{0} - {1}" -f $i, $chapters[$i].chapter
            break
        }
    }
}
