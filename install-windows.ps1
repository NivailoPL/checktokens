param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\CheckTokens'),
    [string]$RegistryRoot = 'Software\Classes',
    [string]$ShortcutDir = [Environment]::GetFolderPath('Programs')
)
. (Join-Path $PSScriptRoot 'windows-install-common.ps1')
if (-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) { throw 'Run this installer using 64-bit Windows PowerShell.' }
$InstallDir = Get-SafePath $InstallDir
$ShortcutDir = Get-SafePath $ShortcutDir
$current = Join-Path $InstallDir 'current'
$stateFile = Join-Path $current 'install-state.json'
$oldState = $null
if (Test-Path -LiteralPath $current) {
    if (-not (Test-Path -LiteralPath $stateFile)) { throw 'The destination contains an unrelated current directory.' }
    $oldState = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    if ($oldState.owner -ne $script:OwnerId -or $oldState.installDir -ne $InstallDir -or $oldState.registryRoot -ne $RegistryRoot -or $oldState.shortcutDir -ne $ShortcutDir) { throw 'Installation ownership or location does not match.' }
}
if ($PSScriptRoot -eq $current) { throw 'Run the installer from a freshly extracted release ZIP.' }
Assert-RegistryOwnership $RegistryRoot
Assert-AppClosed $InstallDir
$manifestPath = Join-Path $PSScriptRoot 'MANIFEST.sha256'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Download and extract the Windows release ZIP first. This source checkout is not an installable package.' }
$entries = @()
foreach ($line in Get-Content -LiteralPath $manifestPath) {
    if ($line -notmatch '^([a-fA-F0-9]{64})  (.+)$') { throw 'Invalid package manifest.' }
    $hash = $Matches[1]
    $relative = $Matches[2]
    if ([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[/\\])\.\.([/\\]|$)' -or $relative.Contains(':')) { throw 'Unsafe manifest path.' }
    $source = Get-SafePath (Join-Path $PSScriptRoot $relative)
    if (-not $source.StartsWith($PSScriptRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Manifest path escaped package.' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $hash) { throw "Package integrity check failed: $relative" }
    $entries += $relative
}
foreach ($required in @('app/CheckTokens.exe','app/checktokens-cli.exe','app/CheckTokensShell.exe','uninstall.cmd','uninstall-windows.ps1','windows-install-common.ps1')) {
    if ($entries -notcontains $required) { throw "Package is missing $required" }
}
$shortcut = Join-Path $ShortcutDir 'CheckTokens.lnk'
if ((Test-Path -LiteralPath $shortcut) -and -not $oldState) { throw 'An unrelated CheckTokens shortcut already exists.' }
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$stage = Join-Path $InstallDir ('.install-' + [guid]::NewGuid())
$backup = Join-Path $InstallDir ('.previous-' + [guid]::NewGuid())
$swapped = $false
$registered = $false
try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    foreach ($relative in $entries) {
        $target = Join-Path $stage $relative
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $relative) -Destination $target
    }
    Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $stage 'MANIFEST.sha256')
    @{ owner=$script:OwnerId; installDir=$InstallDir; registryRoot=$RegistryRoot; shortcutDir=$ShortcutDir } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $stage 'install-state.json') -Encoding UTF8
    # Preserve files that a user placed inside the managed directory as well.
    if ($oldState) {
        $oldFiles = @((Get-Content -LiteralPath (Join-Path $current 'MANIFEST.sha256')) | ForEach-Object { $_.Substring(66).Replace('/', '\') }) + @('MANIFEST.sha256','install-state.json')
        foreach ($file in Get-ChildItem -LiteralPath $current -Recurse -File -Force) {
            $relative = $file.FullName.Substring($current.Length + 1)
            if ($oldFiles -notcontains $relative -and -not (Test-Path -LiteralPath (Join-Path $stage $relative))) {
                $null = Get-SafePath $file.FullName
                $target = Join-Path $stage $relative
                New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $target
            }
        }
        Move-Item -LiteralPath $current -Destination $backup
    }
    Move-Item -LiteralPath $stage -Destination $current
    $swapped = $true
    $registered = $true
    Register-CheckTokens $InstallDir $RegistryRoot
    New-Item -ItemType Directory -Path $ShortcutDir -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcut)
    $link.TargetPath = Join-Path $current 'app\CheckTokens.exe'
    $link.WorkingDirectory = Join-Path $current 'app'
    $link.Description = 'Count text tokens locally'
    $link.Save()
    Notify-Explorer
} catch {
    if ($swapped) { Remove-ManagedTree $current $InstallDir }
    if (Test-Path -LiteralPath $backup) { Move-Item -LiteralPath $backup -Destination $current }
    if ($registered) {
        if ($oldState) { Register-CheckTokens $InstallDir $RegistryRoot }
        else { Unregister-CheckTokens $RegistryRoot }
    }
    throw
} finally {
    Remove-ManagedTree $stage $InstallDir
}
Remove-ManagedTree $backup $InstallDir
Write-Host "Installed CheckTokens in $current"
Write-Host 'Select files in Explorer, right-click, and choose Check Tokens.'
Write-Host "Uninstall: $current\uninstall.cmd"
