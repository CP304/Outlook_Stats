"""Extraktion gegen ein nachgebautes Outlook.

Diese Tests hätten den Fehler gefunden, der in der ersten Fassung dazu führte,
dass null Nachrichten ausgewertet wurden: Folder.DefaultItemType liefert
olMailItem = 0, die vielzitierte 43 stammt aus einer anderen Aufzählung.
"""

from datetime import datetime, timedelta

import pytest

from okoa import extract_outlook
from okoa.config import Config

from . import fake_outlook


JETZT = datetime.now() - timedelta(days=5)


@pytest.fixture
def config():
    return Config(interne_domains=["firma.de"])


@pytest.fixture
def outlook(monkeypatch):
    """Setzt das nachgebaute Outlook an die Stelle der echten Verbindung."""
    def einsetzen(namespace):
        monkeypatch.setattr(extract_outlook, "verbinden", lambda: namespace)
        return namespace
    return einsetzen


# ------------------------------------------------------------ Ordner

def test_mailordner_werden_erkannt(config, outlook):
    """Der Kern des Fehlers: kein erkannter Ordner heißt null Nachrichten."""
    namespace = outlook(fake_outlook.standard_postfach(JETZT))
    ordner = extract_outlook.ordner_sammeln(namespace, config)
    namen = [name for _, name, _ in ordner]
    assert "Posteingang" in namen
    assert "Projekte" in namen, "Unterordner gehören dazu"
    assert "Gesendete Elemente" in namen


def test_kalender_und_junk_bleiben_draussen(config, outlook):
    namespace = outlook(fake_outlook.standard_postfach(JETZT))
    namen = [name for _, name, _ in extract_outlook.ordner_sammeln(namespace, config)]
    assert "Kalender" not in namen, "kein Mailordner"
    assert "Junk-E-Mail" not in namen, "per Vorgabe ausgeschlossen"


def test_ordner_ohne_angabe_werden_mitgenommen(config, outlook):
    """Lieber ein Ordner zu viel geprüft als das halbe Postfach übersehen."""
    ordner = fake_outlook.Folder("Unklar", [])
    del ordner.DefaultItemType
    wurzel = fake_outlook.Folder("Postfach", [], [ordner])
    namespace = outlook(fake_outlook.Namespace([fake_outlook.Store("P", wurzel)]))
    assert "Unklar" in [n for _, n, _ in extract_outlook.ordner_sammeln(namespace, config)]


def test_fremde_postfaecher_bleiben_draussen(config, outlook):
    wurzel = fake_outlook.Folder("Postfach", [], [
        fake_outlook.Folder("Posteingang", [])])
    namespace = outlook(fake_outlook.Namespace([
        fake_outlook.Store("Fremdes Postfach", wurzel, typ=4)]))
    assert extract_outlook.ordner_sammeln(namespace, config) == []

    config.fremde_postfaecher_einbeziehen = True
    assert extract_outlook.ordner_sammeln(namespace, config)


# ---------------------------------------------------------- Auslesen

def test_nachrichten_werden_gelesen(config, outlook):
    outlook(fake_outlook.standard_postfach(JETZT))
    nachrichten, bericht = extract_outlook.auslesen(config)
    assert len(nachrichten) == 4, "drei empfangene und eine gesendete"
    assert bericht["gelesen"] == 4
    assert bericht["gefundene_ordner"] >= 3


def test_x500_adressen_werden_aufgeloest(config, outlook):
    """Ohne Auflösung gälte jede interne Mail als extern."""
    outlook(fake_outlook.standard_postfach(JETZT))
    nachrichten, _ = extract_outlook.auslesen(config)
    absender = {n.absender_id for n in nachrichten}
    assert "kollege@firma.de" in absender
    assert not any(a.startswith("/o=") for a in absender)
    assert all(n.absender_klasse in ("intern", "extern") for n in nachrichten)


def test_richtung_haengt_nicht_am_ordner(config, outlook):
    outlook(fake_outlook.standard_postfach(JETZT))
    nachrichten, _ = extract_outlook.auslesen(config)
    gesendet = [n for n in nachrichten if n.richtung == "gesendet"]
    assert len(gesendet) == 1
    assert gesendet[0].absender_id == "ich@firma.de"


