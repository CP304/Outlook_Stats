"""Weitergabe von Einstellungen und Zuordnungen.

Zwei Zusagen: Die Pflegearbeit geht mit, die Postfachdaten des Erstellers
nicht. Und wer selbst gepflegt hat, verliert seine Arbeit nicht, nur weil
jemand eine Datei geschickt hat.
"""

import json

import pytest

from okoa import einstellungen, mapping
from okoa.config import Config


@pytest.fixture
def quelle(tmp_path):
    """Ein Arbeitsordner mit gepflegten Zuordnungen."""
    ordner = tmp_path / "quelle"
    ordner.mkdir()
    Config(interne_domains=["firma.de"], konzern_domains=["schwester.com"],
           zeitraum_monate=24).speichern(ordner / "config.json")
    mapping.schreiben([
        {"E-Mail": "a@firma.de", "Anzeigename": "A", "Vorgaenge": 84,
         "Nachrichten": 310, "Anteil kumuliert": 0.12,
         "Fachbereich": "Engineering", "Rolle": "Konstruktion"},
        {"E-Mail": "b@firma.de", "Anzeigename": "B", "Vorgaenge": 40,
         "Nachrichten": 120, "Anteil kumuliert": 0.2,
         "Fachbereich": "Qualität", "Rolle": ""},
        # Ungepflegt -- soll nicht mitwandern.
        {"E-Mail": "c@firma.de", "Anzeigename": "C", "Vorgaenge": 3,
         "Nachrichten": 5, "Anteil kumuliert": 0.21, "Fachbereich": "", "Rolle": ""},
    ], mapping.SPALTEN_PERSONEN, ordner / "mapping_personen.xlsx")
    mapping.schreiben([
        {"Domain": "lieferant.com", "Vorgaenge": 20, "Nachrichten": 60,
         "Anteil kumuliert": 0.5, "Kategorie": "Lieferant"},
    ], mapping.SPALTEN_DOMAINS, ordner / "mapping_domains.xlsx")
    return ordner


# ------------------------------------------------------------------ Export

def test_export_enthaelt_die_pflegearbeit(quelle, tmp_path):
    ziel, info = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert info["fachbereiche"] == 2          # die ungepflegte Zeile fehlt
    assert daten["konfiguration"]["interne_domains"] == ["firma.de"]
    assert daten["konfiguration"]["konzern_domains"] == ["schwester.com"]
    assert daten["konfiguration"]["zeitraum_monate"] == 24


def test_export_ohne_volumendaten(quelle, tmp_path):
    """'Vorgaenge: 84' sagt, mit wem der Ersteller wie viel zu tun hatte --
    das sind seine Postfachdaten, nicht die des Unternehmens."""
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    text = ziel.read_text(encoding="utf-8")
    for verboten in ("Vorgaenge", "Vorgänge", "Nachrichten", "Anteil kumuliert",
                     "84", "310"):
        assert verboten not in text
    assert not einstellungen.enthaelt_volumendaten(ziel)


def test_ungepflegte_zeilen_wandern_nicht_mit(quelle, tmp_path):
    """Sonst bekommt der Empfänger nur eine Liste fremder Adressen."""
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    adressen = {z["E-Mail"] for z in json.loads(ziel.read_text(encoding="utf-8"))["fachbereiche"]}
    assert adressen == {"a@firma.de", "b@firma.de"}


def test_export_meldet_wenn_nichts_da_ist(tmp_path):
    leer = tmp_path / "leer"
    leer.mkdir()
    with pytest.raises(einstellungen.ExportFehler):
        einstellungen.exportieren(leer, tmp_path / "Einstellungen.json")


# ------------------------------------------------------------------ Import

def test_import_in_leeren_ordner(quelle, tmp_path):
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    neu = tmp_path / "neu"
    bericht = einstellungen.importieren(ziel, neu)

    assert bericht["fachbereiche"]["neu"] == 2
    assert Config.laden(neu / "config.json").interne_domains == ["firma.de"]
    zuordnung = mapping.zuordnung_lesen(neu / "mapping_personen.xlsx",
                                        "E-Mail", "Fachbereich")
    assert zuordnung == {"a@firma.de": "Engineering", "b@firma.de": "Qualität"}


