"""Oberflaeche.

Geprueft wird, was sich ohne Fenster pruefen laesst: dass die Ablaufschicht
im Hintergrund arbeitet, Fehler meldet statt zu verschwinden, und dass in der
Oberflaeche keine Auswertungslogik steckt.

Die Fensterklasse selbst wird nur dort angefasst, wo eine Anzeige verfuegbar
ist -- sonst uebersprungen.
"""

import time
from datetime import datetime

import pytest

from okoa import auftrag as auftrag_modul
from okoa.config import Config


def _abwarten(auftrag, sekunden=20):
    meldungen = []
    ende = time.time() + sekunden
    while time.time() < ende:
        meldungen.extend(auftrag.abholen())
        if any(art in (auftrag_modul.FERTIG, auftrag_modul.FEHLER)
               for art, _ in meldungen):
            return meldungen
        time.sleep(0.05)
    raise AssertionError("Der Auftrag wurde nicht fertig.")


# ------------------------------------------------------------- Ablauf

def test_auftrag_meldet_verlauf_und_ergebnis():
    auftrag = auftrag_modul.Auftrag()

    def arbeit(melden, faktor):
        melden("läuft")
        return faktor * 2

    assert auftrag.starten(arbeit, 21)
    meldungen = _abwarten(auftrag)
    assert (auftrag_modul.MELDUNG, "läuft") in meldungen
    assert (auftrag_modul.FERTIG, 42) in meldungen


def test_fehler_verschwindet_nicht_im_hintergrundfaden():
    """Ein Fehler im Faden darf nicht dazu führen, dass die Oberfläche wartet."""
    auftrag = auftrag_modul.Auftrag()

    def arbeit(melden):
        raise RuntimeError("etwas ist schiefgegangen")

    auftrag.starten(arbeit)
    meldungen = _abwarten(auftrag)
    art, inhalt = meldungen[-1]
    assert art == auftrag_modul.FEHLER
    assert "schiefgegangen" in inhalt[0]


def test_zweiter_auftrag_wird_abgewiesen():
    auftrag = auftrag_modul.Auftrag()

    def arbeit(melden):
        time.sleep(0.4)
        return "fertig"

    assert auftrag.starten(arbeit) is True
    assert auftrag.starten(arbeit) is False, "Zwei Läufe gleichzeitig wären ein Fehler"
    _abwarten(auftrag)


def test_demo_laeuft_ueber_die_ablaufschicht(tmp_path):
    auftrag = auftrag_modul.Auftrag()
    config = Config(interne_domains=["firma.de"], vollerhebung=True)
    auftrag.starten(auftrag_modul.demo, config, tmp_path, 0.8)
    meldungen = _abwarten(auftrag, 60)
    art, ergebnis = meldungen[-1]
    assert art == auftrag_modul.FERTIG, ergebnis
    assert ergebnis["report"].exists()
    assert ergebnis["kontaktdatei"].exists()


def test_neu_berechnen_ohne_zwischendatei_meldet_verstaendlich(tmp_path):
    auftrag = auftrag_modul.Auftrag()
    auftrag.starten(auftrag_modul.neu_berechnen,
                    Config(interne_domains=["firma.de"]), tmp_path, 0.8)
    art, inhalt = _abwarten(auftrag)[-1]
    assert art == auftrag_modul.FEHLER
    assert "Analyse" in inhalt[0]


# ------------------------------------------------------------ Oberfläche

def test_oberflaeche_enthaelt_keine_auswertungslogik():
    """Die Oberfläche sammelt Eingaben und zeigt an -- gerechnet wird woanders."""
    import ast
    import inspect

    pytest.importorskip("tkinter")
    from okoa import gui

    baum = ast.parse(inspect.getsource(gui))
    namen = {k.func.attr for k in ast.walk(baum)
             if isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)}
    for verboten in ("kern_kpis", "alles_berechnen", "vorgaenge_bilden",
                     "auslesen", "zusammenfuehren"):
        assert verboten not in namen, f"'{verboten}' gehört nicht in die Oberfläche"


def test_fenster_baut_sich_auf(tmp_path):
    tk = pytest.importorskip("tkinter")
    try:
        wurzel = tk.Tk()
    except tk.TclError:
        pytest.skip("keine Anzeige verfügbar")
    wurzel.destroy()

    from okoa.gui import Fenster

    fenster = Fenster()
    try:
        fenster.ordner.set(str(tmp_path))
        fenster.domain.set("firma.de")
        config = fenster._config_bauen()
        assert config is not None
        assert config.interne_domains == ["firma.de"]
        assert fenster.reiter.index("end") == 3
    finally:
        fenster.destroy()


def test_fenster_weist_fehlende_domain_ab(tmp_path, monkeypatch):
    tk = pytest.importorskip("tkinter")
    try:
        wurzel = tk.Tk()
    except tk.TclError:
        pytest.skip("keine Anzeige verfügbar")
    wurzel.destroy()

    from okoa import gui

    gemeldet = []
    monkeypatch.setattr(gui.messagebox, "showwarning",
                        lambda titel, text: gemeldet.append(text))
    fenster = gui.Fenster()
    try:
        fenster.ordner.set(str(tmp_path))
        fenster.domain.set("")
        assert fenster._config_bauen() is None
        assert gemeldet and "Domain" in gemeldet[0]
    finally:
        fenster.destroy()


