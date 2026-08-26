"""Vollerhebung: die Auswertungen, die über die Kern-KPIs hinausgehen."""

from datetime import datetime, timedelta

import pytest

from okoa import metrics, threads
from okoa.config import Config
from okoa.model import (
    EXTERN, INTERN, NORMAL, RICHTUNG_EMPFANGEN, RICHTUNG_GESENDET, TERMIN, Nachricht,
)
from okoa.synthetic import postfach_erzeugen


T0 = datetime(2026, 3, 2, 9, 0)      # ein Montag


def nachricht(nr, *, versatz_h=0, absender="ich@firma.de", absender_klasse=INTERN,
              empfaenger=("kollege@firma.de",), klassen=(INTERN,),
              richtung=RICHTUNG_GESENDET, conv="C1", **rest):
    return Nachricht(
        msg_hash=f"m{nr}", zeitstempel=T0 + timedelta(hours=versatz_h),
        richtung=richtung, absender_id=absender, absender_klasse=absender_klasse,
        absender_domain=absender.split("@")[-1], empfaenger_ids=list(empfaenger),
        empfaenger_klassen=list(klassen), n_to=len(empfaenger),
        conversation_id=conv, betreff_hash="H1", **rest)


def gebaut(nachrichten):
    threads.zuordnen(nachrichten)
    return threads.vorgaenge_bilden(nachrichten)


@pytest.fixture
def config():
    return Config(interne_domains=["firma.de"], vollerhebung=True)


# ---------------------------------------------------------- Antwortzeiten

def test_antwortzeit_nur_bei_sprecherwechsel(config):
    """Zwei Nachrichten derselben Person sind Nachfassen, keine Antwort."""
    n = [nachricht(1), nachricht(2, versatz_h=1),          # gleicher Absender
         nachricht(3, versatz_h=5, absender="kollege@firma.de",
                   empfaenger=("ich@firma.de",))]
    ergebnis = metrics.antwortzeiten(gebaut(n), config)
    assert ergebnis["intern"]["n"] == 1
    assert ergebnis["intern"]["median_stunden"] == 4


def test_zu_lange_spannen_fallen_heraus(config):
    """Nach zwei Wochen ist es kein Reaktions-, sondern ein neuer Anlauf."""
    n = [nachricht(1), nachricht(2, versatz_h=24 * 30, absender="kollege@firma.de",
                                 empfaenger=("ich@firma.de",))]
    assert metrics.antwortzeiten(gebaut(n), config) == {}


def test_antwortrichtung_wird_getrennt(config):
    n = [nachricht(1),
         nachricht(2, versatz_h=3, absender="kollege@firma.de",
                   empfaenger=("ich@firma.de",), richtung=RICHTUNG_EMPFANGEN),
         nachricht(3, versatz_h=9)]
    ergebnis = metrics.antwortzeiten(gebaut(n), config, {"ich@firma.de"})
    assert ergebnis["an_mich"]["median_stunden"] == 3    # ich habe geschrieben, er antwortet
    assert ergebnis["von_mir"]["median_stunden"] == 6    # er schrieb, ich antworte


# ---------------------------------------------------------- Arbeitszeit

def test_arbeitszeit_nur_eigene_nachrichten(config):
    n = [nachricht(1, versatz_h=13),                                   # 22 Uhr
         nachricht(2, versatz_h=0),                                    # 9 Uhr
         nachricht(3, versatz_h=13, richtung=RICHTUNG_EMPFANGEN,
                   absender="kollege@firma.de", empfaenger=("ich@firma.de",))]
    ergebnis = metrics.arbeitszeitmuster(n, config)
    assert ergebnis["n"] == 2
    assert ergebnis["anteil_ausserhalb"] == pytest.approx(0.5)
    assert ergebnis["anteil_nach_ende"] == pytest.approx(0.5)


def test_wochenende_wird_erkannt(config):
    n = [nachricht(1, versatz_h=24 * 5), nachricht(2)]     # Samstag, Montag
    assert metrics.arbeitszeitmuster(n, config)["anteil_wochenende"] == pytest.approx(0.5)


# ------------------------------------------------------------- Netzwerk

def test_netzwerk_laesst_die_eigene_adresse_aus(config):
    n = [nachricht(1), nachricht(2, versatz_h=1)]
    ergebnis = metrics.netzwerk(gebaut(n), n, eigene_adressen={"ich@firma.de"})
    assert all(p["adresse"] != "ich@firma.de" for p in ergebnis["top_intern"])
    assert ergebnis["partner_gesamt"] == 1


