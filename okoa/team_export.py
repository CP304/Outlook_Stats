"""Teamexport und Zusammenfuehrung.

Zwei Zusagen aus docs/08-datenschutz.md, die hier eingeloest werden:

1. Der Export enthaelt ausschliesslich aggregierte Kennzahlen.  Die Liste der
   erlaubten Felder ist abschliessend und wird beim Schreiben erzwungen -- was
   nicht in EXPORT_FELDER steht, kann die Datei nicht verlassen.
2. Die Zusammenfuehrung kennt weder COM noch Zwischendatei.  Dieses Modul
   importiert bewusst nichts, was Zugang zu Rohdaten haette.

Mindestgruppengroesse und Zellensperre sind Konstanten und absichtlich nicht
konfigurierbar.  Ein Schalter, der sie aufweicht, waere genau die Hintertuer,
deren Fehlen das Verfahren zustimmungsfaehig macht.
"""

from __future__ import annotations

import json
import secrets
import statistics
from pathlib import Path


MINDEST_TEILNEHMER = 5
MINDEST_FALLZAHL = 5
NICHT_AUSGEWIESEN = "n. a."

# Abschliessende Liste dessen, was uebermittelt wird.  Sie steht wortgleich in
# docs/09-teilnahme.md, damit jeder Teilnehmer sie pruefen kann.
EXPORT_FELDER = [
    "zeitraum_von", "zeitraum_bis",
    "vorgaenge_intern", "vorgaenge_gemischt", "vorgaenge_extern",
    "nachrichten_intern", "nachrichten_gemischt", "nachrichten_extern",
    "nachrichten_je_vorgang_mittel_intern", "nachrichten_je_vorgang_median_intern",
    "nachrichten_je_vorgang_mittel_gemischt", "nachrichten_je_vorgang_median_gemischt",
    "nachrichten_je_vorgang_mittel_extern", "nachrichten_je_vorgang_median_extern",
    "beteiligte_je_vorgang_mittel_intern", "beteiligte_je_vorgang_median_intern",
    "beteiligte_je_vorgang_mittel_gemischt", "beteiligte_je_vorgang_median_gemischt",
    "beteiligte_je_vorgang_mittel_extern", "beteiligte_je_vorgang_median_extern",
    "cc_quote_intern", "cc_empfaenger_mittel",
    "langlaeufer_ueber5_intern", "langlaeufer_ueber10_intern",
    "langlaeufer_ueber5_gemischt", "langlaeufer_ueber10_gemischt",
    "langlaeufer_ueber5_extern", "langlaeufer_ueber10_extern",
    "aussenorientierung", "interner_anteil_in_gemischten",
    "externe_domains", "externe_domains_aktiv", "hhi",
    "fachbereichsanteile", "wochentage",
    "anteil_unaufgeloest", "anteil_duplikate", "anteil_automatisiert",
]

# Alles, was den Teilnehmer identifizierbar machen koennte.  Der Export wird
# vor dem Schreiben dagegen geprueft -- ein Denkfehler soll auffallen, nicht
# durchrutschen.
VERBOTENE_SCHLUESSEL = {
    "name", "email", "e-mail", "adresse", "absender", "empfaenger", "betreff",
    "domain", "domains_liste", "top_domains", "postfach", "benutzer", "user",
    "rechner", "host", "stunden", "uhrzeit", "erstellt", "zeitstempel", "id",
}


class ExportFehler(ValueError):
    """Der Export haette etwas enthalten, das er nicht enthalten darf."""


def _pruefen(daten: dict) -> None:
    unerlaubt = set(daten) - set(EXPORT_FELDER)
    if unerlaubt:
        raise ExportFehler(
            "Der Teamexport enthielte Felder, die nicht vorgesehen sind: "
            + ", ".join(sorted(unerlaubt))
        )
    for schluessel in daten:
        for verboten in VERBOTENE_SCHLUESSEL:
            if verboten in schluessel.lower() and schluessel in ("domain", "stunden"):
                raise ExportFehler(f"Feld '{schluessel}' darf nicht exportiert werden.")


