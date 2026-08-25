"""Datenmodell der Zwischenschicht.

Eine Zeile je deduplizierter Nachricht.  Bewusst NICHT enthalten: Betreff,
Text, Anhangnamen, BCC-Einzelheiten, Roh-EntryIDs.  Der Betreff existiert nur
als fluechtiger Hash waehrend der Vorgangsbildung und wird nie gespeichert.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime
from pathlib import Path


# Klassifikation einer einzelnen Adresse
INTERN = "intern"
KONZERN = "konzern"
EXTERN = "extern"
UNAUFGELOEST = "unaufgeloest"

# Klassifikation einer Nachricht
NORMAL = "normal"
AUTOMATISIERT = "automatisiert"
TERMIN = "termin"

# Klassifikation eines Vorgangs
VORGANG_INTERN = "intern"
VORGANG_GEMISCHT = "gemischt"
VORGANG_EXTERN = "extern"

RICHTUNG_GESENDET = "gesendet"
RICHTUNG_EMPFANGEN = "empfangen"


@dataclass
class Nachricht:
    """Metadaten einer einzelnen Mail."""

    msg_hash: str
    zeitstempel: datetime
    richtung: str
    absender_id: str
    absender_klasse: str
    absender_domain: str
    empfaenger_ids: list[str] = field(default_factory=list)
    empfaenger_klassen: list[str] = field(default_factory=list)
    n_to: int = 0
    n_cc: int = 0
    n_to_intern: int = 0
    n_to_extern: int = 0
    n_cc_intern: int = 0
    n_cc_extern: int = 0
    n_verteilerlisten: int = 0
    klasse: str = NORMAL
    hat_anhang: bool = False
    ist_antwort: bool = False
    ordner: str = ""
    store: str = ""
    # Nur zur Vorgangsbildung, wird nicht in die Zwischendatei geschrieben.
    conversation_id: str = ""
    betreff_hash: str = ""
    # Werden von threads.py gesetzt.
    thread_id_conv: str = ""
    thread_id_fallback: str = ""

    # ------------------------------------------------------------ abgeleitet
    @property
    def n_empfaenger(self) -> int:
        return self.n_to + self.n_cc

    @property
    def hat_externen_empfaenger(self) -> bool:
        return self.n_to_extern + self.n_cc_extern > 0

    @property
    def alle_beteiligten(self) -> set[str]:
        return {self.absender_id} | set(self.empfaenger_ids)

    @property
    def ist_auswertbar(self) -> bool:
        """Nur normale Mails gehen in die Kern-KPIs ein."""
        return self.klasse == NORMAL


# Spalten der Zwischendatei.  conversation_id und betreff_hash fehlen hier
# absichtlich -- sie sind Zwischenergebnisse und nichts, was aufbewahrt wird.
CACHE_SPALTEN = [
    "msg_hash", "zeitstempel", "richtung", "absender_id", "absender_klasse",
    "absender_domain", "empfaenger_ids", "empfaenger_klassen",
    "n_to", "n_cc", "n_to_intern", "n_to_extern", "n_cc_intern", "n_cc_extern",
    "n_verteilerlisten", "klasse", "hat_anhang", "ist_antwort", "ordner", "store",
    "thread_id_conv", "thread_id_fallback",
]


def cache_schreiben(nachrichten: list[Nachricht], pfad: Path | str) -> None:
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("w", encoding="utf-8", newline="") as f:
        schreiber = csv.DictWriter(f, fieldnames=CACHE_SPALTEN)
        schreiber.writeheader()
        for n in nachrichten:
            zeile = {s: getattr(n, s) for s in CACHE_SPALTEN}
            zeile["zeitstempel"] = n.zeitstempel.isoformat()
            zeile["empfaenger_ids"] = "|".join(n.empfaenger_ids)
            zeile["empfaenger_klassen"] = "|".join(n.empfaenger_klassen)
            zeile["hat_anhang"] = "1" if n.hat_anhang else "0"
            zeile["ist_antwort"] = "1" if n.ist_antwort else "0"
            schreiber.writerow(zeile)


def cache_lesen(pfad: Path | str) -> list[Nachricht]:
    ganzzahlen = {f.name for f in fields(Nachricht) if f.type == "int"}
    nachrichten = []
    with Path(pfad).open(encoding="utf-8", newline="") as f:
        for zeile in csv.DictReader(f):
            werte = dict(zeile)
            werte["zeitstempel"] = datetime.fromisoformat(werte["zeitstempel"])
            werte["empfaenger_ids"] = [x for x in werte["empfaenger_ids"].split("|") if x]
            werte["empfaenger_klassen"] = [x for x in werte["empfaenger_klassen"].split("|") if x]
            werte["hat_anhang"] = werte["hat_anhang"] == "1"
            werte["ist_antwort"] = werte["ist_antwort"] == "1"
            for name in ganzzahlen:
                if name in werte:
                    werte[name] = int(werte[name])
            nachrichten.append(Nachricht(**werte))
    return nachrichten


@dataclass
class Vorgang:
    """Ein zusammenhaengender Kommunikationsstrang (Thread)."""

    thread_id: str
    nachrichten: list[Nachricht] = field(default_factory=list)
    randvorgang: bool = False   # beginnt vor dem Beobachtungsfenster

    @property
    def n_nachrichten(self) -> int:
        return len(self.nachrichten)

    @property
    def beteiligte(self) -> set[str]:
        """Vereinigungsmenge aller Teilnehmer aller Nachrichten."""
        menge: set[str] = set()
        for n in self.nachrichten:
            menge |= n.alle_beteiligten
        return menge

    @property
    def n_beteiligte(self) -> int:
        return len(self.beteiligte)

    @property
    def beginn(self) -> datetime:
        return min(n.zeitstempel for n in self.nachrichten)

    @property
    def ende(self) -> datetime:
        return max(n.zeitstempel for n in self.nachrichten)

    @property
    def dauer_stunden(self) -> float:
        return (self.ende - self.beginn).total_seconds() / 3600.0

    @property
    def klasse(self) -> str:
        """intern / gemischt / extern.

        'gemischt' ist eine eigene Klasse und geht bewusst nicht in 'intern'
        auf: ein Lieferantenvorgang mit interner Abstimmung ist wertschoepfende
        Arbeit, keine Selbstbeschaeftigung.  Sie in die interne Quote zu
        schieben, wuerde die Ausgangshypothese kuenstlich bestaetigen.
        """
        hat_extern = any(
            k == EXTERN
            for n in self.nachrichten
            for k in [n.absender_klasse, *n.empfaenger_klassen]
        )
        if not hat_extern:
            return VORGANG_INTERN
        # Mindestens eine Nachricht ohne jede externe Beteiligung?
        hat_rein_interne_nachricht = any(
            not n.hat_externen_empfaenger and n.absender_klasse != EXTERN
            for n in self.nachrichten
        )
        return VORGANG_GEMISCHT if hat_rein_interne_nachricht else VORGANG_EXTERN

    @property
    def interner_nachrichtenanteil(self) -> float:
        """Anteil rein interner Nachrichten -- fuer gemischte Vorgaenge die
        praeziseste Annaeherung an 'was kostet ein Lieferantenthema intern'."""
        if not self.nachrichten:
            return 0.0
        intern = sum(
            1 for n in self.nachrichten
            if not n.hat_externen_empfaenger and n.absender_klasse != EXTERN
        )
        return intern / len(self.nachrichten)
