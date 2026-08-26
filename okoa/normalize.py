"""Adressaufloesung, Identitaet, Deduplikation, Klassifikation.

Diese Stufe entscheidet ueber die Belastbarkeit aller spaeteren Zahlen.  Der
haeufigste Fehler dieser Analyseart passiert hier: Exchange liefert bei
internen Mails eine X500-Adresse statt einer SMTP-Adresse.  Wer darauf
'@firma.de' prueft, klassifiziert jede interne Mail falsch.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from .config import Config
from .model import (
    AUTOMATISIERT, EXTERN, INTERN, KONZERN, NORMAL, TERMIN, UNAUFGELOEST,
    Nachricht,
)


# Eine X500/EX-DN-Adresse, wie Exchange sie intern verwendet.  Sie ist keine
# E-Mail-Adresse und darf niemals gegen eine Domain geprueft werden.
X500_MUSTER = re.compile(r"^/o=.*?/cn=", re.IGNORECASE)

# Absender, hinter denen kein Mensch steht.
AUTOMAT_PRAEFIXE = (
    "no-reply", "noreply", "donotreply", "do-not-reply", "do_not_reply",
    "mailer-daemon", "postmaster", "bounce", "notification", "notifications",
    "automat", "system", "jira", "confluence", "workflow", "sap-workflow",
    "alert", "alerts", "monitoring", "newsletter", "mailing",
)

# Funktionspostfaecher sind bewusst keine Personen -- sonst erscheinen sie als
# hyperaktive "Kollegen" in jeder Netzwerkgrafik.
FUNKTIONS_PRAEFIXE = (
    "einkauf", "bestellung", "bestellungen", "rechnung", "rechnungen",
    "buchhaltung", "info", "kontakt", "service", "support", "vertrieb",
    "empfang", "zentrale", "poststelle", "purchasing", "orders", "accounting",
)

# Praefixe, die eine Antwort oder Weiterleitung kennzeichnen.
ANTWORT_PRAEFIXE = re.compile(
    r"^\s*(?:(?:re|aw|antw|antwort|fw|fwd|wg|weitergeleitet|tr|rif)\s*(?:\[\d+\])?\s*:\s*)+",
    re.IGNORECASE,
)
# Klammerzusaetze, die Mailsysteme voranstellen.
SYSTEM_ZUSATZ = re.compile(r"^\s*(?:\[(?:extern|external|extern:|spam|sicher)\w*\]\s*)+", re.IGNORECASE)


def ist_x500(adresse: str) -> bool:
    return bool(X500_MUSTER.match(adresse.strip()))


def adresse_normalisieren(adresse: str | None) -> str:
    """Kleinbuchstaben, ohne Whitespace, ohne spitze Klammern."""
    if not adresse:
        return ""
    a = adresse.strip().strip("<>").strip()
    return a.lower()


def domain_von(adresse: str) -> str:
    adresse = adresse_normalisieren(adresse)
    if "@" not in adresse:
        return ""
    return adresse.rsplit("@", 1)[1]


def adresse_klassifizieren(adresse: str, config: Config) -> str:
    """intern / konzern / extern / unaufgeloest.

    Eine nicht aufgeloeste X500-Adresse wird als solche markiert und aus den
    Kern-KPIs ausgeschlossen -- sie wird nicht geraten.
    """
    adresse = adresse_normalisieren(adresse)
    if not adresse or ist_x500(adresse) or "@" not in adresse:
        return UNAUFGELOEST
    domain = adresse.rsplit("@", 1)[1]
    if domain in config.interne_domains_norm:
        return INTERN
    if domain in config.konzern_domains_norm:
        return KONZERN
    return EXTERN


def ist_automat(adresse: str) -> bool:
    adresse = adresse_normalisieren(adresse)
    lokal = adresse.split("@", 1)[0] if "@" in adresse else adresse
    return any(lokal.startswith(p) for p in AUTOMAT_PRAEFIXE)


def ist_funktionspostfach(adresse: str) -> bool:
    adresse = adresse_normalisieren(adresse)
    lokal = adresse.split("@", 1)[0] if "@" in adresse else adresse
    return lokal in FUNKTIONS_PRAEFIXE


def betreff_normalisieren(betreff: str | None) -> str:
    """Entfernt Antwort-, Weiterleitungs- und Systempraefixe.

    Das Ergebnis wird ausschliesslich gehasht und niemals gespeichert -- damit
    bleibt die Zusage 'keine Betreffzeilen in der Auswertung' eingehalten.
    """
    if not betreff:
        return ""
    text = unicodedata.normalize("NFKC", betreff)
    vorher = None
    while vorher != text:
        vorher = text
        text = SYSTEM_ZUSATZ.sub("", text)
        text = ANTWORT_PRAEFIXE.sub("", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def betreff_hashen(betreff: str | None) -> str:
    norm = betreff_normalisieren(betreff)
    if not norm:
        return ""
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def ist_antwort_betreff(betreff: str | None) -> bool:
    if not betreff:
        return False
    ohne_system = SYSTEM_ZUSATZ.sub("", unicodedata.normalize("NFKC", betreff))
    return bool(ANTWORT_PRAEFIXE.match(ohne_system))


WEITERLEITUNG_PRAEFIXE = re.compile(
    r"^\s*(?:(?:fw|fwd|wg|weitergeleitet|tr)\s*(?:\[\d+\])?\s*:\s*)", re.IGNORECASE)


def ist_weiterleitung_betreff(betreff: str | None) -> bool:
    """Durchreichen statt Entscheiden -- ein brauchbarer Nebenindikator."""
    if not betreff:
        return False
    ohne_system = SYSTEM_ZUSATZ.sub("", unicodedata.normalize("NFKC", betreff))
    return bool(WEITERLEITUNG_PRAEFIXE.match(ohne_system))


def nachricht_klassifizieren(absender: str, message_class: str, kopfzeilen: str = "") -> str:
    """normal / automatisiert / termin.

    Terminobjekte sind keine Mails -- eine Serie erzeugt sonst dutzende
    'Nachrichten'.  Sie werden getrennt gefuehrt (siehe Roadmap Stufe 4).
    """
    mc = (message_class or "").lower()
    if mc.startswith("ipm.schedule"):
        return TERMIN
    if ist_automat(absender):
        return AUTOMATISIERT
    kopf = (kopfzeilen or "").lower()
    if "list-unsubscribe" in kopf or "precedence: bulk" in kopf or "auto-submitted: auto" in kopf:
        return AUTOMATISIERT
    return NORMAL


# --------------------------------------------------------------- Duplikate

def duplikat_schluessel(
    internet_message_id: str | None,
    absender: str,
    zeitstempel,
    empfaenger: list[str],
    groesse: int,
) -> str:
    """Primaer die Internet-Message-ID, sonst ein stabiler Ersatzschluessel.

    EntryID ist bewusst KEIN Kandidat -- sie ist pro Store verschieden und
    wuerde dieselbe Mail aus Archiv und Postfach als zwei zaehlen.
    """
    if internet_message_id and internet_message_id.strip():
        return "mid:" + internet_message_id.strip().lower()
    roh = "|".join([
        adresse_normalisieren(absender),
        zeitstempel.replace(second=0, microsecond=0).isoformat(),
        ",".join(sorted(adresse_normalisieren(e) for e in empfaenger)),
        str(groesse),
    ])
    return "sub:" + hashlib.sha256(roh.encode("utf-8")).hexdigest()[:24]


def deduplizieren(nachrichten: list[Nachricht]) -> tuple[list[Nachricht], int]:
    """Behaelt je Schluessel die erste Nachricht.  Gibt (Liste, Anzahl entfernt) zurueck."""
    gesehen: set[str] = set()
    behalten: list[Nachricht] = []
    for n in nachrichten:
        if n.msg_hash in gesehen:
            continue
        gesehen.add(n.msg_hash)
        behalten.append(n)
    return behalten, len(nachrichten) - len(behalten)


# ------------------------------------------------------------- Identitaet

@dataclass
class Identitaeten:
    """Adresse -> kanonische Person.

    Automatisches Zusammenfuehren nach Namensaehnlichkeit unterbleibt: bei
    haeufigen Nachnamen entstehen falsche Verschmelzungen, die im Netzwerkbild
    dramatisch aussehen und schlicht falsch sind.
    """

    zuordnung: dict[str, str]

    @classmethod
    def aus_alias_datei(cls, zeilen: list[tuple[str, str]] | None = None) -> "Identitaeten":
        zuordnung = {}
        for alias, kanonisch in (zeilen or []):
            zuordnung[adresse_normalisieren(alias)] = adresse_normalisieren(kanonisch)
        return cls(zuordnung)

    def aufloesen(self, adresse: str) -> str:
        a = adresse_normalisieren(adresse)
        return self.zuordnung.get(a, a)


def qualitaetskennzahlen(nachrichten: list[Nachricht], entfernte_duplikate: int) -> dict:
    """Werte fuer den Methodikanhang.  Ueber der Warnschwelle ist das Ergebnis
    nicht mehr belastbar -- und dann muss das auch dastehen."""
    gesamt = len(nachrichten) or 1
    unaufgeloest = sum(
        1 for n in nachrichten
        if n.absender_klasse == UNAUFGELOEST or UNAUFGELOEST in n.empfaenger_klassen
    )
    return {
        "nachrichten_gesamt": len(nachrichten),
        "duplikate_entfernt": entfernte_duplikate,
        "anteil_unaufgeloest": unaufgeloest / gesamt,
        "anteil_automatisiert": sum(1 for n in nachrichten if n.klasse == AUTOMATISIERT) / gesamt,
        "anteil_termine": sum(1 for n in nachrichten if n.klasse == TERMIN) / gesamt,
        "nachrichten_an_verteilerlisten": sum(1 for n in nachrichten if n.n_verteilerlisten > 0),
    }
