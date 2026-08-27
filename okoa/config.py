"""Konfiguration.

Einzige Pflichtangabe ist die interne Maildomain.  Alles Weitere hat einen
Vorgabewert, der fuer den ersten Lauf traegt.
"""

from __future__ import annotations

import json
import re
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
    # Arbeitszeitfenster fuer die After-hours-Auswertung.
    arbeitsbeginn_stunde: int = 7
    arbeitsende_stunde: int = 19
    # Antworten oberhalb dieser Spanne sind keine Reaktion mehr, sondern ein
    # neuer Anlauf -- sie wuerden den Median sonst unbrauchbar machen.
    max_antwortzeit_stunden: int = 24 * 14


def _domains_aufraeumen(werte: list[str]) -> list[str]:
    """'Max@Firma.DE ', '@firma.de', 'https://firma.de/' -> 'firma.de'."""
    fertig = []
    einzeln = []
    for wert in werte:
        # Auch innerhalb eines Feldes trennen: 'firma.de, tochter.de' waere
        # sonst eine einzige, nie zutreffende Domain -- und alles gaelte als
        # extern, ohne dass irgendwo ein Fehler erschiene.
        einzeln.extend(teil for teil in re.split(r"[,;\s]+", str(wert)) if teil)
    for wert in einzeln:
        text = str(wert).strip().lower()
        for praefix in ("https://", "http://", "www."):
            if text.startswith(praefix):
                text = text[len(praefix):]
        text = text.split("/")[0].strip()
        if "@" in text:
            text = text.rsplit("@", 1)[1]
        text = text.strip(" .@<>")
        if text and text not in fertig:
            fertig.append(text)
    return fertig


@dataclass
class Config:
    interne_domains: list[str] = field(default_factory=list)
    konzern_domains: list[str] = field(default_factory=list)
    zeitraum_monate: int = 12
    ordner_ausschluss: list[str] = field(default_factory=lambda: list(ORDNER_AUSSCHLUSS_STANDARD))
    fremde_postfaecher_einbeziehen: bool = False
    # Vollerhebung fuer die eigene Auswertung: erfasst zusaetzlich Betreff,
    # Anhangnamen, Groesse und BCC und schaltet alle explorativen Auswertungen
    # frei.  Fuer das eigene Postfach gedacht; fuer den Teammodus bleibt der
    # Export unveraendert aggregiert (siehe team_export.EXPORT_FELDER).
    vollerhebung: bool = False
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
    def aufraeumen(self) -> None:
        """Bringt Eingaben in Form, statt sie abzulehnen.

        Wer nach einer Domain gefragt wird, tippt erfahrungsgemaess auch mal
        die eigene Adresse, ein fuehrendes @ oder eine ganze URL.  Das ist
        keine Fehleingabe, die eine Meldung verdient -- das ist eine
        Schreibweise, die man verstehen kann.
        """
        self.interne_domains = _domains_aufraeumen(self.interne_domains)
        self.konzern_domains = _domains_aufraeumen(self.konzern_domains)
        if self.zeitraum_monate < 1:
            self.zeitraum_monate = 12

    def pruefen(self) -> list[str]:
        """Gibt verstaendliche Meldungen zurueck, wenn etwas fehlt."""
        self.aufraeumen()
        fehler = []
        if not self.interne_domains:
            fehler.append(
                "Es ist keine interne Domain angegeben.  Ohne sie laesst sich "
                "intern nicht von extern unterscheiden."
            )
        for d in self.interne_domains + self.konzern_domains:
            if "." not in d:
                fehler.append(
                    f"'{d}' sieht nicht wie eine Domain aus (erwartet z. B. 'firma.de').")
        return fehler

    # ------------------------------------------------------- normalisiert
    @property
    def interne_domains_norm(self) -> set[str]:
        return {d.strip().lower().lstrip("@") for d in self.interne_domains if d.strip()}

    @property
    def konzern_domains_norm(self) -> set[str]:
        return {d.strip().lower().lstrip("@") for d in self.konzern_domains if d.strip()}