def aufbauen(kennzahlen: dict, qualitaet: dict, zeitraum: tuple[str, str]) -> dict:
    """Baut den Export aus den bereits berechneten Kennzahlen.

    Bewusst nicht enthalten: Domainnamen, Uhrzeiten, Tagesdaten, Postfach- oder
    Rechnername, Laufzeitstempel, Einzelvorgaenge.
    """
    kern = kennzahlen["kern"]
    koord = kennzahlen["koordination"]

    daten = {
        # Monatsaufloesung -- kein Tagesdatum, kein Laufzeitstempel.
        "zeitraum_von": zeitraum[0][:7],
        "zeitraum_bis": zeitraum[1][:7],
        "cc_quote_intern": round(koord["cc_quote_intern"], 4),
        "cc_empfaenger_mittel": round(koord["cc_empfaenger_mittel"], 2),
        "aussenorientierung": round(kern["k5_aussenorientierung"], 4),
        "interner_anteil_in_gemischten": round(koord["interner_anteil_in_gemischten"], 4),
        "externe_domains": kern["k6_reichweite"]["domains_gesamt"],
        "externe_domains_aktiv": kern["k6_reichweite"]["domains_aktiv"],
        "hhi": round(kennzahlen["lieferanten"]["hhi"]),
        "fachbereichsanteile": {
            z["fachbereich"]: round(z["anteil_vorgaenge"], 4)
            for z in kennzahlen["fachbereiche"]["zeilen"]
        },
        "wochentage": kennzahlen["zeit"]["wochentage"],
        "anteil_unaufgeloest": round(qualitaet["anteil_unaufgeloest"], 4),
        "anteil_duplikate": round(
            qualitaet["duplikate_entfernt"] / max(1, qualitaet["nachrichten_gesamt"]), 4),
        "anteil_automatisiert": round(qualitaet["anteil_automatisiert"], 4),
    }

    anteile_v = kern["k1_vorgangsanteile"]
    anteile_n = kern["k2_nachrichtenanteile"]
    for klasse in ("intern", "gemischt", "extern"):
        daten[f"vorgaenge_{klasse}"] = round(anteile_v[klasse] * kern["n_vorgaenge"])
        daten[f"nachrichten_{klasse}"] = round(anteile_n[klasse] * kern["n_nachrichten"])
        tiefe = kern["k3_koordinationstiefe"][klasse]
        breite = kern["k4_beteiligungsbreite"][klasse]
        daten[f"nachrichten_je_vorgang_mittel_{klasse}"] = round(tiefe["mittel"], 2)
        daten[f"nachrichten_je_vorgang_median_{klasse}"] = round(tiefe["median"], 2)
        daten[f"beteiligte_je_vorgang_mittel_{klasse}"] = round(breite["mittel"], 2)
        daten[f"beteiligte_je_vorgang_median_{klasse}"] = round(breite["median"], 2)
        daten[f"langlaeufer_ueber5_{klasse}"] = round(koord["langlaeufer"][klasse]["ueber_5"], 4)
        daten[f"langlaeufer_ueber10_{klasse}"] = round(koord["langlaeufer"][klasse]["ueber_10"], 4)

    _pruefen(daten)
    return daten