def test_grad_zaehlt_gemeinsame_beteiligte(config):
    n = [nachricht(1, empfaenger=("a@firma.de", "b@firma.de"),
                   klassen=(INTERN, INTERN))]
    ergebnis = metrics.netzwerk(gebaut(n), n, eigene_adressen={"ich@firma.de"})
    grade = {p["adresse"]: p["grad"] for p in ergebnis["top_intern"]}
    assert grade["a@firma.de"] == 1     # b, ohne sich selbst und ohne mich


def test_gini_erkennt_konzentration():
    assert metrics._gini([5, 5, 5, 5]) == pytest.approx(0.0)
    assert metrics._gini([100, 1, 1, 1]) > 0.6
    assert metrics._gini([]) == 0.0


def test_netzwerk_zeigt_fachbereich_statt_name(config):
    n = [nachricht(1, empfaenger=("a@firma.de",))]
    ergebnis = metrics.netzwerk(gebaut(n), n, {"a@firma.de": "Engineering"},
                                {"ich@firma.de"})
    assert ergebnis["top_intern"][0]["fachbereich"] == "Engineering"


# ------------------------------------------------- Anhänge, Termine, Rest

def test_anhaenge_und_dateitypen():
    n = [nachricht(1, n_anhaenge=2, hat_anhang=True, groesse=500_000,
                   anhangnamen=["Angebot.PDF", "Preise.xlsx"]),
         nachricht(2, versatz_h=1, groesse=4_000)]
    ergebnis = metrics.anhaenge(n)
    assert ergebnis["anteil_mit_anhang"] == pytest.approx(0.5)
    assert dict(ergebnis["top_dateitypen"])["pdf"] == 1      # Endung normalisiert
    assert ergebnis["volumen_gesamt_mb"] > 0


def test_termine_zaehlen_nicht_als_mail():
    n = [nachricht(1), nachricht(2, versatz_h=1, klasse=TERMIN, conv="C2")]
    assert metrics.termine(n)["n"] == 1
    assert metrics.kern_kpis(gebaut(n), n)["n_nachrichten"] == 1


def test_bcc_nur_bei_eigenen_sendungen():
    n = [nachricht(1, n_bcc=2),
         nachricht(2, versatz_h=1, richtung=RICHTUNG_EMPFANGEN, n_bcc=5,
                   absender="x@firma.de", empfaenger=("ich@firma.de",))]
    ergebnis = metrics.bcc_nutzung(n)
    assert ergebnis["n_gesendet"] == 1
    assert ergebnis["anteil_mit_bcc"] == pytest.approx(1.0)


def test_weiterleitungsanteil():
    n = [nachricht(1, ist_weiterleitung=True), nachricht(2, versatz_h=1)]
    assert metrics.weiterleitungen(n)["anteil_weitergeleitet"] == pytest.approx(0.5)


# ------------------------------------------------------------ Zusammenspiel

def test_vollerhebung_liefert_alle_bereiche(config):
    nachrichten = postfach_erzeugen(120, seed=9)
    vorgaenge = gebaut(nachrichten)
    ergebnis = metrics.vollerhebung(vorgaenge, nachrichten, config)
    assert set(ergebnis) == {"antwortzeiten", "arbeitszeit", "netzwerk", "anhaenge",
                             "termine", "bcc", "weiterleitungen"}
    assert ergebnis["netzwerk"]["partner_gesamt"] > 0


def test_report_zeigt_die_vollerhebung(tmp_path, config):
    from okoa import pipeline

    pipeline.auswerten(postfach_erzeugen(120, seed=9), config, tmp_path,
                       bezugszeitpunkt=datetime(2026, 6, 30))
    text = (tmp_path / pipeline.DATEI_REPORT).read_text(encoding="utf-8")
    for pflicht in ("Vollerhebung", "Antwortzeiten", "Arbeitszeitmuster",
                    "Kommunikationsnetzwerk", "explorativ"):
        assert pflicht in text


def test_ohne_vollerhebung_kein_zusatzteil(tmp_path):
    from okoa import pipeline

    pipeline.auswerten(postfach_erzeugen(60, seed=9),
                       Config(interne_domains=["firma.de"]), tmp_path,
                       bezugszeitpunkt=datetime(2026, 6, 30))
    text = (tmp_path / pipeline.DATEI_REPORT).read_text(encoding="utf-8")
    assert "Antwortzeiten" not in text


def test_teamexport_bleibt_unveraendert(tmp_path, config):
    """Auch bei Vollerhebung geht nur das Aggregat nach draußen."""
    from okoa import pipeline, team_export

    ergebnis = pipeline.auswerten(postfach_erzeugen(80, seed=9), config, tmp_path,
                                  bezugszeitpunkt=datetime(2026, 6, 30))
    assert set(ergebnis["export"]) <= set(team_export.EXPORT_FELDER)
    assert "netzwerk" not in ergebnis["export"]
    assert "stunden" not in ergebnis["export"]
