"""Synthetische Testdaten.

Erzeugt ein Postfach mit bekannten Eigenschaften, damit sich die gesamte
Auswertung ohne Outlook und ohne echte Daten pruefen laesst.  Die Verteilungen
sind so gewaehlt, dass sie den in der Praxis erwarteten Effekt enthalten:
interne Vorgaenge sind laenger als externe.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .model import (
    AUTOMATISIERT, EXTERN, INTERN, NORMAL, RICHTUNG_EMPFANGEN,
    RICHTUNG_GESENDET, TERMIN, Nachricht,
)


INTERNE = [f"person{i}@firma.de" for i in range(1, 13)]
DATEINAMEN = ["Angebot", "Preisliste", "Zeichnung", "Spezifikation", "Rahmenvertrag",
              "Lieferplan", "Reklamation", "Protokoll"]
ENDUNGEN = ["pdf", "xlsx", "docx", "pdf", "pdf", "step", "zip", "msg"]
BETREFFE = ["Angebot", "Anfrage", "Bestellung", "Reklamation", "Rahmenvertrag",
            "Liefertermin", "Preisanpassung", "Abstimmung", "Jour fixe"]
EXTERNE_DOMAINS = [f"lieferant{i}.com" for i in range(1, 9)] + ["dienstleister.de", "kunde.at"]
ICH = "ich@firma.de"


def postfach_erzeugen(
    n_vorgaenge: int = 300,
    anteil_intern: float = 0.55,
    anteil_gemischt: float = 0.20,
    seed: int = 42,
    ende: datetime | None = None,
) -> list[Nachricht]:
    zufall = random.Random(seed)
    ende = ende or datetime(2026, 6, 30, 17, 0)
    beginn = ende - timedelta(days=365)
    nachrichten: list[Nachricht] = []
    laufend = 0

    for vorgang_nr in range(n_vorgaenge):
        wuerfel = zufall.random()
        if wuerfel < anteil_intern:
            art = "intern"
        elif wuerfel < anteil_intern + anteil_gemischt:
            art = "gemischt"
        else:
            art = "extern"

        # Interne Vorgaenge brauchen mehr Runden -- genau der Effekt, den die
        # Analyse sichtbar machen soll.
        laenge = (zufall.randint(2, 12) if art == "intern"
                  else zufall.randint(2, 8) if art == "gemischt"
                  else zufall.randint(1, 4))

        start = beginn + timedelta(seconds=zufall.randint(0, int((ende - beginn).total_seconds())))
        conv = f"CONV{vorgang_nr:05d}"
        betreff_hash = f"HASH{vorgang_nr:05d}"
        # Jeder zehnte Vorgang laeuft ueber einen grossen Verteiler -- ohne die
        # bleibt die Auswertung der Verteilergroesse im Beispiel leer.
        breit = zufall.random() < 0.10
        interne_partner = zufall.sample(
            INTERNE, zufall.randint(6, len(INTERNE)) if breit else zufall.randint(1, 4))
        extern_adresse = f"kontakt@{zufall.choice(EXTERNE_DOMAINS)}"

        zeitpunkt = start
        for runde in range(laenge):
            zeitpunkt += timedelta(hours=zufall.randint(1, 30))
            if zeitpunkt > ende:
                break
            rein_intern = art == "intern" or (art == "gemischt" and zufall.random() < 0.55)
            empfaenger = list(interne_partner)
            klassen = [INTERN] * len(empfaenger)
            if not rein_intern:
                empfaenger.append(extern_adresse)
                klassen.append(EXTERN)

            gesendet = zufall.random() < 0.5
            if gesendet:
                absender, absender_klasse = ICH, INTERN
            elif rein_intern:
                absender, absender_klasse = zufall.choice(interne_partner), INTERN
                empfaenger = [ICH] + [e for e in empfaenger if e != absender]
                klassen = [INTERN] * len(empfaenger)
            else:
                absender, absender_klasse = extern_adresse, EXTERN
                empfaenger = [ICH] + interne_partner
                klassen = [INTERN] * len(empfaenger)

            anzahl_anhaenge = zufall.choice([0, 0, 0, 1, 1, 2, 3])
            namen = [f"{zufall.choice(DATEINAMEN)}.{zufall.choice(ENDUNGEN)}"
                     for _ in range(anzahl_anhaenge)]
            n_cc = zufall.randint(0, 2) if rein_intern else 0
            if breit and rein_intern:
                # Bei Grossverteilern steht die Mehrheit im CC, nicht im TO.
                n_cc = max(n_cc, len(empfaenger) - zufall.randint(1, 2))
            n_bcc = 1 if (gesendet and zufall.random() < 0.05) else 0
            n_to = max(1, len(empfaenger) - n_cc)
            laufend += 1
            nachrichten.append(Nachricht(
                msg_hash=f"mid:{laufend}@firma.de",
                zeitstempel=zeitpunkt,
                richtung=RICHTUNG_GESENDET if gesendet else RICHTUNG_EMPFANGEN,
                absender_id=absender,
                absender_klasse=absender_klasse,
                absender_domain=absender.split("@")[1],
                empfaenger_ids=empfaenger,
                empfaenger_klassen=klassen,
                n_to=n_to,
                n_cc=n_cc,
                n_to_intern=sum(1 for k in klassen[:n_to] if k == INTERN),
                n_to_extern=sum(1 for k in klassen[:n_to] if k == EXTERN),
                n_cc_intern=sum(1 for k in klassen[n_to:] if k == INTERN),
                n_cc_extern=sum(1 for k in klassen[n_to:] if k == EXTERN),
                klasse=NORMAL,
                hat_anhang=anzahl_anhaenge > 0,
                n_anhaenge=anzahl_anhaenge,
                anhangnamen=namen,
                groesse=zufall.randint(3_000, 40_000) + anzahl_anhaenge * 250_000,
                betreff=f"{zufall.choice(BETREFFE)} {vorgang_nr:04d}",
                n_bcc=n_bcc,
                n_bcc_intern=n_bcc,
                ist_antwort=runde > 0,
                ist_weiterleitung=runde > 0 and zufall.random() < 0.15,
                ordner="Posteingang" if not gesendet else "Gesendete Elemente",
                store="Postfach",
                conversation_id=conv,
                betreff_hash=betreff_hash,
            ))

    # Maschinenverkehr und Termine -- sie duerfen die Kern-KPIs nicht verfaelschen.
    for i in range(60):
        laufend += 1
        zeitpunkt = beginn + timedelta(seconds=zufall.randint(0, int((ende - beginn).total_seconds())))
        automat = i % 2 == 0
        nachrichten.append(Nachricht(
            msg_hash=f"mid:auto{laufend}@firma.de",
            zeitstempel=zeitpunkt,
            richtung=RICHTUNG_EMPFANGEN,
            absender_id="noreply@firma.de" if automat else "kollege@firma.de",
            absender_klasse=INTERN,
            absender_domain="firma.de",
            empfaenger_ids=[ICH],
            empfaenger_klassen=[INTERN],
            n_to=1,
            klasse=AUTOMATISIERT if automat else TERMIN,
            ordner="Posteingang",
            store="Postfach",
            conversation_id=f"AUTO{i}",
            betreff_hash=f"AUTOHASH{i}",
        ))

    nachrichten.sort(key=lambda n: n.zeitstempel)
    return nachrichten


# Beispielsignaturen fuer die Demo -- damit sichtbar wird, wie die Spalten
# Funktion, Telefon und Mobil gefuellt aussehen.  Reine Phantasiedaten.
BEISPIEL_SIGNATUREN = [
    ("Anna Schmidt", "Leiterin Vertrieb", "+49 231 55501-10", "0170 1234567"),
    ("Tom Berg", "Key Account Manager", "089 998877-12", "0171 2223344"),
    ("Petra Falk", "Technische Beratung", "0221 4455660", None),
    ("Jan Kruse", "Geschäftsführer", "+49 40 776655-0", "0151 9988776"),
    ("Lea Wolter", "Sachbearbeiterin Auftragsabwicklung", "0511 334455-8", None),
]


def belege_erzeugen(nachrichten: list[Nachricht], seed: int = 42) -> dict:
    """Erfundene Signaturbelege fuer die Demo.

    Bewusst nicht fuer jeden Kontakt: In echten Postfaechern steht die Signatur
    meist nur in der ersten Mail eines Vorgangs, nicht in jeder Antwort -- leere
    Felder sind der Normalfall und sollen es in der Demo auch sein.
    """
    from .kontakte import Beleg

    zufall = random.Random(seed)
    adressen = sorted({n.absender_id for n in nachrichten
                       if n.absender_klasse == EXTERN})
    belege: dict[str, list] = {}
    for i, adresse in enumerate(adressen):
        if i >= len(BEISPIEL_SIGNATUREN):
            break
        name, funktion, telefon, mobil = BEISPIEL_SIGNATUREN[i]
        firma = f"{adresse.split('@')[1].split('.')[0].title()} GmbH"
        # Zwei Belege -- die Konsensregel verlangt mindestens zwei.
        belege[adresse] = [Beleg(adresse, name, firma, funktion, telefon, mobil)
                           for _ in range(zufall.randint(2, 5))]
    return belege
