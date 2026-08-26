"""Firmennamen aus Signaturen -- deterministisch, ohne Sprachmodell.

Dieser Schritt ist der einzige im Projekt, der Mailtexte liest.  Er ist
deshalb ausdrueckliches Opt-in und laeuft nie nebenbei mit.

Deterministisch heisst hier zweierlei:

1. Es wird nur nach Rechtsformen gesucht, nicht "verstanden".  Eine Zeile
   zaehlt als Firmenname, wenn sie eine bekannte Rechtsform enthaelt.
2. Ein Kandidat wird erst uebernommen, wenn er bei derselben Domain
   **mehrfach** auftaucht.  Damit faellt der Einzelfall heraus, in dem jemand
   im Fliesstext eine fremde Firma erwaehnt hat.  Diese Konsensregel ist der
   Grund, warum das Ergebnis reproduzierbar ist und nicht geraten wirkt.

Der Text selbst wird nie gespeichert -- nur der gefundene Name.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter


# Rechtsformen, die als Beleg fuer einen Firmennamen gelten.  Bewusst eng
# gehalten: lieber ein Feld leer lassen als einen falschen Namen ausweisen.
RECHTSFORMEN = [
    r"GmbH\s*&\s*Co\.?\s*KGaA", r"GmbH\s*&\s*Co\.?\s*KG", r"AG\s*&\s*Co\.?\s*KG",
    r"gGmbH", r"GmbH", r"mbH", r"UG\s*\(haftungsbeschränkt\)", r"AG", r"KGaA",
    r"KG", r"OHG", r"GbR", r"e\.\s?K\.", r"e\.\s?V\.", r"SE",
    r"S\.A\.S\.", r"S\.A\.", r"S\.p\.A\.", r"S\.r\.l\.", r"B\.V\.", r"N\.V\.",
    r"Ltd\.?", r"LLC", r"Inc\.?", r"Corp\.?", r"PLC", r"Oy", r"AB", r"A/S", r"ApS",
]
RECHTSFORM_MUSTER = re.compile(
    r"(?<![\w])(?:" + "|".join(RECHTSFORMEN) + r")(?![\w])", re.IGNORECASE
)

# Zeilen, die typischerweise in Signaturen stehen, aber kein Firmenname sind.
STOERZEILEN = re.compile(
    r"(?:^|\s)(?:tel|telefon|phone|fax|mobil|mobile|e-?mail|mail|www\.|http|"
    r"ust-?id|umsatzsteuer|vat|steuernr|handelsregister|hrb|hra|amtsgericht|"
    r"geschäftsführer|geschaeftsführer|vorstand|sitz der gesellschaft|"
    r"registergericht|iban|bic|straße|strasse|str\.|postfach)",
    re.IGNORECASE,
)

# Haftungsausschluesse und Vertraulichkeitshinweise -- sie enthalten oft
# Rechtsformen, sind aber kein Absender.
RECHTSTEXT = re.compile(
    r"(?:diese e-?mail|this e-?mail|vertraulich|confidential|disclaimer|"
    r"irrtümlich erhalten|received this message in error|"
    r"nicht der beabsichtigte empfänger|intended recipient)",
    re.IGNORECASE,
)

# Wie viele Zeilen vom Ende her betrachtet werden.  Signaturen stehen unten;
# alles davor ist Inhalt und geht uns nichts an.
ZEILEN_AM_ENDE = 18
MAX_LAENGE = 70
# Ab so vielen uebereinstimmenden Funden gilt ein Name als belegt.
MINDEST_BELEGE = 2


def _bereinigen(zeile: str) -> str:
    zeile = unicodedata.normalize("NFKC", zeile)
    zeile = re.sub(r"^[\s>*|_=-]+", "", zeile)
    zeile = re.sub(r"[\s*|_=-]+$", "", zeile)
    return re.sub(r"\s+", " ", zeile).strip()


def firma_kandidat(text: str | None) -> str | None:
    """Sucht in den letzten Zeilen eines Mailtexts einen Firmennamen.

    Gibt None zurueck, wenn nichts eindeutig ist -- das ist der haeufige und
    voellig akzeptable Fall.
    """
    if not text:
        return None
    zeilen = [_bereinigen(z) for z in text.splitlines()]
    zeilen = [z for z in zeilen if z]
    if not zeilen:
        return None

    for zeile in reversed(zeilen[-ZEILEN_AM_ENDE:]):
        if len(zeile) > MAX_LAENGE or len(zeile) < 3:
            continue
        if RECHTSTEXT.search(zeile) or STOERZEILEN.search(zeile):
            continue
        if not RECHTSFORM_MUSTER.search(zeile):
            continue
        # Eine Zeile, die ueberwiegend aus Satzzeichen oder Ziffern besteht,
        # ist keine Firmierung.
        buchstaben = sum(1 for z in zeile if z.isalpha())
        if buchstaben < len(zeile) * 0.5:
            continue
        return zeile
    return None


def konsens(kandidaten: list[str]) -> tuple[str | None, int]:
    """Der haeufigste Kandidat, sofern er oft genug belegt ist.

    Rueckgabe: (Name oder None, Anzahl Belege).  Bei Gleichstand zwischen zwei
    Namen wird nichts uebernommen -- ein Muenzwurf waere nicht deterministisch.
    """
    gefiltert = [k for k in kandidaten if k]
    if not gefiltert:
        return None, 0
    zaehler = Counter(gefiltert)
    haeufigste = zaehler.most_common(2)
    name, anzahl = haeufigste[0]
    if anzahl < MINDEST_BELEGE:
        return None, anzahl
    if len(haeufigste) > 1 and haeufigste[1][1] == anzahl:
        return None, anzahl
    return name, anzahl


def aus_domain(domain: str) -> str:
    """Notbehelf, wenn keine Signatur vorliegt: der Domainname selbst.

    Das ist ausdruecklich KEIN Firmenname, sondern eine Lesehilfe -- die
    Herkunftsspalte weist das entsprechend aus.
    """
    if not domain:
        return ""
    teil = domain.split(".")[0]
    return teil.replace("-", " ").title()
