"""Vorgangsbildung und Kern-KPIs.

Geprueft wird vor allem das, was das Konzept ausdruecklich zusichert:
'gemischt' geht nicht in 'intern' auf, Anteile stehen auf Vorgangsebene und
Lasten auf Nachrichtenebene, und Randvorgaenge verfaelschen keine Tiefen.
"""

from datetime import datetime, timedelta

import pytest

from okoa.config import Config
from okoa.metrics import kern_kpis, koordinationslast, stabilitaet
from okoa.model import (
    AUTOMATISIERT, EXTERN, INTERN, NORMAL, RICHTUNG_EMPFANGEN,
    RICHTUNG_GESENDET, TERMIN, Nachricht, Vorgang,
)
from okoa import threads


T0 = datetime(2026, 1, 5, 9, 0)


def nachricht(nr, *, conv="C1", betreff="H1", versatz_h=0, absender="ich@firma.de",
              absender_klasse=INTERN, empfaenger=("kollege@firma.de",),
              klassen=(INTERN,), klasse=NORMAL, richtung=RICHTUNG_GESENDET, cc=0):
    return Nachricht(
        msg_hash=f"m{nr}",
        zeitstempel=T0 + timedelta(hours=versatz_h),
        richtung=richtung,
        absender_id=absender,
        absender_klasse=absender_klasse,
        absender_domain=absender.split("@")[-1],
        empfaenger_ids=list(empfaenger),
        empfaenger_klassen=list(klassen),
        n_to=len(empfaenger) - cc,
        n_cc=cc,
        n_to_extern=sum(1 for k in klassen if k == EXTERN),
        n_cc_intern=cc,
        klasse=klasse,
        conversation_id=conv,
        betreff_hash=betreff,
    )


def gebaut(nachrichten, fensterbeginn=None):
    threads.zuordnen(nachrichten)
    return threads.vorgaenge_bilden(nachrichten, fensterbeginn=fensterbeginn)


# ------------------------------------------------------------ Klassifikation

def test_reiner_interner_vorgang():
    v = gebaut([nachricht(1), nachricht(2, versatz_h=2)])[0]
    assert v.klasse == "intern"
    assert v.n_nachrichten == 2


def test_reiner_externer_vorgang():
    n = [nachricht(1, empfaenger=("kunde@extern.com",), klassen=(EXTERN,))]
    assert gebaut(n)[0].klasse == "extern"


def test_gemischt_geht_nicht_in_intern_auf():
    """Ein Lieferantenvorgang mit interner Abstimmung ist wertschoepfende
    Arbeit -- ihn als 'intern' zu zaehlen wuerde die Hypothese kuenstlich
    bestaetigen."""
    n = [
        nachricht(1, empfaenger=("kunde@extern.com",), klassen=(EXTERN,)),
        nachricht(2, versatz_h=1),                      # rein interne Rueckfrage
        nachricht(3, versatz_h=2, empfaenger=("kunde@extern.com",), klassen=(EXTERN,)),
    ]
    v = gebaut(n)[0]
    assert v.klasse == "gemischt"
    assert v.interner_nachrichtenanteil == pytest.approx(1 / 3)


def test_beteiligte_ueber_alle_nachrichten():
    n = [
        nachricht(1, empfaenger=("a@firma.de",)),
        nachricht(2, versatz_h=1, empfaenger=("b@firma.de",)),
    ]
    assert gebaut(n)[0].n_beteiligte == 3   # ich + a + b


# ------------------------------------------------------------- Zuordnung

def test_gleicher_betreff_nach_langer_pause_ist_neuer_vorgang():
    """Sonst verschmilzt ein wiederkehrender Betreff ueber Jahre zu einem
    einzigen Endlosvorgang."""
    n = [nachricht(1, conv=""), nachricht(2, conv="", versatz_h=24 * 200)]
    threads.zuordnen(n, luecke_tage=30)
    assert n[0].thread_id_fallback != n[1].thread_id_fallback


def test_gleicher_betreff_ohne_gemeinsame_person_bleibt_getrennt():
    n = [
        nachricht(1, conv="", absender="ich@firma.de", empfaenger=("a@firma.de",)),
        nachricht(2, conv="", versatz_h=1, absender="x@firma.de",
                  empfaenger=("y@firma.de",)),
    ]
    threads.zuordnen(n)
    assert n[0].thread_id_fallback != n[1].thread_id_fallback


