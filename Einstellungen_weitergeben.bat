@echo off
rem ---------------------------------------------------------------------
rem  Eigene Einstellungen weitergeben
rem
rem  Schreibt Einstellungen.json mit interner Domain, Fachbereichs-
rem  zuordnung und Domainkategorien.  Die Volumenzahlen aus der
rem  Zuordnungsdatei bleiben absichtlich draussen -- sie gehoeren zum
rem  eigenen Postfach, nicht zum Unternehmen.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"
python -m okoa export
pause
endlocal
