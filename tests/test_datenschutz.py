"""Die Zusagen aus docs/08-datenschutz.md, als Test.

Diese Datei ist der Nachweis, mit dem sich das Verfahren gegenueber
Datenschutzbeauftragtem und Betriebsrat belegen laesst.  Faellt einer dieser
Tests, ist die Zusage gebrochen.
"""

import json
from datetime import datetime

import pytest

from okoa import pipeline, team_export
from okoa.config import Config
from okoa.model import cache_lesen
from okoa.synthetic import postfach_erzeugen


@pytest.fixture
def ergebnis(tmp_path):
    return pipeline.auswerten(
        postfach_erzeugen(120, seed=7), Config(interne_domains=["firma.de"]),
        tmp_path, bezugszeitpunkt=datetime(2026, 6, 30),
    )


# ------------------------------------------------- Zwischendatei ohne Inhalte

def test_zwischendatei_enthaelt_keine_betreffe(tmp_path, ergebnis):
    """Ohne Vollerhebung bleibt die Betreffspalte leer.

    Die Spalte existiert im Kopf, damit dieselbe Datei beide Betriebsarten
    traegt -- gefuellt wird sie nur, wenn die Vollerhebung eingeschaltet ist.
    """
    zeilen = (tmp_path / pipeline.DATEI_CACHE).read_text(encoding="utf-8").splitlines()
    kopf = zeilen[0].split(",")
    stelle = kopf.index("betreff")
    for zeile in zeilen[1:]:
        assert zeile.split(",")[stelle] == "", "Betreff darf hier nicht gespeichert sein"
    for verboten in ("subject", "body", "conversation_id", "betreff_hash"):
        assert verboten not in zeilen[0].lower()


def test_vollerhebung_speichert_betreff_und_anhangnamen(tmp_path):
    """Die Vollerhebung tut ausdruecklich, was Stufe 1 unterlaesst.

    Sie ist fuer das eigene Postfach gedacht -- deshalb ist sie abschaltbar
    und nicht die Vorgabe.
    """
    config = Config(interne_domains=["firma.de"], vollerhebung=True)
    assert Config().vollerhebung is False
    pipeline.auswerten(postfach_erzeugen(60, seed=5), config, tmp_path,
                       bezugszeitpunkt=datetime(2026, 6, 30))
    nachrichten = cache_lesen(tmp_path / pipeline.DATEI_CACHE)
    assert any(n.betreff for n in nachrichten)
    assert any(n.anhangnamen for n in nachrichten)
    assert any(n.groesse for n in nachrichten)


def test_zwischendatei_ist_wieder_einlesbar(tmp_path, ergebnis):
    nachrichten = cache_lesen(tmp_path / pipeline.DATEI_CACHE)
    assert nachrichten and all(n.thread_id_conv for n in nachrichten)


def test_auswertung_ist_reproduzierbar(tmp_path, ergebnis):
    """Gleiche Eingabe, gleiches Ergebnis -- sonst ist nichts nachpruefbar."""
    zweiter = pipeline.aus_cache(tmp_path, Config(interne_domains=["firma.de"]),
                                 bezugszeitpunkt=datetime(2026, 6, 30))
    assert zweiter["export"] == ergebnis["export"]


# ----------------------------------------------------------- Teamexport

def test_export_enthaelt_nur_erlaubte_felder(ergebnis):
    assert set(ergebnis["export"]) <= set(team_export.EXPORT_FELDER)


def test_export_enthaelt_keine_personenbezogenen_daten(ergebnis):
    text = json.dumps(ergebnis["export"], ensure_ascii=False).lower()
    for verboten in ("@", "firma.de", "lieferant", "person", "ich@", "postfach"):
        assert verboten not in text, f"'{verboten}' darf den Rechner nicht verlassen"


def test_export_enthaelt_keine_uhrzeiten_und_kein_tagesdatum(ergebnis):
    export = ergebnis["export"]
    assert "stunden" not in export
    # Monatsaufloesung: 'JJJJ-MM', kein Tag.
    assert len(export["zeitraum_von"]) == 7
    assert len(export["zeitraum_bis"]) == 7


def test_export_verweigert_zusaetzliche_felder(ergebnis, tmp_path):
    """Ein Denkfehler soll auffallen, nicht durchrutschen."""
    with pytest.raises(team_export.ExportFehler):
        team_export.schreiben({**ergebnis["export"], "absender": "max@firma.de"}, tmp_path)


def test_dateiname_enthaelt_keinen_benutzernamen(ergebnis, tmp_path):
    pfad = team_export.schreiben(ergebnis["export"], tmp_path)
    assert pfad.stem.startswith("team_export_")
    assert len(pfad.stem.split("_")[-1]) == 16      # Zufalls-ID


def test_klartextanzeige_zeigt_alles_was_geteilt_wird(ergebnis):
    text = team_export.als_klartext(ergebnis["export"])
    for feld in ergebnis["export"]:
        assert feld in text, "Der Teilnehmer muss jedes uebermittelte Feld sehen"


# --------------------------------------------------- Mindestgruppengroesse

def _exporte(anzahl, tmp_path):
    daten = []
    for seed in range(anzahl):
        ergebnis = pipeline.auswerten(
            postfach_erzeugen(80, seed=seed), Config(interne_domains=["firma.de"]),
            tmp_path / f"lauf{seed}", bezugszeitpunkt=datetime(2026, 6, 30))
        daten.append(ergebnis["export"])
    return daten


def test_unter_fuenf_teilnehmern_kein_ergebnis(tmp_path):
    with pytest.raises(team_export.ZuWenigTeilnehmer):
        team_export.zusammenfuehren(_exporte(4, tmp_path))


def test_ab_fuenf_teilnehmern_ergebnis(tmp_path):
    ergebnis = team_export.zusammenfuehren(_exporte(5, tmp_path))
    assert ergebnis["n_teilnehmer"] == 5
    assert isinstance(ergebnis["kennzahlen"]["aussenorientierung"], dict)


def test_gruppenergebnis_ohne_minima_und_maxima(tmp_path):
    """Spannweiten verraten Ausreisser und damit Personen."""
    ergebnis = team_export.zusammenfuehren(_exporte(5, tmp_path))
    text = json.dumps(ergebnis).lower()
    for verboten in ("min", "max", "spannweite", "einzel"):
        assert verboten not in text


def test_zellensperre_bei_duenner_besetzung(tmp_path):
    """Eine Kategorie, die nur zwei Teilnehmer melden, wird nicht ausgewiesen."""
    exporte = _exporte(5, tmp_path)
    for i, export in enumerate(exporte):
        export["fachbereichsanteile"] = ({"Nische": 1.0} if i < 2 else {"Breit": 1.0})
    ergebnis = team_export.zusammenfuehren(exporte)
    assert ergebnis["fachbereiche"]["Nische"] == team_export.NICHT_AUSGEWIESEN


def test_zusammenfuehrung_kennt_keine_rohdaten():
    """Der Merge-Code darf konstruktionsbedingt keinen Zugang zu Postfaechern
    haben -- das ist das Kernargument gegenueber Betriebsrat und DSB."""
    import inspect

    quelle = inspect.getsource(team_export)
    for verboten in ("win32com", "extract_outlook", "cache_lesen", "Outlook"):
        assert verboten not in quelle


def test_merge_liest_nur_exportdateien(tmp_path):
    (tmp_path / "messages.csv").write_text("etwas anderes", encoding="utf-8")
    (tmp_path / "team_export_abc.json").write_text(json.dumps({"kein": "export"}),
                                                   encoding="utf-8")
    assert team_export.einlesen(tmp_path) == []
