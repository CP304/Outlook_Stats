"""Verteilergröße in TO, CC und BCC.

Die heikle Stelle ist BCC: nur bei eigenen Sendungen sichtbar, und es darf
niemals still in die TO-Zahl geschlagen werden — sonst ist jede TO-Kennzahl
verfälscht, ohne dass es jemand merkt.
"""

from datetime import datetime, timedelta

import pytest

from okoa import metrics, threads
from okoa.config import Config
from okoa.model import EXTERN, INTERN, RICHTUNG_EMPFANGEN, RICHTUNG_GESENDET, Nachricht


T0 = datetime(2026, 3, 2, 9, 0)


def nachricht(nr, *, to=1, cc=0, bcc=0, extern=0, versatz_h=0, conv="C1",
              richtung=RICHTUNG_GESENDET, verteilerlisten=0):
    empfaenger = [f"p{i}@firma.de" for i in range(to + cc + bcc - extern)]
    empfaenger += [f"k{i}@extern.com" for i in range(extern)]
    klassen = [INTERN] * (to + cc + bcc - extern) + [EXTERN] * extern
    return Nachricht(
        msg_hash=f"m{nr}", zeitstempel=T0 + timedelta(hours=versatz_h),
        richtung=richtung, absender_id="ich@firma.de", absender_klasse=INTERN,
        absender_domain="firma.de", empfaenger_ids=empfaenger,
        empfaenger_klassen=klassen,
        n_to=to, n_cc=cc, n_bcc=bcc,
        n_to_intern=to - extern, n_to_extern=extern,
        n_cc_intern=cc, n_bcc_intern=bcc,
        n_verteilerlisten=verteilerlisten,
        conversation_id=conv, betreff_hash="H1")


def gebaut(nachrichten):
    threads.zuordnen(nachrichten)
    return threads.vorgaenge_bilden(nachrichten)


@pytest.fixture
def config():
    return Config(interne_domains=["firma.de"])


# ------------------------------------------------------------ Grundlagen

def test_bcc_zaehlt_nicht_als_to(config):
    """Der Fehler, der sonst unbemerkt jede TO-Kennzahl verfälscht."""
    n = [nachricht(1, to=2, cc=1, bcc=3)]
    gesamt = metrics.verteilergroesse(gebaut(n), n, config)["gesamt"]
    assert gesamt["to"]["mittel"] == 2
    assert gesamt["cc"]["mittel"] == 1
    assert gesamt["bcc"]["mittel"] == 3
    assert gesamt["gesamt"]["mittel"] == 6


def test_mittel_und_median_trennen_zwei_muster(config):
    """„Selten, dann breit“ ist etwas anderes als „ständig, aber knapp“."""
    n = [nachricht(1, cc=10), nachricht(2, versatz_h=1), nachricht(3, versatz_h=2),
         nachricht(4, versatz_h=3)]
    cc = metrics.verteilergroesse(gebaut(n), n, config)["gesamt"]["cc"]
    assert cc["mittel"] == pytest.approx(2.5)          # über alle Nachrichten
    assert cc["median_wenn_genutzt"] == 10             # nur wo CC benutzt wurde
    assert cc["anteil_genutzt"] == pytest.approx(0.25)


def test_feldanteile_summieren_sich(config):
    n = [nachricht(1, to=3, cc=1, bcc=1)]
    g = metrics.verteilergroesse(gebaut(n), n, config)["gesamt"]
    assert g["anteil_to"] + g["anteil_cc"] + g["anteil_bcc"] == pytest.approx(1.0)
    assert g["anteil_to"] == pytest.approx(0.6)


def test_groessenklassen(config):
    n = [nachricht(1, to=1), nachricht(2, to=3, versatz_h=1),
         nachricht(3, to=6, versatz_h=2), nachricht(4, to=15, versatz_h=3),
         nachricht(5, to=40, versatz_h=4)]
    klassen = metrics.verteilergroesse(gebaut(n), n, config)["gesamt"]["groessenklassen"]
    assert klassen == {"1": 1, "2–3": 1, "4–8": 1, "9–20": 1, "über 20": 1}


