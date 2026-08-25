@echo off
rem ---------------------------------------------------------------------
rem  Outlook-Kommunikationsanalyse starten
rem
rem  Liest das eigene Postfach ausschliesslich lesend aus und wertet nur
rem  Metadaten aus -- keine Mailtexte, keine Betreffzeilen, keine
rem  Anhangnamen.  Am Postfach wird nichts veraendert.
rem
rem  Beim ersten Start werden fehlende Pakete installiert.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo   Python wurde nicht gefunden.
    echo   Bitte Python 3.11 oder neuer installieren: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

python -c "import win32com.client" >nul 2>nul
if errorlevel 1 (
    echo.
    echo   Erststart: benoetigte Pakete werden installiert ...
    echo.
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   Die Installation ist fehlgeschlagen.
        echo.
        pause
        exit /b 1
    )
)

set /p DOMAIN="  Interne Maildomain (z. B. firma.de): "
if "%DOMAIN%"=="" (
    echo   Ohne interne Domain laesst sich intern nicht von extern unterscheiden.
    pause
    exit /b 1
)

set MONATE=12
set /p MONATE="  Zeitraum in Monaten [12]: "

python -m okoa analyse --domain "%DOMAIN%" --monate %MONATE%
if errorlevel 1 (
    echo.
    echo   Die Auswertung wurde mit einem Fehler beendet.
    echo.
)
pause
endlocal
