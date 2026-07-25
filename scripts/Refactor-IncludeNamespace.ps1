param([string]$Root = ".", [switch]$Apply)
$Root = (Resolve-Path $Root).Path
$Inc  = Join-Path $Root "include"
$Dest = Join-Path $Inc "rakshak"
if (!(Test-Path $Inc)) { Write-Error "include/ not found"; exit 2 }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# Move under include/ except rakshak
Get-ChildItem $Inc | Where-Object { $_.Name -ne "rakshak" } | ForEach-Object {
  $src = $_.FullName; $tgt = Join-Path $Dest $_.Name
  Write-Host "[MOVE] $src -> $tgt"
  if ($Apply) {
    if ($_.PSIsContainer) {
      New-Item -ItemType Directory -Force -Path $tgt | Out-Null
      Get-ChildItem $src -Force | ForEach-Object {
        Move-Item $_.FullName (Join-Path $tgt $_.Name) -Force
      }
      Try { Remove-Item $src -Force } Catch {}
    } else {
      Move-Item $src $tgt -Force
    }
  }
}

# Build moved header list (relative to include/)
$headers = Get-ChildItem $Dest -Recurse -Include *.h,*.hh,*.hpp,*.ipp | ForEach-Object {
  $_.FullName.Substring($Inc.Length + 1).Substring(8).Replace("\","/")
}

# Rewrite includes
$files = Get-ChildItem $Root -Recurse -Include *.c,*.cc,*.cpp,*.cxx,*.h,*.hh,*.hpp,*.ipp,*.cmake,CMakeLists.txt
foreach ($f in $files) {
  $text = Get-Content $f.FullName -Raw
  $orig = $text
  $text = $text -replace '(?m)^(?\s*#\s*include\s*[<"])([^">]+)([>"].*)$', {
    param($m)
    $lead = $m.Groups[1].Value
    $path = $m.Groups[2].Value.Replace("\","/")
    $trail = $m.Groups[3].Value
    if ($path.StartsWith("rakshak/")) { return $m.Value }
    if ($headers -contains $path) { return "$lead"+"rakshak/$path"+$trail }
    return $m.Value
  }
  foreach ($h in $headers) {
    $text = $text -replace [regex]::Escape("include/$h"), ("include/rakshak/" + $h)
  }
  if ($Apply -and $text -ne $orig) { Set-Content -Path $f.FullName -Value $text -NoNewline }
}

if ($Apply) { Write-Host "[DONE] Applied" } else { Write-Host "[DRY-RUN] Use -Apply" }
