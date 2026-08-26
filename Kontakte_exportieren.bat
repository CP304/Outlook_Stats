@echo off
rem ---------------------------------------------------------------------
rem  Externe Kontakte als Excel exportieren
rem
rem  Ergebnis: Externe_Kontakte.xlsx -- alle externen Mailadressen mit
rem  Unternehmen, Volumen, Richtung und letztem Kontakt.
rem  Ausgelassen werden nur Junk und Papierkorb.
rem
rem  Hinweis: Die Firmenerkennung aus Signaturen liest das Ende der
rem  Mailtexte.  Das ist die einzige Stelle des Programms, die Mailtexte
rem  anfasst -- deshalb wird ausdruecklich gefragt.  Gespeichert wird
rem  davon nur der gefundene Firmenname.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set /p DOMAIN="  Interne Maildomain (z. B. firma.de): "
if "%DOMAIN%"=="" (
    echo   Ohne interne Domain laesst sich intern nicht von extern unterscheiden.
    pause
    exit /b 1
)

set SIG=n
set /p SIG="  Firmennamen aus Signaturen lesen? [j/N]: "

if /i "%SIG%"=="j" (
    python -m okoa kontakte --domain "%DOMAIN%" --signaturen
) else (
    python -m okoa kontakte --domain "%DOMAIN%"
)
pause
endlocal
