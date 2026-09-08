Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# A PowerShell 7 parent may pass an incompatible PSModulePath to Windows PowerShell.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Management\Microsoft.PowerShell.Management.psd1') -Force
$script:OwnerId = 'CheckTokens-28e4a510-ebad-4b47-93c5-0a8511a4c1c8'
$script:ClassId = '{28e4a510-ebad-4b47-93c5-0a8511a4c1c8}'

function Get-SafePath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ($full -eq [IO.Path]::GetPathRoot($full).TrimEnd('\')) { throw 'A drive root is not an installation directory.' }
    $ancestor = $full
    while ($ancestor) {
        if (Test-Path -LiteralPath $ancestor) {
            if ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing to traverse a junction or symbolic link: $ancestor"
            }
        }
        $ancestor = [IO.Path]::GetDirectoryName($ancestor)
    }
    return $full
}

function Remove-ManagedTree([string]$Path, [string]$Root) {
    $full = Get-SafePath $Path
    $base = Get-SafePath $Root
    if (-not $full.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup path escaped installation directory.' }
    if (Test-Path -LiteralPath $full) {
        foreach ($item in Get-ChildItem -LiteralPath $full -Recurse -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Cleanup refuses reparse points.' }
        }
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

function Get-VerbKeys([string]$RegistryRoot) {
    if (-not $RegistryRoot.StartsWith('Software\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Registry root must be under HKCU Software.' }
    return @("$RegistryRoot\*\shell\CheckTokens", "$RegistryRoot\CLSID\$script:ClassId")
}

function Assert-RegistryOwnership([string]$RegistryRoot) {
    foreach ($path in Get-VerbKeys $RegistryRoot) {
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($path)
        if ($key) {
            try { if ($key.GetValue('CheckTokensOwner') -ne $script:OwnerId) { throw "An unrelated registry entry exists: $path" } }
            finally { $key.Dispose() }
        }
    }
}

function Register-CheckTokens([string]$InstallDir, [string]$RegistryRoot) {
    Assert-RegistryOwnership $RegistryRoot
    $paths = Get-VerbKeys $RegistryRoot
    $verb = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($paths[0])
    try {
        $verb.SetValue('CheckTokensOwner', $script:OwnerId)
        $verb.SetValue('', 'Check Tokens')
        $verb.SetValue('Icon', '"' + $InstallDir + '\current\app\CheckTokens.exe",0')
        $verb.SetValue('MultiSelectModel', 'Player')
        $command = $verb.CreateSubKey('command')
        try { $command.SetValue('DelegateExecute', $script:ClassId) } finally { $command.Dispose() }
    } finally { $verb.Dispose() }
    $class = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($paths[1])
    try {
        $class.SetValue('CheckTokensOwner', $script:OwnerId)
        $class.SetValue('', 'CheckTokens Explorer command')
        $server = $class.CreateSubKey('LocalServer32')
        try { $server.SetValue('', '"' + $InstallDir + '\current\app\CheckTokensShell.exe"') } finally { $server.Dispose() }
    } finally { $class.Dispose() }
}

function Unregister-CheckTokens([string]$RegistryRoot) {
    Assert-RegistryOwnership $RegistryRoot
    foreach ($path in Get-VerbKeys $RegistryRoot) { [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($path, $false) }
}

function Notify-Explorer {
    if (-not ('CheckTokensShellNotify' -as [type])) {
        Add-Type 'using System; using System.Runtime.InteropServices; public static class CheckTokensShellNotify { [DllImport("shell32.dll")] public static extern void SHChangeNotify(uint e, uint f, IntPtr a, IntPtr b); }'
    }
    [CheckTokensShellNotify]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
}

function Assert-AppClosed([string]$InstallDir) {
    $prefix = $InstallDir + '\current\app\'
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        $running = @(Get-Process -Name CheckTokens,checktokens-cli,CheckTokensShell -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) })
        if (-not $running.Count) { return }
        if (@($running | Where-Object ProcessName -ne 'CheckTokensShell').Count) { throw 'Close CheckTokens windows and CLI jobs before installing or uninstalling.' }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'The Explorer command is still active. Try again in a few seconds.'
}
