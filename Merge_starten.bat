@echo off
rem ---------------------------------------------------------------------
rem  Teamexporte zusammenfuehren
rem
rem  Liest ausschliesslich team_export-Dateien.  Dieser Schritt hat
rem  konstruktionsbedingt keinen Zugang zu Postfaechern oder Rohdaten.
rem  Unter fuenf Teilnehmern wird bewusst kein Ergebnis ausgegeben.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set ORDNER=%CD%\Eingang
set /p ORDNER="  Ordner mit den eingegangenen Dateien [%ORDNER%]: "

python -m okoa merge --ordner "%ORDNER%"
pause
endlocal
