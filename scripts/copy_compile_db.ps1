Param()
$src = Join-Path -Path $PSScriptRoot -ChildPath "..\ui\build\compile_commands.json"
$dst = Join-Path -Path $PSScriptRoot -ChildPath "..\compile_commands.json"
if (Test-Path $src) {
    Copy-Item -Path $src -Destination $dst -Force
    Write-Host "Copied compile_commands.json to workspace root."
} else {
    Write-Host "No compile_commands.json found at $src. Run the CMake configure+build task first." -ForegroundColor Yellow
}
