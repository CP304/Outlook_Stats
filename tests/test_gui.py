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
