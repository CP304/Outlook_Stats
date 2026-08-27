"""Ein nachgebautes Outlook fuer die Tests.

Die COM-Schnittstelle laesst sich hier nicht ausfuehren -- aber ihre Zusagen
lassen sich nachbauen.  Genau das haette den Fehler gefunden, der in der ersten
Fassung jeden Mailordner uebersehen liess: Folder.DefaultItemType liefert
olMailItem = 0, nicht die 43 aus einer anderen Aufzaehlung.

Die Attrappe haelt sich bewusst an die echten Eigenheiten:

  * DefaultItemType kommt aus OlItemType (Mail = 0)
  * SenderEmailAddress liefert bei internen Mails eine X500-Adresse
  * Restrict wirft nicht, wenn der Ausdruck nicht passt -- es liefert nichts
"""

from __future__ import annotations

from datetime import datetime


OL_MAIL, OL_TERMIN, OL_KONTAKT = 0, 1, 2


class Eigenschaften:
    """PropertyAccessor-Ersatz."""

    def __init__(self, werte: dict):
        self._werte = werte

    def GetProperty(self, name):
        if name not in self._werte:
            raise RuntimeError("Eigenschaft nicht vorhanden")
        return self._werte[name]


class AddressEntry:
    def __init__(self, smtp: str, anzeigename: str = "", typ: str = "SMTP",
                 display_type: int = 0):
        self._smtp = smtp
        self.Name = anzeigename
        self.Type = typ
        self.DisplayType = display_type

    def GetExchangeUser(self):
        if self.Type != "EX":
            raise RuntimeError("kein Exchange-Nutzer")
        return type("Nutzer", (), {"PrimarySmtpAddress": self._smtp})()


class Recipient:
    def __init__(self, smtp: str, typ: int = 1, name: str = "", exchange: bool = False,
                 verteilerliste: bool = False):
        self.Type = typ
        self.Name = name
        self.Address = ("/o=Firma/ou=Gruppe/cn=Recipients/cn=" + smtp.split("@")[0]
                        if exchange else smtp)
        self.AddressEntry = AddressEntry(
            smtp, name, "EX" if exchange else "SMTP",
            1 if verteilerliste else 0)
        self.PropertyAccessor = Eigenschaften(
            {"http://schemas.microsoft.com/mapi/proptag/0x39FE001E": smtp})


class MailItem:
    def __init__(self, absender: str, empfaenger: list[Recipient],
                 zeitpunkt: datetime, betreff: str = "Angebot",
                 message_class: str = "IPM.Note", exchange: bool = False,
                 body: str = "", message_id: str = "", groesse: int = 4096):
        self.MessageClass = message_class
        self.Subject = betreff
        self.ReceivedTime = zeitpunkt
        self.SentOn = zeitpunkt
        self.Size = groesse
        self.Body = body
        self.SenderName = ""
        self.Recipients = empfaenger
        self.Attachments = type("Anhaenge", (), {"Count": 0})()
        self.ConversationID = "CV" + betreff
        self.SenderEmailType = "EX" if exchange else "SMTP"
        self.SenderEmailAddress = (
            "/o=Firma/ou=Gruppe/cn=Recipients/cn=" + absender.split("@")[0]
            if exchange else absender)
        # Bewusst wie das Original: PR_SMTP_ADDRESS (0x39FE001E) existiert auf
        # Recipients und AddressEntries, NICHT auf dem MailItem.  Fuer den
        # Absender gibt es PidTagSenderSmtpAddress (0x5D01001E).  Eine
        # Attrappe, die hier freundlicher ist als Outlook, wuerde genau den
        # Fehler verdecken, den sie finden soll.
        self.PropertyAccessor = Eigenschaften({
            "http://schemas.microsoft.com/mapi/proptag/0x5D01001E": absender,
            "http://schemas.microsoft.com/mapi/proptag/0x1035001E":
                message_id or f"<{betreff}-{zeitpunkt.isoformat()}@firma.de>",
            "http://schemas.microsoft.com/mapi/proptag/0x007D001E": "",
        })


