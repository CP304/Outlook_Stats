"""Kontakte für die Massenpflege aufbereiten.

Die heikle Stelle ist die Namenszerlegung: Ein falsch zerlegter Name fällt
beim Import nicht auf und steht danach jahrelang falsch im Adressbuch.
Deshalb im Zweifel lieber unzerlegt.
"""

from datetime import datetime

import pytest

from okoa import kontaktexport


# ------------------------------------------------------------- Namen

@pytest.mark.parametrize("eingabe,erwartet", [
    ("Anna Schmidt", ("", "Anna", "Schmidt")),
    ("Schmidt, Anna", ("", "Anna", "Schmidt")),
    ("Dr. Anna Schmidt", ("Dr.", "Anna", "Schmidt")),
    ("Prof. Dr. Jan Kruse", ("Prof. Dr.", "Jan", "Kruse")),
    ("Anna von Schmidt", ("", "Anna", "von Schmidt")),
    ("Anna Maria von der Heide", ("", "Anna Maria", "von der Heide")),
    ("Jean-Luc de la Fontaine", ("", "Jean-Luc", "de la Fontaine")),
    ("Lea Wolter (Einkauf)", ("", "Lea", "Wolter")),
])
def test_namen_werden_zerlegt(eingabe, erwartet):
    assert kontaktexport.namen_zerlegen(eingabe) == erwartet


def test_einzelner_name_bleibt_nachname():
    assert kontaktexport.namen_zerlegen("Müller") == ("", "", "Müller")


@pytest.mark.parametrize("eingabe", ["", None, "   ", "info@firma.de",
                                     "Anna <anna@firma.de>"])
def test_kein_name_wird_nicht_geraten(eingabe):
    assert kontaktexport.namen_zerlegen(eingabe) == ("", "", "")


# ------------------------------------------------------- Aufbereitung

def zeile(**rest):
    grund = {
        "E-Mail": "anna@lieferant.de", "Anzeigename": "Anna Schmidt",
        "Funktion": "Leiterin Vertrieb", "Telefon": "+49 123 4567-0",
        "Mobil": "0170 1234567", "Unternehmen": "Muster GmbH",
        "Herkunft Unternehmen": "Signatur", "Signaturbelege": 3,
        "Letzter Kontakt": datetime(2026, 5, 14, 9, 30), "Nachrichten": 12,
        "Kategorie": "Lieferant",
    }
    grund.update(rest)
    return grund


def test_aufbereitung_uebernimmt_die_felder():
    kontakt = kontaktexport.kontakte_aufbereiten([zeile()])[0]
    assert kontakt["Vorname"] == "Anna"
    assert kontakt["Nachname"] == "Schmidt"
    assert kontakt["Firma"] == "Muster GmbH"
    assert kontakt["Position"] == "Leiterin Vertrieb"
    assert kontakt["Mobil"] == "0170 1234567"


def test_firma_aus_dem_domainnamen_wandert_nicht_ins_adressbuch():
    """'Lieferant4' ist eine Lesehilfe, keine Firmierung."""
    kontakt = kontaktexport.kontakte_aufbereiten(
        [zeile(Unternehmen="Lieferant4", **{"Herkunft Unternehmen": "Domainname"})])[0]
    assert kontakt["Firma"] == ""


def test_ohne_personennamen_wird_uebersprungen():
    assert kontaktexport.kontakte_aufbereiten([zeile(Anzeigename="")]) == []
    assert len(kontaktexport.kontakte_aufbereiten([zeile(Anzeigename="")],
                                                  nur_mit_namen=False)) == 1


def test_notiz_haelt_die_herkunft_fest():
    notiz = kontaktexport.kontakte_aufbereiten([zeile()])[0]["Notiz"]
    assert "aus 3 Signaturen gelesen" in notiz
    assert "14.05.2026" in notiz, "Zeitstempel gehören formatiert, nicht roh"
    assert "09:30" not in notiz


def test_notiz_benennt_fehlenden_signaturfund():
    notiz = kontaktexport.kontakte_aufbereiten([zeile(Signaturbelege=0)])[0]["Notiz"]
    assert "kein Signaturfund" in notiz


