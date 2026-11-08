@echo off
setlocal
cd /d "%~dp0"
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo Run Install.bat first.
  if not "%~1"=="nopause" pause
  exit /b 1
)

rem Drag-and-drop for the window.
"%VPY%" -m pip install -q --disable-pip-version-check tkinterdnd2

rem A "Karaoke Maker" shortcut on the desktop that opens the window.
set "TARGET=%CD%\.venv\Scripts\pythonw.exe"
set "HOME_DIR=%CD%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop = [Environment]::GetFolderPath('Desktop');" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Karaoke Maker.lnk'));" ^
  "$s.TargetPath = $env:TARGET; $s.Arguments = '-m karaoke_maker.gui';" ^
  "$s.WorkingDirectory = $env:HOME_DIR; $s.IconLocation = (Join-Path $env:HOME_DIR 'karaoke.ico');" ^
  "$s.Description = 'Make MP3+CDG karaoke tracks'; $s.Save()"
if errorlevel 1 (
  echo Couldn't make the desktop shortcut.
) else (
  echo Made the "Karaoke Maker" shortcut on your desktop.
)
if not "%~1"=="nopause" pause
