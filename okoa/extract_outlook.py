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
    duplikat_schluessel, ist_antwort_betreff, ist_weiterleitung_betreff, ist_x500,
    nachricht_klassifizieren,
)
from .signaturen import firma_kandidat, funktion_kandidat, telefon_kandidaten


# MAPI-Eigenschaften, die ueber den PropertyAccessor erreichbar sind.
# PR_SMTP_ADDRESS existiert auf Recipients und AddressEntries -- nicht auf
# dem MailItem.  Fuer den Absender einer Nachricht ist PidTagSenderSmtpAddress
# der richtige Weg; er funktioniert auch dann noch, wenn der Absender das
# Unternehmen verlassen hat und GetExchangeUser() deshalb nichts mehr findet.
PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
PR_SENDER_SMTP = "http://schemas.microsoft.com/mapi/proptag/0x5D01001E"
PR_INTERNET_MESSAGE_ID = "http://schemas.microsoft.com/mapi/proptag/0x1035001E"
PR_TRANSPORT_MESSAGE_HEADERS = "http://schemas.microsoft.com/mapi/proptag/0x007D001E"

# Folder.DefaultItemType liefert einen Wert aus OlItemType -- dort ist
# olMailItem = 0.  Die haeufig zitierte 43 stammt aus OlObjectClass (olMail)
# und gehoert zu Item.Class.  Wer die beiden verwechselt, erkennt keinen
# einzigen Mailordner und wertet null Nachrichten aus.
OL_MAIL_ITEM = 0           # OlItemType.olMailItem
OL_KLASSE_MAIL = 43        # OlObjectClass.olMail
OL_TO, OL_CC, OL_BCC = 1, 2, 3
OL_DISTRIBUTION_LIST = 1   # AddressEntry.DisplayType olDistList
OL_PRIVATE_DIST_LIST = 5

# OlExchangeStoreType: 0 = Exchange-Postfach, 1 = eigenes Exchange-Postfach,
# 3 = kein Exchange (PST-Datei).  4 waere ein zusaetzlich eingebundenes
# fremdes Postfach -- das bleibt per Vorgabe aussen vor.
EIGENE_STORES = (0, 1, 3)


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
        raise OutlookNichtVerfuegbar(_outlook_hinweis(fehler)) from fehler


def _outlook_hinweis(fehler: Exception) -> str:
    """Uebersetzt COM-Fehler in die tatsaechliche Ursache.

    Ein blanker Fehlercode wie -2147221164 hilft niemandem weiter.  Die drei
    Faelle unten decken praktisch alles ab, was im Alltag schiefgeht.
    """
    text = str(fehler).lower()
    if "0x800401f0" in text or "coinitialize" in text:
        return ("Der Outlook-Zugriff wurde nicht angemeldet (CoInitialize). "
                "Das ist ein Programmfehler -- bitte melden.")
    if "80080005" in text or "server execution failed" in text:
        return ("Outlook liess sich nicht starten.\n\n"
                "Das passiert, wenn Outlook mit anderen Rechten laeuft als "
                "dieses Programm.  Beides gleich starten: entweder beide "
                "normal oder beide als Administrator.")
    if "0x80029c4a" in text or "-2147319779" in text or "class not registered" in text:
        return ("Auf diesem Rechner ist kein Outlook installiert, das sich "
                "ansprechen laesst.\n\n"
                "Die neue Outlook-App aus dem Microsoft Store hat keine "
                "solche Schnittstelle -- gebraucht wird das klassische "
                "Outlook aus Microsoft 365 oder Office.")
    return ("Outlook liess sich nicht ansprechen.\n\n"
            "Bitte Outlook starten und erneut versuchen.  Laeuft Outlook "
            "bereits, hilft haeufig ein Neustart von Outlook.\n\n"
            f"Meldung von Windows: {fehler}")


# ------------------------------------------------------------ Adressen

