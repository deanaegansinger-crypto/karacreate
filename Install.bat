@echo off
setlocal
cd /d "%~dp0"
title Karaoke Maker setup

echo Setting up Karaoke Maker.
echo This downloads the AI tools, about 3 GB, and can take 10-20 minutes.
echo.

set "PY="
for %%V in (3.12 3.13 3.11 3.10) do if not defined PY py -%%V -c "pass" >nul 2>nul && set "PY=py -%%V"
if not defined PY python -c "import sys; sys.exit(not (3,10) <= sys.version_info[:2] <= (3,13))" >nul 2>nul && set "PY=python"
if not defined PY goto nopython

if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || goto failed
set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip || goto failed
"%VPY%" -m pip install -r requirements.txt || goto failed

where nvidia-smi >nul 2>nul
if errorlevel 1 goto nogpu
echo.
echo NVIDIA graphics card found: installing the faster graphics-card version.
"%VPY%" setup_gpu.py
:nogpu

echo.
echo Downloading the AI models now, so the first song does not wait for them...
"%VPY%" -c "from demucs.pretrained import get_model; get_model('htdemucs')"
echo.
echo All set. Drag a song onto "Make Karaoke.bat" to make a karaoke track.
pause
exit /b 0

:nopython
echo Python 3.12 is needed. Get it from https://www.python.org/downloads/windows/
echo or the Microsoft Store, then run Install.bat again.
pause
exit /b 1

:failed
echo.
echo Setup did not finish: see the messages above.
pause
exit /b 1
