"""Kontakte in ein importierbares Format bringen.

Die Kontaktliste aus okoa.kontakte ist eine Auswertung -- eine Tabelle zum
Ansehen.  Fuer die Massenpflege braucht es etwas anderes: getrennte Namensfelder
und ein Format, das ein Adressbuch versteht.

Zwei Ausgaben:

    .vcf   vCard 3.0, alle Kontakte in einer Datei.  Sprachunabhaengig und
           damit der zuverlaessigere Weg -- Outlook, Windows-Kontakte und die
           meisten CRM-Systeme lesen es unveraendert.
    .csv   Outlook-Importformat mit den Spaltennamen, die der Importassistent
           erwartet.  Die haengen an der Sprache der Outlook-Installation,
           deshalb umschaltbar.

Der Anzeigename wird regelbasiert in Vor- und Nachname zerlegt.  Wo das nicht
eindeutig geht, bleibt das Feld leer -- ein falsch zerlegter Name faellt beim
Import nicht auf und steht danach jahrelang falsch im Adressbuch.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path


# Titel und Anreden, die kein Namensbestandteil sind.
TITEL = re.compile(
    r"^(?:herr|frau|mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?|dipl\.?-?\s?(?:ing|kfm|inf|wirt)\.?|"
    r"mag\.?|ing\.?|b\.?\s?sc\.?|m\.?\s?sc\.?|b\.?\s?a\.?|m\.?\s?a\.?|ph\.?\s?d\.?)$",
    re.IGNORECASE)

# Namenszusaetze, die zum Nachnamen gehoeren.
PARTIKEL = {"von", "van", "de", "del", "della", "der", "den", "du", "da", "di",
            "dos", "la", "le", "ten", "ter", "zu", "zum", "vom", "af", "av"}

# Was nach Funktionspostfach aussieht, ist keine Person.
KEIN_NAME = re.compile(r"[@<>]|^\s*$")


def namen_zerlegen(anzeigename: str | None) -> tuple[str, str, str]:
    """Ergibt (Titel, Vorname, Nachname).

    Erkannt werden 'Anna Schmidt', 'Schmidt, Anna', 'Dr. Anna von Schmidt'.
    Bei allem anderen bleibt der Vorname leer und der ganze Text steht im
    Nachnamen -- lieber unzerlegt als falsch zerlegt.
    """
    if not anzeigename or KEIN_NAME.search(anzeigename):
        return "", "", ""

    text = unicodedata.normalize("NFKC", anzeigename).strip()
    text = re.sub(r"\s+", " ", text)
    # Klammerzusaetze wie '(Einkauf)' oder '(extern)' gehoeren nicht zum Namen.
    text = re.sub(r"\s*[\(\[].*?[\)\]]\s*", " ", text).strip()

    # 'Nachname, Vorname'
    if text.count(",") == 1:
        hinten, vorne = (teil.strip() for teil in text.split(","))
        if hinten and vorne:
            titel, vorname, _ = namen_zerlegen(vorne + " X")
            return titel, vorname or vorne, hinten

    teile = text.split(" ")
    titel = []
    while teile and TITEL.match(teile[0]):
        titel.append(teile.pop(0))
    if not teile:
        return " ".join(titel), "", ""
    if len(teile) == 1:
        return " ".join(titel), "", teile[0]

    # Namenszusaetze von hinten einsammeln: 'Anna von der Heide'
    nachname = [teile.pop()]
    while teile and teile[-1].lower() in PARTIKEL:
        nachname.insert(0, teile.pop())
    if not teile:
        return " ".join(titel), "", " ".join(nachname)
    return " ".join(titel), " ".join(teile), " ".join(nachname)


def _ist_person(zeile: dict) -> bool:
    """Nur Zeilen mit erkennbarem Personennamen taugen fuer ein Adressbuch."""
    _, vorname, nachname = namen_zerlegen(zeile.get("Anzeigename"))
    return bool(nachname)


def kontakte_aufbereiten(zeilen: list[dict], nur_mit_namen: bool = True) -> list[dict]:
    """Bereitet die Auswertungszeilen fuer den Import auf."""
    fertig = []
    for zeile in zeilen:
        titel, vorname, nachname = namen_zerlegen(zeile.get("Anzeigename"))
        if nur_mit_namen and not nachname:
            continue
        unternehmen = str(zeile.get("Unternehmen", "")).strip()
        # Eine aus dem Domainnamen abgeleitete Firma ist eine Lesehilfe, kein
        # Firmenname -- sie gehoert nicht ungeprueft ins Adressbuch.
        if str(zeile.get("Herkunft Unternehmen", "")).strip() != "Signatur":
            unternehmen = ""
        fertig.append({
            "Titel": titel,
            "Vorname": vorname,
            "Nachname": nachname or str(zeile.get("Anzeigename", "")).strip(),
            "Firma": unternehmen,
            "Position": str(zeile.get("Funktion", "")).strip(),
            "E-Mail": str(zeile.get("E-Mail", "")).strip(),
            "Telefon": str(zeile.get("Telefon", "")).strip(),
            "Mobil": str(zeile.get("Mobil", "")).strip(),
            "Notiz": _notiz(zeile),
        })
    return fertig


def _notiz(zeile: dict) -> str:
    """Herkunft und Kontaktstand, damit im Adressbuch nachvollziehbar bleibt,
    woher der Eintrag stammt und wie sicher er ist."""
    teile = []
    belege = str(zeile.get("Signaturbelege", "")).strip()
    if belege and belege not in ("0", ""):
        teile.append(f"aus {belege} Signaturen gelesen")
    else:
        teile.append("kein Signaturfund")
    for feld, name in (("Letzter Kontakt", "letzter Kontakt"),
                       ("Nachrichten", "Nachrichten"),
                       ("Kategorie", "Kategorie")):
        roh = zeile.get(feld)
        # Die Zeitspalten sind echte Datumswerte -- unformatiert stuenden
        # Sekunden und Mikrosekunden im Adressbuch.
        wert = (roh.strftime("%d.%m.%Y") if isinstance(roh, datetime)
                else str(roh or "").strip())
        if wert:
            teile.append(f"{name}: {wert}")
    return "; ".join(["Outlook-Kommunikationsanalyse", *teile])


# --------------------------------------------------------------- vCard

def _vcard_maskieren(text: str) -> str:
    """Maskiert die Zeichen, die in vCard Feldtrenner sind."""
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def als_vcard(kontakte: list[dict], pfad: Path | str) -> Path:
    """Alle Kontakte als eine vCard-3.0-Datei."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    bloecke = []
    for k in kontakte:
        voller_name = " ".join(t for t in (k["Titel"], k["Vorname"], k["Nachname"]) if t)
        zeilen = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"N:{_vcard_maskieren(k['Nachname'])};{_vcard_maskieren(k['Vorname'])};;"
            f"{_vcard_maskieren(k['Titel'])};",
            f"FN:{_vcard_maskieren(voller_name)}",
        ]
        if k["Firma"]:
            zeilen.append(f"ORG:{_vcard_maskieren(k['Firma'])}")
        if k["Position"]:
            zeilen.append(f"TITLE:{_vcard_maskieren(k['Position'])}")
        if k["E-Mail"]:
            zeilen.append(f"EMAIL;TYPE=INTERNET,WORK:{k['E-Mail']}")
        if k["Telefon"]:
            zeilen.append(f"TEL;TYPE=WORK,VOICE:{k['Telefon']}")
        if k["Mobil"]:
            zeilen.append(f"TEL;TYPE=CELL:{k['Mobil']}")
        if k["Notiz"]:
            zeilen.append(f"NOTE:{_vcard_maskieren(k['Notiz'])}")
        zeilen.append("END:VCARD")
        bloecke.append("\r\n".join(zeilen))
    # vCard verlangt CRLF; Outlook ist da eigen.
    pfad.write_text("\r\n".join(bloecke) + "\r\n", encoding="utf-8")
    return pfad


