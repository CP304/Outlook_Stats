"""Kontaktliste und Signaturerkennung.

Der Anspruch ist 'deterministisch': gleiche Eingabe, gleicher Firmenname, und
im Zweifel lieber ein leeres Feld als eine Vermutung.
"""

from datetime import datetime, timedelta

import pytest

from okoa import kontakte, threads
from okoa.signaturen import aus_domain, firma_kandidat, konsens
from okoa.synthetic import postfach_erzeugen


SIGNATUR = """Sehr geehrte Damen und Herren,

anbei das Angebot.

Mit freundlichen Grüßen
Anna Schmidt
Leiterin Vertrieb

Muster Werkzeugbau GmbH & Co. KG
Industriestraße 14 | 12345 Musterstadt
Tel. +49 123 4567-0
anna.schmidt@muster-werkzeugbau.de
"""


# ------------------------------------------------------------- Signaturen

def test_firmenname_aus_signatur():
    assert firma_kandidat(SIGNATUR) == "Muster Werkzeugbau GmbH & Co. KG"


def test_haftungsausschluss_wird_nicht_als_firma_gelesen():
    """Disclaimer enthalten fast immer eine Rechtsform -- und nie den Absender."""
    text = SIGNATUR + ("\nDiese E-Mail ist vertraulich. Die Muster Holding AG "
                       "haftet nicht für den Inhalt.\n")
    assert firma_kandidat(text) == "Muster Werkzeugbau GmbH & Co. KG"


@pytest.mark.parametrize("zeile", [
    "Tel. +49 123 4567 GmbH",
    "Geschäftsführer: Max Mustermann, Muster GmbH",
    "Handelsregister: HRB 1234, Amtsgericht Musterstadt, Muster GmbH",
])
def test_stoerzeilen_werden_uebergangen(zeile):
    assert firma_kandidat(f"Gruß\nAnna\n{zeile}\n") is None


def test_ohne_rechtsform_kein_treffer():
    assert firma_kandidat("Viele Grüße\nAnna Schmidt\nEinkauf\n") is None
    assert firma_kandidat("") is None
    assert firma_kandidat(None) is None


def test_konsens_braucht_mehrere_belege():
    """Ein Einzelfund kann eine im Fließtext erwähnte Fremdfirma sein."""
    assert konsens(["Muster GmbH"]) == (None, 1)
    assert konsens(["Muster GmbH", "Muster GmbH"]) == ("Muster GmbH", 2)


def test_konsens_bei_gleichstand_lieber_nichts():
    """Ein Münzwurf wäre nicht deterministisch."""
    name, _ = konsens(["A GmbH", "A GmbH", "B AG", "B AG"])
    assert name is None


def test_konsens_ist_reproduzierbar():
    kandidaten = ["A GmbH", "B AG", "A GmbH", "A GmbH", "B AG"]
    assert konsens(kandidaten) == konsens(list(reversed(kandidaten)))


def test_domainname_ist_nur_lesehilfe():
    assert aus_domain("muster-werkzeugbau.de") == "Muster Werkzeugbau"
    assert aus_domain("") == ""


# -------------------------------------------------------------- Kontakte

@pytest.fixture
def vorgaenge():
    nachrichten = postfach_erzeugen(120, seed=11)
    threads.zuordnen(nachrichten)
    return threads.vorgaenge_bilden(nachrichten)


def test_nur_externe_kontakte(vorgaenge):
    for kontakt in kontakte.sammeln(vorgaenge):
        assert not kontakt.adresse.endswith("@firma.de")


def test_automaten_bleiben_draussen(vorgaenge):
    adressen = {k.adresse for k in kontakte.sammeln(vorgaenge)}
    assert not any(a.startswith(("noreply", "no-reply", "mailer-daemon"))
                   for a in adressen)


def test_richtung_wird_getrennt_gezaehlt(vorgaenge):
    for kontakt in kontakte.sammeln(vorgaenge):
        assert kontakt.gesendet + kontakt.empfangen == kontakt.nachrichten


def test_herkunft_wird_immer_ausgewiesen(vorgaenge):
    """Wer die Spalte weiterverwendet, muss sehen, wie sicher sie ist."""
    for zeile in kontakte.als_zeilen(kontakte.sammeln(vorgaenge)):
        assert zeile["Herkunft Unternehmen"] in (kontakte.HERKUNFT_SIGNATUR,
                                                 kontakte.HERKUNFT_DOMAIN)