# ------------------------------------------------------------- vCard

def test_vcard_aufbau(tmp_path):
    pfad = kontaktexport.als_vcard(
        kontaktexport.kontakte_aufbereiten([zeile()]), tmp_path / "k.vcf")
    text = pfad.read_text(encoding="utf-8")
    assert text.startswith("BEGIN:VCARD")
    assert text.rstrip().endswith("END:VCARD")
    assert "VERSION:3.0" in text
    assert "N:Schmidt;Anna;;;" in text
    assert "FN:Anna Schmidt" in text
    assert "ORG:Muster GmbH" in text
    assert "TEL;TYPE=CELL:0170 1234567" in text
    # Beim Lesen im Textmodus übersetzt Python CRLF zu LF -- deshalb die Bytes.
    assert b"\r\n" in pfad.read_bytes(), "vCard verlangt CRLF"


def test_vcard_maskiert_sonderzeichen(tmp_path):
    pfad = kontaktexport.als_vcard(
        kontaktexport.kontakte_aufbereiten(
            [zeile(Unternehmen="Meier, Schulz & Co. KG; Werk 2")]),
        tmp_path / "k.vcf")
    text = pfad.read_text(encoding="utf-8")
    assert "ORG:Meier\\, Schulz & Co. KG\\; Werk 2" in text


def test_mehrere_kontakte_in_einer_datei(tmp_path):
    zeilen = [zeile(), zeile(**{"E-Mail": "tom@x.de", "Anzeigename": "Tom Berg"})]
    pfad = kontaktexport.als_vcard(
        kontaktexport.kontakte_aufbereiten(zeilen), tmp_path / "k.vcf")
    assert pfad.read_text(encoding="utf-8").count("BEGIN:VCARD") == 2


# --------------------------------------------------------- Outlook-CSV

def test_csv_verwendet_die_deutschen_spaltennamen(tmp_path):
    pfad = kontaktexport.als_outlook_csv(
        kontaktexport.kontakte_aufbereiten([zeile()]), tmp_path / "k.csv", "de")
    kopf = pfad.read_text(encoding="utf-8-sig").splitlines()[0]
    assert kopf.startswith("Anrede,Vorname,Nachname,Firma,Position,E-Mail-Adresse")
    assert "Telefon geschäftlich" in kopf


def test_csv_kann_englisch(tmp_path):
    """Ein deutsches Outlook erkennt englische Kopfzeilen nicht -- und umgekehrt."""
    pfad = kontaktexport.als_outlook_csv(
        kontaktexport.kontakte_aufbereiten([zeile()]), tmp_path / "k.csv", "en")
    kopf = pfad.read_text(encoding="utf-8-sig").splitlines()[0]
    assert "First Name" in kopf and "Business Phone" in kopf


def test_unbekannte_sprache_wird_abgelehnt(tmp_path):
    with pytest.raises(ValueError, match="Sprache"):
        kontaktexport.als_outlook_csv([], tmp_path / "k.csv", "fr")


def test_csv_hat_bom_fuer_excel(tmp_path):
    pfad = kontaktexport.als_outlook_csv(
        kontaktexport.kontakte_aufbereiten([zeile()]), tmp_path / "k.csv")
    assert pfad.read_bytes().startswith(b"\xef\xbb\xbf")


# ------------------------------------------------------------ Zusammen

def test_schreiben_erzeugt_beide_dateien(tmp_path):
    ergebnis = kontaktexport.schreiben([zeile(), zeile(Anzeigename="")], tmp_path)
    assert ergebnis["kontakte"] == 1
    assert ergebnis["uebersprungen"] == 1
    assert ergebnis["mit_firma"] == 1
    assert ergebnis["vcf"].exists() and ergebnis["csv"].exists()


def test_ohne_kontakte_keine_dateien(tmp_path):
    ergebnis = kontaktexport.schreiben([zeile(Anzeigename="")], tmp_path)
    assert ergebnis["kontakte"] == 0
    assert ergebnis["vcf"] is None
    assert not (tmp_path / "Kontakte_Import.vcf").exists()