# ----------------------------------------------------------- Outlook-CSV

# Die Spaltennamen, die der Outlook-Importassistent erwartet.  Sie haengen an
# der Sprache der Installation -- ein deutsches Outlook erkennt die englischen
# Kopfzeilen nicht und legt die Werte in keinem Feld ab.
SPALTEN = {
    "de": {
        "Titel": "Anrede",
        "Vorname": "Vorname",
        "Nachname": "Nachname",
        "Firma": "Firma",
        "Position": "Position",
        "E-Mail": "E-Mail-Adresse",
        "Telefon": "Telefon geschäftlich",
        "Mobil": "Mobiltelefon",
        "Notiz": "Notizen",
    },
    "en": {
        "Titel": "Title",
        "Vorname": "First Name",
        "Nachname": "Last Name",
        "Firma": "Company",
        "Position": "Job Title",
        "E-Mail": "E-mail Address",
        "Telefon": "Business Phone",
        "Mobil": "Mobile Phone",
        "Notiz": "Notes",
    },
}


def als_outlook_csv(kontakte: list[dict], pfad: Path | str,
                    sprache: str = "de") -> Path:
    """CSV im Outlook-Importformat."""
    if sprache not in SPALTEN:
        raise ValueError(f"Unbekannte Sprache '{sprache}' -- erwartet: "
                         + ", ".join(SPALTEN))
    zuordnung = SPALTEN[sprache]
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    # Der Importassistent erwartet Komma als Trenner; BOM, damit Excel die
    # Umlaute richtig anzeigt, wenn jemand vorher hineinschaut.
    with pfad.open("w", encoding="utf-8-sig", newline="") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=list(zuordnung.values()))
        schreiber.writeheader()
        for kontakt in kontakte:
            schreiber.writerow({ziel: kontakt.get(quelle, "")
                                for quelle, ziel in zuordnung.items()})
    return pfad


def schreiben(zeilen: list[dict], ordner: Path | str, sprache: str = "de",
              nur_mit_namen: bool = True) -> dict:
    """Erzeugt beide Dateien und meldet, was dabei herauskam."""
    ordner = Path(ordner)
    kontakte = kontakte_aufbereiten(zeilen, nur_mit_namen)
    ergebnis = {
        "kontakte": len(kontakte),
        "uebersprungen": len(zeilen) - len(kontakte),
        "mit_firma": sum(1 for k in kontakte if k["Firma"]),
        "mit_position": sum(1 for k in kontakte if k["Position"]),
        "mit_telefon": sum(1 for k in kontakte if k["Telefon"] or k["Mobil"]),
        "vcf": None,
        "csv": None,
    }
    if not kontakte:
        return ergebnis
    ergebnis["vcf"] = als_vcard(kontakte, ordner / "Kontakte_Import.vcf")
    ergebnis["csv"] = als_outlook_csv(kontakte, ordner / "Kontakte_Import.csv",
                                      sprache)
    return ergebnis