class Items:
    def __init__(self, eintraege: list, filter_versteht_dasl: bool = True):
        self._eintraege = list(eintraege)
        self._filter_versteht_dasl = filter_versteht_dasl
        self._zeiger = 0

    @property
    def Count(self):
        return len(self._eintraege)

    def Sort(self, *_a):
        self._eintraege.sort(key=lambda x: x.ReceivedTime, reverse=True)

    def Restrict(self, ausdruck: str):
        # Genau wie das Original: ein Ausdruck, den Outlook nicht versteht,
        # liefert eine leere Menge statt eines Fehlers.
        if not self._filter_versteht_dasl:
            return Items([], self._filter_versteht_dasl)
        grenze = datetime.strptime(ausdruck.split("'")[1], "%Y-%m-%d %H:%M")
        return Items([e for e in self._eintraege if e.ReceivedTime >= grenze],
                     self._filter_versteht_dasl)

    def GetFirst(self):
        self._zeiger = 0
        return self.GetNext()

    def GetNext(self):
        if self._zeiger >= len(self._eintraege):
            return None
        eintrag = self._eintraege[self._zeiger]
        self._zeiger += 1
        return eintrag


class Folder:
    def __init__(self, name: str, eintraege: list | None = None,
                 unterordner: list | None = None, art: int = OL_MAIL,
                 filter_versteht_dasl: bool = True):
        self.Name = name
        self.DefaultItemType = art
        self.Items = Items(eintraege or [], filter_versteht_dasl)
        self.Folders = unterordner or []


class Store:
    def __init__(self, name: str, wurzel: Folder, typ: int = 1):
        self.DisplayName = name
        self.ExchangeStoreType = typ
        self._wurzel = wurzel

    def GetRootFolder(self):
        return self._wurzel


class Konto:
    def __init__(self, smtp: str):
        self.SmtpAddress = smtp


class Namespace:
    """Wie das Original: Accounts haengt am Namespace, eine Session-Eigenschaft
    gibt es hier bewusst nicht -- Code, der sie voraussetzt, soll fallen."""

    def __init__(self, stores: list[Store], eigene: str = "ich@firma.de",
                 konten: list[str] | None = None):
        self.Stores = stores
        self.CurrentUser = type("Nutzer", (), {
            "Address": eigene,
            "AddressEntry": AddressEntry(eigene, typ="EX"),
        })()
        if konten is not None:
            self.Accounts = [Konto(k) for k in konten]


def standard_postfach(zeitpunkt: datetime, filter_versteht_dasl: bool = True) -> Namespace:
    """Ein Postfach mit Posteingang, Unterordner, Gesendetem und Junk."""
    intern = Recipient("kollege@firma.de", 1, "Kollege", exchange=True)
    extern = Recipient("kontakt@lieferant.com", 1, "Anna Schmidt")

    posteingang = Folder("Posteingang", [
        MailItem("kontakt@lieferant.com", [Recipient("ich@firma.de", 1, exchange=True)],
                 zeitpunkt, "Angebot 1"),
        MailItem("kollege@firma.de", [Recipient("ich@firma.de", 1, exchange=True)],
                 zeitpunkt, "Abstimmung", exchange=True),
    ], unterordner=[
        Folder("Projekte", [
            MailItem("kontakt@lieferant.com",
                     [Recipient("ich@firma.de", 1, exchange=True)],
                     zeitpunkt, "Angebot 2"),
        ], filter_versteht_dasl=filter_versteht_dasl),
    ], filter_versteht_dasl=filter_versteht_dasl)

    gesendet = Folder("Gesendete Elemente", [
        MailItem("ich@firma.de", [intern, extern], zeitpunkt, "Anfrage", exchange=True),
    ], filter_versteht_dasl=filter_versteht_dasl)

    junk = Folder("Junk-E-Mail", [
        MailItem("spam@irgendwo.xy", [Recipient("ich@firma.de", 1)], zeitpunkt, "Werbung"),
    ], filter_versteht_dasl=filter_versteht_dasl)

    kalender = Folder("Kalender", [], art=OL_TERMIN)

    wurzel = Folder("Postfach", [], [posteingang, gesendet, junk, kalender])
    return Namespace([Store("Postfach – Ich", wurzel)])
