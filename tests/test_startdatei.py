"""Prüfung der Startdatei.

Windows lässt sich hier nicht ausführen — aber die Fehler, die eine
Batchdatei still falsch laufen lassen, sind statisch prüfbar: ein Sprung ins
Leere bricht wortlos ab, eine fehlende Zeilenendung lässt Sprungmarken
verfehlen, und ein Umlaut wird auf einer deutschen Konsole zu Kauderwelsch.
"""

import re
from pathlib import Path

import pytest


STARTDATEI = Path(__file__).resolve().parent.parent / "start.bat"


@pytest.fixture(scope="module")
def roh() -> bytes:
    return STARTDATEI.read_bytes()


@pytest.fixture(scope="module")
def text(roh) -> str:
    return roh.decode("ascii")


@pytest.fixture(scope="module")
def zeilen(text) -> list[str]:
    return [z.strip() for z in text.splitlines()]


def _ist_befehl(zeile: str) -> bool:
    """Kommentarzeilen sind kein Code -- sonst prueft man seine eigene Prosa."""
    schlank = zeile.strip().lower()
    return bool(schlank) and not schlank.startswith(("rem ", "::", "@rem"))


def _marken(zeilen) -> set[str]:
    """Nur echte Sprungmarken: eine Zeile, die mit dem Doppelpunkt beginnt."""
    return {z[1:].split()[0].lower() for z in zeilen
            if z.startswith(":") and not z.startswith("::")}


def _abschnitt(text: str, marke: str) -> str:
    """Der Code zwischen einer Sprungmarke und der naechsten.

    Zeilenanfang-genau: ':python_suchen' steht auch in 'call :python_suchen',
    und ein einfaches split traefe diese Fundstelle zuerst.
    """
    treffer = re.search(rf"^:{marke}\s*$", text, re.MULTILINE)
    assert treffer, f"Sprungmarke :{marke} fehlt"
    rest = text[treffer.end():]
    naechste = re.search(r"^:", rest, re.MULTILINE)
    return rest[:naechste.start()] if naechste else rest


def _markenposition(text: str, marke: str) -> int:
    treffer = re.search(rf"^:{marke}\s*$", text, re.MULTILINE)
    assert treffer, f"Sprungmarke :{marke} fehlt"
    return treffer.start()


def _spruenge(zeilen) -> list[tuple[str, str]]:
    ziele = []
    for zeile in zeilen:
        if not _ist_befehl(zeile):
            continue
        for treffer in re.finditer(r"\b(?:goto|call)\s+:?([A-Za-z_][\w]*)", zeile):
            ziele.append((zeile, treffer.group(1).lower()))
    return ziele


# --------------------------------------------------------------- Format

def test_crlf_zeilenenden(roh):
    """Mit reinen LF-Enden verfehlt cmd.exe Sprungmarken."""
    assert b"\r\n" in roh
    assert re.search(rb"(?<!\r)\n", roh) is None, "Es gibt Zeilen ohne CR"


def test_reines_ascii(roh):
    """Die Konsole läuft je nach Windows in cp850 oder cp1252 -- ein Umlaut
    sieht dort unterschiedlich falsch aus. Deshalb gar keine."""
    roh.decode("ascii")


def test_beginnt_mit_echo_off(zeilen):
    assert zeilen[0] == "@echo off"


# ---------------------------------------------------------------- Sprünge

def test_jede_sprungmarke_existiert(zeilen):
    """Ein Sprung ins Leere bricht die Datei wortlos ab."""
    vorhanden = _marken(zeilen) | {"eof"}
    fehlend = {ziel for _, ziel in _spruenge(zeilen) if ziel not in vorhanden}
    assert not fehlend, f"Sprungziele ohne Marke: {sorted(fehlend)}"


def test_keine_doppelten_sprungmarken(zeilen):
    """cmd springt zur ersten -- ein Duplikat wäre ein stiller Umweg."""
    namen = [z[1:].split()[0].lower() for z in zeilen
             if z.startswith(":") and not z.startswith("::")]
    doppelt = {n for n in namen if namen.count(n) > 1}
    assert not doppelt, f"Doppelte Sprungmarken: {sorted(doppelt)}"


