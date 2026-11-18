@echo off
cd /d "%~dp0"
if exist "RekrutacjaPK.exe" (
  start "" "RekrutacjaPK.exe"
) else if exist "..\.venv\Scripts\pythonw.exe" (
  start "" "..\.venv\Scripts\pythonw.exe" "start.py"
) else if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "start.py"
) else (
  echo Brak srodowiska. Uzyj gotowego pakietu przenosnego lub instrukcji README.md.
  pause
)