# ------------------------------------------------- Zuordnungen pflegen

def _zuordnungsfenster(tmp_path, monkeypatch):
    tk = pytest.importorskip("tkinter")
    try:
        wurzel = tk.Tk()
    except tk.TclError:
        pytest.skip("keine Anzeige verfügbar")
    wurzel.destroy()

    from okoa import gui, mapping

    datei = tmp_path / "mapping_personen.csv"
    mapping.schreiben([
        {"E-Mail": "viel@firma.de", "Anzeigename": "Viel", "Nachrichten": 300,
         "Fachbereich": "", "Rolle": ""},
        {"E-Mail": "wenig@firma.de", "Anzeigename": "Wenig", "Nachrichten": 100,
         "Fachbereich": "Finance", "Rolle": ""},
    ], mapping.SPALTEN_PERSONEN, datei)

    eltern = gui.Fenster()
    fenster = gui.ZuordnungsFenster(
        eltern, datei, "E-Mail", "Fachbereich", mapping.SPALTEN_PERSONEN,
        "Test", ["Engineering"])
    return eltern, fenster, datei


def test_zuordnung_ist_nach_volumen_sortiert(tmp_path, monkeypatch):
    eltern, fenster, _ = _zuordnungsfenster(tmp_path, monkeypatch)
    try:
        erste = fenster.tabelle.item(fenster.tabelle.get_children()[0])["values"]
        assert erste[0] == "viel@firma.de", "Die größten Posten gehören nach oben"
    finally:
        fenster.destroy()
        eltern.destroy()


def test_zuweisen_und_speichern(tmp_path, monkeypatch):
    eltern, fenster, datei = _zuordnungsfenster(tmp_path, monkeypatch)
    from okoa import gui, mapping

    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: None)
    try:
        fenster.tabelle.selection_set(fenster.tabelle.get_children()[0])
        fenster.eingabe.set("Engineering")
        fenster._zuweisen()
        fenster._speichern()
        zuordnung = mapping.zuordnung_lesen(datei, "E-Mail", "Fachbereich")
        assert zuordnung["viel@firma.de"] == "Engineering"
        assert zuordnung["wenig@firma.de"] == "Finance", "Vorhandenes bleibt"
    finally:
        fenster.destroy()
        eltern.destroy()


def test_ohne_auswahl_wird_nichts_gesetzt(tmp_path, monkeypatch):
    eltern, fenster, _ = _zuordnungsfenster(tmp_path, monkeypatch)
    from okoa import gui

    gemeldet = []
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda titel, text: gemeldet.append(text))
    try:
        fenster.tabelle.selection_remove(*fenster.tabelle.selection())
        fenster.eingabe.set("Engineering")
        fenster._zuweisen()
        assert gemeldet, "Der Nutzer muss erfahren, warum nichts passiert ist"
        assert all(not z.get("Fachbereich") or z["Fachbereich"] == "Finance"
                   for z in fenster.zeilen)
    finally:
        fenster.destroy()
        eltern.destroy()


def test_abdeckung_zeigt_den_nutzen(tmp_path, monkeypatch):
    """Die Anzeige sagt, wann sich weitere Pflege nicht mehr lohnt."""
    eltern, fenster, _ = _zuordnungsfenster(tmp_path, monkeypatch)
    from okoa import gui

    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: None)
    try:
        # Vorher ist nur der kleine Kontakt gepflegt: 100 von 400 Nachrichten.
        assert "25%" in fenster.stand.cget("text")
        fenster.tabelle.selection_set(fenster.tabelle.get_children()[0])
        fenster.eingabe.set("Engineering")
        fenster._zuweisen()
        assert "100%" in fenster.stand.cget("text")
    finally:
        fenster.destroy()
        eltern.destroy()


def test_filter_zeigt_nur_ungepflegte(tmp_path, monkeypatch):
    eltern, fenster, _ = _zuordnungsfenster(tmp_path, monkeypatch)
    try:
        fenster.nur_offene.set(True)
        fenster._fuellen()
        sichtbar = [fenster.tabelle.item(k)["values"][0]
                    for k in fenster.tabelle.get_children()]
        assert sichtbar == ["viel@firma.de"]
    finally:
        fenster.destroy()
        eltern.destroy()


def test_vollerhebung_hinterlaesst_eine_spur(tmp_path):
    """Sonst sieht ein Lauf mit Vollerhebung genauso aus wie einer ohne."""
    auftrag = auftrag_modul.Auftrag()
    auftrag.starten(auftrag_modul.demo,
                    Config(interne_domains=["firma.de"], vollerhebung=True),
                    tmp_path, None)
    meldungen = [inhalt for art, inhalt in _abwarten(auftrag, 60)
                 if art == auftrag_modul.MELDUNG]
    assert any("Vollerhebung gerechnet" in str(m) for m in meldungen)