def test_jede_sprungmarke_wird_erreicht(zeilen):
    """Eine Marke, die niemand anspringt, ist entweder tot oder ein Tippfehler."""
    angesprungen = {ziel for _, ziel in _spruenge(zeilen)}
    unerreicht = _marken(zeilen) - angesprungen
    assert not unerreicht, f"Nie angesprungen: {sorted(unerreicht)}"


def test_unterprogramme_kehren_zurueck(text):
    """Ein per call betretener Abschnitt muss mit goto :eof enden, sonst
    laeuft er in den naechsten hinein."""
    for name in ("python_suchen", "suche_python", "suche_ordner", "pruefe_pfad"):
        assert "goto :eof" in _abschnitt(text, name), f":{name} kehrt nicht zurueck"


def test_hauptlauf_endet_vor_den_unterprogrammen(text):
    """Ohne ein exit vor dem ersten Unterprogramm faellt der normale Lauf
    hinein und startet die Suche ein zweites Mal."""
    start = _markenposition(text, "starten")
    unterprogramm = _markenposition(text, "python_suchen")
    assert start < unterprogramm, "Die Unterprogramme stehen vor dem Hauptlauf"
    assert "exit /b 0" in text[start:unterprogramm]


# ------------------------------------------------------------- Substanz

def test_python_wird_ausgefuehrt_nicht_nur_gesucht(text):
    """'where python' findet auf frischem Windows den Store-Platzhalter, der
    beim Aufruf nur den Store oeffnet. Deshalb muss jeder Kandidat wirklich
    laufen."""
    befehle = [z for z in text.splitlines() if _ist_befehl(z)]
    assert not any("where python" in z for z in befehle)
    assert text.count("import sys; raise SystemExit") >= 3


def test_launcher_kommt_vor_python(text):
    """py -3 umgeht den Store-Platzhalter -- deshalb zuerst."""
    assert text.index("py -3 -c") < text.index('python -c "import sys')


def test_installiert_ohne_adminrechte(text):
    assert "InstallAllUsers=0" in text
    assert "--scope user" in text


def test_tcltk_wird_mitinstalliert(text):
    """Ohne Tcl/Tk gibt es kein Fenster."""
    assert "Include_tcltk=1" in text


def test_beide_downloadwege(text):
    """curl fehlt auf aelteren Windows-Installationen."""
    assert "curl" in text and "Invoke-WebRequest" in text


def test_pfadsuche_nach_der_installation(text):
    """Die laufende Eingabeaufforderung kennt den neuen PATH noch nicht."""
    assert "%LOCALAPPDATA%\\Programs\\Python\\Python3*" in text
    assert "%ProgramFiles%\\Python3*" in text


def test_pakete_werden_geprueft_nicht_nur_installiert(text):
    """pip meldet auch dann Erfolg, wenn danach der Import scheitert."""
    assert text.count("import win32com.client") >= 2


def test_fehlerwege_halten_das_fenster_offen(text):
    """Ohne pause schliesst sich das Fenster und niemand liest die Meldung."""
    for marke in ("fehler_python", "fehler_download", "fehler_pakete",
                  "fehler_tkinter", "fehler_start"):
        assert "pause" in _abschnitt(text, marke), f":{marke} laeuft ohne pause"


def test_kein_pythonw(text):
    """Mit pythonw bleiben Fehler unsichtbar -- die Konsole ist Absicht."""
    assert "pythonw" not in text


def test_arbeitsverzeichnis_wird_gesetzt(text):
    """Ohne das startet ein Doppelklick im falschen Ordner."""
    assert 'pushd "%~dp0"' in text


def test_netzlaufwerk_wird_unterstuetzt(text):
    """cmd.exe kann einen UNC-Pfad nicht als Arbeitsverzeichnis setzen. Wer
    den Ordner an Kollegen weitergibt, landet aber genau dort -- pushd hängt
    dafür kurz einen Laufwerksbuchstaben ein."""
    assert 'pushd "%~dp0"' in text
    assert "cd /d" not in text


