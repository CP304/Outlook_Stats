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


# --------------------------------------------------------------- Funktion

# Rollenwoerter, die eine Funktionszeile belegen.  Wie bei den Rechtsformen
# gilt: lieber ein leeres Feld als eine geratene Funktion.
ROLLENWOERTER = [
    r"leiter(?:in)?", r"leitung", r"geschäftsführ\w*", r"geschaeftsführ\w*",
    r"prokurist(?:in)?", r"vorstand", r"inhaber(?:in)?", r"gesellschafter(?:in)?",
    r"einkauf\w*", r"vertrieb\w*", r"verkauf\w*", r"disponent(?:in)?",
    r"sachbearbeiter(?:in)?", r"referent(?:in)?", r"assistenz", r"assistent(?:in)?",
    r"projektleiter(?:in)?", r"projektmanager(?:in)?", r"ingenieur(?:in)?",
    r"techniker(?:in)?", r"meister(?:in)?", r"konstrukteur(?:in)?",
    r"qualitätsmanag\w*", r"berater(?:in)?", r"consultant", r"controller(?:in)?",
    r"buchhalt\w*", r"personal\w*", r"produktmanager(?:in)?",
    r"key\s?account\s?manager(?:in)?", r"account\s?manager(?:in)?",
    r"sales\s?manager(?:in)?", r"head\s+of\s+[\w\s]+", r"director",
    r"manager(?:in)?", r"managing\s+director", r"CEO", r"CTO", r"CFO", r"COO",
    r"teamleiter(?:in)?", r"bereichsleiter(?:in)?", r"abteilungsleiter(?:in)?",
    r"niederlassungsleiter(?:in)?", r"werkleiter(?:in)?", r"betriebsleiter(?:in)?",
]
ROLLEN_MUSTER = re.compile(r"(?<![\w])(?:" + "|".join(ROLLENWOERTER) + r")(?![\w])",
                           re.IGNORECASE)
MAX_LAENGE_FUNKTION = 60


def funktion_kandidat(text: str | None) -> str | None:
    """Sucht die Funktionszeile einer Signatur.

    Eine Zeile zaehlt, wenn sie ein Rollenwort enthaelt und weder Rechtsform
    noch Kontaktdaten -- 'Leiter Einkauf' ja, 'Muster GmbH' und
    'Tel. 0123 / Leitung' nein.
    """
    if not text:
        return None
    zeilen = [z for z in (_bereinigen(z) for z in text.splitlines()) if z]
    if not zeilen:
        return None

    for zeile in reversed(zeilen[-ZEILEN_AM_ENDE:]):
        if not (3 <= len(zeile) <= MAX_LAENGE_FUNKTION):
            continue
        if RECHTSTEXT.search(zeile) or STOERZEILEN.search(zeile):
            continue
        # Eine Firmenzeile ist keine Funktionszeile.
        if RECHTSFORM_MUSTER.search(zeile):
            continue
        if TELEFON_MUSTER.search(zeile):
            continue
        if not ROLLEN_MUSTER.search(zeile):
            continue
        buchstaben = sum(1 for z in zeile if z.isalpha())
        if buchstaben < len(zeile) * 0.6:
            continue
        return zeile
    return None


# --------------------------------------------------------------- Telefon

TELEFON_MUSTER = re.compile(r"(?:\+|00)\d[\d\s/().\-]{6,}\d|\b0\d[\d\s/().\-]{5,}\d")

# Nur beschriftete Nummern werden uebernommen.  Eine unbeschriftete Ziffernfolge
# koennte eine Kundennummer, eine PLZ-Kombination oder eine Registernummer sein.
# Die Etiketten werden im Textstueck unmittelbar VOR der Nummer gesucht --
# deshalb am Ende verankert und nicht mit einem Lookahead.
LABEL_FESTNETZ = re.compile(
    r"(?:^|[\s|•·(])(?:tel(?:efon)?|phone|fon|festnetz|durchwahl|dw|office|t)"
    r"\s*[.:]?\s*$", re.IGNORECASE)
LABEL_MOBIL = re.compile(
    r"(?:^|[\s|•·(])(?:mobil(?:e)?|handy|cell(?:ular)?|m)\s*[.:]?\s*$",
    re.IGNORECASE)
# Fax wird ausdruecklich nie uebernommen -- eine Faxnummer im Telefonfeld ist
# schlimmer als ein leeres Feld.
LABEL_FAX = re.compile(r"(?:^|[\s|•·(])(?:fax|telefax|f)\s*[.:]?\s*$", re.IGNORECASE)


def _nummer_normalisieren(roh: str) -> str:
    """Vereinheitlicht die Schreibweise, ohne die Nummer zu veraendern."""
    # Der Bindestrich bleibt: er trennt in deutschen Nummern die Durchwahl und
    # ist damit eine Information, keine Formatierung.
    text = re.sub(r"[^\d+\-]", " ", roh)
    text = re.sub(r"\s+", " ", text).strip(" -")
    if not text:
        return ""
    ziffern = text.replace("+", "").strip(" -")
    return ("+" + ziffern) if roh.strip().startswith("+") else ziffern


def _nummern_aus_zeile(zeile: str) -> list[tuple[str, str]]:
    """Ergibt Paare (art, nummer) fuer eine Zeile -- 'fest', 'mobil' oder 'fax'."""
    treffer = []
    for fund in TELEFON_MUSTER.finditer(zeile):
        vorspann = zeile[:fund.start()]
        # Nur das direkt vorangehende Etikett zaehlt, nicht eines vom Zeilenanfang.
        rest = vorspann[-14:]
        if LABEL_FAX.search(rest):
            art = "fax"
        elif LABEL_MOBIL.search(rest):
            art = "mobil"
        elif LABEL_FESTNETZ.search(rest):
            art = "fest"
        else:
            continue
        nummer = _nummer_normalisieren(fund.group())
        if len(nummer.replace("+", "")) >= 7:
            treffer.append((art, nummer))
    return treffer


def telefon_kandidaten(text: str | None) -> tuple[str | None, str | None]:
    """Ergibt (Festnetz, Mobil) aus einer Signatur.  Fax wird verworfen."""
    if not text:
        return None, None
    fest = mobil = None
    zeilen = [z for z in (_bereinigen(z) for z in text.splitlines()) if z]
    for zeile in reversed(zeilen[-ZEILEN_AM_ENDE:]):
        if RECHTSTEXT.search(zeile):
            continue
        for art, nummer in _nummern_aus_zeile(zeile):
            if art == "fest" and fest is None:
                fest = nummer
            elif art == "mobil" and mobil is None:
                mobil = nummer
    return fest, mobil


def aus_domain(domain: str) -> str:
    """Notbehelf, wenn keine Signatur vorliegt: der Domainname selbst.

    Das ist ausdruecklich KEIN Firmenname, sondern eine Lesehilfe -- die
    Herkunftsspalte weist das entsprechend aus.
    """
    if not domain:
        return ""
    teil = domain.split(".")[0]
    return teil.replace("-", " ").title()