# --------------------------------------------------------- Aufschlüsselung

def test_aufschluesselung_nach_richtung(config):
    n = [nachricht(1, cc=4),
         nachricht(2, versatz_h=1, cc=0, richtung=RICHTUNG_EMPFANGEN)]
    richtung = metrics.verteilergroesse(gebaut(n), n, config)["nach_richtung"]
    assert richtung["gesendet"]["cc"]["mittel"] == 4
    assert richtung["empfangen"]["cc"]["mittel"] == 0


def test_aufschluesselung_nach_klasse(config):
    n = [nachricht(1, to=2, cc=3),
         nachricht(2, versatz_h=1, conv="C2", to=2, extern=1)]
    klassen = metrics.verteilergroesse(gebaut(n), n, config)["nach_klasse"]
    assert klassen["intern"]["cc"]["mittel"] == 3
    assert klassen["extern"]["cc"]["mittel"] == 0


def test_aufschluesselung_nach_fachbereich(config):
    n = [nachricht(1, to=1, cc=4)]
    zuordnung = {"p0@firma.de": "Engineering", "ich@firma.de": "Einkauf"}
    bereiche = metrics.verteilergroesse(gebaut(n), n, config,
                                        zuordnung)["nach_fachbereich"]
    assert bereiche["Engineering"]["cc"]["mittel"] == 4
    assert bereiche["Einkauf"]["cc"]["mittel"] == 4


def test_nicht_zugeordnete_landen_in_sonstige(config):
    n = [nachricht(1, to=2)]
    bereiche = metrics.verteilergroesse(gebaut(n), n, config, {})["nach_fachbereich"]
    assert "Unbekannt/Sonstige" in bereiche


# ---------------------------------------------------------- Großverteiler

def test_grossverteiler_und_ursache(config):
    """Was macht einen großen Verteiler groß — TO oder CC?"""
    n = [nachricht(1, to=1, cc=12),          # durch CC groß
         nachricht(2, versatz_h=1, to=12),   # durch TO groß
         nachricht(3, versatz_h=2, to=2)]    # klein
    gross = metrics.verteilergroesse(gebaut(n), n, config)["grossverteiler"]
    assert gross["anzahl"] == 2
    assert gross["davon_durch_cc"] == pytest.approx(0.5)


def test_verteilerlisten_werden_ausgewiesen(config):
    n = [nachricht(1, to=1, verteilerlisten=1), nachricht(2, versatz_h=1)]
    gesamt = metrics.verteilergroesse(gebaut(n), n, config)["gesamt"]
    assert gesamt["mit_verteilerliste"] == 1


def test_intern_extern_getrennt(config):
    n = [nachricht(1, to=3, extern=2, cc=1)]
    ie = metrics.verteilergroesse(gebaut(n), n, config)["gesamt"]["intern_extern"]
    assert ie["to_extern"] == 2
    assert ie["to_intern"] == 1
    assert ie["cc_intern"] == 1


# ------------------------------------------------------------- Im Report

def test_report_zeigt_die_verteilergroesse(tmp_path):
    from okoa import pipeline
    from okoa.synthetic import postfach_erzeugen

    pipeline.auswerten(postfach_erzeugen(120, seed=4),
                       Config(interne_domains=["firma.de"]), tmp_path,
                       bezugszeitpunkt=datetime(2026, 6, 30))
    text = (tmp_path / pipeline.DATEI_REPORT).read_text(encoding="utf-8")
    for pflicht in ("Verteilergröße", "Nach Vorgangsklasse", "Nach Richtung",
                    "BCC (nur eigene Sendungen)", "Große Verteiler"):
        assert pflicht in text


def test_leere_menge_bricht_nicht(config):
    assert metrics.verteilergroesse([], [], config)["gesamt"] == {"n": 0}
