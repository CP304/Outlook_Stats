@echo off
rem ---------------------------------------------------------------------
rem  Einstellungen eines Kollegen uebernehmen
rem
rem  Bei Widerspruch gilt die eigene Zuordnung -- eigene Pflegearbeit
rem  geht nicht verloren.  Neue Eintraege kommen hinzu, leere Felder
rem  werden ergaenzt.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set DATEI=Einstellungen.json
set /p DATEI="  Erhaltene Datei [%DATEI%]: "

python -m okoa import "%DATEI%"
pause
endlocal