def schreiben(daten: dict, ordner: Path | str) -> Path:
    """Schreibt unter einer Zufalls-ID -- kein Benutzername im Dateinamen."""
    _pruefen(daten)
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"team_export_{secrets.token_hex(8)}.json"
    pfad.write_text(json.dumps(daten, indent=2, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8")
    return pfad


def als_klartext(daten: dict) -> str:
    """Fuer den Abschlussdialog: 'Das -- und nur das -- wuerde geteilt.'"""
    zeilen = ["Das -- und nur das -- wuerde geteilt:", ""]
    for schluessel in EXPORT_FELDER:
        if schluessel not in daten:
            continue
        wert = daten[schluessel]
        if isinstance(wert, dict):
            wert = ", ".join(f"{k}: {v}" for k, v in wert.items())
        zeilen.append(f"  {schluessel:42s} {wert}")
    zeilen += ["", "Nicht enthalten: Namen, E-Mail-Adressen, Domainnamen, Betreffzeilen,",
               "Anhangnamen, Uhrzeiten, Tagesdaten, Postfach- oder Rechnername."]
    return "\n".join(zeilen)


# ------------------------------------------------------------ Zusammenfuehren

class ZuWenigTeilnehmer(RuntimeError):
    pass


def einlesen(ordner: Path | str) -> list[dict]:
    ordner = Path(ordner)
    dateien = sorted(ordner.glob("team_export*.json"))
    daten = []
    for datei in dateien:
        try:
            inhalt = json.loads(datei.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(inhalt, dict) and "vorgaenge_intern" in inhalt:
            daten.append(inhalt)
    return daten


def _gesperrt(werte: list, fallzahl: int):
    """Zellensperre: zu kleine Fallzahl wird nicht ausgewiesen.

    Das verhindert den klassischen Angriff auf anonymisierte Aggregate --
    Rueckschluss ueber die Kombination duenn besetzter Kategorien.
    """
    if fallzahl < MINDEST_FALLZAHL or not werte:
        return NICHT_AUSGEWIESEN
    return werte


def zusammenfuehren(exporte: list[dict]) -> dict:
    """Gruppenkennzahlen.

    Keine Einzelbeitraege, keine Min-/Max-Werte, keine Spannweiten -- sie
    verraten Ausreisser und damit Personen.  Stattdessen Median und Quartile.
    """
    if len(exporte) < MINDEST_TEILNEHMER:
        raise ZuWenigTeilnehmer(
            f"Es liegen {len(exporte)} Dateien vor, noetig sind mindestens "
            f"{MINDEST_TEILNEHMER}.  Mit weniger Teilnehmern liesse sich aus dem "
            f"Ergebnis auf einzelne Personen schliessen; deshalb wird hier "
            f"bewusst kein Teilergebnis ausgegeben."
        )

    ergebnis: dict = {"n_teilnehmer": len(exporte), "kennzahlen": {}, "fachbereiche": {}}

    zahlenfelder = [f for f in EXPORT_FELDER
                    if f not in ("zeitraum_von", "zeitraum_bis", "fachbereichsanteile", "wochentage")]
    for feld in zahlenfelder:
        werte = [e[feld] for e in exporte if isinstance(e.get(feld), (int, float))]
        if len(werte) < MINDEST_FALLZAHL:
            ergebnis["kennzahlen"][feld] = NICHT_AUSGEWIESEN
            continue
        q1, q3 = statistics.quantiles(werte, n=4)[0], statistics.quantiles(werte, n=4)[2]
        ergebnis["kennzahlen"][feld] = {
            "median": round(statistics.median(werte), 4),
            "q1": round(q1, 4),
            "q3": round(q3, 4),
            "summe": round(sum(werte), 4) if feld.startswith(("vorgaenge_", "nachrichten_")) else None,
        }

    # Fachbereiche: nur ausweisen, wenn genuegend Teilnehmer sie ueberhaupt melden.
    alle_fb: dict[str, list[float]] = {}
    for e in exporte:
        for fb, anteil in (e.get("fachbereichsanteile") or {}).items():
            alle_fb.setdefault(fb, []).append(anteil)
    for fb, werte in sorted(alle_fb.items(), key=lambda x: -len(x[1])):
        ergebnis["fachbereiche"][fb] = (
            {"median": round(statistics.median(werte), 4), "teilnehmer": len(werte)}
            if len(werte) >= MINDEST_FALLZAHL else NICHT_AUSGEWIESEN
        )

    wochentage = {t: [] for t in range(7)}
    for e in exporte:
        for t, wert in (e.get("wochentage") or {}).items():
            wochentage[int(t)].append(wert)
    ergebnis["wochentage"] = {
        t: (round(statistics.median(w)) if len(w) >= MINDEST_FALLZAHL else NICHT_AUSGEWIESEN)
        for t, w in wochentage.items()
    }
    zeitraeume = [e.get("zeitraum_von", "") for e in exporte if e.get("zeitraum_von")]
    ergebnis["zeitraum"] = (min(zeitraeume, default=""),
                            max((e.get("zeitraum_bis", "") for e in exporte), default=""))
    return ergebnis
