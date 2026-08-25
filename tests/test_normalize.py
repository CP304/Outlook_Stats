"""Adressaufloesung und Klassifikation.

Der Kern dieser Tests ist der haeufigste Fehler der Analyseart: eine
X500-Adresse darf niemals als extern durchgehen.
"""

import pytest

from okoa.config import Config
from okoa.model import EXTERN, INTERN, KONZERN, UNAUFGELOEST
from okoa.normalize import (
    adresse_klassifizieren, betreff_hashen, betreff_normalisieren,
    duplikat_schluessel, ist_antwort_betreff, ist_automat, ist_funktionspostfach,
    ist_x500, nachricht_klassifizieren,
)


@pytest.fixture
def config():
    return Config(interne_domains=["firma.de"], konzern_domains=["schwester.com"])


def test_intern_extern_konzern(config):
    assert adresse_klassifizieren("Max.Mustermann@FIRMA.de", config) == INTERN
    assert adresse_klassifizieren("kontakt@lieferant.com", config) == EXTERN
    assert adresse_klassifizieren("kollege@schwester.com", config) == KONZERN


def test_x500_wird_nicht_als_extern_gezaehlt(config):
    """Ohne diese Regel waere jede interne Mail faelschlich extern."""
    x500 = "/O=FIRMA/OU=EXCHANGE ADMINISTRATIVE GROUP (FYDIBOHF23SPDLT)/CN=RECIPIENTS/CN=ABC123"
    assert ist_x500(x500)
    assert adresse_klassifizieren(x500, config) == UNAUFGELOEST


def test_leere_adresse_ist_unaufgeloest(config):
    assert adresse_klassifizieren("", config) == UNAUFGELOEST
    assert adresse_klassifizieren("kein-at-zeichen", config) == UNAUFGELOEST


@pytest.mark.parametrize("betreff,erwartet", [
    ("AW: Angebot", "angebot"),
    ("RE: Re: AW: Angebot", "angebot"),
    ("WG: [EXTERN] Angebot", "angebot"),
    ("FWD: Angebot   Nr 5", "angebot nr 5"),
    ("Angebot", "angebot"),
])
def test_betreff_normalisierung(betreff, erwartet):
    assert betreff_normalisieren(betreff) == erwartet


def test_betreff_wird_nur_gehasht():
    """Der Klartext darf die Vorgangsbildung nicht verlassen."""
    hash_a = betreff_hashen("AW: Vertraulicher Preis 12,50 EUR")
    hash_b = betreff_hashen("Vertraulicher Preis 12,50 EUR")
    assert hash_a == hash_b
    assert "preis" not in hash_a.lower()
    assert len(hash_a) == 16


def test_antwort_erkennung():
    assert ist_antwort_betreff("AW: Test")
    assert ist_antwort_betreff("[EXTERN] WG: Test")
    assert not ist_antwort_betreff("Test")


def test_automaten_und_funktionspostfaecher():
    assert ist_automat("noreply@firma.de")
    assert ist_automat("mailer-daemon@firma.de")
    assert not ist_automat("max@firma.de")
    assert ist_funktionspostfach("einkauf@firma.de")
    assert not ist_funktionspostfach("max.einkauf@firma.de")


def test_nachrichtenklassen():
    assert nachricht_klassifizieren("a@b.de", "IPM.Schedule.Meeting.Request") == "termin"
    assert nachricht_klassifizieren("noreply@b.de", "IPM.Note") == "automatisiert"
    assert nachricht_klassifizieren("a@b.de", "IPM.Note",
                                    "List-Unsubscribe: <x>") == "automatisiert"
    assert nachricht_klassifizieren("a@b.de", "IPM.Note") == "normal"


def test_duplikatschluessel_bevorzugt_message_id():
    from datetime import datetime
    zeit = datetime(2026, 1, 1, 9, 0)
    a = duplikat_schluessel("<abc@firma.de>", "x@firma.de", zeit, ["y@firma.de"], 100)
    b = duplikat_schluessel("<ABC@firma.de>", "anders@firma.de", zeit, [], 999)
    assert a == b, "Dieselbe Mail aus Postfach und Archiv muss ein Duplikat sein"


def test_duplikatschluessel_ohne_message_id():
    from datetime import datetime
    zeit = datetime(2026, 1, 1, 9, 0, 30)
    a = duplikat_schluessel("", "x@firma.de", zeit, ["y@firma.de"], 100)
    b = duplikat_schluessel("", "x@firma.de", zeit.replace(second=59), ["Y@FIRMA.de"], 100)
    assert a == b, "Sekunden und Schreibweise duerfen kein Duplikat verhindern"