def _smtp_aufloesen(objekt, adresse: str, typ: str) -> str:
    """Loest eine Exchange-Adresse in eine SMTP-Adresse auf.

    Ohne diesen Schritt liefert SenderEmailAddress bei internen Mails eine
    X500-Adresse.  Wer darauf '@firma.de' prueft, klassifiziert jede interne
    Mail falsch -- der haeufigste und folgenschwerste Fehler dieser Analyseart.
    """
    if adresse and typ and typ.upper() != "EX" and not ist_x500(adresse):
        return adresse_normalisieren(adresse)

    # Reihenfolge: erst die Eigenschaften des Objekts selbst (Recipient bzw.
    # MailItem), dann die Umwege ueber das Adressbuch.
    for versuch in (
        lambda: objekt.PropertyAccessor.GetProperty(PR_SMTP_ADDRESS),
        lambda: objekt.PropertyAccessor.GetProperty(PR_SENDER_SMTP),
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
        # Ordner ohne Angabe werden mitgenommen: lieber ein Ordner zu viel
        # geprueft als das halbe Postfach uebersehen.  Nicht-Mailobjekte
        # filtert nachricht_lesen ohnehin ueber die MessageClass heraus.
        art = _eigenschaft(ordner, "DefaultItemType", None)
        if art in (None, OL_MAIL_ITEM):
            gefunden.append((store_name, name, ordner))
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
        eigenes = _eigenschaft(store, "ExchangeStoreType", 0) in EIGENE_STORES
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
    text = _signaturteil(item) if mit_signaturen else ""
    firma = firma_kandidat(text) if text else None
    funktion = funktion_kandidat(text) if text else None
    telefon, mobil = telefon_kandidaten(text) if text else (None, None)
    belege = []

    if nachricht.absender_klasse == "extern":
        belege.append(Beleg(
            adresse=nachricht.absender_id,
            anzeigename=str(_eigenschaft(item, "SenderName", "")),
            # Die Signatur gehoert dem Absender -- nur ihm wird sie zugerechnet.
            # Fuer Empfaenger waere sie schlicht falsch.
            firma_kandidat=firma,
            funktion_kandidat=funktion,
            telefon_kandidat=telefon,
            mobil_kandidat=mobil,
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
    try:
        return int(item.Attachments.Count)
    except Exception:
        return 0


def _anhangnamen(item, anzahl: int) -> list[str]:
    """Nur bei Vollerhebung -- sonst bleibt es bei der blossen Anzahl."""
    namen = []
    for i in range(1, min(anzahl, 25) + 1):
        try:
            namen.append(str(item.Attachments.Item(i).FileName))
        except Exception:
            continue
    return namen


def _empfaenger_lesen(item, config: Config):
    ids, klassen = [], []
    n_to = n_cc = n_bcc = 0
    n_to_intern = n_to_extern = n_cc_intern = n_cc_extern = 0
    n_bcc_intern = n_bcc_extern = 0
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
        elif typ == OL_BCC:
            # BCC ist nur bei selbst gesendeten Nachrichten ueberhaupt sichtbar.
            # Es wird deshalb getrennt gefuehrt und nicht in die TO-Zahl
            # geschlagen -- sonst waere jede TO-Kennzahl still verfaelscht.
            n_bcc += 1
            n_bcc_intern += klasse in ("intern", "konzern")
            n_bcc_extern += klasse == "extern"
        else:
            n_to += 1
            n_to_intern += klasse in ("intern", "konzern")
            n_to_extern += klasse == "extern"
    return (ids, klassen, n_to, n_cc, n_bcc, n_to_intern, n_to_extern,
            n_cc_intern, n_cc_extern, n_bcc_intern, n_bcc_extern, n_listen)


def nachricht_lesen(item, config: Config, ordner: str, store: str,
                    eigene_adressen: set[str]) -> Nachricht | None:
    """Metadaten einer Nachricht.

    Bei config.vollerhebung kommen Betreff, Anhangnamen, Groesse und die
    BCC-Zahl dazu.  Fuer die eigene Auswertung gedacht.
    """
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
    # Outlook stellt nicht gesetzte Datumsfelder als 1.1.4501 dar.  So ein
    # Element hat keinen brauchbaren Zeitstempel und wuerde als absurder
    # 'letzter Kontakt' in der Kontaktliste stehen.
    if zeitstempel.year >= 4500:
        return None

    absender = _smtp_aufloesen(item, str(_eigenschaft(item, "SenderEmailAddress", "")),
                               str(_eigenschaft(item, "SenderEmailType", "")))
    (ids, klassen, n_to, n_cc, n_bcc, n_to_intern, n_to_extern,
     n_cc_intern, n_cc_extern, n_bcc_intern, n_bcc_extern,
     n_listen) = _empfaenger_lesen(item, config)

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
    anzahl_anhaenge = _anhangszahl(item)

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
        n_bcc_intern=n_bcc_intern, n_bcc_extern=n_bcc_extern,
        n_verteilerlisten=n_listen,
        klasse=nachricht_klassifizieren(absender, message_class, kopfzeilen),
        hat_anhang=anzahl_anhaenge > 0,
        ist_antwort=ist_antwort_betreff(betreff),
        ist_weiterleitung=ist_weiterleitung_betreff(betreff),
        ordner=ordner,
        store=store,
        n_bcc=n_bcc,
        groesse=groesse if config.vollerhebung else 0,
        n_anhaenge=anzahl_anhaenge,
        anhangnamen=(_anhangnamen(item, anzahl_anhaenge)
                     if config.vollerhebung else []),
        betreff=betreff if config.vollerhebung else "",
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
    # NameSpace.Accounts direkt -- ein Umweg ueber .Session wuerde bereits am
    # Attributzugriff scheitern koennen, bevor irgendein Schutz greift.
    try:
        konten = list(namespace.Accounts)
    except Exception:
        konten = []
    for konto in konten:
        try:
            adressen.add(adresse_normalisieren(str(konto.SmtpAddress)))
        except Exception:
            continue
    return {a for a in adressen if a}


def umgebung() -> dict:
    """Sammelt, was zur Fehlersuche auf einem fremden Rechner noetig ist.

    Steht kein Claude auf dem Rechner, muss eine einzige Datei alle Fragen
    beantworten: Welches Python, welches pywin32, welches Outlook, wie viele
    Speicher.  Sonst beginnt genau das Hin und Her, das niemand will.
    """
    import platform
    import sys

    bericht = {
        "python": sys.version.split()[0],
        "python_pfad": sys.executable,
        "windows": platform.platform(),
        "pywin32": "fehlt",
        "outlook": "nicht erreichbar",
        "profil": "",
        "speicher": [],
    }
    try:
        import win32com.client  # noqa: PLC0415
        try:
            import win32api  # noqa: PLC0415

            bericht["pywin32"] = str(win32api.GetFileVersionInfo(
                win32com.client.__file__.rsplit("\\", 3)[0] + "\\pywintypes.dll",
                "\\"))
        except Exception:
            bericht["pywin32"] = "vorhanden"
    except ImportError:
        return bericht

    try:
        anwendung = win32com.client.Dispatch("Outlook.Application")
        bericht["outlook"] = str(_eigenschaft(anwendung, "Version", "?"))
        namespace = anwendung.GetNamespace("MAPI")
        bericht["profil"] = str(_eigenschaft(namespace, "CurrentProfileName", ""))
        for store in namespace.Stores:
            bericht["speicher"].append({
                "name": str(_eigenschaft(store, "DisplayName", "?")),
                "typ": _eigenschaft(store, "ExchangeStoreType", None),
                "zwischenspeicher": _eigenschaft(store, "IsCachedExchange", None),
            })
    except Exception as fehler:
        bericht["outlook"] = f"nicht erreichbar: {fehler}"
    return bericht


def eigene_domain() -> list[str]:
    """Ermittelt die interne Maildomain aus dem eigenen Postfach.

    Damit entfaellt die einzige Pflichteingabe.  Wer sein Postfach oeffnet,
    hat die Antwort ohnehin schon im Programm stehen -- danach zu fragen ist
    eine Fehlerquelle ohne Gegenwert.
    """
    try:
        namespace = verbinden()
    except OutlookNichtVerfuegbar:
        return []
    domains = []
    for adresse in sorted(eigene_adressen_ermitteln(namespace)):
        domain = adresse.rsplit("@", 1)[1] if "@" in adresse else ""
        # Freemail-Domains sind keine Firmendomains -- wer privat testet,
        # soll nicht 'gmail.com' als internes Unternehmen gemeldet bekommen.
        if domain and domain not in FREEMAIL and domain not in domains:
            domains.append(domain)
    return domains


# Bekannte Freemail-Anbieter.  Bewusst kurz gehalten: Die Liste soll die
# offensichtlichen Faelle abfangen, nicht vollstaendig sein.
FREEMAIL = {
    "gmail.com", "googlemail.com", "outlook.com", "outlook.de", "hotmail.com",
    "hotmail.de", "live.com", "live.de", "web.de", "gmx.de", "gmx.net",
    "gmx.at", "gmx.ch", "t-online.de", "yahoo.com", "yahoo.de", "icloud.com",
    "me.com", "aol.com", "freenet.de", "posteo.de", "mailbox.org",
}


def _elemente_holen(ordner, beginn: datetime):
    """Liefert (Elemente, ob_gefiltert) fuer einen Ordner.

    Der Zeitfilter wird ueber DASL gestellt und nicht ueber die
    Klammer-Schreibweise: Deren Datumsformat haengt an den Windows-
    Laendereinstellungen, und ein nicht passendes Format liefert klaglos eine
    leere Menge statt eines Fehlers -- man sieht dann null Nachrichten und
    keinen Hinweis darauf, warum.

    Schlaegt der Filter fehl, wird der Ordner ungefiltert gelesen und der
    Zeitraum spaeter in Python geprueft: lieber langsam als leer.
    """
    try:
        elemente = ordner.Items
    except Exception:
        return None, False
    try:
        elemente.Sort("[ReceivedTime]", True)
    except Exception:
        pass

    ausdruck = ('@SQL="urn:schemas:httpmail:datereceived" >= \''
               + beginn.strftime("%Y-%m-%d %H:%M") + "'")
    try:
        gefiltert = elemente.Restrict(ausdruck)
        # Ein unpassender Filter wirft nicht, er liefert nichts.  Deshalb wird
        # unterschieden, ob das leere Ergebnis echt sein kann.
        if int(gefiltert.Count) > 0 or int(elemente.Count) == 0:
            return gefiltert, True
        # Leer, obwohl der Ordner Elemente hat: Die Sortierung ist absteigend,
        # das erste Element also das juengste.  Liegt es vor dem Fenster, hat
        # der Ordner schlicht nichts im Zeitraum -- das leere Ergebnis stimmt,
        # und ein ungefilterter Vollscan (bei Archiven teuer) unterbleibt.
        try:
            juengstes = elemente.GetFirst()
            zeit = juengstes.ReceivedTime if juengstes is not None else None
            if zeit is not None and datetime(zeit.year, zeit.month, zeit.day,
                                             zeit.hour, zeit.minute) < beginn:
                return gefiltert, True
        except Exception:
            pass
    except Exception:
        pass
    return elemente, False


def pruefen(config: Config) -> dict:
    """Zeigt, was Outlook tatsaechlich hergibt.

    Gedacht fuer den Fall 'null Nachrichten ausgewertet': Sie beantwortet, ob
    das Postfach erreichbar ist, welche Speicher und Ordner gesehen werden, wie
    viele Elemente darin liegen und ob der Zeitfilter greift.
    """
    namespace = verbinden()
    beginn = datetime.now() - timedelta(days=30 * config.zeitraum_monate)
    bericht = {
        "eigene_adressen": sorted(eigene_adressen_ermitteln(namespace)),
        "zeitraum_ab": beginn.strftime("%d.%m.%Y"),
        "stores": [],
        "ordner": [],
        "elemente_gesamt": 0,
        "elemente_im_zeitraum": 0,
        "ordner_ohne_filter": 0,
    }

    for store in namespace.Stores:
        bericht["stores"].append({
            "name": str(_eigenschaft(store, "DisplayName", "?")),
            "typ": _eigenschaft(store, "ExchangeStoreType", None),
            "einbezogen": (_eigenschaft(store, "ExchangeStoreType", 0) in EIGENE_STORES
                           or config.fremde_postfaecher_einbeziehen),
        })

    for store_name, ordnername, ordner in ordner_sammeln(namespace, config):
        gesamt = 0
        try:
            gesamt = int(ordner.Items.Count)
        except Exception:
            pass
        elemente, gefiltert = _elemente_holen(ordner, beginn)
        im_zeitraum = 0
        if elemente is not None:
            try:
                im_zeitraum = int(elemente.Count) if gefiltert else gesamt
            except Exception:
                pass
        if not gefiltert:
            bericht["ordner_ohne_filter"] += 1
        bericht["elemente_gesamt"] += gesamt
        bericht["elemente_im_zeitraum"] += im_zeitraum
        bericht["ordner"].append({
            "store": store_name, "ordner": ordnername,
            "elemente": gesamt, "im_zeitraum": im_zeitraum,
            "filter_greift": gefiltert,
        })
    return bericht


class Abgebrochen(RuntimeError):
    """Der Nutzer hat den Lauf beendet."""


# Nach so vielen Elementen wird der Fortschritt gemeldet.  Klein genug, dass
# sich das Fenster sichtbar ruehrt; gross genug, dass das Melden nicht bremst.
MELDESCHRITT = 250


def auslesen(config: Config, fortschritt=None, kontakte_sammeln: bool = False,
             mit_signaturen: bool = False, abbruch=None) -> tuple[list[Nachricht], dict]:
    """Liest alle freigegebenen Ordner im Zeitfenster.  Rein lesend.

    mit_signaturen liest zusaetzlich das Ende der Mailtexte, um Firmennamen zu
    finden.  Das ist ein bewusster Bruch mit dem Grundsatz 'nur Metadaten' und
    deshalb nur auf ausdrueckliche Anforderung aktiv.
    """
    namespace = verbinden()
    eigene = eigene_adressen_ermitteln(namespace)
    beginn = datetime.now() - timedelta(days=30 * config.zeitraum_monate)

    nachrichten: list[Nachricht] = []
    belege: dict[str, list[Beleg]] = {}
    berichte = {"ordner": [], "stores": set(), "uebersprungen": [],
                "ohne_filter": [], "gefundene_ordner": 0}

    ordnerliste = ordner_sammeln(namespace, config)
    berichte["gefundene_ordner"] = len(ordnerliste)
    if fortschritt:
        fortschritt(f"{len(ordnerliste)} Ordner gefunden.")
    gesamt_gelesen = 0

    for store_name, ordnername, ordner in ordnerliste:
        if abbruch is not None and abbruch.is_set():
            raise Abgebrochen("Der Lauf wurde abgebrochen.")
        berichte["stores"].add(store_name)
        elemente, gefiltert = _elemente_holen(ordner, beginn)
        if elemente is None:
            berichte["uebersprungen"].append(f"{store_name}/{ordnername}")
            continue
        if not gefiltert:
            berichte["ohne_filter"].append(f"{store_name}/{ordnername}")

        anzahl = 0
        try:
            item = elemente.GetFirst()
        except Exception:
            continue
        while item is not None:
            if abbruch is not None and abbruch.is_set():
                raise Abgebrochen("Der Lauf wurde abgebrochen.")
            try:
                nachricht = nachricht_lesen(item, config, ordnername, store_name, eigene)
                # Ohne wirksamen Filter muss der Zeitraum hier geprueft werden.
                if (nachricht is not None and not gefiltert
                        and nachricht.zeitstempel < beginn):
                    nachricht = None
                if nachricht is not None:
                    nachrichten.append(nachricht)
                    anzahl += 1
                    if kontakte_sammeln:
                        for beleg in _kontaktbelege(item, nachricht, mit_signaturen):
                            belege.setdefault(beleg.adresse, []).append(beleg)
            except Exception:
                pass
            gesamt_gelesen += 1
            # Ohne laufende Meldung sieht ein grosses Postfach minutenlang aus
            # wie ein haengendes Programm -- und wird abgeschossen.
            if fortschritt and gesamt_gelesen % MELDESCHRITT == 0:
                fortschritt(f"  {gesamt_gelesen} Elemente gelesen "
                            f"({store_name} / {ordnername}) ...")
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
    berichte["gelesen"] = len(nachrichten)
    return nachrichten, berichte
