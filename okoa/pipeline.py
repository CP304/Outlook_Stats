"""Ablaufsteuerung: von den Rohnachrichten bis zu Report und Teamexport.

Die Stufe kennt bewusst keinen COM-Zugriff -- sie bekommt die Nachrichten
uebergeben.  Dadurch laesst sich der gesamte Ablauf ohne Outlook pruefen.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from . import mapping, metrics, report, team_export, threads
from .config import Config
from .model import Nachricht, cache_lesen, cache_schreiben
from .normalize import deduplizieren, qualitaetskennzahlen


DATEI_CACHE = "messages.csv"
DATEI_PERSONEN = "mapping_personen.xlsx"
DATEI_DOMAINS = "mapping_domains.xlsx"
DATEI_REPORT = "Mein_Report.html"


def fensterbeginn(config: Config, bezug: datetime | None = None) -> datetime:
    bezug = bezug or datetime.now()
    return bezug - timedelta(days=30 * config.zeitraum_monate)


def auswerten(nachrichten: list[Nachricht], config: Config, ordner: Path | str,
              kontext: dict | None = None, hypothese: float | None = 0.80,
              bezugszeitpunkt: datetime | None = None) -> dict:
    """Rechnet die gesamte Auswertung und schreibt alle Ergebnisdateien."""
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    kontext = dict(kontext or {})

    entdoppelt, entfernt = deduplizieren(nachrichten)
    threads.zuordnen(entdoppelt, luecke_tage=config.schwellen.thread_luecke_tage)

    beginn = fensterbeginn(config, bezugszeitpunkt)
    vorgaenge = threads.vorgaenge_bilden(entdoppelt, threads.VERFAHREN_CONV, beginn)
    vorgaenge_fb = threads.vorgaenge_bilden(entdoppelt, threads.VERFAHREN_FALLBACK, beginn)

    # Gepflegte Zuordnungen einlesen, falls vorhanden.
    zuordnung = mapping.zuordnung_lesen(ordner / DATEI_PERSONEN, "E-Mail", "Fachbereich")
    kategorien = mapping.zuordnung_lesen(ordner / DATEI_DOMAINS, "Domain", "Kategorie")

    kpi = metrics.alles_berechnen(vorgaenge, entdoppelt, config, zuordnung, kategorien)
    if config.vollerhebung:
        eigene = set(kontext.get("eigene_adressen") or [])
        if not eigene:
            # Ohne Outlook (Demo, Cache) aus der Richtung ableiten.
            eigene = {n.absender_id for n in entdoppelt
                      if n.richtung == "gesendet" and n.absender_id}
        kpi["vollerhebung"] = metrics.vollerhebung(
            vorgaenge, entdoppelt, config, zuordnung, eigene)
    kpi_fb = metrics.kern_kpis(vorgaenge_fb, entdoppelt)
    stabilitaet = metrics.stabilitaet(kpi["kern"], kpi_fb)
    qualitaet = qualitaetskennzahlen(entdoppelt, entfernt)

    if entdoppelt:
        von = min(n.zeitstempel for n in entdoppelt).strftime("%d.%m.%Y")
        bis = max(n.zeitstempel for n in entdoppelt).strftime("%d.%m.%Y")
        iso = (min(n.zeitstempel for n in entdoppelt).date().isoformat(),
               max(n.zeitstempel for n in entdoppelt).date().isoformat())
    else:
        von = bis = "—"
        iso = ("", "")
    kontext.setdefault("zeitraum", f"{von} bis {bis}")
    kontext.setdefault("ausgeschlossene_ordner", config.ordner_ausschluss)
    kontext.setdefault("stores", sorted({n.store for n in entdoppelt if n.store}))

    if not config.vollerhebung:
        # Die Zusage 'keine Inhalte' wird hier durchgesetzt, nicht erst beim
        # Auslesen: Wo die Daten herkommen, darf keine Rolle spielen.
        for n in entdoppelt:
            n.betreff = ""
            n.anhangnamen = []
            n.groesse = 0
    cache_schreiben(entdoppelt, ordner / DATEI_CACHE)

    # Mapping-Dateien erzeugen bzw. behutsam ergaenzen.
    personen = mapping.personen_sammeln(vorgaenge, entdoppelt)
    domains = mapping.domains_sammeln(vorgaenge, entdoppelt)
    pfad_personen, neue_personen = mapping.ergaenzen(
        personen, mapping.SPALTEN_PERSONEN, ordner / DATEI_PERSONEN, "E-Mail")
    pfad_domains, neue_domains = mapping.ergaenzen(
        domains, mapping.SPALTEN_DOMAINS, ordner / DATEI_DOMAINS, "Domain")

    pfad_report = report.erzeugen(
        kpi, qualitaet, stabilitaet, kontext, ordner / DATEI_REPORT, hypothese,
        config.schwellen.warnschwelle_unaufgeloest,
        config.schwellen.warnschwelle_unbekannter_fachbereich,
    )
    export = team_export.aufbauen(kpi, qualitaet, iso)

    return {
        "kpi": kpi,
        "qualitaet": qualitaet,
        "stabilitaet": stabilitaet,
        "export": export,
        "report": pfad_report,
        "cache": ordner / DATEI_CACHE,
        "mapping_personen": pfad_personen,
        "mapping_domains": pfad_domains,
        "neue_personen": neue_personen,
        "neue_domains": neue_domains,
        "n_nachrichten": len(entdoppelt),
        "n_vorgaenge": kpi["kern"]["n_vorgaenge"],
    }


def aus_cache(ordner: Path | str, config: Config, **kwargs) -> dict:
    """Rechnet erneut auf der vorhandenen Zwischendatei -- ohne Outlook."""
    ordner = Path(ordner)
    nachrichten = cache_lesen(ordner / DATEI_CACHE)
    return auswerten(nachrichten, config, ordner, **kwargs)
