"""Sicheres Schreiben von Ergebnisdateien.

Unter Windows laesst sich eine Datei nicht ueberschreiben, solange Excel oder
der Browser sie geoeffnet haelt.  Das ist kein Sonderfall, sondern der
Normalfall beim zweiten Lauf: Man schaut sich den Report an, pflegt die
Zuordnung in Excel und rechnet neu.

Ohne Behandlung endet das in einem PermissionError mitten in der Auswertung --
nach der langen Lesephase, also genau dann, wenn es am meisten weh tut.  Hier
wird daraus eine verstaendliche Meldung, und wo es geht, wird die Arbeit
gerettet: Laesst sich das Ziel nicht schreiben, entsteht eine Datei mit
Zeitstempel daneben, statt das Ergebnis wegzuwerfen.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class DateiBelegt(OSError):
    """Die Zieldatei ist von einem anderen Programm geoeffnet."""

    def __init__(self, pfad: Path, ersatz: Path | None = None):
        self.pfad = Path(pfad)
        self.ersatz = ersatz
        text = (f"Die Datei '{self.pfad.name}' ist geöffnet und lässt sich "
                f"nicht überschreiben.\n\nBitte in Excel bzw. im Browser "
                f"schließen und erneut versuchen.")
        if ersatz:
            text += f"\n\nDas Ergebnis wurde daneben abgelegt:\n{ersatz.name}"
        super().__init__(text)


def _ausweichname(pfad: Path) -> Path:
    """Ein Name, der garantiert frei ist -- mit Zeitstempel im Namen."""
    stempel = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return pfad.with_name(f"{pfad.stem}_{stempel}{pfad.suffix}")


def schreibbar(pfad: Path | str) -> bool:
    """Prueft, ob die Datei ueberschrieben werden koennte.

    Absichtlich vor der Arbeit aufrufbar: Lieber vorher fragen, ob Excel die
    Zuordnungsdatei offen haelt, als nach zwanzig Minuten Lesephase daran zu
    scheitern.
    """
    pfad = Path(pfad)
    if not pfad.exists():
        return True
    try:
        with pfad.open("ab"):
            return True
    except OSError:
        return False


def mit_ausweichen(pfad: Path | str, schreiben, ausweichen: bool = True) -> Path:
    """Fuehrt `schreiben(ziel)` aus und weicht bei belegter Datei aus.

    `schreiben` bekommt den Zielpfad und schreibt dorthin.  Rueckgabe ist der
    Pfad, unter dem die Datei tatsaechlich gelandet ist.
    """
    pfad = Path(pfad)
    try:
        schreiben(pfad)
        return pfad
    except PermissionError:
        pass
    except OSError as fehler:
        # Errno 13 und 32 (Windows: Zugriff verweigert / Datei in Benutzung)
        if fehler.errno not in (13, 32):
            raise
    if not ausweichen:
        raise DateiBelegt(pfad)
    ersatz = _ausweichname(pfad)
    try:
        schreiben(ersatz)
    except OSError:
        raise DateiBelegt(pfad) from None
    return ersatz


def belegte_dateien(ordner: Path | str, namen: list[str]) -> list[Path]:
    """Alle genannten Dateien, die gerade nicht beschreibbar sind."""
    ordner = Path(ordner)
    belegt = []
    for name in namen:
        for endung in ("", ".xlsx", ".csv"):
            pfad = ordner / (name + endung)
            if pfad.exists() and not schreibbar(pfad):
                belegt.append(pfad)
    return belegt
