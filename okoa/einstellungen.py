"""Einstellungen weitergeben.

Die Pflegearbeit steckt nicht in der Konfiguration, sondern in der
Fachbereichszuordnung: Wer einmal 200 Kollegen ihren Abteilungen zugeordnet
hat, soll das nicht noch einmal tun -- und der naechste Nutzer erst recht nicht.

Was mitgeht, ist Organisationswissen: welche Domain intern ist, wer zu welchem
Fachbereich gehoert, welche externe Domain ein Lieferant ist.

Was **nicht** mitgeht, sind die Volumenzahlen aus der Mapping-Datei.  Sie sehen
harmlos aus ("Vorgaenge: 84"), sind aber eine Aussage darueber, mit wem der
Ersteller wie viel zu tun hatte -- also seine Postfachdaten und nicht die des
Unternehmens.  Sie werden beim Export entfernt.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from . import mapping
from .config import Config


DATEIFORMAT = 2
STANDARDNAME = "Einstellungen.json"

# Spalten der Mapping-Dateien, die das Postfach des Erstellers verraten.
VOLUMENSPALTEN = {"Vorgaenge", "Vorgänge", "Nachrichten", "Anteil kumuliert"}

# Die Felder, um die es beim Weitergeben ueberhaupt geht.  Eine Zeile ohne
# eines davon ist keine Pflegearbeit, sondern nur eine Adresse.
PFLEGEFELDER = {"Fachbereich", "Rolle", "Kategorie"}


class ImportFehler(ValueError):
    """Die Datei ist keine gueltige Einstellungsdatei."""


class ExportFehler(ValueError):
    """Es gaebe nichts zu exportieren."""


def _ohne_volumen(zeilen: list[dict]) -> list[dict]:
    """Entfernt Volumenzahlen und leere Zeilen."""
    bereinigt = []
    for zeile in zeilen:
        rest = {k: v for k, v in zeile.items()
                if k not in VOLUMENSPALTEN and str(v).strip()}
        # Eine Zeile ohne gepflegte Zuordnung ist nichts wert -- sie wuerde beim
        # Empfaenger nur eine Liste fremder Adressen erzeugen.
        if PFLEGEFELDER & set(rest):
            bereinigt.append(rest)
    return bereinigt


def exportieren(ordner: Path | str, ziel: Path | str | None = None) -> tuple[Path, dict]:
    """Schreibt Konfiguration und gepflegte Zuordnungen in eine Datei."""
    ordner = Path(ordner)
    ziel = Path(ziel) if ziel else ordner / STANDARDNAME

    config = Config.laden(ordner / "config.json")
    personen = _ohne_volumen(mapping.lesen(ordner / "mapping_personen.xlsx"))
    domains = _ohne_volumen(mapping.lesen(ordner / "mapping_domains.xlsx"))

    if not config.interne_domains and not personen and not domains:
        raise ExportFehler(
            "Im Ordner steht nichts, was sich weitergeben liesse: keine interne "
            "Domain, keine gepflegten Fachbereiche, keine Domainkategorien.\n"
            "  Bitte zuerst eine Analyse ausfuehren und die Zuordnungsdateien "
            "ausfuellen."
        )

    daten = {
        "format": DATEIFORMAT,
        "konfiguration": asdict(config),
        "fachbereiche": personen,
        "domainkategorien": domains,
    }
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(daten, indent=2, ensure_ascii=False), encoding="utf-8")
    return ziel, {
        "fachbereiche": len(personen),
        "domainkategorien": len(domains),
        "interne_domains": len(config.interne_domains),
    }


def lesen(datei: Path | str) -> dict:
    datei = Path(datei)
    if not datei.exists():
        raise ImportFehler(f"Die Datei {datei} gibt es nicht.")
    try:
        daten = json.loads(datei.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fehler:
        raise ImportFehler(f"Die Datei {datei.name} ist beschädigt.") from fehler
    if not isinstance(daten, dict) or "konfiguration" not in daten:
        raise ImportFehler(f"{datei.name} ist keine Einstellungsdatei dieses Programms.")
    if daten.get("format", 1) > DATEIFORMAT:
        raise ImportFehler(
            f"{datei.name} stammt aus einer neueren Programmversion "
            f"(Format {daten['format']}, unterstützt wird {DATEIFORMAT})."
        )
    return daten


def _zusammenfuehren(fremd: list[dict], eigen: list[dict], schluessel: str,
                     ueberschreiben: bool) -> tuple[list[dict], dict]:
    """Fremde Zuordnungen ergaenzen, eigene per Vorgabe behalten.

    Wer selbst schon gepflegt hat, soll seine Arbeit nicht verlieren, nur weil
    jemand eine Datei geschickt hat.
    """
    nach_schluessel = {str(z.get(schluessel, "")).strip().lower(): dict(z) for z in eigen}
    bericht = {"neu": 0, "ergaenzt": 0, "behalten": 0, "ueberschrieben": 0}

    for zeile in fremd:
        wert = str(zeile.get(schluessel, "")).strip().lower()
        if not wert:
            continue
        vorhanden = nach_schluessel.get(wert)
        if vorhanden is None:
            nach_schluessel[wert] = dict(zeile)
            bericht["neu"] += 1
            continue
        for feld, inhalt in zeile.items():
            if feld == schluessel or not str(inhalt).strip():
                continue
            eigener_wert = str(vorhanden.get(feld, "")).strip()
            if not eigener_wert:
                vorhanden[feld] = inhalt
                bericht["ergaenzt"] += 1
            elif eigener_wert != str(inhalt).strip():
                if ueberschreiben:
                    vorhanden[feld] = inhalt
                    bericht["ueberschrieben"] += 1
                else:
                    bericht["behalten"] += 1
    return list(nach_schluessel.values()), bericht


def importieren(datei: Path | str, ordner: Path | str,
                ueberschreiben: bool = False,
                konfiguration_uebernehmen: bool = True) -> dict:
    """Liest eine Einstellungsdatei und fuehrt sie mit dem Vorhandenen zusammen."""
    daten = lesen(datei)
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    bericht: dict = {}

    if konfiguration_uebernehmen:
        roh = dict(daten["konfiguration"])
        schwellen = roh.pop("schwellen", {})
        from .config import Schwellen

        config = Config(schwellen=Schwellen(**schwellen), **roh)
        fehler = config.pruefen()
        if fehler:
            raise ImportFehler("Die enthaltene Konfiguration ist unbrauchbar: "
                               + " ".join(fehler))
        config.speichern(ordner / "config.json")
        bericht["konfiguration"] = {"interne_domains": config.interne_domains,
                                    "zeitraum_monate": config.zeitraum_monate}

    personen, bericht["fachbereiche"] = _zusammenfuehren(
        daten.get("fachbereiche", []),
        mapping.lesen(ordner / "mapping_personen.xlsx"),
        "E-Mail", ueberschreiben)
    domains, bericht["domainkategorien"] = _zusammenfuehren(
        daten.get("domainkategorien", []),
        mapping.lesen(ordner / "mapping_domains.xlsx"),
        "Domain", ueberschreiben)

    if personen:
        mapping.schreiben(personen, mapping.SPALTEN_PERSONEN,
                          ordner / "mapping_personen.xlsx")
    if domains:
        mapping.schreiben(domains, mapping.SPALTEN_DOMAINS,
                          ordner / "mapping_domains.xlsx",
                          ("Kategorie", mapping.KATEGORIE_VORSCHLAEGE))
    return bericht


def enthaelt_volumendaten(datei: Path | str) -> bool:
    """Pruefung fuer den Empfaenger: steckt in der Datei mehr, als sein soll?"""
    daten = lesen(datei)
    for bereich in ("fachbereiche", "domainkategorien"):
        for zeile in daten.get(bereich, []):
            if VOLUMENSPALTEN & set(zeile):
                return True
    return False