def test_zuordnung_ist_wiederholbar():
    """Aus der Zwischendatei gelesene Nachrichten bringen ihre IDs mit --
    ein erneutes Zuordnen darf sie nicht zerlegen."""
    n = [nachricht(1), nachricht(2, versatz_h=1)]
    threads.zuordnen(n)
    vorher = [(x.thread_id_conv, x.thread_id_fallback) for x in n]
    for x in n:
        x.conversation_id = ""
        x.betreff_hash = ""
    threads.zuordnen(n)
    assert [(x.thread_id_conv, x.thread_id_fallback) for x in n] == vorher


# ---------------------------------------------------------------- KPIs

def test_anteile_vorgang_und_nachricht_weichen_ab():
    """Der eigentliche Befund: interne Themen kosten mehr Kommunikation."""
    n = []
    for i in range(6):      # ein interner Vorgang mit sechs Nachrichten
        n.append(nachricht(f"i{i}", conv="INT", betreff="HI", versatz_h=i))
    n.append(nachricht("e1", conv="EXT", betreff="HE",
                       empfaenger=("kunde@extern.com",), klassen=(EXTERN,)))
    v = gebaut(n)
    k = kern_kpis(v, n)
    assert k["k1_vorgangsanteile"]["intern"] == pytest.approx(0.5)
    assert k["k2_nachrichtenanteile"]["intern"] == pytest.approx(6 / 7)


def test_automaten_und_termine_zaehlen_nicht_mit():
    n = [
        nachricht(1),
        nachricht(2, conv="A", betreff="HA", absender="noreply@firma.de",
                  klasse=AUTOMATISIERT, richtung=RICHTUNG_EMPFANGEN),
        nachricht(3, conv="T", betreff="HT", klasse=TERMIN),
    ]
    k = kern_kpis(gebaut(n), n)
    assert k["n_nachrichten"] == 1
    assert k["n_vorgaenge"] == 1


def test_aussenorientierung_zaehlt_nur_eigene_sendungen():
    """Empfangenes ist fremdbestimmt und darf die Kennzahl nicht verwaessern."""
    n = [
        nachricht(1, empfaenger=("kunde@extern.com",), klassen=(EXTERN,),
                  richtung=RICHTUNG_GESENDET),
        nachricht(2, conv="C2", betreff="H2", richtung=RICHTUNG_GESENDET),
        nachricht(3, conv="C3", betreff="H3", richtung=RICHTUNG_EMPFANGEN,
                  absender="kunde@extern.com", absender_klasse=EXTERN,
                  empfaenger=("ich@firma.de",), klassen=(INTERN,)),
    ]
    k = kern_kpis(gebaut(n), n)
    assert k["n_gesendet"] == 2
    assert k["k5_aussenorientierung"] == pytest.approx(0.5)


def test_randvorgaenge_verfaelschen_die_tiefe_nicht():
    """Vorgaenge vor dem Fenster sind abgeschnitten und bleiben aussen vor."""
    alt = [nachricht(f"a{i}", conv="ALT", betreff="HALT", versatz_h=-24 * 40 + i)
           for i in range(2)]
    neu = [nachricht(f"n{i}", conv="NEU", betreff="HNEU", versatz_h=i) for i in range(4)]
    v = gebaut(alt + neu, fensterbeginn=T0 - timedelta(days=10))
    k = kern_kpis(v, alt + neu)
    assert k["k3_koordinationstiefe"]["intern"]["n"] == 1
    assert k["k3_koordinationstiefe"]["intern"]["median"] == 4


def test_reichweite_zaehlt_domains_nicht_adressen():
    n = [
        nachricht(1, empfaenger=("a@lieferant.com",), klassen=(EXTERN,)),
        nachricht(2, conv="C2", betreff="H2", empfaenger=("b@lieferant.com",),
                  klassen=(EXTERN,)),
    ]
    assert kern_kpis(gebaut(n), n)["k6_reichweite"]["domains_gesamt"] == 1


def test_cc_quote(config_intern=None):
    n = [nachricht(1, empfaenger=("a@firma.de", "b@firma.de"),
                   klassen=(INTERN, INTERN), cc=1),
         nachricht(2, conv="C2", betreff="H2")]
    k = koordinationslast(gebaut(n), n, Config(interne_domains=["firma.de"]))
    assert k["cc_quote_intern"] == pytest.approx(0.5)


def test_stabilitaet_meldet_abweichung():
    a = {"k1_vorgangsanteile": {"intern": 0.5, "gemischt": 0.2, "extern": 0.3},
         "n_vorgaenge": 10}
    b = {"k1_vorgangsanteile": {"intern": 0.8, "gemischt": 0.1, "extern": 0.1},
         "n_vorgaenge": 4}
    s = stabilitaet(a, b)
    assert not s["stabil"]
    assert s["groesste_abweichung"] == pytest.approx(0.3)
