@echo off
setlocal
title Karaoke Maker
set "HERE=%~dp0"
set "PY=%HERE%.venv\Scripts\python.exe"
set "PYTHONPATH=%HERE%"
echo "%~dp0" | find /i "\AppData\Local\Temp\" >nul && goto inzip
if not exist "%PY%" goto noinstall
if "%~1"=="" goto nofile

rem Drag in songs, their lalal.ai files, or both: each song is done once.
rem The slow part runs for every song first; then each song's lyrics open
rem in Notepad in turn, and its MP3 and CDG are made when Notepad closes.
"%PY%" -m karaoke_maker batch %*
echo.
pause
exit /b

:inzip
echo This is running from inside the zip file. Extract the zip first ^(right-click it,
echo "Extract All..."^), run Install.bat in the extracted folder, then use the
echo "Make Karaoke.bat" there.
pause
exit /b 1

:noinstall
echo Run Install.bat first.
pause
exit /b 1

:nofile
echo Drag songs onto "Make Karaoke.bat": the song, its lalal.ai files, or all of them.
pause
exit /b 1
