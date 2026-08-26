"""Extraktion aus Outlook ueber COM.  Ausschliesslich lesend.

Diese Stufe ist die einzige, die Windows und Outlook braucht.  Sie liest nur
Metadaten -- .Body wird nie angefasst, was zugleich Datenschutz und technische
Robustheit dient (der Zugriff auf den Text kann je nach Konfiguration den
Sicherheitsdialog ausloesen).

Es wird nichts geschrieben: kein Save, kein Move, kein Delete, kein Markieren
als gelesen.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from .config import Config
from .model import (
    RICHTUNG_EMPFANGEN, RICHTUNG_GESENDET, UNAUFGELOEST, Nachricht,
)
from .kontakte import Beleg
from .normalize import (
    adresse_klassifizieren, adresse_normalisieren, betreff_hashen,
    duplikat_schluessel, ist_antwort_betreff, ist_x500, nachricht_klassifizieren,
)
from .signaturen import firma_kandidat


# MAPI-Eigenschaften, die ueber den PropertyAccessor erreichbar sind.
PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
PR_INTERNET_MESSAGE_ID = "http://schemas.microsoft.com/mapi/proptag/0x1035001E"
PR_TRANSPORT_MESSAGE_HEADERS = "http://schemas.microsoft.com/mapi/proptag/0x007D001E"

OL_MAIL_ITEM = 43          # olMailItem
OL_TO, OL_CC, OL_BCC = 1, 2, 3
OL_DISTRIBUTION_LIST = 1   # AddressEntry.DisplayType olDistList
OL_PRIVATE_DIST_LIST = 5


class OutlookNichtVerfuegbar(RuntimeError):
    """Outlook oder pywin32 fehlt -- mit verstaendlicher Meldung abbrechen."""


def verbinden():
    try:
        import win32com.client  # noqa: PLC0415
    except ImportError as fehler:
        raise OutlookNichtVerfuegbar(
            "Das Paket pywin32 fehlt.  Es wird nur unter Windows gebraucht und "
            "laesst sich mit 'pip install pywin32' nachinstallieren."
        ) from fehler
    try:
        return win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    except Exception as fehler:  # pragma: no cover -- nur auf Windows erreichbar
        raise OutlookNichtVerfuegbar(
            "Outlook liess sich nicht ansprechen.  Bitte Outlook starten und "
            "erneut versuchen."
        ) from fehler


# ------------------------------------------------------------ Adressen

def _smtp_aufloesen(objekt, adresse: str, typ: str) -> str:
    """Loest eine Exchange-Adresse in eine SMTP-Adresse auf.

    Ohne diesen Schritt liefert SenderEmailAddress bei internen Mails eine
    X500-Adresse.  Wer darauf '@firma.de' prueft, klassifiziert jede interne
    Mail falsch -- der haeufigste und folgenschwerste Fehler dieser Analyseart.
    """
    if adresse and typ and typ.upper() != "EX" and not ist_x500(adresse):
        return adresse_normalisieren(adresse)

    for versuch in (
        lambda: objekt.PropertyAccessor.GetProperty(PR_SMTP_ADDRESS),
        lambda: objekt.AddressEntry.GetExchangeUser().PrimarySmtpAddress,
        lambda: objekt.Sender.GetExchangeUser().PrimarySmtpAddress,
    ):
        try:
            wert = versuch()
        except Exception:
            continue
        if wert and "@" in str(wert):
            return adresse_normalisieren(str(wert))
    # Nicht raten: als unaufgeloest markieren und aus den Kern-KPIs nehmen.
    return adresse_normalisieren(adresse)


def _eigenschaft(objekt, name: str, vorgabe=""):
    try:
        wert = getattr(objekt, name)
    except Exception:
        return vorgabe
    return vorgabe if wert is None else wert


# ------------------------------------------------------------- Ordner

def ordner_sammeln(namespace, config: Config) -> list:
    """Rekursiv ueber alle zugaenglichen Stores.

    Fremde Postfaecher werden per Vorgabe uebersprungen -- technisch sind sie
    erreichbar, datenschutzrechtlich brauchen sie eine ausdrueckliche Freigabe
    (siehe docs/08-datenschutz.md).
    """
    ausgeschlossen = {n.strip().lower() for n in config.ordner_ausschluss}
    gefunden = []

    def absteigen(ordner, store_name: str, tiefe: int = 0) -> None:
        if tiefe > 12:      # Schutz vor zyklischen Verknuepfungen
            return
        name = str(_eigenschaft(ordner, "Name", ""))
        if name.strip().lower() in ausgeschlossen:
            return
        try:
            if _eigenschaft(ordner, "DefaultItemType", OL_MAIL_ITEM) == OL_MAIL_ITEM:
                gefunden.append((store_name, name, ordner))
        except Exception:
            pass
        try:
            unterordner = list(ordner.Folders)
        except Exception:
            return
        for unter in unterordner:
            absteigen(unter, store_name, tiefe + 1)

    for store in namespace.Stores:
        store_name = str(_eigenschaft(store, "DisplayName", "Postfach"))
        try:
            wurzel = store.GetRootFolder()
        except Exception:
            continue
        eigenes = bool(_eigenschaft(store, "ExchangeStoreType", 0) in (0, 1, 3))
        if not eigenes and not config.fremde_postfaecher_einbeziehen:
            continue
        absteigen(wurzel, store_name)
    return gefunden


# ---------------------------------------------------------- Nachrichten

def _signaturteil(item) -> str:
    """Liest NUR das Ende des Mailtexts, fuer die Firmenerkennung.

    Dies ist die einzige Stelle im Projekt, die einen Mailtext anfasst.  Sie
    laeuft ausschliesslich, wenn die Signaturauswertung ausdruecklich
    eingeschaltet wurde, gibt hoechstens die letzten Zeilen zurueck und
    speichert nichts davon -- weiterverwendet wird allein der gefundene
    Firmenname.
    """
    try:
        text = item.Body
    except Exception:
        return ""
    if not text:
        return ""
    zeilen = str(text).splitlines()
    return "\n".join(zeilen[-40:])


def _kontaktbelege(item, nachricht: Nachricht, mit_signaturen: bool) -> list[Beleg]:
    """Anzeigenamen und -- optional -- den Firmenkandidaten je externem Kontakt."""
    kandidat = firma_kandidat(_signaturteil(item)) if mit_signaturen else None
    belege = []

    if nachricht.absender_klasse == "extern":
        belege.append(Beleg(
            adresse=nachricht.absender_id,
            anzeigename=str(_eigenschaft(item, "SenderName", "")),
            # Die Signatur gehoert dem Absender -- nur ihm wird sie zugerechnet.
            firma_kandidat=kandidat,
        ))

    # Die Empfaengerliste der Nachricht entsteht in _empfaenger_lesen in genau
    # dieser Reihenfolge -- deshalb passen die Anzeigenamen positionsgenau dazu.
    try:
        empfaenger = list(item.Recipients)
    except Exception:
        empfaenger = []
    for e, adresse, klasse in zip(empfaenger, nachricht.empfaenger_ids,
                                  nachricht.empfaenger_klassen):
        if klasse == "extern" and adresse:
            belege.append(Beleg(adresse=adresse,
                                anzeigename=str(_eigenschaft(e, "Name", ""))))
    return belege


def _anhangszahl(item) -> int:
    """Nur die Anzahl -- Anhangnamen werden bewusst nicht gelesen."""
    try:
        return int(item.Attachments.Count)
    except Exception:
        return 0


def _empfaenger_lesen(item, config: Config):
    ids, klassen = [], []
    n_to = n_cc = n_to_intern = n_to_extern = n_cc_intern = n_cc_extern = 0
    n_listen = 0
    try:
        empfaenger = list(item.Recipients)
    except Exception:
        empfaenger = []

    for e in empfaenger:
        typ = _eigenschaft(e, "Type", OL_TO)
        eintrag = getattr(e, "AddressEntry", None)
        adresse = _smtp_aufloesen(e, str(_eigenschaft(e, "Address", "")),
                                  str(_eigenschaft(eintrag, "Type", "")))
        # Verteilerlisten werden bewusst nicht aufgeloest: der Mitgliederstand
        # von heute passt nicht zur Mail von vor acht Monaten.  Sie werden
        # gezaehlt, damit die Empfaengerzahl als Untergrenze erkennbar bleibt.
        if _eigenschaft(eintrag, "DisplayType", None) in (OL_DISTRIBUTION_LIST,
                                                          OL_PRIVATE_DIST_LIST):
            n_listen += 1

        klasse = adresse_klassifizieren(adresse, config)
        ids.append(adresse)
        klassen.append(klasse)
        if typ == OL_CC:
            n_cc += 1
            n_cc_intern += klasse in ("intern", "konzern")
            n_cc_extern += klasse == "extern"
        else:
            # BCC wird der Empfaengerzahl zugerechnet, aber nie separat
            # berichtet -- bei empfangenen Mails ist es prinzipiell unsichtbar
            # und jede Kennzahl darauf waere systematisch verzerrt.
            n_to += 1
            n_to_intern += klasse in ("intern", "konzern")
            n_to_extern += klasse == "extern"
    return ids, klassen, n_to, n_cc, n_to_intern, n_to_extern, n_cc_intern, n_cc_extern, n_listen


def nachricht_lesen(item, config: Config, ordner: str, store: str,
                    eigene_adressen: set[str]) -> Nachricht | None:
    message_class = str(_eigenschaft(item, "MessageClass", ""))
    if message_class.lower().startswith(("report.", "ipm.task", "ipm.contact",
                                         "ipm.activity", "ipm.stickynote")):
        return None

    zeitstempel = _eigenschaft(item, "ReceivedTime", None) or _eigenschaft(item, "SentOn", None)
    if not zeitstempel:
        return None
    try:
        zeitstempel = datetime(zeitstempel.year, zeitstempel.month, zeitstempel.day,
                               zeitstempel.hour, zeitstempel.minute, zeitstempel.second)
    except Exception:
        return None

    absender = _smtp_aufloesen(item, str(_eigenschaft(item, "SenderEmailAddress", "")),
                               str(_eigenschaft(item, "SenderEmailType", "")))
    (ids, klassen, n_to, n_cc, n_to_intern, n_to_extern,
     n_cc_intern, n_cc_extern, n_listen) = _empfaenger_lesen(item, config)

    try:
        kopfzeilen = str(item.PropertyAccessor.GetProperty(PR_TRANSPORT_MESSAGE_HEADERS))
    except Exception:
        kopfzeilen = ""
    try:
        message_id = str(item.PropertyAccessor.GetProperty(PR_INTERNET_MESSAGE_ID))
    except Exception:
        message_id = ""

    betreff = str(_eigenschaft(item, "Subject", ""))
    groesse = int(_eigenschaft(item, "Size", 0) or 0)

    # Richtung nicht am Ordner festmachen -- Ordner sind unzuverlaessig.
    gesendet = adresse_normalisieren(absender) in eigene_adressen

    return Nachricht(
        msg_hash=duplikat_schluessel(message_id, absender, zeitstempel, ids, groesse),
        zeitstempel=zeitstempel,
        richtung=RICHTUNG_GESENDET if gesendet else RICHTUNG_EMPFANGEN,
        absender_id=absender,
        absender_klasse=adresse_klassifizieren(absender, config),
        absender_domain=absender.rsplit("@", 1)[1] if "@" in absender else "",
        empfaenger_ids=ids,
        empfaenger_klassen=klassen,
        n_to=n_to, n_cc=n_cc,
        n_to_intern=n_to_intern, n_to_extern=n_to_extern,
        n_cc_intern=n_cc_intern, n_cc_extern=n_cc_extern,
        n_verteilerlisten=n_listen,
        klasse=nachricht_klassifizieren(absender, message_class, kopfzeilen),
        hat_anhang=_anhangszahl(item) > 0,
        ist_antwort=ist_antwort_betreff(betreff),
        ordner=ordner,
        store=store,
        conversation_id=str(_eigenschaft(item, "ConversationID", "")),
        # Der Betreff wird gehasht und nie gespeichert.
        betreff_hash=betreff_hashen(betreff),
    )


def eigene_adressen_ermitteln(namespace) -> set[str]:
    adressen = set()
    for zugriff in (
        lambda: namespace.CurrentUser.AddressEntry.GetExchangeUser().PrimarySmtpAddress,
        lambda: namespace.CurrentUser.Address,
    ):
        try:
            wert = zugriff()
        except Exception:
            continue
        if wert and "@" in str(wert):
            adressen.add(adresse_normalisieren(str(wert)))
    for konto in _eigenschaft(namespace.Session, "Accounts", []) or []:
        try:
            adressen.add(adresse_normalisieren(str(konto.SmtpAddress)))
        except Exception:
            continue
    return {a for a in adressen if a}


def auslesen(config: Config, fortschritt=None, kontakte_sammeln: bool = False,
             mit_signaturen: bool = False) -> tuple[list[Nachricht], dict]:
    """Liest alle freigegebenen Ordner im Zeitfenster.  Rein lesend.

    mit_signaturen liest zusaetzlich das Ende der Mailtexte, um Firmennamen zu
    finden.  Das ist ein bewusster Bruch mit dem Grundsatz 'nur Metadaten' und
    deshalb nur auf ausdrueckliche Anforderung aktiv.
    """
    namespace = verbinden()
    eigene = eigene_adressen_ermitteln(namespace)
    beginn = datetime.now() - timedelta(days=30 * config.zeitraum_monate)
    filter_ausdruck = "[ReceivedTime] >= '" + beginn.strftime("%d.%m.%Y 00:00") + "'"

    nachrichten: list[Nachricht] = []
    belege: dict[str, list[Beleg]] = {}
    berichte = {"ordner": [], "stores": set(), "uebersprungen": []}

    for store_name, ordnername, ordner in ordner_sammeln(namespace, config):
        berichte["stores"].add(store_name)
        try:
            elemente = ordner.Items
            elemente.Sort("[ReceivedTime]", True)
            # Restrict statt Vollscan -- sonst dauert es auf grossen Postfaechern
            # unnoetig lange.
            elemente = elemente.Restrict(filter_ausdruck)
        except Exception:
            berichte["uebersprungen"].append(f"{store_name}/{ordnername}")
            continue

        anzahl = 0
        try:
            item = elemente.GetFirst()
        except Exception:
            continue
        while item is not None:
            try:
                nachricht = nachricht_lesen(item, config, ordnername, store_name, eigene)
                if nachricht is not None:
                    nachrichten.append(nachricht)
                    anzahl += 1
                    if kontakte_sammeln:
                        for beleg in _kontaktbelege(item, nachricht, mit_signaturen):
                            belege.setdefault(beleg.adresse, []).append(beleg)
            except Exception:
                pass
            try:
                item = elemente.GetNext()
            except Exception:
                break
        berichte["ordner"].append({"store": store_name, "ordner": ordnername, "elemente": anzahl})
        if fortschritt:
            fortschritt(f"{store_name} / {ordnername}: {anzahl}")

    berichte["stores"] = sorted(berichte["stores"])
    berichte["eigene_adressen"] = sorted(eigene)
    berichte["kontaktbelege"] = belege
    return nachrichten, berichte
