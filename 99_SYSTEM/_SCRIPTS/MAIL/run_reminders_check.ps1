$root = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$scriptPath = Join-Path $root "99_SYSTEM\_SCRIPTS\MAIL\telegram_reminders_check.py"
$csvPath = "C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\_PHOTO_DEDUP\photo_duplicates_20260203_133053.csv"

Set-Location $root
& python $scriptPath $csvPath

