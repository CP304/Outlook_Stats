@echo off
rem ---------------------------------------------------------------------
rem  Outlook-Kommunikationsanalyse -- Oberflaeche starten
rem
rem  Doppelklick genuegt.  Es wird ausschliesslich gelesen; am Postfach
rem  aendert sich nichts.
rem
rem  Die Oberflaeche gehoert zum Lieferumfang von Python -- es muss also
rem  nichts nachinstalliert werden.  Nur fuer den Zugriff auf Outlook
rem  wird pywin32 benoetigt; das wird beim ersten Start eingerichtet.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo   Python wurde nicht gefunden.
    echo   Bitte Python 3.11 oder neuer installieren: https://www.python.org/downloads/
    echo   Wichtig: beim Installieren "Add python.exe to PATH" ankreuzen.
    echo.
    pause
    exit /b 1
)

python -c "import win32com.client" >nul 2>nul
if errorlevel 1 (
    echo.
    echo   Erststart: benoetigte Pakete werden eingerichtet ...
    echo.
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
)

start "" pythonw -m okoa
endlocal
