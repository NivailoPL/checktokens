param([string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\CheckTokens'))
. (Join-Path $PSScriptRoot 'windows-install-common.ps1')
$InstallDir = Get-SafePath $InstallDir
$current = Join-Path $InstallDir 'current'
$stateFile = Join-Path $current 'install-state.json'
if (-not (Test-Path -LiteralPath $stateFile)) { throw 'No CheckTokens installation was found here.' }
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
if ($state.owner -ne $script:OwnerId -or $state.installDir -ne $InstallDir) { throw 'Installation ownership does not match.' }
Assert-AppClosed $InstallDir
Assert-RegistryOwnership $state.registryRoot
# Validate every deletion target before changing registration or deleting files.
$files = @('MANIFEST.sha256', 'install-state.json')
foreach ($line in Get-Content -LiteralPath (Join-Path $current 'MANIFEST.sha256')) {
    if ($line -notmatch '^([a-fA-F0-9]{64})  (.+)$') { throw 'Invalid installed manifest.' }
    $files += $Matches[2]
}
$targets = foreach ($relative in $files) {
    $target = Get-SafePath (Join-Path $current $relative)
    if (-not $target.StartsWith($current + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe uninstall path.' }
    $target
}
$shortcut = Get-SafePath (Join-Path $state.shortcutDir 'CheckTokens.lnk')
if (Test-Path -LiteralPath $shortcut) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcut)
    Write-Host ('SHORTCUT DIAGNOSTIC ' + (@{ actual=$link.TargetPath; expected=(Join-Path $current 'app\CheckTokens.exe') } | ConvertTo-Json -Compress))
    if ($link.TargetPath -eq (Join-Path $current 'app\CheckTokens.exe')) { Remove-Item -LiteralPath $shortcut }
}
Unregister-CheckTokens $state.registryRoot
foreach ($target in $targets) { if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target -Force } }
# Only prune empty directories, leaving unrelated files intact.
if (Test-Path -LiteralPath $current) {
    Get-ChildItem -LiteralPath $current -Directory -Recurse -Force | Sort-Object { $_.FullName.Length } -Descending | ForEach-Object {
        if (-not (Get-ChildItem -LiteralPath $_.FullName -Force)) { Remove-Item -LiteralPath (Get-SafePath $_.FullName) }
    }
    if (-not (Get-ChildItem -LiteralPath $current -Force)) { Remove-Item -LiteralPath $current }
}
if (-not (Get-ChildItem -LiteralPath $InstallDir -Force)) { Remove-Item -LiteralPath $InstallDir }
Notify-Explorer
Write-Host 'CheckTokens uninstalled. Unrelated files were preserved.'