def test_signatur_schlaegt_domain(vorgaenge):
    liste = kontakte.sammeln(vorgaenge)
    adresse = liste[0].adresse
    belege = {adresse: [kontakte.Beleg(adresse, "Anna Schmidt", "Muster GmbH")] * 2}
    zeile = kontakte.als_zeilen(kontakte.sammeln(vorgaenge, belege))[0]
    assert zeile["Unternehmen"] == "Muster GmbH"
    assert zeile["Herkunft Unternehmen"] == kontakte.HERKUNFT_SIGNATUR
    assert zeile["Belege"] == 2


def test_firma_gilt_fuer_die_ganze_domain(vorgaenge):
    """Ein Kollege ohne Signatur erbt die Firmierung seines Hauses."""
    liste = kontakte.sammeln(vorgaenge)
    domain = liste[0].domain
    partner = kontakte.Kontakt(adresse=f"zweiter@{domain}", domain=domain)
    liste.append(partner)
    liste[0].firma_kandidaten = ["Muster GmbH"] * 2
    zeilen = {z["E-Mail"]: z for z in kontakte.als_zeilen(liste)}
    assert zeilen[partner.adresse]["Unternehmen"] == "Muster GmbH"


def test_zeitstempel_sind_echte_datumswerte(vorgaenge):
    """Als Text sortiert Excel den 01.02. vor den 30.01. -- also echte Werte."""
    zeile = kontakte.als_zeilen(kontakte.sammeln(vorgaenge))[0]
    for spalte in kontakte.ZEITSPALTEN:
        assert isinstance(zeile[spalte], datetime), spalte


def test_letzter_kontakt_ist_der_juengste(vorgaenge):
    for kontakt in kontakte.sammeln(vorgaenge):
        zeitpunkte = [t for t in (kontakt.letzte_eigene, kontakt.letzte_fremde) if t]
        assert kontakt.letzter_kontakt == max(zeitpunkte)
        assert kontakt.erstkontakt <= kontakt.letzter_kontakt


def test_richtung_der_letzten_nachricht_wird_getrennt(vorgaenge):
    """Eine eigene Nachricht ohne Antwort ist etwas anderes als ein Dialog."""
    liste = kontakte.sammeln(vorgaenge)
    assert any(k.letzte_eigene != k.letzte_fremde for k in liste)


def test_excel_formatiert_die_zeitstempel(vorgaenge, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    zeilen = kontakte.als_zeilen(kontakte.sammeln(vorgaenge))
    ziel = kontakte.schreiben(zeilen, tmp_path / "Externe_Kontakte.xlsx")
    blatt = openpyxl.load_workbook(ziel).active
    spalte = kontakte.SPALTEN.index("Letzter Kontakt") + 1
    zelle = blatt.cell(row=2, column=spalte)
    assert isinstance(zelle.value, datetime)
    assert zelle.number_format == kontakte.ZEITFORMAT


def test_csv_schreibt_zeitstempel_aus(vorgaenge, tmp_path):
    zeilen = kontakte.als_zeilen(kontakte.sammeln(vorgaenge))
    ziel = kontakte.schreiben(zeilen, tmp_path / "Kontakte.csv")
    text = ziel.read_text(encoding="utf-8-sig")
    assert "datetime.datetime" not in text
    assert ":" in text.splitlines()[1]


def test_tage_seit_kontakt_nie_negativ(vorgaenge):
    stichtag = datetime(2020, 1, 1)      # vor allen Nachrichten
    for zeile in kontakte.als_zeilen(kontakte.sammeln(vorgaenge), stichtag=stichtag):
        assert zeile["Tage seit letztem Kontakt"] >= 0


def test_status_haengt_am_letzten_kontakt(vorgaenge):
    liste = kontakte.sammeln(vorgaenge)
    stichtag = max(k.letzter_kontakt for k in liste) + timedelta(days=400)
    zeilen = kontakte.als_zeilen(liste, stichtag=stichtag)
    assert all(z["Status"] == "eingeschlafen" for z in zeilen)


def test_excel_enthaelt_alle_spalten(vorgaenge, tmp_path):
    zeilen = kontakte.als_zeilen(kontakte.sammeln(vorgaenge))
    ziel = kontakte.schreiben(zeilen, tmp_path / "Externe_Kontakte.xlsx")
    assert ziel.exists()
    from okoa.mapping import lesen
    gelesen = lesen(ziel)
    assert gelesen and set(kontakte.SPALTEN) <= set(gelesen[0])
    assert len(gelesen) == len(zeilen)


def test_sortierung_nach_volumen(vorgaenge):
    zeilen = kontakte.als_zeilen(kontakte.sammeln(vorgaenge))
    mengen = [z["Nachrichten"] for z in zeilen]
    assert mengen == sorted(mengen, reverse=True)
