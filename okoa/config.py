"""Konfiguration.

Einzige Pflichtangabe ist die interne Maildomain.  Alles Weitere hat einen
Vorgabewert, der fuer den ersten Lauf traegt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


# Ordner, die per Vorgabe nicht ausgewertet werden.  Entwuerfe wurden nie
# versendet, geloeschte Elemente sind eine Zufallsauswahl und Junk ist kein
# Arbeitsverkehr.  Der Ausschluss wird im Report benannt.
ORDNER_AUSSCHLUSS_STANDARD = [
    "Entwürfe", "Entwuerfe", "Drafts",
    "Gelöschte Elemente", "Geloeschte Elemente", "Deleted Items",
    "Junk-E-Mail", "Junk Email", "Spam",
    "RSS-Feeds", "RSS Feeds",
    "Synchronisierungsprobleme", "Sync Issues",
]


@dataclass
class Schwellen:
    """Grenzwerte, ab denen eine Auffaelligkeit als solche gezaehlt wird."""

    grossverteiler_empfaenger: int = 8
    langlaeufer_nachrichten: int = 5
    langlaeufer_lang: int = 10
    thread_luecke_tage: int = 30
    # Ab diesem Anteil unaufloesbarer Adressen ist das Ergebnis nicht mehr
    # belastbar und der Report sagt das auch.
    warnschwelle_unaufgeloest: float = 0.05
    warnschwelle_unbekannter_fachbereich: float = 0.25


@dataclass
class Config:
    interne_domains: list[str] = field(default_factory=list)
    konzern_domains: list[str] = field(default_factory=list)
    zeitraum_monate: int = 12
    ordner_ausschluss: list[str] = field(default_factory=lambda: list(ORDNER_AUSSCHLUSS_STANDARD))
    fremde_postfaecher_einbeziehen: bool = False
    schwellen: Schwellen = field(default_factory=Schwellen)

    # ---------------------------------------------------------------- laden
    @classmethod
    def laden(cls, pfad: Path | str) -> "Config":
        pfad = Path(pfad)
        if not pfad.exists():
            return cls()
        roh = json.loads(pfad.read_text(encoding="utf-8"))
        schwellen = Schwellen(**roh.pop("schwellen", {}))
        return cls(schwellen=schwellen, **roh)

    def speichern(self, pfad: Path | str) -> None:
        Path(pfad).write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ------------------------------------------------------------ pruefen
    def pruefen(self) -> list[str]:
        """Gibt verstaendliche Meldungen zurueck, wenn etwas fehlt."""
        fehler = []
        if not self.interne_domains:
            fehler.append(
                "Es ist keine interne Domain angegeben.  Ohne sie laesst sich "
                "intern nicht von extern unterscheiden."
            )
        for d in self.interne_domains + self.konzern_domains:
            if "@" in d or "." not in d:
                fehler.append(f"'{d}' sieht nicht wie eine Domain aus (erwartet z. B. 'firma.de').")
        if self.zeitraum_monate < 1:
            fehler.append("Der Zeitraum muss mindestens einen Monat umfassen.")
        return fehler

    # ------------------------------------------------------- normalisiert
    @property
    def interne_domains_norm(self) -> set[str]:
        return {d.strip().lower().lstrip("@") for d in self.interne_domains if d.strip()}

    @property
    def konzern_domains_norm(self) -> set[str]:
        return {d.strip().lower().lstrip("@") for d in self.konzern_domains if d.strip()}
