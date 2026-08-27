"""Laufende Arbeiten fuer die Oberflaeche.

Die Oberflaeche darf nicht blockieren, waehrend Outlook ausgelesen wird -- ein
eingefrorenes Fenster sieht aus wie ein Absturz.  Deshalb laeuft jede laengere
Arbeit in einem eigenen Faden und meldet sich ueber eine Warteschlange zurueck.

Hier steht ausschliesslich Ablauflogik, keine Oberflaeche.  Damit laesst sich
alles ohne Fenster pruefen.
"""

from __future__ import annotations

import queue
import threading
import traceback
from datetime import datetime
from pathlib import Path

from . import kontakte as kontakte_modul
from . import kontaktexport
from . import einstellungen as einstellungen_modul
from . import mapping, pipeline, team_export
from .config import Config


# Nachrichtenarten in der Warteschlange
MELDUNG = "meldung"
FERTIG = "fertig"
FEHLER = "fehler"


class Auftrag:
    """Fuehrt eine Arbeit im Hintergrund aus und meldet den Verlauf."""

    def __init__(self) -> None:
        self.warteschlange: queue.Queue = queue.Queue()
        self._faden: threading.Thread | None = None

    @property
    def laeuft(self) -> bool:
        return self._faden is not None and self._faden.is_alive()

    def starten(self, arbeit, *args, **kwargs) -> bool:
        """Startet eine Arbeit, wenn nicht schon eine laeuft."""
        if self.laeuft:
            return False
        self._faden = threading.Thread(
            target=self._ausfuehren, args=(arbeit, args, kwargs), daemon=True)
        self._faden.start()
        return True

    def _ausfuehren(self, arbeit, args, kwargs) -> None:
        # COM muss in jedem Faden einzeln angemeldet werden.  Ohne das schlaegt
        # der Outlook-Zugriff im Hintergrundfaden fehl -- ein Fehler, der sonst
        # erst beim Anwender auftritt und dort unerklaerlich aussieht.
        angemeldet = False
        try:
            import pythoncom  # noqa: PLC0415  -- nur unter Windows vorhanden

            pythoncom.CoInitialize()
            angemeldet = True
        except Exception:
            pass

        try:
            ergebnis = arbeit(self.melden, *args, **kwargs)
            self.warteschlange.put((FERTIG, ergebnis))
        except Exception as fehler:
            self.warteschlange.put((FEHLER, (str(fehler), traceback.format_exc())))
        finally:
            if angemeldet:
                try:
                    import pythoncom

                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def melden(self, text: str) -> None:
        self.warteschlange.put((MELDUNG, text))

    def abholen(self) -> list[tuple[str, object]]:
        """Holt alle vorliegenden Meldungen ab, ohne zu warten."""
        meldungen = []
        while True:
            try:
                meldungen.append(self.warteschlange.get_nowait())
            except queue.Empty:
                return meldungen


# ------------------------------------------------------------- Arbeiten

def _vollerhebung_melden(melden, ergebnis: dict) -> None:
    """Sagt im Verlauf, was die Vollerhebung zusaetzlich gerechnet hat.

    Ohne diese Zeile sieht ein Lauf mit Vollerhebung im Fenster genauso aus
    wie einer ohne -- der Unterschied steckt nur im Report.
    """
    voll = ergebnis.get("kpi", {}).get("vollerhebung")
    if not voll:
        return
    antwort = voll["antwortzeiten"].get("intern", {}).get("median_stunden")
    netz = voll["netzwerk"]["partner_gesamt"]
    teile = [f"{netz} Kommunikationspartner"]
    if antwort:
        teile.append(f"interne Antwortzeit im Median {antwort:.0f} h")
    if voll["termine"].get("n"):
        teile.append(f"{voll['termine']['n']} Terminobjekte")
    melden("Vollerhebung gerechnet: " + ", ".join(teile) + ".")
    melden("Einzelheiten im Report unter „Vollerhebung“.")

def analyse(melden, config: Config, ordner: Path, hypothese: float) -> dict:
    """Postfach auslesen und auswerten."""
    from .extract_outlook import auslesen

    melden(f"Lese Outlook, Zeitraum {config.zeitraum_monate} Monate ...")
    melden("Es wird ausschließlich gelesen; am Postfach ändert sich nichts.")
    if config.vollerhebung:
        melden("Vollerhebung: Betreff, Anhangnamen, Größe und BCC werden erfasst.")

    nachrichten, berichte = auslesen(config, fortschritt=melden)
    melden(f"{len(nachrichten)} Elemente gelesen. Werte aus ...")

    config.speichern(ordner / "config.json")
    ergebnis = pipeline.auswerten(
        nachrichten, config, ordner,
        kontext={"stores": berichte["stores"],
                 "ausgeschlossene_ordner": config.ordner_ausschluss,
                 "eigene_adressen": berichte.get("eigene_adressen", [])},
        hypothese=hypothese)
    _vollerhebung_melden(melden, ergebnis)
    melden("Fertig.")
    return ergebnis


def neu_berechnen(melden, config: Config, ordner: Path, hypothese: float) -> dict:
    """Auswertung aus der Zwischendatei wiederholen -- ohne Outlook."""
    if not (ordner / pipeline.DATEI_CACHE).exists():
        raise FileNotFoundError(
            "Es gibt noch keine Zwischendatei. Bitte zuerst eine Analyse ausführen.")
    melden("Rechne auf der vorhandenen Zwischendatei ...")
    ergebnis = pipeline.aus_cache(ordner, config, hypothese=hypothese)
    _vollerhebung_melden(melden, ergebnis)
    melden("Fertig.")
    return ergebnis