def test_ohne_vollerhebung_keine_zusatzmeldung(tmp_path):
    auftrag = auftrag_modul.Auftrag()
    auftrag.starten(auftrag_modul.demo, Config(interne_domains=["firma.de"]),
                    tmp_path, None)
    meldungen = [inhalt for art, inhalt in _abwarten(auftrag, 60)
                 if art == auftrag_modul.MELDUNG]
    assert not any("Vollerhebung" in str(m) for m in meldungen)


# --------------------------------------------------- Robustheit im Alltag

def test_abbruch_beendet_den_lauf(tmp_path):
    """Ein großes Postfach muss sich stoppen lassen, ohne den Prozess zu killen."""
    import threading

    from okoa.extract_outlook import Abgebrochen

    auftrag = auftrag_modul.Auftrag()

    def lange_arbeit(melden, abbruch=None):
        for i in range(1000):
            if abbruch is not None and abbruch.is_set():
                raise Abgebrochen("Der Lauf wurde abgebrochen.")
            time.sleep(0.002)
        return "durchgelaufen"

    auftrag.starten(lange_arbeit)
    time.sleep(0.1)
    auftrag.abbrechen()
    meldungen = _abwarten(auftrag, 20)
    art, inhalt = meldungen[-1]
    assert art == auftrag_modul.FERTIG, "Abbruch ist kein Fehler"
    assert inhalt is None
    assert any("Abgebrochen" in str(m) for _, m in meldungen)


def test_protokoll_haelt_die_meldungen_fest(tmp_path):
    """Nach einem Fehler soll eine Datei genügen, kein abfotografiertes Fenster."""
    auftrag = auftrag_modul.Auftrag()
    auftrag.protokollieren(tmp_path, "Erste Meldung")
    auftrag.protokollieren(tmp_path, "Zweite Meldung")
    inhalt = (tmp_path / "protokoll.txt").read_text(encoding="utf-8")
    assert "Erste Meldung" in inhalt and "Zweite Meldung" in inhalt
    assert inhalt.count("\n") == 2


def test_protokoll_scheitert_lautlos(tmp_path):
    """Ein fehlendes Protokoll darf niemals den Lauf kosten."""
    auftrag = auftrag_modul.Auftrag()
    datei = tmp_path / "belegt"
    datei.write_text("kein Ordner", encoding="utf-8")
    auftrag.protokollieren(datei, "egal")     # darf nicht werfen


def test_gesperrte_dateien_werden_vorab_gemeldet(tmp_path, monkeypatch):
    """Nach zwanzig Minuten Lesephase daran zu scheitern wäre das Ärgerlichste."""
    from okoa import auftrag as modul
    from okoa import dateien

    (tmp_path / "Mein_Report.html").write_text("x", encoding="utf-8")
    monkeypatch.setattr(dateien, "schreibbar", lambda pfad: False)

    meldungen = []
    modul._vorab_pruefen(meldungen.append, tmp_path)
    assert any("gesperrt" in m for m in meldungen)
    assert any("Mein_Report.html" in m for m in meldungen)


def test_ergebnis_geht_bei_gesperrter_datei_nicht_verloren(tmp_path):
    """Die Auswertung ist zu teuer, um sie an einem offenen Excel zu verlieren."""
    from okoa import dateien

    ziel = tmp_path / "Report.html"
    ziel.write_text("alt", encoding="utf-8")

    def schreiben(pfad):
        if pfad == ziel:
            raise PermissionError(13, "Zugriff verweigert")
        pfad.write_text("neu", encoding="utf-8")

    ergebnis = dateien.mit_ausweichen(ziel, schreiben)
    assert ergebnis != ziel
    assert ergebnis.read_text(encoding="utf-8") == "neu"
    assert ziel.read_text(encoding="utf-8") == "alt", "Das Original bleibt unberührt"


def test_umgebungskopf_ist_fuer_sich_lesbar(tmp_path):
    """Ohne Claude auf dem Zielrechner muss diese eine Datei alles beantworten:
    welches Python, welches pywin32, welches Outlook, welche Speicher."""
    from okoa.config import Config

    auftrag = auftrag_modul.Auftrag()
    auftrag.umgebung_protokollieren(
        tmp_path, Config(interne_domains=["firma.de"], zeitraum_monate=24))
    inhalt = (tmp_path / "protokoll.txt").read_text(encoding="utf-8")
    for pflicht in ("Neuer Lauf", "Programmstand", "Python", "System",
                    "pywin32", "Outlook", "Einstellung"):
        assert pflicht in inhalt, f"'{pflicht}' fehlt im Protokollkopf"
    assert "firma.de" in inhalt and "24 Monate" in inhalt


def test_umgebungskopf_ohne_outlook(tmp_path):
    """Auch ohne Outlook muss der Kopf entstehen -- gerade dann."""
    auftrag = auftrag_modul.Auftrag()
    auftrag.umgebung_protokollieren(tmp_path)
    inhalt = (tmp_path / "protokoll.txt").read_text(encoding="utf-8")
    assert "nicht erreichbar" in inhalt or "Outlook" in inhalt
