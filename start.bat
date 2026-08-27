@echo off
rem ---------------------------------------------------------------------
rem  Outlook-Kommunikationsanalyse starten
rem
rem  Doppelklick genuegt.  Diese Datei richtet alles selbst ein:
rem    1. Python, falls es fehlt -- erst ueber winget, sonst von python.org.
rem       Installation nur fuer den eigenen Benutzer, ohne Adminrechte.
rem    2. Die benoetigten Pakete: pywin32 fuer den Outlook-Zugriff,
rem       openpyxl fuer die Excel-Dateien.
rem
rem  Es wird ausschliesslich gelesen; am Postfach aendert sich nichts.
rem ---------------------------------------------------------------------
setlocal
rem  pushd statt cd: Liegt der Ordner auf einem Netzlaufwerk
rem  (\\server\freigabe\...), kann cmd.exe ihn nicht als Arbeitsverzeichnis
rem  setzen -- pushd haengt dafuer kurz einen Laufwerksbuchstaben ein.  Genau
rem  dieser Fall tritt ein, wenn der Ordner an Kollegen weitergegeben wird.
pushd "%~dp0" || (echo Ordner nicht erreichbar: %~dp0 & pause & exit /b 1)
set "PY="

call :python_suchen
if defined PY goto pakete

echo.
echo   Python wurde nicht gefunden und wird jetzt eingerichtet.
echo   Installation nur fuer den eigenen Benutzer -- ohne Adminrechte.
echo.

where winget >nul 2>nul
if errorlevel 1 goto direktinstallation
echo   Versuche Installation ueber winget ...
winget install --id Python.Python.3.12 -e --silent --scope user --accept-package-agreements --accept-source-agreements
call :python_suchen
if defined PY goto pakete

:direktinstallation
set "PYSETUP=%TEMP%\okoa-python-setup.exe"
echo   Lade Python 3.12 von python.org ...
where curl >nul 2>nul
if errorlevel 1 goto lade_powershell
curl -L --fail -o "%PYSETUP%" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
if not errorlevel 1 goto installieren

:lade_powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%PYSETUP%'"
if errorlevel 1 goto fehler_download
if not exist "%PYSETUP%" goto fehler_download

:installieren
echo   Installiere Python -- das dauert ein bis zwei Minuten ...
rem  Tcl/Tk wird ausdruecklich mitinstalliert; ohne das gibt es kein Fenster.
"%PYSETUP%" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_test=0
del "%PYSETUP%" >nul 2>nul
call :python_suchen
if defined PY goto pakete
goto fehler_python

rem =====================================================================
:pakete
%PY% -c "import win32com.client" >nul 2>nul
if not errorlevel 1 goto excel_paket

echo.
echo   Erststart: benoetigte Pakete werden eingerichtet ...
echo.
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
rem  Einmalige Nacharbeit von pywin32.  Scheitert sie, ist das unkritisch --
rem  fuer den lesenden Zugriff auf Outlook wird sie in aller Regel nicht
rem  gebraucht.  Deshalb wird das Ergebnis bewusst nicht geprueft.
%PY% -m pywin32_postinstall -install >nul 2>nul
rem  Nur pywin32 ist Pflicht -- ohne den Zugriff auf Outlook gibt es nichts
rem  auszuwerten.  Der Rueckgabewert von pip genuegt als Nachweis nicht: pip
rem  meldet auch dann Erfolg, wenn der Import danach scheitert.
%PY% -c "import win32com.client" >nul 2>nul
if errorlevel 1 goto fehler_pakete