def test_bcc_wird_nicht_als_to_gezaehlt(config, outlook):
    empfaenger = [
        fake_outlook.Recipient("a@firma.de", 1, exchange=True),
        fake_outlook.Recipient("b@firma.de", 2, exchange=True),
        fake_outlook.Recipient("c@firma.de", 3, exchange=True),
    ]
    wurzel = fake_outlook.Folder("Postfach", [], [fake_outlook.Folder("Posteingang", [
        fake_outlook.MailItem("ich@firma.de", empfaenger, JETZT, exchange=True)])])
    outlook(fake_outlook.Namespace([fake_outlook.Store("P", wurzel)]))
    nachricht = extract_outlook.auslesen(config)[0][0]
    assert (nachricht.n_to, nachricht.n_cc, nachricht.n_bcc) == (1, 1, 1)


def test_verteilerlisten_werden_gezaehlt(config, outlook):
    empfaenger = [fake_outlook.Recipient("alle@firma.de", 1, exchange=True,
                                         verteilerliste=True)]
    wurzel = fake_outlook.Folder("Postfach", [], [fake_outlook.Folder("Posteingang", [
        fake_outlook.MailItem("ich@firma.de", empfaenger, JETZT, exchange=True)])])
    outlook(fake_outlook.Namespace([fake_outlook.Store("P", wurzel)]))
    assert extract_outlook.auslesen(config)[0][0].n_verteilerlisten == 1


# ------------------------------------------------------------- Filter

def test_zeitraum_wird_beachtet(config, outlook):
    alt = JETZT - timedelta(days=400)
    wurzel = fake_outlook.Folder("Postfach", [], [fake_outlook.Folder("Posteingang", [
        fake_outlook.MailItem("a@lieferant.com",
                              [fake_outlook.Recipient("ich@firma.de", 1)], JETZT),
        fake_outlook.MailItem("b@lieferant.com",
                              [fake_outlook.Recipient("ich@firma.de", 1)], alt,
                              betreff="Uralt"),
    ])])
    outlook(fake_outlook.Namespace([fake_outlook.Store("P", wurzel)]))
    nachrichten, _ = extract_outlook.auslesen(config)
    assert len(nachrichten) == 1


def test_ohne_wirksamen_filter_wird_trotzdem_gelesen(config, outlook):
    """Ein Outlook, das den Filterausdruck nicht versteht, liefert klaglos
    nichts zurück. Dann muss ungefiltert gelesen und in Python geprüft werden --
    sonst steht der Nutzer vor null Nachrichten ohne Erklärung."""
    outlook(fake_outlook.standard_postfach(JETZT, filter_versteht_dasl=False))
    nachrichten, bericht = extract_outlook.auslesen(config)
    assert len(nachrichten) == 4
    assert bericht["ohne_filter"], "Der Bericht muss das benennen"


def test_alte_nachrichten_auch_ohne_filter_draussen(config, outlook):
    alt = JETZT - timedelta(days=400)
    wurzel = fake_outlook.Folder("Postfach", [], [fake_outlook.Folder(
        "Posteingang",
        [fake_outlook.MailItem("b@lieferant.com",
                               [fake_outlook.Recipient("ich@firma.de", 1)], alt)],
        filter_versteht_dasl=False)])
    outlook(fake_outlook.Namespace([fake_outlook.Store("P", wurzel)]))
    assert extract_outlook.auslesen(config)[0] == []


# ------------------------------------------------------------- Prüfen

def test_pruefbericht_zeigt_was_da_ist(config, outlook):
    outlook(fake_outlook.standard_postfach(JETZT))
    bericht = extract_outlook.pruefen(config)
    assert bericht["elemente_gesamt"] == 4
    assert bericht["elemente_im_zeitraum"] == 4
    assert bericht["stores"][0]["einbezogen"] is True
    assert any(o["ordner"] == "Posteingang" for o in bericht["ordner"])


def test_pruefbericht_meldet_wirkungslosen_filter(config, outlook):
    outlook(fake_outlook.standard_postfach(JETZT, filter_versteht_dasl=False))
    bericht = extract_outlook.pruefen(config)
    assert bericht["ordner_ohne_filter"] > 0


# ------------------------------------------------- Meldung bei null Treffern

def test_leeres_ergebnis_wird_gemeldet(config, outlook, tmp_path):
    """Null Nachrichten darf nicht wortlos durchgehen."""
    from okoa import auftrag as auftrag_modul

    wurzel = fake_outlook.Folder("Postfach", [], [fake_outlook.Folder("Posteingang", [])])
    outlook(fake_outlook.Namespace([fake_outlook.Store("P", wurzel)]))

    meldungen = []
    bericht = auftrag_modul.postfach_pruefen(meldungen.append, config)
    assert bericht["elemente_gesamt"] == 0
    assert any("Gesamt: 0 Elemente" in m for m in meldungen)
    assert any("Eigene Adressen" in m for m in meldungen)