def test_eigene_zuordnung_gewinnt(quelle, tmp_path):
    """Wer selbst gepflegt hat, verliert seine Arbeit nicht."""
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    ziel_ordner = tmp_path / "ziel"
    ziel_ordner.mkdir()
    mapping.schreiben([{"E-Mail": "a@firma.de", "Fachbereich": "Produktion"}],
                      mapping.SPALTEN_PERSONEN, ziel_ordner / "mapping_personen.xlsx")

    bericht = einstellungen.importieren(ziel, ziel_ordner)
    assert bericht["fachbereiche"]["behalten"] == 1
    zuordnung = mapping.zuordnung_lesen(ziel_ordner / "mapping_personen.xlsx",
                                        "E-Mail", "Fachbereich")
    assert zuordnung["a@firma.de"] == "Produktion"
    assert zuordnung["b@firma.de"] == "Qualität"   # das Neue kommt trotzdem dazu


def test_ueberschreiben_auf_wunsch(quelle, tmp_path):
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    ziel_ordner = tmp_path / "ziel"
    ziel_ordner.mkdir()
    mapping.schreiben([{"E-Mail": "a@firma.de", "Fachbereich": "Produktion"}],
                      mapping.SPALTEN_PERSONEN, ziel_ordner / "mapping_personen.xlsx")

    bericht = einstellungen.importieren(ziel, ziel_ordner, ueberschreiben=True)
    assert bericht["fachbereiche"]["ueberschrieben"] == 1
    assert mapping.zuordnung_lesen(ziel_ordner / "mapping_personen.xlsx",
                                   "E-Mail", "Fachbereich")["a@firma.de"] == "Engineering"


def test_leeres_eigenes_feld_wird_ergaenzt(quelle, tmp_path):
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    ziel_ordner = tmp_path / "ziel"
    ziel_ordner.mkdir()
    mapping.schreiben([{"E-Mail": "a@firma.de", "Fachbereich": "", "Rolle": ""}],
                      mapping.SPALTEN_PERSONEN, ziel_ordner / "mapping_personen.xlsx")

    bericht = einstellungen.importieren(ziel, ziel_ordner)
    assert bericht["fachbereiche"]["ergaenzt"] >= 1
    assert mapping.zuordnung_lesen(ziel_ordner / "mapping_personen.xlsx",
                                   "E-Mail", "Fachbereich")["a@firma.de"] == "Engineering"


def test_konfiguration_kann_ausgelassen_werden(quelle, tmp_path):
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    ziel_ordner = tmp_path / "ziel"
    ziel_ordner.mkdir()
    Config(interne_domains=["andere.de"]).speichern(ziel_ordner / "config.json")

    einstellungen.importieren(ziel, ziel_ordner, konfiguration_uebernehmen=False)
    assert Config.laden(ziel_ordner / "config.json").interne_domains == ["andere.de"]
    assert mapping.zuordnung_lesen(ziel_ordner / "mapping_personen.xlsx",
                                   "E-Mail", "Fachbereich")


def test_import_ist_wiederholbar(quelle, tmp_path):
    """Zweimal einlesen darf nicht doppelte Zeilen erzeugen."""
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    ziel_ordner = tmp_path / "ziel"
    einstellungen.importieren(ziel, ziel_ordner)
    einstellungen.importieren(ziel, ziel_ordner)
    assert len(mapping.lesen(ziel_ordner / "mapping_personen.xlsx")) == 2


# ------------------------------------------------------------ Fehlerfaelle

def test_fremde_datei_wird_abgelehnt(tmp_path):
    datei = tmp_path / "irgendwas.json"
    datei.write_text(json.dumps({"etwas": "anderes"}), encoding="utf-8")
    with pytest.raises(einstellungen.ImportFehler):
        einstellungen.lesen(datei)


def test_beschaedigte_datei_wird_abgelehnt(tmp_path):
    datei = tmp_path / "kaputt.json"
    datei.write_text("{kein json", encoding="utf-8")
    with pytest.raises(einstellungen.ImportFehler):
        einstellungen.lesen(datei)


def test_neueres_format_wird_abgelehnt(quelle, tmp_path):
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    daten["format"] = einstellungen.DATEIFORMAT + 1
    ziel.write_text(json.dumps(daten), encoding="utf-8")
    with pytest.raises(einstellungen.ImportFehler, match="neueren"):
        einstellungen.lesen(ziel)


def test_unbrauchbare_konfiguration_wird_abgelehnt(quelle, tmp_path):
    ziel, _ = einstellungen.exportieren(quelle, tmp_path / "Einstellungen.json")
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    daten["konfiguration"]["interne_domains"] = []
    ziel.write_text(json.dumps(daten), encoding="utf-8")
    with pytest.raises(einstellungen.ImportFehler):
        einstellungen.importieren(ziel, tmp_path / "ziel")
