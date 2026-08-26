"""KPI-Berechnung.

Grundregel des Konzepts (docs/02-methodik.md):
    Anteile werden auf Vorgangsebene berichtet, Lasten auf Nachrichtenebene.
Beide Sichten stehen immer nebeneinander -- ihre Differenz ist der eigentliche
Befund und nicht ein Schoenheitsfehler.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime

from .config import Config
from .model import (
    EXTERN, INTERN, KONZERN, NORMAL, RICHTUNG_GESENDET, TERMIN, UNAUFGELOEST,
    VORGANG_EXTERN, VORGANG_GEMISCHT, VORGANG_INTERN, Nachricht, Vorgang,
)
from .normalize import domain_von


KLASSEN = [VORGANG_INTERN, VORGANG_GEMISCHT, VORGANG_EXTERN]


def _anteil(zaehler: float, nenner: float) -> float:
    return zaehler / nenner if nenner else 0.0


def _median(werte: list[float]) -> float:
    return statistics.median(werte) if werte else 0.0


def _mittel(werte: list[float]) -> float:
    return statistics.fmean(werte) if werte else 0.0


def _quartile(werte: list[float]) -> tuple[float, float]:
    if len(werte) < 4:
        return (_median(werte), _median(werte))
    q = statistics.quantiles(werte, n=4)
    return (q[0], q[2])


# ------------------------------------------------------------- Kern-KPIs

def kern_kpis(vorgaenge: list[Vorgang], nachrichten: list[Nachricht]) -> dict:
    """K1 bis K6 aus docs/01-kpi-konzept.md."""
    auswertbar = [n for n in nachrichten if n.ist_auswertbar]
    vorgaenge = [v for v in vorgaenge if any(n.ist_auswertbar for n in v.nachrichten)]

    # K1 -- Anteile auf Vorgangsebene (Hauptkennzahl)
    klasse_je_vorgang = {v.thread_id: v.klasse for v in vorgaenge}
    zaehler_v = Counter(klasse_je_vorgang.values())
    n_v = len(vorgaenge)
    k1 = {k: _anteil(zaehler_v.get(k, 0), n_v) for k in KLASSEN}

    # K2 -- dieselbe Frage auf Nachrichtenebene (Kontrastkennzahl)
    zaehler_n: Counter = Counter()
    for v in vorgaenge:
        anzahl = sum(1 for n in v.nachrichten if n.ist_auswertbar)
        zaehler_n[v.klasse] += anzahl
    n_n = sum(zaehler_n.values())
    k2 = {k: _anteil(zaehler_n.get(k, 0), n_n) for k in KLASSEN}

    # K3 -- Koordinationstiefe.  Randvorgaenge sind abgeschnitten und bleiben
    # bei Tiefen- und Dauerkennzahlen aussen vor.
    vollstaendig = [v for v in vorgaenge if not v.randvorgang]
    k3 = {}
    k4 = {}
    for k in KLASSEN:
        laengen = [float(v.n_nachrichten) for v in vollstaendig if v.klasse == k]
        breiten = [float(v.n_beteiligte) for v in vollstaendig if v.klasse == k]
        k3[k] = {"mittel": _mittel(laengen), "median": _median(laengen), "n": len(laengen)}
        k4[k] = {"mittel": _mittel(breiten), "median": _median(breiten), "n": len(breiten)}

    # K5 -- Aussenorientierung.  Empfangenes ist fremdbestimmt, Gesendetes ist
    # die eigene Kapazitaetsentscheidung -- deshalb nur eigene Sendungen.
    gesendet = [n for n in auswertbar if n.richtung == RICHTUNG_GESENDET]
    k5 = _anteil(sum(1 for n in gesendet if n.hat_externen_empfaenger), len(gesendet))

    # K6 -- externe Reichweite
    domain_vorgaenge: dict[str, set[str]] = defaultdict(set)
    for v in vorgaenge:
        for n in v.nachrichten:
            if not n.ist_auswertbar:
                continue
            for adr, kl in zip([n.absender_id, *n.empfaenger_ids],
                               [n.absender_klasse, *n.empfaenger_klassen]):
                if kl == EXTERN:
                    domain_vorgaenge[domain_von(adr)].add(v.thread_id)
    k6 = {
        "domains_gesamt": len(domain_vorgaenge),
        "domains_aktiv": sum(1 for d in domain_vorgaenge.values() if len(d) >= 3),
    }

    return {
        "k1_vorgangsanteile": k1,
        "k2_nachrichtenanteile": k2,
        "k3_koordinationstiefe": k3,
        "k4_beteiligungsbreite": k4,
        "k5_aussenorientierung": k5,
        "k6_reichweite": k6,
        "n_vorgaenge": n_v,
        "n_nachrichten": n_n,
        "n_gesendet": len(gesendet),
    }


# ---------------------------------------------------------- Sekundaer-KPIs

def koordinationslast(vorgaenge: list[Vorgang], nachrichten: list[Nachricht],
                      config: Config) -> dict:
    s = config.schwellen
    intern = [n for n in nachrichten
              if n.ist_auswertbar and not n.hat_externen_empfaenger]
    mit_cc = sum(1 for n in intern if n.n_cc > 0)
    cc_zahlen = [float(n.n_cc) for n in intern if n.n_cc > 0]

    ergebnis = {
        "cc_quote_intern": _anteil(mit_cc, len(intern)),
        "cc_empfaenger_mittel": _mittel(cc_zahlen),
        "anteil_grossverteiler": _anteil(
            sum(1 for n in intern if n.n_empfaenger > s.grossverteiler_empfaenger), len(intern)
        ),
        "anteil_an_verteilerlisten": _anteil(
            sum(1 for n in nachrichten if n.ist_auswertbar and n.n_verteilerlisten > 0),
            sum(1 for n in nachrichten if n.ist_auswertbar),
        ),
        "langlaeufer": {},
        "dauer_stunden_median": {},
        "laengenverteilung": {},
    }

    vollstaendig = [v for v in vorgaenge if not v.randvorgang
                    and any(n.ist_auswertbar for n in v.nachrichten)]
    for k in KLASSEN:
        gruppe = [v for v in vollstaendig if v.klasse == k]
        ergebnis["langlaeufer"][k] = {
            "ueber_5": _anteil(sum(1 for v in gruppe if v.n_nachrichten > s.langlaeufer_nachrichten),
                               len(gruppe)),
            "ueber_10": _anteil(sum(1 for v in gruppe if v.n_nachrichten > s.langlaeufer_lang),
                                len(gruppe)),
        }
        ergebnis["dauer_stunden_median"][k] = _median([v.dauer_stunden for v in gruppe])
        # Histogramm statt nur Mittelwert -- eine Verteilung luegt weniger.
        eimer = Counter()
        for v in gruppe:
            n = v.n_nachrichten
            eimer["1" if n == 1 else "2-3" if n <= 3 else "4-5" if n <= 5
                  else "6-10" if n <= 10 else ">10"] += 1
        ergebnis["laengenverteilung"][k] = dict(eimer)

    gemischt = [v for v in vollstaendig if v.klasse == VORGANG_GEMISCHT]
    # Praeziseste Annaeherung an "was kostet ein Lieferantenthema intern".
    ergebnis["interner_anteil_in_gemischten"] = _mittel(
        [v.interner_nachrichtenanteil for v in gemischt]
    )
    return ergebnis


def fachbereiche(vorgaenge: list[Vorgang], nachrichten: list[Nachricht],
                 zuordnung: dict[str, str]) -> dict:
    """Volumen je Fachbereich -- immer doppelt: Vorgaenge und Nachrichten."""
    v_je_fb: dict[str, set[str]] = defaultdict(set)
    n_je_fb: Counter = Counter()
    laengen_je_fb: dict[str, list[float]] = defaultdict(list)

    for v in vorgaenge:
        if not any(n.ist_auswertbar for n in v.nachrichten):
            continue
        beteiligte_fb = set()
        for adr in v.beteiligte:
            fb = zuordnung.get(adr)
            if fb:
                beteiligte_fb.add(fb)
        if not beteiligte_fb:
            beteiligte_fb = {"Unbekannt/Sonstige"}
        for fb in beteiligte_fb:
            v_je_fb[fb].add(v.thread_id)
            n_je_fb[fb] += sum(1 for n in v.nachrichten if n.ist_auswertbar)
            laengen_je_fb[fb].append(float(v.n_nachrichten))

    gesamt_v = sum(len(s) for s in v_je_fb.values()) or 1
    gesamt_n = sum(n_je_fb.values()) or 1
    zeilen = []
    for fb in sorted(v_je_fb, key=lambda x: -len(v_je_fb[x])):
        zeilen.append({
            "fachbereich": fb,
            "vorgaenge": len(v_je_fb[fb]),
            "nachrichten": n_je_fb[fb],
            "anteil_vorgaenge": len(v_je_fb[fb]) / gesamt_v,
            "anteil_nachrichten": n_je_fb[fb] / gesamt_n,
            "vorgangsgroesse_median": _median(laengen_je_fb[fb]),
        })
    unbekannt = next((z for z in zeilen if z["fachbereich"] == "Unbekannt/Sonstige"), None)
    return {
        "zeilen": zeilen,
        # Solange der ueber der Warnschwelle liegt, sind die Aussagen dieser
        # Seite nicht belastbar -- und das muss im Report stehen.
        "anteil_unbekannt": unbekannt["anteil_vorgaenge"] if unbekannt else 0.0,
    }


def lieferanten(vorgaenge: list[Vorgang], nachrichten: list[Nachricht],
                kategorien: dict[str, str] | None = None) -> dict:
    kategorien = kategorien or {}
    volumen: Counter = Counter()
    vorgaenge_je_domain: dict[str, set[str]] = defaultdict(set)
    gesendet_je_domain: Counter = Counter()
    empfangen_je_domain: Counter = Counter()
    erstkontakt: dict[str, datetime] = {}

    for v in vorgaenge:
        for n in v.nachrichten:
            if not n.ist_auswertbar:
                continue
            for adr, kl in zip([n.absender_id, *n.empfaenger_ids],
                               [n.absender_klasse, *n.empfaenger_klassen]):
                if kl != EXTERN:
                    continue
                d = domain_von(adr)
                volumen[d] += 1
                vorgaenge_je_domain[d].add(v.thread_id)
                if n.richtung == RICHTUNG_GESENDET:
                    gesendet_je_domain[d] += 1
                else:
                    empfangen_je_domain[d] += 1
                if d not in erstkontakt or n.zeitstempel < erstkontakt[d]:
                    erstkontakt[d] = n.zeitstempel

    gesamt = sum(volumen.values()) or 1
    top = volumen.most_common(15)
    anteile = sorted((v / gesamt for v in volumen.values()), reverse=True)
    return {
        "top_domains": [
            {
                "domain": d,
                "nachrichten": v,
                "vorgaenge": len(vorgaenge_je_domain[d]),
                "anteil": v / gesamt,
                "gesendet": gesendet_je_domain[d],
                "empfangen": empfangen_je_domain[d],
                "kategorie": kategorien.get(d, "Unbekannt"),
            }
            for d, v in top
        ],
        "anteil_top10": sum(anteile[:10]),
        # HHI ueber Anteile in Prozentpunkten -- gaengige Lesart: >2500 stark
        # konzentriert.  Bewusst ohne Ampel, es gibt keinen Zielwert.
        "hhi": sum((a * 100) ** 2 for a in anteile),
        "domains_gesamt": len(volumen),
    }


def zeitverlauf(vorgaenge: list[Vorgang], nachrichten: list[Nachricht]) -> dict:
    monate_v: dict[str, Counter] = defaultdict(Counter)
    monate_n: dict[str, Counter] = defaultdict(Counter)
    wochentage: Counter = Counter()
    stunden: Counter = Counter()

    for v in vorgaenge:
        auswertbare = [n for n in v.nachrichten if n.ist_auswertbar]
        if not auswertbare:
            continue
        monat = v.beginn.strftime("%Y-%m")
        monate_v[monat][v.klasse] += 1
        for n in auswertbare:
            monate_n[n.zeitstempel.strftime("%Y-%m")][v.klasse] += 1
            wochentage[n.zeitstempel.weekday()] += 1
            stunden[n.zeitstempel.hour] += 1

    return {
        "monate_vorgaenge": {m: dict(c) for m, c in sorted(monate_v.items())},
        "monate_nachrichten": {m: dict(c) for m, c in sorted(monate_n.items())},
        "wochentage": {t: wochentage.get(t, 0) for t in range(7)},
        # Nur im persoenlichen Report -- im Teamexport bewusst nicht enthalten.
        "stunden": {h: stunden.get(h, 0) for h in range(24)},
    }


def stabilitaet(kpi_conv: dict, kpi_fallback: dict) -> dict:
    """Abweichung der Kern-KPIs zwischen beiden Vorgangsverfahren.

    Weicht sie deutlich ab, ist die Vorgangsbildung instabil und die
    Vorgangsebene entsprechend zu relativieren.
    """
    abweichungen = {
        k: abs(kpi_conv["k1_vorgangsanteile"][k] - kpi_fallback["k1_vorgangsanteile"][k])
        for k in KLASSEN
    }
    groesste = max(abweichungen.values()) if abweichungen else 0.0
    return {
        "abweichung_je_klasse": abweichungen,
        "groesste_abweichung": groesste,
        "stabil": groesste <= 0.05,
        "vorgaenge_conv": kpi_conv["n_vorgaenge"],
        "vorgaenge_fallback": kpi_fallback["n_vorgaenge"],
    }


def alles_berechnen(vorgaenge: list[Vorgang], nachrichten: list[Nachricht],
                    config: Config, zuordnung: dict[str, str] | None = None,
                    kategorien: dict[str, str] | None = None) -> dict:
    return {
        "kern": kern_kpis(vorgaenge, nachrichten),
        "koordination": koordinationslast(vorgaenge, nachrichten, config),
        "fachbereiche": fachbereiche(vorgaenge, nachrichten, zuordnung or {}),
        "lieferanten": lieferanten(vorgaenge, nachrichten, kategorien),
        "zeit": zeitverlauf(vorgaenge, nachrichten),
    }


# =====================================================================
#  Vollerhebung -- Auswertungen, die ueber die Kern-KPIs hinausgehen.
#  Sie sind aussagekraeftig, aber methodisch angreifbar; im Report sind
#  sie als explorativ gekennzeichnet und gehen nie in den Teamexport ein.
# =====================================================================

def antwortzeiten(vorgaenge: list[Vorgang], config: Config,
                  eigene_adressen: set[str] | None = None) -> dict:
    """Zeit bis zur Antwort, getrennt nach Klasse und Richtung.

    Gezaehlt wird nur der Sprecherwechsel innerhalb eines Vorgangs: zwei
    Nachrichten derselben Person hintereinander sind Nachfassen, keine Antwort.
    Spannen ueber der Obergrenze fallen heraus -- nach zwei Wochen ist eine
    Nachricht kein Reaktions-, sondern ein neuer Anlauf.
    """
    grenze = config.schwellen.max_antwortzeit_stunden
    eigene = eigene_adressen or set()
    spannen: dict[str, list[float]] = defaultdict(list)

    for vorgang in vorgaenge:
        auswertbar = [n for n in vorgang.nachrichten if n.ist_auswertbar]
        for vorher, nachher in zip(auswertbar, auswertbar[1:]):
            if vorher.absender_id == nachher.absender_id:
                continue
            stunden = (nachher.zeitstempel - vorher.zeitstempel).total_seconds() / 3600
            if not 0 <= stunden <= grenze:
                continue
            spannen[vorgang.klasse].append(stunden)
            if eigene:
                richtung = ("von_mir" if nachher.absender_id in eigene
                            else "an_mich" if vorher.absender_id in eigene else None)
                if richtung:
                    spannen[richtung].append(stunden)

    ergebnis = {}
    for schluessel, werte in spannen.items():
        q1, q3 = _quartile(werte)
        ergebnis[schluessel] = {
            "median_stunden": _median(werte),
            "q1": q1, "q3": q3, "n": len(werte),
            "anteil_unter_4h": _anteil(sum(1 for w in werte if w <= 4), len(werte)),
            "anteil_ueber_48h": _anteil(sum(1 for w in werte if w > 48), len(werte)),
        }
    return ergebnis


def arbeitszeitmuster(nachrichten: list[Nachricht], config: Config) -> dict:
    """Wann gearbeitet wird -- bezogen auf selbst gesendete Nachrichten.

    Empfangene Mails sagen nichts ueber die eigene Arbeitszeit, nur ueber die
    der anderen.  Deshalb zaehlt hier nur, was man selbst verschickt hat.
    """
    beginn = config.schwellen.arbeitsbeginn_stunde
    ende = config.schwellen.arbeitsende_stunde
    gesendet = [n for n in nachrichten
                if n.ist_auswertbar and n.richtung == RICHTUNG_GESENDET]
    if not gesendet:
        return {"n": 0}

    ausserhalb = [n for n in gesendet
                  if not (beginn <= n.zeitstempel.hour < ende)]
    wochenende = [n for n in gesendet if n.zeitstempel.weekday() >= 5]
    return {
        "n": len(gesendet),
        "anteil_ausserhalb": _anteil(len(ausserhalb), len(gesendet)),
        "anteil_wochenende": _anteil(len(wochenende), len(gesendet)),
        "anteil_vor_beginn": _anteil(
            sum(1 for n in gesendet if n.zeitstempel.hour < beginn), len(gesendet)),
        "anteil_nach_ende": _anteil(
            sum(1 for n in gesendet if n.zeitstempel.hour >= ende), len(gesendet)),
        "fenster": (beginn, ende),
    }


def netzwerk(vorgaenge: list[Vorgang], nachrichten: list[Nachricht],
             zuordnung: dict[str, str] | None = None,
             eigene_adressen: set[str] | None = None, top: int = 15) -> dict:
    """Wichtigste Gegenueber und wie stark sich Kommunikation auf sie ballt."""
    zuordnung = zuordnung or {}
    eigene = eigene_adressen or set()

    volumen: Counter = Counter()
    threads_je: dict[str, set[str]] = defaultdict(set)
    partner_je: dict[str, set[str]] = defaultdict(set)
    klasse_je: dict[str, str] = {}

    for vorgang in vorgaenge:
        for n in vorgang.nachrichten:
            if not n.ist_auswertbar:
                continue
            beteiligte = [(a, k) for a, k in
                          zip([n.absender_id, *n.empfaenger_ids],
                              [n.absender_klasse, *n.empfaenger_klassen])
                          if a and a not in eigene]
            for adresse, klasse in beteiligte:
                volumen[adresse] += 1
                threads_je[adresse].add(vorgang.thread_id)
                klasse_je[adresse] = klasse
                # Grad: mit wie vielen anderen taucht diese Person zusammen auf.
                partner_je[adresse] |= {a for a, _ in beteiligte if a != adresse}

    gesamt = sum(volumen.values()) or 1
    anteile = sorted((v / gesamt for v in volumen.values()), reverse=True)

    def zeilen(nur_klasse: str) -> list[dict]:
        gefiltert = [(a, v) for a, v in volumen.most_common()
                     if klasse_je.get(a) == nur_klasse]
        return [{
            "adresse": a,
            "fachbereich": zuordnung.get(a, "Unbekannt/Sonstige"),
            "nachrichten": v,
            "vorgaenge": len(threads_je[a]),
            "grad": len(partner_je[a]),
            "anteil": v / gesamt,
        } for a, v in gefiltert[:top]]

    return {
        "top_intern": zeilen(INTERN),
        "top_extern": zeilen(EXTERN),
        "partner_gesamt": len(volumen),
        # Wie stark haengt die Kommunikation an wenigen Personen?
        "anteil_top5": sum(anteile[:5]),
        "anteil_top10": sum(anteile[:10]),
        "gini": _gini(list(volumen.values())),
    }


def _gini(werte: list[int]) -> float:
    """0 = gleichmaessig verteilt, 1 = alles haengt an einer Person."""
    if not werte or sum(werte) == 0:
        return 0.0
    sortiert = sorted(werte)
    n = len(sortiert)
    summe = sum((2 * i - n + 1) * w for i, w in enumerate(sortiert))
    return summe / (n * sum(sortiert))


def anhaenge(nachrichten: list[Nachricht]) -> dict:
    """Anhaenge und Dateitypen.

    Die Groesse steht bewusst nur hier und wird nie als Aufwandsmass benutzt --
    sie misst Dateianhaenge, nicht Arbeit.
    """
    auswertbar = [n for n in nachrichten if n.ist_auswertbar]
    if not auswertbar:
        return {"n": 0}
    mit = [n for n in auswertbar if n.n_anhaenge or n.hat_anhang]
    endungen: Counter = Counter()
    for n in auswertbar:
        for name in n.anhangnamen:
            if "." in name:
                endungen[name.rsplit(".", 1)[1].lower()[:8]] += 1
    groessen = [n.groesse for n in auswertbar if n.groesse]
    return {
        "n": len(auswertbar),
        "anteil_mit_anhang": _anteil(len(mit), len(auswertbar)),
        "anhaenge_je_nachricht": _mittel([float(n.n_anhaenge) for n in mit]),
        "top_dateitypen": endungen.most_common(12),
        "groesse_median_kb": _median([g / 1024 for g in groessen]),
        "volumen_gesamt_mb": sum(groessen) / (1024 * 1024) if groessen else 0.0,
    }


def termine(nachrichten: list[Nachricht]) -> dict:
    """Terminobjekte -- getrennt gefuehrt, nie als Mail gezaehlt.

    Koordinationslast steckt primaer in Meetings.  Ohne Kalenderdaten ist das
    hier nur ein Abbild der Einladungen, aber es ist der erste Hinweis darauf,
    wie viel Abstimmung ueberhaupt neben den Mails laeuft.
    """
    objekte = [n for n in nachrichten if n.klasse == TERMIN]
    if not objekte:
        return {"n": 0}
    extern = [n for n in objekte if n.hat_externen_empfaenger
              or n.absender_klasse == EXTERN]
    return {
        "n": len(objekte),
        "anteil_extern": _anteil(len(extern), len(objekte)),
        "organisatoren": len({n.absender_id for n in objekte}),
        "teilnehmer_mittel": _mittel([float(n.n_empfaenger) for n in objekte]),
    }


def bcc_nutzung(nachrichten: list[Nachricht]) -> dict:
    """BCC -- nur bei selbst gesendeten Nachrichten ueberhaupt sichtbar.

    Deshalb ausdruecklich als eigene Kennzahl und nicht in den Empfaengerzahlen
    versteckt: Ein Vergleich mit empfangener Kommunikation waere sinnlos.
    """
    gesendet = [n for n in nachrichten
                if n.ist_auswertbar and n.richtung == RICHTUNG_GESENDET]
    mit = [n for n in gesendet if n.n_bcc]
    return {
        "n_gesendet": len(gesendet),
        "anteil_mit_bcc": _anteil(len(mit), len(gesendet)),
        "bcc_empfaenger_mittel": _mittel([float(n.n_bcc) for n in mit]),
    }


def weiterleitungen(nachrichten: list[Nachricht]) -> dict:
    """Anteil Weiterleitungen -- Indikator fuer Durchreichen statt Entscheiden."""
    intern = [n for n in nachrichten
              if n.ist_auswertbar and not n.hat_externen_empfaenger]
    return {
        "n_intern": len(intern),
        "anteil_weitergeleitet": _anteil(
            sum(1 for n in intern if n.ist_weiterleitung), len(intern)),
        "anteil_antworten": _anteil(
            sum(1 for n in intern if n.ist_antwort), len(intern)),
    }


def vollerhebung(vorgaenge: list[Vorgang], nachrichten: list[Nachricht],
                 config: Config, zuordnung: dict[str, str] | None = None,
                 eigene_adressen: set[str] | None = None) -> dict:
    """Alle zusaetzlichen Auswertungen in einem Rutsch."""
    return {
        "antwortzeiten": antwortzeiten(vorgaenge, config, eigene_adressen),
        "arbeitszeit": arbeitszeitmuster(nachrichten, config),
        "netzwerk": netzwerk(vorgaenge, nachrichten, zuordnung, eigene_adressen),
        "anhaenge": anhaenge(nachrichten),
        "termine": termine(nachrichten),
        "bcc": bcc_nutzung(nachrichten),
        "weiterleitungen": weiterleitungen(nachrichten),
    }
