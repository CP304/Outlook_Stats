"""Kommandozeile.

Drei Befehle:
    analyse   Postfach auslesen und auswerten            (braucht Outlook)
    neu       Auswertung aus der Zwischendatei wiederholen (ohne Outlook)
    merge     Teamexporte zusammenfuehren                 (ohne Rohdatenzugang)
    demo      Beispielreport aus synthetischen Daten      (zum Ausprobieren)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import kontakte as kontakte_modul
from . import mapping, pipeline, team_export
from .config import Config


ARBEITSORDNER = Path("Auswertung")
DATEI_CONFIG = "config.json"


def _konfiguration(args, ordner: Path) -> Config:
    config = Config.laden(ordner / DATEI_CONFIG)
    if args.domain:
        config.interne_domains = [d.strip() for d in args.domain.split(",") if d.strip()]
    if args.konzern:
        config.konzern_domains = [d.strip() for d in args.konzern.split(",") if d.strip()]
    if args.monate:
        config.zeitraum_monate = args.monate
    if getattr(args, "fremde_postfaecher", False):
        config.fremde_postfaecher_einbeziehen = True
    return config


def _abschluss(ergebnis: dict, ordner: Path, teilen_anbieten: bool) -> None:
    kern = ergebnis["kpi"]["kern"]
    k1, k2 = kern["k1_vorgangsanteile"], kern["k2_nachrichtenanteile"]
    print()
    print("  Auswertung fertig.")
    print(f"    {ergebnis['n_nachrichten']} Nachrichten, {ergebnis['n_vorgaenge']} Vorgänge")
    print(f"    intern:  {k1['intern']:.0%} der Vorgänge, {k2['intern']:.0%} der Nachrichten")
    print(f"    extern:  {k1['extern']:.0%} der Vorgänge, {k2['extern']:.0%} der Nachrichten")
    if not ergebnis["stabilitaet"]["stabil"]:
        print("    Hinweis: Die beiden Verfahren zur Vorgangsbildung weichen deutlich")
        print("             voneinander ab -- die Vorgangsebene ist zu relativieren.")
    print()
    print(f"    Report:  {ergebnis['report']}")
    print(f"    Zuordnung Fachbereiche: {ergebnis['mapping_personen']}")
    if ergebnis["neue_personen"]:
        print(f"      ({ergebnis['neue_personen']} neue Personen ergänzt)")
    print(f"    Zuordnung Domains:      {ergebnis['mapping_domains']}")
    print()
    if not teilen_anbieten:
        return

    print(team_export.als_klartext(ergebnis["export"]))
    print()
    antwort = input("  Diese Kennzahlen als Datei zum Teilen ablegen? [j/N] ").strip().lower()
    if antwort in ("j", "ja", "y", "yes"):
        pfad = team_export.schreiben(ergebnis["export"], ordner)
        print(f"  Abgelegt unter: {pfad}")
        print("  Der persönliche Report bleibt bei Ihnen und wird nicht geteilt.")
    else:
        print("  Nichts geteilt. Der persönliche Report bleibt bei Ihnen.")


def befehl_analyse(args) -> int:
    from .extract_outlook import OutlookNichtVerfuegbar, auslesen

    ordner = Path(args.ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    config = _konfiguration(args, ordner)
    fehler = config.pruefen()
    if fehler:
        for f in fehler:
            print(f"  {f}")
        print("\n  Beispiel:  python -m okoa analyse --domain firma.de")
        return 2

    print(f"  Lese Outlook (Zeitraum: letzte {config.zeitraum_monate} Monate) ...")
    print("  Es wird ausschließlich gelesen; am Postfach wird nichts verändert.")
    try:
        nachrichten, berichte = auslesen(config, fortschritt=lambda t: print(f"    {t}"))
    except OutlookNichtVerfuegbar as fehler:
        print(f"\n  {fehler}")
        print("\n  Zum Ausprobieren ohne Outlook:  python -m okoa demo")
        return 3

    config.speichern(ordner / DATEI_CONFIG)
    ergebnis = pipeline.auswerten(
        nachrichten, config, ordner,
        kontext={"stores": berichte["stores"],
                 "ausgeschlossene_ordner": config.ordner_ausschluss},
        hypothese=args.hypothese,
    )
    _abschluss(ergebnis, ordner, teilen_anbieten=not args.ohne_teilen)
    return 0


def befehl_neu(args) -> int:
    ordner = Path(args.ordner)
    config = _konfiguration(args, ordner)
    if not (ordner / pipeline.DATEI_CACHE).exists():
        print(f"  Keine Zwischendatei in {ordner}. Bitte zuerst 'analyse' ausführen.")
        return 2
    ergebnis = pipeline.aus_cache(ordner, config, hypothese=args.hypothese)
    _abschluss(ergebnis, ordner, teilen_anbieten=not args.ohne_teilen)
    return 0


def befehl_demo(args) -> int:
    from .synthetic import belege_erzeugen, postfach_erzeugen

    ordner = Path(args.ordner)
    config = Config(interne_domains=["firma.de"])
    print("  Erzeuge Beispieldaten (kein Outlook, keine echten Mails) ...")
    nachrichten = postfach_erzeugen(args.vorgaenge)
    ergebnis = pipeline.auswerten(
        nachrichten, config, ordner,
        kontext={"stores": ["Beispielpostfach"]},
        bezugszeitpunkt=datetime(2026, 6, 30),
    )
    _abschluss(ergebnis, ordner, teilen_anbieten=False)

    from . import threads

    vorgaenge = threads.vorgaenge_bilden(nachrichten)
    zeilen = kontakte_modul.als_zeilen(
        kontakte_modul.sammeln(vorgaenge, belege_erzeugen(nachrichten)),
        stichtag=datetime(2026, 6, 30))
    ziel = kontakte_modul.schreiben(zeilen, ordner / "Externe_Kontakte.xlsx")
    print(f"    Externe Kontakte: {ziel} ({len(zeilen)} Einträge)")
    return 0


def befehl_kontakte(args) -> int:
    """Externe Kontakte als Excel.

    Das Ergebnis ist eine personenbezogene Liste und keine Kennzahl -- es faellt
    damit unter eine andere Bewertung als die aggregierte Auswertung.
    Siehe docs/10-kontaktliste.md.
    """
    from .extract_outlook import OutlookNichtVerfuegbar, auslesen

    ordner = Path(args.ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    config = _konfiguration(args, ordner)
    fehler = config.pruefen()
    if fehler:
        for f in fehler:
            print(f"  {f}")
        return 2

    # Fuer die Adressernte zaehlt Vollstaendigkeit: hier werden nur Junk und
    # Papierkorb ausgelassen, nicht die weiteren Ordner der Kennzahlenanalyse.
    config.ordner_ausschluss = [n for n in config.ordner_ausschluss
                                if any(wort in n.lower() for wort in
                                       ("junk", "spam", "gelöscht", "geloescht",
                                        "deleted"))]
    print(f"  Lese Outlook (Zeitraum: letzte {config.zeitraum_monate} Monate) ...")
    print(f"  Ausgelassen werden nur: {', '.join(config.ordner_ausschluss)}")
    if args.signaturen:
        print("  Signaturauswertung ist eingeschaltet: Vom Mailtext wird das Ende")
        print("  gelesen, um Firmennamen zu finden. Gespeichert wird davon nur der")
        print("  gefundene Name -- kein Text, keine Betreffzeile.")
    else:
        print("  Ohne Signaturauswertung: Der Firmenname wird aus der Domain")
        print("  abgeleitet. Mit --signaturen wird er aus Signaturen belegt.")
    try:
        nachrichten, berichte = auslesen(
            config, fortschritt=lambda t: print(f"    {t}"),
            kontakte_sammeln=True, mit_signaturen=args.signaturen)
    except OutlookNichtVerfuegbar as fehler:
        print(f"\n  {fehler}")
        return 3

    from .normalize import deduplizieren
    from . import threads

    entdoppelt, _ = deduplizieren(nachrichten)
    threads.zuordnen(entdoppelt, luecke_tage=config.schwellen.thread_luecke_tage)
    vorgaenge = threads.vorgaenge_bilden(entdoppelt)
    liste = kontakte_modul.sammeln(vorgaenge, berichte.get("kontaktbelege"))
    kategorien = mapping.zuordnung_lesen(ordner / pipeline.DATEI_DOMAINS,
                                        "Domain", "Kategorie")
    zeilen = kontakte_modul.als_zeilen(liste, kategorien)
    ziel = kontakte_modul.schreiben(zeilen, ordner / "Externe_Kontakte.xlsx")

    zusammen = kontakte_modul.zusammenfassung(zeilen)
    print()
    print(f"  {zusammen['kontakte']} externe Kontakte bei {zusammen['domains']} Unternehmen")
    print(f"  davon {zusammen['aktiv']} in den letzten "
          f"{kontakte_modul.INAKTIV_AB_TAGEN} Tagen aktiv")
    if args.signaturen:
        print(f"  Firmenname aus Signatur belegt: {zusammen['aus_signatur']} Kontakte "
              f"({zusammen['anteil_aus_signatur']:.0%})")
        print("  Beim Rest steht der Domainname -- die Spalte 'Herkunft Unternehmen'")
        print("  weist das aus, damit niemand eine Lesehilfe fuer eine Firmierung haelt.")
        print(f"  Funktion gefunden:  {zusammen['mit_funktion']} Kontakte")
        print(f"  Rufnummer gefunden: {zusammen['mit_telefon']} Kontakte")
        print("  Leere Felder sind der Normalfall: Signaturen stehen meist nur in")
        print("  der ersten Mail eines Vorgangs, nicht in jeder Antwort.")
    print(f"\n  Datei: {ziel}")
    return 0


def befehl_merge(args) -> int:
    """Liest ausschließlich Teamexporte -- kein Zugang zu Postfächern oder Rohdaten."""
    ordner = Path(args.ordner)
    exporte = team_export.einlesen(ordner)
    print(f"  {len(exporte)} Datei(en) gefunden in {ordner}")
    try:
        ergebnis = team_export.zusammenfuehren(exporte)
    except team_export.ZuWenigTeilnehmer as fehler:
        print(f"\n  {fehler}")
        return 2

    kennzahlen = ergebnis["kennzahlen"]
    print(f"\n  Zusammenführung über {ergebnis['n_teilnehmer']} Teilnehmer")
    print(f"  Zeitraum: {ergebnis['zeitraum'][0]} bis {ergebnis['zeitraum'][1]}\n")
    for feld in ("vorgaenge_intern", "vorgaenge_extern", "nachrichten_intern",
                 "nachrichten_extern", "aussenorientierung", "cc_quote_intern",
                 "nachrichten_je_vorgang_median_intern",
                 "nachrichten_je_vorgang_median_extern"):
        wert = kennzahlen.get(feld)
        if isinstance(wert, dict):
            print(f"    {feld:44s} Median {wert['median']}  (Q1 {wert['q1']} / Q3 {wert['q3']})")
        else:
            print(f"    {feld:44s} {wert}")
    ziel = ordner / "Team_Report.json"
    import json
    ziel.write_text(json.dumps(ergebnis, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Gruppenkennzahlen: {ziel}")
    print("  Einzelbeiträge, Minima und Maxima werden bewusst nicht ausgewiesen.")
    return 0


def parser_bauen() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="okoa",
        description="Outlook-Kommunikationsanalyse -- ausschließlich Metadaten, nur lesend.",
    )
    unterbefehle = parser.add_subparsers(dest="befehl", required=True)

    def gemeinsam(p, mit_domain=True):
        p.add_argument("--ordner", default=str(ARBEITSORDNER),
                       help="Arbeitsordner für Ergebnisse (Vorgabe: Auswertung)")
        if mit_domain:
            p.add_argument("--domain", help="interne Maildomain, z. B. firma.de "
                                            "(mehrere durch Komma getrennt)")
            p.add_argument("--konzern", help="verbundene Domains -- formal extern, "
                                             "faktisch interne Abstimmung")
            p.add_argument("--monate", type=int, help="Zeitraum in Monaten (Vorgabe: 12)")
            p.add_argument("--hypothese", type=float, default=0.80,
                           help="vermuteter interner Anteil für den Vergleich (Vorgabe: 0.80)")
            p.add_argument("--ohne-teilen", action="store_true",
                           help="am Ende nicht nach dem Teamexport fragen")

    p_analyse = unterbefehle.add_parser("analyse", help="Postfach auslesen und auswerten")
    gemeinsam(p_analyse)
    p_analyse.add_argument("--fremde-postfaecher", action="store_true",
                           help="fremde Postfächer einbeziehen -- nur mit ausdrücklicher "
                                "Freigabe, siehe docs/08-datenschutz.md")
    p_analyse.set_defaults(funktion=befehl_analyse)

    p_neu = unterbefehle.add_parser("neu", help="Auswertung ohne Outlook wiederholen")
    gemeinsam(p_neu)
    p_neu.set_defaults(funktion=befehl_neu)

    p_demo = unterbefehle.add_parser("demo", help="Beispielreport aus synthetischen Daten")
    gemeinsam(p_demo, mit_domain=False)
    p_demo.add_argument("--vorgaenge", type=int, default=300)
    p_demo.set_defaults(funktion=befehl_demo, hypothese=0.80, ohne_teilen=True,
                        domain=None, konzern=None, monate=None)

    p_kontakte = unterbefehle.add_parser(
        "kontakte", help="externe Kontakte als Excel ausgeben")
    gemeinsam(p_kontakte)
    p_kontakte.add_argument(
        "--signaturen", action="store_true",
        help="Firmennamen aus Signaturen lesen. Liest dafür das Ende der "
             "Mailtexte -- bewusst nicht die Vorgabe, siehe docs/10-kontaktliste.md")
    p_kontakte.set_defaults(funktion=befehl_kontakte)

    p_merge = unterbefehle.add_parser("merge", help="Teamexporte zusammenführen")
    p_merge.add_argument("--ordner", default=".", help="Ordner mit den team_export-Dateien")
    p_merge.set_defaults(funktion=befehl_merge)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = parser_bauen().parse_args(argv)
    return args.funktion(args)


if __name__ == "__main__":
    sys.exit(main())
