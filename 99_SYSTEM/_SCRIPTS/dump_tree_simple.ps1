param(
  [string]$Root = "C:\Users\alimg\Dropbox\Archiwum 3.0",
  [string]$OutDir = "C:\Users\alimg\Desktop\ARCHIWUM_DUMP",
  [int]$MaxDepth = 6
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Root)) { throw "Root not found: $Root" }
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$treePath = Join-Path $OutDir ("TREE_" + $ts + ".txt")
$sumPath  = Join-Path $OutDir ("SUMMARY_" + $ts + ".txt")

$rootResolved = (Resolve-Path -LiteralPath $Root).Path

"ROOT=" + $rootResolved | Set-Content -Encoding UTF8 -LiteralPath $sumPath
"GENERATED=" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") | Add-Content -Encoding UTF8 -LiteralPath $sumPath

# Dump folders up to MaxDepth
Get-ChildItem -LiteralPath $Root -Directory -Recurse -Force |
  ForEach-Object {
    $full = $_.FullName
    $rel  = $full.Substring($rootResolved.Length).TrimStart('\','/')
    if ($rel -eq "") { $rel = "." }
    $depth = ($rel -split '[\\\/]').Count
    if ($depth -le $MaxDepth) { $rel }
  } |
  Sort-Object |
  Set-Content -Encoding UTF8 -LiteralPath $treePath

# Add counts
$folderCount = (Get-ChildItem -LiteralPath $Root -Directory -Recurse -Force | Measure-Object).Count
$fileCount   = (Get-ChildItem -LiteralPath $Root -File -Recurse -Force | Measure-Object).Count

"FOLDERS=" + $folderCount | Add-Content -Encoding UTF8 -LiteralPath $sumPath
"FILES=" + $fileCount     | Add-Content -Encoding UTF8 -LiteralPath $sumPath

"OK. TREE: $treePath"
"OK. SUMMARY: $sumPath"
