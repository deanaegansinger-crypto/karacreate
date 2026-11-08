@echo off
setlocal
cd /d "%~dp0"
title Karaoke Maker setup

echo Setting up Karaoke Maker.
echo This downloads the AI tools and models, about 5 GB, and can take 15-30 minutes.
echo.

rem The AI tools work with Python 3.10 to 3.13. Newer Pythons (3.14, 3.15...)
rem are missing parts they need, so look for a suitable one alongside them.
set "TRIED="
:findpython
set "PY="
for %%V in (3.13 3.12 3.11 3.10) do if not defined PY py -%%V -c "pass" >nul 2>nul && set "PY=py -%%V"
for %%D in (Python313 Python312 Python311 Python310) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\%%D\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\%%D\python.exe"
  if not defined PY if exist "%ProgramFiles%\%%D\python.exe" set PY="%ProgramFiles%\%%D\python.exe"
)
if not defined PY python -c "import sys; sys.exit(not (3,10) <= sys.version_info[:2] <= (3,13))" >nul 2>nul && set "PY=python"
if not defined PY goto nopython

echo Using:
%PY% --version
echo.

rem A setup folder made by an unsuitable Python is replaced.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(not (3,10) <= sys.version_info[:2] <= (3,13))" >nul 2>nul || rmdir /s /q .venv
)
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
echo Downloading the word-recognition models now, about 2 GB, so the first song does not wait...
"%VPY%" -c "from faster_whisper import WhisperModel; WhisperModel('turbo', device='cpu', compute_type='int8')" || goto failed
"%VPY%" -c "import whisperx; whisperx.load_align_model('en', 'cpu')" || goto failed
echo.
echo All set. Drag a song onto "Make Karaoke.bat" to make a karaoke track.
pause
exit /b 0

:nopython
if defined TRIED goto manualpython
echo Karaoke Maker needs Python 3.13. The Pythons found on this PC are:
py -0 2>nul || echo    none
echo.
echo Python 3.14 and newer are too new for the AI tools Karaoke Maker uses.
echo Python 3.13 can be installed alongside them: you don't need to remove anything.
echo.
where winget >nul 2>nul || goto manualpython
choice /c YN /m "Install Python 3.13 now"
if errorlevel 2 goto manualpython
winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements
set "TRIED=1"
echo.
goto findpython

:manualpython
echo.
echo Please install Python 3.13 from https://www.python.org/downloads/windows/
echo (scroll down to the latest "Python 3.13" release and pick "Windows installer (64-bit)"),
echo then run Install.bat again.
pause
exit /b 1

:failed
echo.
echo Setup did not finish: see the messages above.
pause
exit /b 1