:excel_paket
rem  openpyxl ist ausdruecklich optional: Ohne das Paket entstehen CSV- statt
rem  Excel-Dateien, die sich ebenso in Excel oeffnen lassen.  Daran darf der
rem  Start nicht scheitern -- ein blockierender Proxy wuerde sonst die ganze
rem  Auswertung kosten, obwohl sie vollstaendig liefe.
%PY% -c "import openpyxl" >nul 2>nul
if not errorlevel 1 goto starten
%PY% -m pip install openpyxl >nul 2>nul
%PY% -c "import openpyxl" >nul 2>nul
if not errorlevel 1 goto starten
echo.
echo   Hinweis: openpyxl liess sich nicht einrichten.  Die Auswertung laeuft
echo   vollstaendig weiter, die Tabellen entstehen als CSV statt als XLSX.
echo   Beide oeffnen sich in Excel per Doppelklick.
echo.

:starten
%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 goto fehler_tkinter
echo.
echo   Starte die Oberflaeche.  Dieses Fenster bitte offen lassen -- hier
echo   erscheinen Meldungen, falls etwas schiefgeht.
echo.
%PY% -m okoa
if errorlevel 1 goto fehler_start
popd
exit /b 0

rem =====================================================================
rem  Sucht eine brauchbare Python-Installation und setzt PY.
rem
rem  Jeder Kandidat wird wirklich ausgefuehrt.  'where python' genuegt nicht:
rem  Auf frischem Windows findet es den Platzhalter aus dem Microsoft Store,
rem  der beim Aufruf nur den Store oeffnet.  Der Launcher 'py' kommt zuerst,
rem  weil er diesen Platzhalter umgeht.  Und direkt nach einer Installation
rem  kennt diese Eingabeaufforderung den neuen PATH noch nicht -- deshalb
rem  werden zuletzt die Installationsordner direkt abgesucht.
rem =====================================================================
:python_suchen
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if errorlevel 1 goto suche_python
set "PY=py -3"
goto :eof

:suche_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if errorlevel 1 goto suche_ordner
set "PY=python"
goto :eof

:suche_ordner
for /d %%V in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :pruefe_pfad "%%~fV\python.exe"
for /d %%V in ("%ProgramFiles%\Python3*") do call :pruefe_pfad "%%~fV\python.exe"
for /d %%V in ("%ProgramFiles(x86)%\Python3*") do call :pruefe_pfad "%%~fV\python.exe"
goto :eof

:pruefe_pfad
if defined PY goto :eof
if not exist "%~1" goto :eof
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set PY="%~1"
goto :eof

rem =====================================================================
:fehler_python
echo.
echo   Python liess sich nicht automatisch einrichten.
echo   Bitte einmal von Hand installieren: https://www.python.org/downloads/
echo   Dabei "Add python.exe to PATH" ankreuzen.
echo   Danach diese Datei erneut starten.
echo.
pause
popd
exit /b 1

:fehler_download
echo.
echo   Der Download von python.org ist fehlgeschlagen.
echo   In Firmennetzen blockiert das haeufig der Proxy.
echo   Bitte Python von Hand installieren: https://www.python.org/downloads/
echo   Dabei "Add python.exe to PATH" ankreuzen.
echo.
pause
popd
exit /b 1

:fehler_pakete
echo.
echo   Die Paketinstallation ist fehlgeschlagen.
echo   In Firmennetzen blockiert das haeufig der Proxy.  Von Hand geht es so:
echo       %PY% -m pip install -r requirements.txt
echo.
pause
popd
exit /b 1

:fehler_tkinter
echo.
echo   Diese Python-Installation enthaelt kein Tcl/Tk -- ohne das gibt es
echo   kein Fenster.  Beim Installer von python.org ist es dabei, sofern
echo   die Option "tcl/tk and IDLE" nicht abgewaehlt wurde.
echo.
echo   Die Kommandozeile laeuft auch ohne Fenster:
echo       %PY% -m okoa analyse --domain firma.de
echo.
pause
popd
exit /b 1

:fehler_start
echo.
echo   Das Programm wurde mit einem Fehler beendet.  Die Meldung steht
echo   oberhalb dieser Zeilen.
echo.
pause
popd
exit /b 1
