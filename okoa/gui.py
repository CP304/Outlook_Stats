"""Oberflaeche.

Bewusst tkinter: Es gehoert zum Lieferumfang von Python, braucht also keine
Installation und startet sofort.  Wer das Werkzeug an Kollegen weitergibt, will
nicht vorher 100 MB Abhaengigkeiten erklaeren muessen.

Die Oberflaeche enthaelt keine Auswertungslogik -- sie sammelt Eingaben, startet
eine Arbeit aus okoa.auftrag im Hintergrund und zeigt an, was zurueckkommt.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import auftrag as auftrag_modul
from . import mapping, pipeline, team_export
from .config import Config


TITEL = "Outlook-Kommunikationsanalyse"
ARBEITSORDNER = "Auswertung"
TAKT_MS = 120        # wie oft die Warteschlange abgefragt wird


def datei_oeffnen(pfad: Path) -> None:
    """Oeffnet eine Datei oder einen Ordner im Betriebssystem."""
    pfad = Path(pfad)
    try:
        if sys.platform == "win32":
            os.startfile(pfad)          # noqa: S606 -- unter Windows der Weg
        elif sys.platform == "darwin":
            subprocess.run(["open", str(pfad)], check=False)
        else:
            webbrowser.open(pfad.as_uri())
    except Exception as fehler:
        messagebox.showerror(TITEL, f"Konnte {pfad.name} nicht öffnen:\n{fehler}")



class ZuordnungsFenster(tk.Toplevel):
    """Tabelle zum Pflegen der Zuordnungen -- Fachbereiche oder Kategorien.

    Nach Volumen sortiert, weil in der Praxis 15 bis 25 gepflegte Zeilen rund
    80 % des Volumens abdecken.  Die Spalte 'kumuliert' zeigt, ab wann sich
    weitere Zeilen nicht mehr lohnen -- man soll aufhoeren duerfen.
    """

    def __init__(self, eltern, datei: Path, schluessel: str, wert: str,
                 spalten: list[str], titel: str, vorschlaege: list[str],
                 auswahlliste: tuple[str, list[str]] | None = None) -> None:
        super().__init__(eltern)
        self.title(titel)
        self.geometry("900x600")
        self.minsize(700, 460)

        self.datei = Path(datei)
        self.schluessel = schluessel
        self.wert = wert
        self.spalten = spalten
        self.auswahlliste = auswahlliste
        self.zeilen = mapping.lesen(self.datei)
        self.nur_offene = tk.BooleanVar(value=False)
        self.eingabe = tk.StringVar()

        self._aufbauen(vorschlaege)
        self._fuellen()

    # ------------------------------------------------------------ Aufbau
    def _aufbauen(self, vorschlaege: list[str]) -> None:
        kopf = ttk.Frame(self, padding=(14, 12, 14, 6))
        kopf.pack(fill="x")
        ttk.Label(kopf, text=self.title(), font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(kopf, style="Leise.TLabel", text=(
            "Zeilen auswählen (Strg oder Umschalt für mehrere), unten den Wert "
            "eintragen und zuweisen.\nNach Volumen sortiert — die obersten Zeilen "
            "bringen den meisten Nutzen.")).pack(anchor="w")

        mitte = ttk.Frame(self, padding=(14, 0, 14, 0))
        mitte.pack(fill="both", expand=True)

        anzeige = [self.schluessel, "Anzeigename", "Volumen", "kumuliert", self.wert]
        self.tabelle = ttk.Treeview(mitte, columns=anzeige, show="headings",
                                    selectmode="extended")
        breiten = {self.schluessel: 300, "Anzeigename": 170, "Volumen": 80,
                   "kumuliert": 90, self.wert: 190}
        for name in anzeige:
            self.tabelle.heading(name, text=name)
            self.tabelle.column(name, width=breiten.get(name, 120),
                                anchor="w" if breiten.get(name, 120) > 100 else "e")
        leiste = ttk.Scrollbar(mitte, command=self.tabelle.yview)
        self.tabelle.configure(yscrollcommand=leiste.set)
        self.tabelle.pack(side="left", fill="both", expand=True)
        leiste.pack(side="right", fill="y")
        self.tabelle.tag_configure("offen", foreground="#8a6d1f")
        self.tabelle.bind("<Double-1>", lambda _e: self.feld.focus_set())

        unten = ttk.Frame(self, padding=(14, 10, 14, 6))
        unten.pack(fill="x")
        ttk.Label(unten, text=self.wert + ":").pack(side="left")
        self.feld = ttk.Combobox(unten, textvariable=self.eingabe, width=26,
                                 values=vorschlaege)
        self.feld.pack(side="left", padx=8)
        self.feld.bind("<Return>", lambda _e: self._zuweisen())
        ttk.Button(unten, text="Zuweisen", command=self._zuweisen).pack(side="left")
        ttk.Button(unten, text="Leeren", command=self._leeren).pack(side="left", padx=6)
        ttk.Checkbutton(unten, variable=self.nur_offene, command=self._fuellen,
                        text="nur ungepflegte anzeigen").pack(side="left", padx=16)

        fuss = ttk.Frame(self, padding=(14, 0, 14, 12))
        fuss.pack(fill="x")
        self.stand = ttk.Label(fuss, style="Leise.TLabel", text="")
        self.stand.pack(side="left")
        ttk.Button(fuss, text="Schließen", command=self.destroy).pack(side="right")
        ttk.Button(fuss, text="Speichern", command=self._speichern).pack(
            side="right", padx=6)
        ttk.Button(fuss, text="In Excel öffnen",
                   command=lambda: datei_oeffnen(self.datei)).pack(side="right")

    # ------------------------------------------------------------ Inhalt
    def _volumen(self, zeile: dict) -> int:
        for name in ("Nachrichten", "Vorgaenge", "Vorgänge"):
            try:
                return int(zeile.get(name) or 0)
            except (TypeError, ValueError):
                continue
        return 0

    def _fuellen(self) -> None:
        self.tabelle.delete(*self.tabelle.get_children())
        sortiert = sorted(self.zeilen, key=self._volumen, reverse=True)
        gesamt = sum(self._volumen(z) for z in sortiert) or 1
        summe = 0
        for index, zeile in enumerate(sortiert):
            summe += self._volumen(zeile)
            gepflegt = str(zeile.get(self.wert, "")).strip()
            if self.nur_offene.get() and gepflegt:
                continue
            self.tabelle.insert(
                "", "end", iid=str(self.zeilen.index(zeile)),
                values=(zeile.get(self.schluessel, ""),
                        zeile.get("Anzeigename", ""),
                        self._volumen(zeile) or "",
                        f"{summe / gesamt:.0%}",
                        gepflegt),
                tags=() if gepflegt else ("offen",))
        self._stand_zeigen()

    def _stand_zeigen(self) -> None:
        gepflegt = sum(1 for z in self.zeilen if str(z.get(self.wert, "")).strip())
        gesamt_volumen = sum(self._volumen(z) for z in self.zeilen) or 1
        abgedeckt = sum(self._volumen(z) for z in self.zeilen
                        if str(z.get(self.wert, "")).strip()) / gesamt_volumen
        self.stand.configure(text=(
            f"{gepflegt} von {len(self.zeilen)} Zeilen gepflegt — "
            f"das deckt {abgedeckt:.0%} des Volumens ab."))

    def _zuweisen(self) -> None:
        wert = self.eingabe.get().strip()
        if not wert:
            messagebox.showinfo(self.title(), "Bitte einen Wert eintragen.")
            return
        self._setzen(wert)

    def _leeren(self) -> None:
        self._setzen("")

    def _setzen(self, wert: str) -> None:
        markiert = self.tabelle.selection()
        if not markiert:
            messagebox.showinfo(self.title(), "Bitte zuerst Zeilen auswählen.")
            return
        for kennung in markiert:
            self.zeilen[int(kennung)][self.wert] = wert
        self._fuellen()

    def _speichern(self) -> None:
        try:
            ziel = mapping.schreiben(self.zeilen, self.spalten, self.datei,
                                     self.auswahlliste)
        except Exception as fehler:
            messagebox.showerror(self.title(), str(fehler))
            return
        messagebox.showinfo(self.title(), (
            f"Gespeichert: {ziel.name}\n\nDie Auswertung rechnet die Zuordnung "
            f"mit, sobald „Neu berechnen“ gedrückt wird — dafür ist kein "
            f"weiterer Outlook-Zugriff nötig."))


class Fenster(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(TITEL)
        self.geometry("960x720")
        self.minsize(820, 600)

        self.auftrag = auftrag_modul.Auftrag()
        self.ordner = tk.StringVar(value=ARBEITSORDNER)
        self.domain = tk.StringVar()
        self.konzern = tk.StringVar()
        self.monate = tk.IntVar(value=12)
        self.vollerhebung = tk.BooleanVar(value=False)
        self.signaturen = tk.BooleanVar(value=False)
        self.fremde = tk.BooleanVar(value=False)
        self.ueberschreiben = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Bereit.")
        self._letztes_ergebnis: dict | None = None

        self._aufbauen()
        self._konfiguration_laden()
        self.after(TAKT_MS, self._warteschlange_pruefen)

    # ------------------------------------------------------------ Aufbau
    def _aufbauen(self) -> None:
        stil = ttk.Style(self)
        if "vista" in stil.theme_names():
            stil.theme_use("vista")
        stil.configure("Kopf.TLabel", font=("Segoe UI", 15, "bold"))
        stil.configure("Leise.TLabel", foreground="#5f5f5f")

        kopf = ttk.Frame(self, padding=(16, 12, 16, 8))
        kopf.pack(fill="x")
        ttk.Label(kopf, text=TITEL, style="Kopf.TLabel").pack(anchor="w")
        ttk.Label(kopf, style="Leise.TLabel", text=(
            "Wie viel Kommunikationskapazität wird intern gebunden? — Es wird "
            "ausschließlich gelesen, am Postfach ändert sich nichts.")).pack(anchor="w")

        # Reihenfolge zaehlt: Fusszeile und Verlauf werden zuerst unten
        # verankert, sonst schiebt der wachsende Verlauf sie aus dem Fenster --
        # und mit ihnen den Knopf, der den Report oeffnet.
        fuss = ttk.Frame(self, padding=(16, 0, 16, 12))
        fuss.pack(side="bottom", fill="x")
        unten = ttk.Frame(self, padding=(16, 8, 16, 4))
        unten.pack(side="bottom", fill="x")

        self.reiter = ttk.Notebook(self)
        self.reiter.pack(fill="both", expand=True, padx=16, pady=(4, 0))
        self.reiter.add(self._reiter_analyse(), text="  Analyse  ")
        self.reiter.add(self._reiter_kontakte(), text="  Kontakte  ")
        self.reiter.add(self._reiter_weitergabe(), text="  Weitergabe und Team  ")
        ttk.Label(unten, text="Verlauf").pack(anchor="w")
        rahmen = ttk.Frame(unten)
        rahmen.pack(fill="both", expand=True)
        self.protokoll = tk.Text(rahmen, height=7, wrap="word", relief="solid",
                                 borderwidth=1, font=("Consolas", 9))
        leiste = ttk.Scrollbar(rahmen, command=self.protokoll.yview)
        self.protokoll.configure(yscrollcommand=leiste.set, state="disabled")
        self.protokoll.pack(side="left", fill="both", expand=True)
        leiste.pack(side="right", fill="y")

        self.balken = ttk.Progressbar(fuss, mode="indeterminate", length=180)
        self.balken.pack(side="left")
        ttk.Label(fuss, textvariable=self.status, style="Leise.TLabel").pack(
            side="left", padx=12)
        self.knopf_report = ttk.Button(fuss, text="Report öffnen", state="disabled",
                                       command=self._report_oeffnen)
        self.knopf_report.pack(side="right")
        ttk.Button(fuss, text="Ordner öffnen",
                   command=lambda: datei_oeffnen(self._ordner())).pack(
            side="right", padx=6)

    def _feldzeile(self, eltern, zeile, text, variable, breite=34, hinweis=""):
        ttk.Label(eltern, text=text).grid(row=zeile, column=0, sticky="w", pady=4)
        feld = ttk.Entry(eltern, textvariable=variable, width=breite)
        feld.grid(row=zeile, column=1, sticky="w", padx=8)
        if hinweis:
            ttk.Label(eltern, text=hinweis, style="Leise.TLabel").grid(
                row=zeile, column=2, sticky="w")
        return feld

    def _reiter_analyse(self) -> ttk.Frame:
        seite = ttk.Frame(self.reiter, padding=16)
        seite.columnconfigure(2, weight=1)

        self._feldzeile(seite, 0, "Interne Domain", self.domain,
                        hinweis="z. B. firma.de — mehrere mit Komma")
        self._feldzeile(seite, 1, "Konzerndomains", self.konzern,
                        hinweis="optional — Schwestergesellschaften")

        ttk.Label(seite, text="Zeitraum").grid(row=2, column=0, sticky="w", pady=4)
        zeile = ttk.Frame(seite)
        zeile.grid(row=2, column=1, sticky="w", padx=8)
        ttk.Spinbox(zeile, from_=1, to=120, width=6, textvariable=self.monate).pack(
            side="left")
        ttk.Label(zeile, text=" Monate").pack(side="left")
        ttk.Label(seite, text="deckt Saison- und Budgetzyklen ab",
                  style="Leise.TLabel").grid(row=2, column=2, sticky="w")

        ttk.Separator(seite).grid(row=4, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Checkbutton(
            seite, variable=self.vollerhebung,
            text="Vollerhebung — auch Betreff, Anhangnamen, Größe und BCC").grid(
            row=5, column=0, columnspan=3, sticky="w")
        ttk.Label(seite, style="Leise.TLabel", text=(
            "     dazu Antwortzeiten, Arbeitszeitmuster und Netzwerk. Für das eigene\n"
            "     Postfach gedacht; der Teamexport bleibt auch dann aggregiert.")).grid(
            row=6, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(
            seite, variable=self.fremde,
            text="Fremde Postfächer einbeziehen — nur mit ausdrücklicher Freigabe").grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Separator(seite).grid(row=8, column=0, columnspan=3, sticky="ew", pady=12)

        knoepfe = ttk.Frame(seite)
        knoepfe.grid(row=9, column=0, columnspan=3, sticky="w")
        self.knopf_analyse = ttk.Button(knoepfe, text="Analyse starten",
                                        command=self._analyse_starten)
        self.knopf_analyse.pack(side="left")
        ttk.Button(knoepfe, text="Neu berechnen (ohne Outlook)",
                   command=self._neu_starten).pack(side="left", padx=8)
        ttk.Button(knoepfe, text="Beispiel ansehen",
                   command=self._demo_starten).pack(side="left")

        ttk.Label(seite, style="Leise.TLabel", text=(
            "„Neu berechnen“ rechnet auf der bereits erzeugten Zwischendatei — "
            "sinnvoll, nachdem die\nFachbereiche gepflegt wurden.")).grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.zusammenfassung = ttk.Label(seite, style="Leise.TLabel", text="")
        self.zusammenfassung.grid(row=11, column=0, columnspan=3, sticky="w", pady=(14, 0))

        zeile3 = ttk.Frame(seite)
        zeile3.grid(row=12, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Button(zeile3, text="Interne Kontakte und Fachbereiche …",
                   command=self._fachbereiche_pflegen).pack(side="left")
        ttk.Button(zeile3, text="Externe Domains und Kategorien …",
                   command=self._kategorien_pflegen).pack(side="left", padx=8)
        return seite

    def _reiter_kontakte(self) -> ttk.Frame:
        seite = ttk.Frame(self.reiter, padding=16)
        ttk.Label(seite, text=(
            "Alle externen Mailadressen als Excel — mit Unternehmen, Volumen, "
            "Richtung und letztem Kontakt.\nAusgelassen werden nur Junk und "
            "Papierkorb.")).pack(anchor="w")
        ttk.Separator(seite).pack(fill="x", pady=12)
        ttk.Checkbutton(
            seite, variable=self.signaturen,
            text="Funktion, Telefon und Unternehmen aus Signaturen lesen").pack(
            anchor="w")
        ttk.Label(seite, style="Leise.TLabel", text=(
            "     Dies ist die einzige Stelle, die Mailtexte liest — nur das Ende, "
            "und gespeichert wird\n     davon nur das Gefundene. Ohne den Haken "
            "kommt der Firmenname aus dem Domainnamen.")).pack(anchor="w")
        ttk.Button(seite, text="Kontakte exportieren",
                   command=self._kontakte_starten).pack(anchor="w", pady=16)
        self.kontakt_ergebnis = ttk.Label(seite, style="Leise.TLabel", text="")
        self.kontakt_ergebnis.pack(anchor="w")
        return seite

    def _reiter_weitergabe(self) -> ttk.Frame:
        seite = ttk.Frame(self.reiter, padding=16)

        ttk.Label(seite, text="Einstellungen weitergeben",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(seite, style="Leise.TLabel", text=(
            "Gibt interne Domains, Fachbereiche und Domainkategorien weiter — "
            "nicht die Volumenzahlen,\ndenn die gehören zum eigenen Postfach.")).pack(
            anchor="w")
        zeile = ttk.Frame(seite)
        zeile.pack(anchor="w", pady=8)
        ttk.Button(zeile, text="Exportieren …",
                   command=self._einstellungen_export).pack(side="left")
        ttk.Button(zeile, text="Übernehmen …",
                   command=self._einstellungen_import).pack(side="left", padx=8)
        ttk.Checkbutton(zeile, variable=self.ueberschreiben,
                        text="bei Widerspruch die Datei gewinnen lassen").pack(
            side="left", padx=8)

        ttk.Separator(seite).pack(fill="x", pady=16)

        ttk.Label(seite, text="Teamauswertung",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(seite, style="Leise.TLabel", text=(
            "Führt die anonymen Kennzahlendateien mehrerer Teilnehmer zusammen. "
            "Unter fünf Dateien\nwird bewusst kein Ergebnis ausgegeben — sonst "
            "ließe sich auf Einzelne schließen.")).pack(anchor="w")
        zeile2 = ttk.Frame(seite)
        zeile2.pack(anchor="w", pady=8)
        ttk.Button(zeile2, text="Eigene Kennzahlen ablegen …",
                   command=self._teamexport_ablegen).pack(side="left")
        ttk.Button(zeile2, text="Dateien zusammenführen …",
                   command=self._team_merge).pack(side="left", padx=8)
        self.team_ergebnis = ttk.Label(seite, style="Leise.TLabel", text="")
        self.team_ergebnis.pack(anchor="w", pady=(8, 0))

        ttk.Separator(seite).pack(fill="x", pady=16)
        ttk.Label(seite, text="Arbeitsordner").pack(anchor="w")
        zeile3 = ttk.Frame(seite)
        zeile3.pack(anchor="w", pady=4)
        ttk.Entry(zeile3, textvariable=self.ordner, width=52).pack(side="left")
        ttk.Button(zeile3, text="Wählen …", command=self._ordner_waehlen).pack(
            side="left", padx=8)
        return seite

    # ------------------------------------------------------------ Hilfen
    def _ordner(self) -> Path:
        pfad = Path(self.ordner.get() or ARBEITSORDNER)
        pfad.mkdir(parents=True, exist_ok=True)
        return pfad

    def _konfiguration_laden(self) -> None:
        config = Config.laden(self._ordner() / "config.json")
        if config.interne_domains:
            self.domain.set(", ".join(config.interne_domains))
        if config.konzern_domains:
            self.konzern.set(", ".join(config.konzern_domains))
        self.monate.set(config.zeitraum_monate)
        self.vollerhebung.set(config.vollerhebung)
        self.fremde.set(config.fremde_postfaecher_einbeziehen)

    def _config_bauen(self) -> Config | None:
        config = Config.laden(self._ordner() / "config.json")
        config.interne_domains = [d.strip() for d in self.domain.get().split(",")
                                  if d.strip()]
        config.konzern_domains = [d.strip() for d in self.konzern.get().split(",")
                                  if d.strip()]
        config.zeitraum_monate = max(1, int(self.monate.get() or 12))
        config.vollerhebung = self.vollerhebung.get()
        config.fremde_postfaecher_einbeziehen = self.fremde.get()
        fehler = config.pruefen()
        if fehler:
            messagebox.showwarning(TITEL, "\n\n".join(fehler))
            return None
        return config

    def _schreiben(self, text: str) -> None:
        self.protokoll.configure(state="normal")
        self.protokoll.insert("end", text + "\n")
        self.protokoll.see("end")
        self.protokoll.configure(state="disabled")

    def _beschaeftigt(self, an: bool, was: str = "") -> None:
        self.status.set(was or ("Bereit." if not an else "Läuft ..."))
        if an:
            self.balken.start(12)
        else:
            self.balken.stop()
        for knopf in (self.knopf_analyse,):
            knopf.configure(state="disabled" if an else "normal")

    def _starten(self, arbeit, *args, beschreibung: str = "Läuft ...", **kwargs) -> None:
        if self.auftrag.laeuft:
            messagebox.showinfo(TITEL, "Es läuft bereits eine Auswertung.")
            return
        self._schreiben("")
        self._beschaeftigt(True, beschreibung)
        self.auftrag.starten(arbeit, *args, **kwargs)

    def _warteschlange_pruefen(self) -> None:
        for art, inhalt in self.auftrag.abholen():
            if art == auftrag_modul.MELDUNG:
                self._schreiben(str(inhalt))
            elif art == auftrag_modul.FEHLER:
                meldung, spur = inhalt
                self._schreiben("Fehler: " + meldung)
                self._beschaeftigt(False, "Abgebrochen.")
                messagebox.showerror(TITEL, meldung)
                print(spur, file=sys.stderr)
            else:
                self._beschaeftigt(False, "Fertig.")
                self._ergebnis_zeigen(inhalt)
        self.after(TAKT_MS, self._warteschlange_pruefen)

    def _ergebnis_zeigen(self, ergebnis) -> None:
        if not isinstance(ergebnis, dict):
            return
        if "kpi" in ergebnis:
            self._letztes_ergebnis = ergebnis
            kern = ergebnis["kpi"]["kern"]
            k1, k2 = kern["k1_vorgangsanteile"], kern["k2_nachrichtenanteile"]
            self.zusammenfassung.configure(text=(
                f"{ergebnis['n_nachrichten']} Nachrichten in "
                f"{ergebnis['n_vorgaenge']} Vorgängen\n"
                f"intern: {k1['intern']:.0%} der Vorgänge, aber "
                f"{k2['intern']:.0%} der Nachrichten — die Differenz ist der Befund."))
            self.knopf_report.configure(state="normal")
            self._schreiben(f"Report: {ergebnis['report']}")
            if not ergebnis["stabilitaet"]["stabil"]:
                self._schreiben("Hinweis: Die beiden Verfahren zur Vorgangsbildung "
                                "weichen deutlich ab — die Vorgangsebene ist zu "
                                "relativieren.")
        elif "zusammenfassung" in ergebnis:
            z = ergebnis["zusammenfassung"]
            text = (f"{z['kontakte']} Kontakte bei {z['domains']} Unternehmen, "
                    f"{z['aktiv']} davon aktiv.")
            if self.signaturen.get():
                text += (f"\nAus Signatur belegt: {z['aus_signatur']} Firmen, "
                         f"{z['mit_funktion']} Funktionen, {z['mit_telefon']} Rufnummern.")
            self.kontakt_ergebnis.configure(text=text)
            self._schreiben(f"Datei: {ergebnis['datei']}")
            datei_oeffnen(ergebnis["datei"])
        elif "ergebnis" in ergebnis:
            n = ergebnis["ergebnis"]["n_teilnehmer"]
            self.team_ergebnis.configure(
                text=f"Zusammengeführt über {n} Teilnehmer: {ergebnis['datei']}")

    # ------------------------------------------------------------ Aktionen
    def _analyse_starten(self) -> None:
        config = self._config_bauen()
        if config:
            self._starten(auftrag_modul.analyse, config, self._ordner(),
                          None, beschreibung="Lese Outlook ...")

    def _neu_starten(self) -> None:
        config = self._config_bauen()
        if config:
            self._starten(auftrag_modul.neu_berechnen, config, self._ordner(),
                          None, beschreibung="Rechne neu ...")

    def _demo_starten(self) -> None:
        config = Config.laden(self._ordner() / "config.json")
        config.interne_domains = ["firma.de"]
        config.vollerhebung = self.vollerhebung.get()
        self.domain.set("firma.de")
        self._starten(auftrag_modul.demo, config, self._ordner(), None,
                      beschreibung="Erzeuge Beispiel ...")

    def _kontakte_starten(self) -> None:
        config = self._config_bauen()
        if config:
            self._starten(auftrag_modul.kontakte_exportieren, config, self._ordner(),
                          self.signaturen.get(),
                          beschreibung="Sammle Kontakte ...")

    def _report_oeffnen(self) -> None:
        if self._letztes_ergebnis:
            datei_oeffnen(self._letztes_ergebnis["report"])
        else:
            bericht = self._ordner() / pipeline.DATEI_REPORT
            if bericht.exists():
                datei_oeffnen(bericht)

    def _mapping_datei(self, name: str) -> Path | None:
        for endung in (".xlsx", ".csv"):
            pfad = self._ordner() / (name + endung)
            if pfad.exists():
                return pfad
        messagebox.showinfo(TITEL, (
            "Die Zuordnungsdatei entsteht beim ersten Lauf — sie wird aus den "
            "tatsächlich vorkommenden Kontakten gefüllt.\n\nBitte zuerst eine "
            "Analyse ausführen (oder „Beispiel ansehen“ zum Ausprobieren)."))
        return None

    def _bekannte_werte(self, datei: Path, spalte: str) -> list[str]:
        """Bereits vergebene Werte als Vorschlag -- vermeidet Tippvarianten."""
        vorhanden = {str(z.get(spalte, "")).strip()
                     for z in mapping.lesen(datei) if str(z.get(spalte, "")).strip()}
        return sorted(vorhanden)

    def _fachbereiche_pflegen(self) -> None:
        datei = self._mapping_datei("mapping_personen")
        if not datei:
            return
        ZuordnungsFenster(
            self, datei, "E-Mail", "Fachbereich", mapping.SPALTEN_PERSONEN,
            "Interne Kontakte und Fachbereiche",
            self._bekannte_werte(datei, "Fachbereich") or
            ["Einkauf", "Engineering", "Qualität", "Produktion", "Logistik",
             "Finance", "Vertrieb", "IT", "Funktionspostfach"])

    def _kategorien_pflegen(self) -> None:
        datei = self._mapping_datei("mapping_domains")
        if not datei:
            return
        ZuordnungsFenster(
            self, datei, "Domain", "Kategorie", mapping.SPALTEN_DOMAINS,
            "Externe Domains und Kategorien", mapping.KATEGORIE_VORSCHLAEGE,
            auswahlliste=("Kategorie", mapping.KATEGORIE_VORSCHLAEGE))

    def _ordner_waehlen(self) -> None:
        gewaehlt = filedialog.askdirectory(title="Arbeitsordner wählen")
        if gewaehlt:
            self.ordner.set(gewaehlt)
            self._konfiguration_laden()

    def _einstellungen_export(self) -> None:
        ziel = filedialog.asksaveasfilename(
            title="Einstellungen speichern", defaultextension=".json",
            initialfile="Einstellungen.json",
            filetypes=[("Einstellungsdatei", "*.json")])
        if not ziel:
            return
        try:
            datei, info = __import__("okoa.einstellungen", fromlist=["x"]).exportieren(
                self._ordner(), ziel)
        except Exception as fehler:
            messagebox.showerror(TITEL, str(fehler))
            return
        self._schreiben(f"Geschrieben: {datei}")
        messagebox.showinfo(TITEL, (
            f"{info['fachbereiche']} Fachbereichs- und {info['domainkategorien']} "
            f"Domainzuordnungen geschrieben.\n\nDie Volumenzahlen bleiben bewusst "
            f"draußen — sie gehören zum eigenen Postfach."))

    def _einstellungen_import(self) -> None:
        datei = filedialog.askopenfilename(title="Einstellungsdatei wählen",
                                           filetypes=[("Einstellungsdatei", "*.json")])
        if not datei:
            return
        try:
            bericht = __import__("okoa.einstellungen", fromlist=["x"]).importieren(
                datei, self._ordner(), ueberschreiben=self.ueberschreiben.get())
        except Exception as fehler:
            messagebox.showerror(TITEL, str(fehler))
            return
        self._konfiguration_laden()
        teile = []
        for name, titel in (("fachbereiche", "Fachbereiche"),
                            ("domainkategorien", "Domainkategorien")):
            z = bericht[name]
            teile.append(f"{titel}: {z['neu']} neu, {z['ergaenzt']} ergänzt, "
                         f"{z['behalten']} eigene behalten")
        self._schreiben(" | ".join(teile))
        messagebox.showinfo(TITEL, "\n".join(teile))

    def _teamexport_ablegen(self) -> None:
        if not self._letztes_ergebnis:
            messagebox.showinfo(TITEL, "Bitte zuerst eine Auswertung ausführen.")
            return
        export = self._letztes_ergebnis["export"]
        vorschau = tk.Toplevel(self)
        vorschau.title("Das — und nur das — würde geteilt")
        vorschau.geometry("640x520")
        text = tk.Text(vorschau, wrap="none", font=("Consolas", 9))
        text.insert("1.0", team_export.als_klartext(export))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=12, pady=12)

        def ablegen():
            ziel = filedialog.askdirectory(title="Wohin ablegen?")
            if not ziel:
                return
            pfad = team_export.schreiben(export, ziel)
            self._schreiben(f"Abgelegt: {pfad}")
            vorschau.destroy()
            messagebox.showinfo(TITEL, f"Abgelegt unter:\n{pfad}")

        zeile = ttk.Frame(vorschau, padding=(12, 0, 12, 12))
        zeile.pack(fill="x")
        ttk.Button(zeile, text="Anonym ablegen", command=ablegen).pack(side="left")
        ttk.Button(zeile, text="Nicht teilen",
                   command=vorschau.destroy).pack(side="left", padx=8)

    def _team_merge(self) -> None:
        eingang = filedialog.askdirectory(title="Ordner mit den erhaltenen Dateien")
        if eingang:
            self._starten(auftrag_modul.team_zusammenfuehren, Path(eingang),
                          beschreibung="Führe zusammen ...")


def starten() -> int:
    try:
        fenster = Fenster()
    except tk.TclError as fehler:
        print(f"Die Oberfläche liess sich nicht starten: {fehler}", file=sys.stderr)
        print("Auf der Kommandozeile: python -m okoa analyse --domain firma.de",
              file=sys.stderr)
        return 1
    fenster.mainloop()
    return 0
