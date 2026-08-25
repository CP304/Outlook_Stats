"""Report und Outlook-Anbindung.

Die Extraktion laesst sich ohne Windows nicht ausfuehren -- pruefbar ist aber,
dass sie ausschliesslich liest und dass die Aufloesungslogik stimmt.
"""

import re
from datetime import datetime

import pytest

from okoa import extract_outlook, pipeline, report
from okoa.config import Config
from okoa.synthetic import postfach_erzeugen


def _quelltext_ohne_text(modul) -> str:
    """Quelltext ohne Kommentare und Docstrings.

    Sonst schlaegt der Test bereits an, wenn die Dokumentation erklaert, was
    das Modul bewusst NICHT tut.
    """
    import ast
    import inspect

    baum = ast.parse(inspect.getsource(modul))
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)) and ast.get_docstring(knoten):
            knoten.body = knoten.body[1:]
    return ast.unparse(baum)


@pytest.fixture
def bericht(tmp_path):
    ergebnis = pipeline.auswerten(
        postfach_erzeugen(150, seed=3), Config(interne_domains=["firma.de"]),
        tmp_path, bezugszeitpunkt=datetime(2026, 6, 30))
    return (tmp_path / pipeline.DATEI_REPORT).read_text(encoding="utf-8")


def test_report_ist_selbsttragend(bericht):
    """Keine externen Assets -- die Datei muss offline und per Mail funktionieren."""
    for verboten in ("http://", "https://", "<script", "cdn.", "src=\"//"):
        assert verboten not in bericht


def test_report_zeigt_beide_zaehlweisen(bericht):
    assert "Vorgänge" in bericht and "Nachrichten" in bericht
    assert "Ausgangshypothese und Messergebnis" in bericht


def test_report_nennt_die_grenzen(bericht):
    """Der Abschnitt schuetzt vor dem naheliegendsten Missverstaendnis."""
    assert "Was diese Zahlen nicht beweisen" in bericht
    assert "Benchmark" in bericht
    assert "Meetings fehlen" in bericht


def test_report_ohne_ampeln_und_zielwerte(bericht):
    """Eine rote Kachel wuerde eine Bewertung behaupten, die die Daten nicht hergeben."""
    # Keine Signalfarben und keine Sollwerte -- eine rote Kachel wuerde eine
    # Bewertung behaupten, die die Daten nicht hergeben.
    for verboten in ("Ziel:", "Sollwert", "#d00", "#ff0000", "red;", "green;",
                     "#c00", "#e74c3c", "#2ecc71"):
        assert verboten not in bericht
    # Das Fehlen eines Zielwerts darf der Text dagegen ausdruecklich benennen.
    assert "keinen Zielwert" in bericht
    assert "ohne Ampel" in bericht


def test_report_enthaelt_keine_mailadressen(bericht):
    treffer = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", bericht)
    assert not treffer, f"Der Report darf keine Adressen zeigen: {treffer[:3]}"


def test_report_weist_datenqualitaet_aus(bericht):
    for pflicht in ("Entfernte Duplikate", "unauflösbarer Adressen",
                    "Ersatzverfahren", "Abweichung der Kern-KPIs"):
        assert pflicht in bericht


def test_hinweis_wenn_mapping_fehlt(bericht):
    assert "mapping_personen" in bericht


# ------------------------------------------------------------- Extraktion

def test_extraktion_schreibt_nicht():
    """Read-only ist eine Zusage, keine Absicht: kein Save, kein Move, kein Delete."""
    quelle = _quelltext_ohne_text(extract_outlook)
    for verboten in (".Save()", ".Move(", ".Delete()", ".Send()", "UnRead",
                     ".Body", "MarkAsTask", "PropertyAccessor.SetProperty"):
        assert verboten not in quelle, f"'{verboten}' wuerde das Postfach anfassen"


def test_extraktion_ohne_outlook_meldet_verstaendlich():
    with pytest.raises(extract_outlook.OutlookNichtVerfuegbar) as fehler:
        extract_outlook.verbinden()
    assert "pywin32" in str(fehler.value) or "Outlook" in str(fehler.value)


def test_smtp_aufloesung_nimmt_direkte_adresse():
    class Attrappe:
        pass

    assert extract_outlook._smtp_aufloesen(Attrappe(), "Max@Firma.de", "SMTP") == "max@firma.de"


class _Zugriff:
    """Tut so, als lieferte MAPI die SMTP-Adresse."""

    def GetProperty(self, name):
        assert name == extract_outlook.PR_SMTP_ADDRESS
        return "Max.Mustermann@firma.de"


def test_smtp_aufloesung_greift_bei_x500_auf_mapi_zurueck():
    """Ohne diesen Weg waere jede interne Mail falsch klassifiziert."""
    class Attrappe:
        PropertyAccessor = _Zugriff()

    x500 = "/o=Firma/ou=Gruppe/cn=Recipients/cn=abc"
    assert extract_outlook._smtp_aufloesen(Attrappe(), x500, "EX") == "max.mustermann@firma.de"


def test_smtp_aufloesung_raet_nicht():
    class Attrappe:
        pass

    x500 = "/o=Firma/ou=Gruppe/cn=Recipients/cn=abc"
    ergebnis = extract_outlook._smtp_aufloesen(Attrappe(), x500, "EX")
    assert "@" not in ergebnis, "Eine nicht aufloesbare Adresse wird nicht erfunden"


def test_fremde_postfaecher_sind_per_vorgabe_aus():
    assert Config().fremde_postfaecher_einbeziehen is False
