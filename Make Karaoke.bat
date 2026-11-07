@echo off
setlocal
title Karaoke Maker
set "HERE=%~dp0"
set "PY=%HERE%.venv\Scripts\python.exe"
set "PYTHONPATH=%HERE%"
if not exist "%PY%" goto noinstall
if "%~1"=="" goto nofile

rem Step 1 for every song first: the slow part, and it needs no one watching.
for %%F in (%*) do (
  echo.
  echo === %%~nxF ===
  "%PY%" -m karaoke_maker prepare "%%~fF" || goto failed
)

rem Step 2: check the lyrics of each song, then make its MP3+CDG.
for %%F in (%*) do (
  echo.
  echo === Check the lyrics for %%~nxF, then save and close Notepad ===
  notepad "%%~dpnF (karaoke work)\lyrics.txt"
  "%PY%" -m karaoke_maker build "%%~dpnF (karaoke work)" || goto failed
)

echo.
echo All done. The MP3 and CDG files are next to your songs.
pause
exit /b 0

:noinstall
echo Run Install.bat first.
pause
exit /b 1

:nofile
echo Drag one or more songs, MP4 or MP3, onto "Make Karaoke.bat".
pause
exit /b 1

:failed
echo.
echo Something went wrong: see the messages above.
pause
exit /b 1