def demo(melden, config: Config, ordner: Path, hypothese: float) -> dict:
    """Beispielreport aus synthetischen Daten."""
    from .synthetic import belege_erzeugen, postfach_erzeugen

    melden("Erzeuge Beispieldaten (kein Outlook, keine echten Mails) ...")
    nachrichten = postfach_erzeugen(300)
    config.speichern(ordner / "config.json")
    ergebnis = pipeline.auswerten(
        nachrichten, config, ordner, kontext={"stores": ["Beispielpostfach"]},
        hypothese=hypothese, bezugszeitpunkt=datetime(2026, 6, 30))

    from . import threads

    zeilen = kontakte_modul.als_zeilen(
        kontakte_modul.sammeln(threads.vorgaenge_bilden(nachrichten),
                               belege_erzeugen(nachrichten)),
        stichtag=datetime(2026, 6, 30))
    ergebnis["kontaktdatei"] = kontakte_modul.schreiben(
        zeilen, ordner / "Externe_Kontakte.xlsx")
    _vollerhebung_melden(melden, ergebnis)
    melden("Fertig.")
    return ergebnis


def postfach_pruefen(melden, config: Config) -> dict:
    """Zeigt, was Outlook hergibt -- fuer den Fall 'null Nachrichten'."""
    from .extract_outlook import pruefen

    melden("Frage Outlook ab ...")
    bericht = pruefen(config)
    melden(f"Eigene Adressen: {', '.join(bericht['eigene_adressen']) or 'keine erkannt'}")
    for store in bericht["stores"]:
        melden(f"Speicher: {store['name']} (Typ {store['typ']}, "
               f"{'einbezogen' if store['einbezogen'] else 'übersprungen'})")
    for eintrag in bericht["ordner"]:
        melden(f"  {eintrag['store']} / {eintrag['ordner']}: "
               f"{eintrag['elemente']} Elemente, {eintrag['im_zeitraum']} im Zeitraum"
               + ("" if eintrag["filter_greift"] else "  (Zeitfilter ohne Wirkung)"))
    melden(f"Gesamt: {bericht['elemente_gesamt']} Elemente, "
           f"{bericht['elemente_im_zeitraum']} ab {bericht['zeitraum_ab']}")
    return bericht


def kontakte_exportieren(melden, config: Config, ordner: Path,
                         mit_signaturen: bool, fuer_import: bool = False,
                         sprache: str = "de") -> dict:
    """Externe Kontakte als Excel."""
    from . import threads
    from .extract_outlook import auslesen
    from .normalize import deduplizieren

    # Fuer die Adressernte zaehlt Vollstaendigkeit -- hier bleiben nur Junk und
    # Papierkorb aussen vor.
    config = Config(**{**config.__dict__})
    config.ordner_ausschluss = [
        n for n in config.ordner_ausschluss
        if any(w in n.lower() for w in ("junk", "spam", "gelösch", "gelosch",
                                        "geloesch", "deleted"))]
    melden("Lese Outlook für die Kontaktliste ...")
    if mit_signaturen:
        melden("Signaturauswertung an: das Ende der Mailtexte wird gelesen,")
        melden("gespeichert wird davon nur der gefundene Firmenname.")

    nachrichten, berichte = auslesen(config, fortschritt=melden,
                                     kontakte_sammeln=True,
                                     mit_signaturen=mit_signaturen)
    entdoppelt, _ = deduplizieren(nachrichten)
    threads.zuordnen(entdoppelt, luecke_tage=config.schwellen.thread_luecke_tage)
    vorgaenge = threads.vorgaenge_bilden(entdoppelt)

    liste = kontakte_modul.sammeln(vorgaenge, berichte.get("kontaktbelege"))
    kategorien = mapping.zuordnung_lesen(ordner / pipeline.DATEI_DOMAINS,
                                         "Domain", "Kategorie")
    zeilen = kontakte_modul.als_zeilen(liste, kategorien)
    ziel = kontakte_modul.schreiben(zeilen, ordner / "Externe_Kontakte.xlsx")
    ergebnis = {"datei": ziel,
                "zusammenfassung": kontakte_modul.zusammenfassung(zeilen),
                "zeilen": len(zeilen)}
    if fuer_import:
        melden("Bereite die Kontakte für den Import auf ...")
        ergebnis["import"] = kontaktexport.schreiben(zeilen, ordner, sprache)
    melden("Fertig.")
    return ergebnis


def team_zusammenfuehren(melden, eingang: Path) -> dict:
    """Teamexporte zusammenfuehren -- ohne Zugang zu Rohdaten."""
    melden(f"Lese Dateien aus {eingang} ...")
    exporte = team_export.einlesen(eingang)
    melden(f"{len(exporte)} Datei(en) gefunden.")
    ergebnis = team_export.zusammenfuehren(exporte)
    ziel = eingang / "Team_Report.json"
    import json

    ziel.write_text(json.dumps(ergebnis, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    melden("Fertig.")
    return {"datei": ziel, "ergebnis": ergebnis}


def einstellungen_exportieren(melden, ordner: Path, ziel: Path) -> dict:
    datei, info = einstellungen_modul.exportieren(ordner, ziel)
    melden(f"Geschrieben: {datei}")
    return {"datei": datei, "info": info}


def einstellungen_importieren(melden, datei: Path, ordner: Path,
                              ueberschreiben: bool) -> dict:
    bericht = einstellungen_modul.importieren(datei, ordner,
                                              ueberschreiben=ueberschreiben)
    melden("Übernommen.")
    return bericht