def test_jeder_ausstieg_gibt_das_laufwerk_frei(text):
    """Ohne popd bleibt der eingehängte Buchstabe bis zum Abmelden belegt."""
    ausstiege = [z for z in text.splitlines() if z.strip().startswith("exit /b")]
    assert ausstiege
    for stelle in re.finditer(r"^exit /b \d", text, re.MULTILINE):
        davor = text[:stelle.start()].splitlines()[-3:]
        assert any("popd" in z for z in davor), \
            f"exit ohne popd nach: {davor}"


# ------------------------------------------------------- Ablaufsimulation

def _ablauf(text: str) -> dict[str, list[str]]:
    """Baut den Ablaufgraphen: von welchem Abschnitt geht es wohin."""
    graph: dict[str, list[str]] = {"@start": []}
    aktuell = "@start"
    for zeile in text.splitlines():
        schlank = zeile.strip()
        if schlank.startswith(":") and not schlank.startswith("::"):
            aktuell = schlank[1:].split()[0].lower()
            graph.setdefault(aktuell, [])
            continue
        if not _ist_befehl(schlank):
            continue
        for treffer in re.finditer(r"\bgoto\s+:?([A-Za-z_][\w]*)", schlank):
            graph[aktuell].append(treffer.group(1).lower())
        if re.match(r"^exit /b", schlank):
            graph[aktuell].append("@ende")
    return graph


def test_jeder_weg_endet(text):
    """Kein Pfad darf im Nichts auslaufen -- sonst faellt der Ablauf in den
    naechsten Abschnitt und tut etwas anderes als gedacht."""
    graph = _ablauf(text)
    unterprogramme = {"python_suchen", "suche_python", "suche_ordner", "pruefe_pfad"}
    besucht: set[str] = set()

    def verfolgen(knoten: str, weg: tuple[str, ...]) -> None:
        if knoten in ("@ende", "eof") or knoten in weg:
            return
        besucht.add(knoten)
        ziele = graph.get(knoten, [])
        assert ziele or knoten in unterprogramme, \
            f"Abschnitt :{knoten} endet ohne Sprung oder exit (Weg: {' -> '.join(weg)})"
        for ziel in ziele:
            verfolgen(ziel, weg + (knoten,))

    verfolgen("@start", ())
    # Jeder Abschnitt muss vom Start aus erreichbar sein.
    unerreicht = set(graph) - besucht - unterprogramme - {"@ende"}
    assert not unerreicht, f"Nie erreichbar: {sorted(unerreicht)}"


def test_erfolgsweg_startet_das_programm(text):
    """Der Weg ohne jedes Hindernis muss beim Programmstart ankommen."""
    graph = _ablauf(text)
    assert "starten" in graph
    assert "@ende" in graph["starten"]
    abschnitt = _abschnitt(text, "starten")
    assert "%PY% -m okoa" in abschnitt


def test_installationsweg_fuehrt_zurueck_zu_den_paketen(text):
    """Nach erfolgreicher Installation darf nicht erneut installiert werden."""
    graph = _ablauf(text)
    assert "pakete" in graph["installieren"] or "pakete" in graph["@start"]
    assert "fehler_python" in graph["installieren"]


def test_nur_pywin32_ist_pflicht(text):
    """openpyxl ist optional -- ohne das Paket entstehen CSV- statt
    Excel-Dateien. Ein blockierender Proxy darf nicht die ganze Auswertung
    kosten, obwohl sie vollständig liefe."""
    pflicht = _abschnitt(text, "pakete")
    assert 'import win32com.client" >nul' in pflicht
    assert "openpyxl" not in pflicht.split("goto fehler_pakete")[0]

    optional = _abschnitt(text, "excel_paket")
    assert "openpyxl" in optional
    assert "fehler" not in optional, "openpyxl darf keinen Abbruch ausloesen"
    assert "CSV" in optional


def test_pip_rueckgabewert_ist_kein_nachweis(text):
    """pip meldet auch dann Erfolg, wenn der Import danach scheitert --
    geprüft wird deshalb der Import selbst."""
    pflicht = _abschnitt(text, "pakete")
    assert pflicht.count('import win32com.client') >= 2
