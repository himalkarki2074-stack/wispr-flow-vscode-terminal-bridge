# Adds a Startup-folder shortcut so the bridge launches hidden at every login, then starts it now.

$ErrorActionPreference = 'Stop'

$script = Join-Path $PSScriptRoot 'flow_terminal_bridge.py'
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    throw 'pythonw.exe was not found on PATH. Install Python from python.org and tick "Add python.exe to PATH".'
}

$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Wispr Flow Terminal Bridge.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "`"$script`""
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = 'Pastes Wispr Flow dictations into the VS Code terminal'
$shortcut.Save()

Start-Process -FilePath $pythonw -ArgumentList "`"$script`"" -WorkingDirectory $PSScriptRoot

Write-Host "Startup shortcut created: $shortcutPath"
Write-Host 'The bridge is running. Dictate into the VS Code terminal to test it.'
