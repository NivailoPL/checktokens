@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall-windows.ps1" %*
set "result=%errorlevel%"
if not "%CHECKTOKENS_NO_PAUSE%"=="1" pause
exit /b %result%
