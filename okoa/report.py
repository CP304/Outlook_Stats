"""HTML-Report.

Eine einzelne, selbsttragende Datei: keine externen Assets, keine
Internetverbindung, per Mail weitergebbar, als PDF druckbar.  Diagramme sind
handgeschriebenes SVG -- das spart eine schwere Abhaengigkeit und haelt die
Datei klein.

Gestaltungsregeln aus docs/05-reporting.md, die hier durchgehalten werden:
keine Ampelfarben und keine Zielwerte (es gibt keinen Benchmark fuer die
'richtige' interne Quote), keine Personennamen, Median vor Mittelwert, und
jede Zahl mit Bezugsgroesse.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from .model import VORGANG_EXTERN, VORGANG_GEMISCHT, VORGANG_INTERN


FARBEN = {
    VORGANG_INTERN: "#4a6fa5",
    VORGANG_GEMISCHT: "#7a9cc6",
    VORGANG_EXTERN: "#c08a3e",
}
BESCHRIFTUNG = {
    VORGANG_INTERN: "intern",
    VORGANG_GEMISCHT: "gemischt",
    VORGANG_EXTERN: "extern",
}
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

CSS = """
:root{--fg:#1c1c1c;--gedaempft:#5f5f5f;--linie:#d8d8d8;--flaeche:#f6f6f4;--akzent:#4a6fa5}
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
     color:var(--fg);background:#fff}
main{max-width:1040px;margin:0 auto;padding:32px 24px 80px}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:20px;margin:44px 0 12px;padding-top:20px;border-top:1px solid var(--linie)}
h3{font-size:16px;margin:24px 0 8px}
p,li{max-width:74ch}
.leise{color:var(--gedaempft);font-size:14px}
.kopf{padding-bottom:18px;border-bottom:2px solid var(--fg)}
.hypothese{background:var(--flaeche);border-left:4px solid var(--akzent);
           padding:18px 22px;margin:24px 0;border-radius:0 4px 4px 0}
.hypothese table{margin:10px 0 0}
.kacheln{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:20px 0}
.kachel{border:1px solid var(--linie);border-radius:5px;padding:14px 16px;background:#fff}
.kachel .wert{font-size:27px;font-weight:600;letter-spacing:-.5px}
.kachel .titel{font-size:13px;color:var(--gedaempft);text-transform:uppercase;
               letter-spacing:.5px;margin-bottom:6px}
.kachel .bezug{font-size:13px;color:var(--gedaempft);margin-top:4px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0}
th,td{text-align:right;padding:7px 10px;border-bottom:1px solid var(--linie)}
th:first-child,td:first-child{text-align:left}
thead th{border-bottom:2px solid var(--fg);font-size:13px;text-transform:uppercase;
         letter-spacing:.4px;color:var(--gedaempft)}
tbody tr:hover{background:var(--flaeche)}
.hinweis{border:1px solid var(--linie);background:var(--flaeche);padding:14px 18px;
         border-radius:4px;margin:18px 0;font-size:14px}
.explorativ{border-left:3px solid #b9b9b9;padding-left:14px;color:var(--gedaempft)}
.explorativ h2,.explorativ h3{color:var(--fg)}
.marke{display:inline-block;font-size:11px;letter-spacing:.6px;text-transform:uppercase;
       border:1px solid var(--gedaempft);color:var(--gedaempft);border-radius:3px;
       padding:1px 6px;vertical-align:middle;margin-left:8px}
figure{margin:16px 0}
figcaption{font-size:13px;color:var(--gedaempft);margin-top:6px}
.legende{font-size:13px;color:var(--gedaempft);margin:8px 0 0}
.legende span{margin-right:16px}
.legende i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--linie);
       font-size:13px;color:var(--gedaempft)}
@media print{body{font-size:12px}h2{page-break-after:avoid}figure,table{page-break-inside:avoid}}
"""


def _p(wert: float, stellen: int = 0) -> str:
    return f"{wert * 100:.{stellen}f} %".replace(".", ",")


def _z(wert: float, stellen: int = 1) -> str:
    return f"{wert:.{stellen}f}".replace(".", ",")


def _e(text) -> str:
    return html.escape(str(text))


# ------------------------------------------------------------- Diagramme

def _balken_gestapelt(anteile: dict[str, float], breite: int = 640, hoehe: int = 34) -> str:
    teile, x = [], 0.0
    for klasse in (VORGANG_INTERN, VORGANG_GEMISCHT, VORGANG_EXTERN):
        anteil = anteile.get(klasse, 0.0)
        w = anteil * breite
        if w > 0:
            teile.append(
                f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="{hoehe}" '
                f'fill="{FARBEN[klasse]}"><title>{BESCHRIFTUNG[klasse]}: '
                f'{_p(anteil, 1)}</title></rect>'
            )
            if w > 54:
                teile.append(
                    f'<text x="{x + w / 2:.1f}" y="{hoehe / 2 + 5:.0f}" fill="#fff" '
                    f'font-size="13" text-anchor="middle">{_p(anteil)}</text>'
                )
        x += w
    return (f'<svg viewBox="0 0 {breite} {hoehe}" width="100%" height="{hoehe}" '
            f'role="img">{"".join(teile)}</svg>')


def _legende() -> str:
    teile = [f'<span><i style="background:{FARBEN[k]}"></i>{BESCHRIFTUNG[k]}</span>'
             for k in (VORGANG_INTERN, VORGANG_GEMISCHT, VORGANG_EXTERN)]
    return f'<p class="legende">{"".join(teile)}</p>'


def _saeulen_monat(monate: dict[str, dict], breite: int = 900, hoehe: int = 240) -> str:
    if not monate:
        return '<p class="leise">Keine Daten im Zeitraum.</p>'
    schluessel = list(monate)
    maximum = max((sum(w.values()) for w in monate.values()), default=1) or 1
    rand_unten, rand_links = 30, 34
    zeichenhoehe = hoehe - rand_unten - 10
    spalte = (breite - rand_links) / len(schluessel)
    teile = [f'<line x1="{rand_links}" y1="{hoehe - rand_unten}" x2="{breite}" '
             f'y2="{hoehe - rand_unten}" stroke="#999"/>']
    for i, monat in enumerate(schluessel):
        x = rand_links + i * spalte + spalte * 0.15
        w = spalte * 0.7
        y = hoehe - rand_unten
        for klasse in (VORGANG_INTERN, VORGANG_GEMISCHT, VORGANG_EXTERN):
            wert = monate[monat].get(klasse, 0)
            h = wert / maximum * zeichenhoehe
            y -= h
            if h > 0:
                teile.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                             f'fill="{FARBEN[klasse]}"><title>{_e(monat)} '
                             f'{BESCHRIFTUNG[klasse]}: {wert}</title></rect>')
        if len(schluessel) <= 18 or i % 2 == 0:
            teile.append(f'<text x="{x + w / 2:.1f}" y="{hoehe - rand_unten + 15:.0f}" '
                         f'font-size="11" fill="#5f5f5f" text-anchor="middle" '
                         f'transform="rotate(-40 {x + w / 2:.1f} {hoehe - rand_unten + 15:.0f})">'
                         f'{_e(monat[2:])}</text>')
    teile.append(f'<text x="0" y="14" font-size="11" fill="#5f5f5f">{maximum}</text>')
    return (f'<svg viewBox="0 0 {breite} {hoehe}" width="100%" role="img">'
            f'{"".join(teile)}</svg>')


def _saeulen_einfach(werte: dict, beschriftungen: list[str], breite: int = 620,
                     hoehe: int = 170) -> str:
    maximum = max(werte.values(), default=1) or 1
    rand = 26
    spalte = breite / max(1, len(werte))
    teile = []
    for i, (schluessel, wert) in enumerate(sorted(werte.items())):
        h = wert / maximum * (hoehe - rand - 12)
        x = i * spalte + spalte * 0.18
        w = spalte * 0.64
        teile.append(f'<rect x="{x:.1f}" y="{hoehe - rand - h:.1f}" width="{w:.1f}" '
                     f'height="{h:.1f}" fill="{FARBEN[VORGANG_INTERN]}">'
                     f'<title>{wert}</title></rect>')
        name = beschriftungen[i] if i < len(beschriftungen) else str(schluessel)
        teile.append(f'<text x="{x + w / 2:.1f}" y="{hoehe - 8:.0f}" font-size="12" '
                     f'fill="#5f5f5f" text-anchor="middle">{_e(name)}</text>')
    return (f'<svg viewBox="0 0 {breite} {hoehe}" width="100%" role="img">'
            f'{"".join(teile)}</svg>')


# --------------------------------------------------------------- Bausteine

def _kachel(titel: str, wert: str, bezug: str = "") -> str:
    return (f'<div class="kachel"><div class="titel">{_e(titel)}</div>'
            f'<div class="wert">{_e(wert)}</div>'
            f'<div class="bezug">{_e(bezug)}</div></div>')


def _seite_management(kpi: dict, hypothese: float | None) -> str:
    kern = kpi["kern"]
    k1, k2 = kern["k1_vorgangsanteile"], kern["k2_nachrichtenanteile"]
    tiefe = kern["k3_koordinationstiefe"]
    breite = kern["k4_beteiligungsbreite"]

    vergleich = ""
    if hypothese is not None:
        vergleich = (f'<tr><td>Vermutet</td><td colspan="3">rund {_p(hypothese)} '
                     f'interne Kommunikation</td></tr>')

    return f"""
<div class="hypothese">
  <h3 style="margin-top:0">Ausgangshypothese und Messergebnis</h3>
  <table>
    <thead><tr><th>Sicht</th><th>intern</th><th>gemischt</th><th>extern</th></tr></thead>
    <tbody>
      {vergleich}
      <tr><td><strong>Vorgänge</strong> (Themen)</td>
          <td>{_p(k1[VORGANG_INTERN], 1)}</td><td>{_p(k1[VORGANG_GEMISCHT], 1)}</td>
          <td>{_p(k1[VORGANG_EXTERN], 1)}</td></tr>
      <tr><td><strong>Nachrichten</strong> (Aufwand)</td>
          <td>{_p(k2[VORGANG_INTERN], 1)}</td><td>{_p(k2[VORGANG_GEMISCHT], 1)}</td>
          <td>{_p(k2[VORGANG_EXTERN], 1)}</td></tr>
    </tbody>
  </table>
  {_balken_gestapelt(k1)}{_legende()}
  <p class="leise" style="margin-bottom:0">Die Differenz zwischen beiden Zeilen ist der
  eigentliche Befund: Sie zeigt, wie viel Kommunikation ein internes Thema kostet —
  nicht, wie viele Themen intern sind.</p>
</div>

<div class="kacheln">
  {_kachel("Interne Vorgänge", _p(k1[VORGANG_INTERN]),
           f'{round(k1[VORGANG_INTERN] * kern["n_vorgaenge"])} von {kern["n_vorgaenge"]}')}
  {_kachel("Interne Nachrichten", _p(k2[VORGANG_INTERN]),
           f'{round(k2[VORGANG_INTERN] * kern["n_nachrichten"])} von {kern["n_nachrichten"]}')}
  {_kachel("Koordinationstiefe intern", _z(tiefe[VORGANG_INTERN]["median"]),
           f'Nachrichten je Vorgang (Median), extern {_z(tiefe[VORGANG_EXTERN]["median"])}')}
  {_kachel("Beteiligungsbreite intern", _z(breite[VORGANG_INTERN]["median"]),
           f'Personen je Vorgang (Median), extern {_z(breite[VORGANG_EXTERN]["median"])}')}
  {_kachel("Außenorientierung", _p(kern["k5_aussenorientierung"]),
           f'der {kern["n_gesendet"]} selbst gesendeten Nachrichten')}
  {_kachel("Externe Reichweite", str(kern["k6_reichweite"]["domains_gesamt"]),
           f'Domains, davon {kern["k6_reichweite"]["domains_aktiv"]} mit ≥ 3 Vorgängen')}
</div>
"""


def _seite_koordination(kpi: dict) -> str:
    koord = kpi["koordination"]
    kern = kpi["kern"]
    zeilen = []
    for klasse in (VORGANG_INTERN, VORGANG_GEMISCHT, VORGANG_EXTERN):
        tiefe = kern["k3_koordinationstiefe"][klasse]
        breite = kern["k4_beteiligungsbreite"][klasse]
        lang = koord["langlaeufer"][klasse]
        zeilen.append(
            f"<tr><td>{BESCHRIFTUNG[klasse]}</td><td>{tiefe['n']}</td>"
            f"<td>{_z(tiefe['median'])}</td><td>{_z(tiefe['mittel'])}</td>"
            f"<td>{_z(breite['median'])}</td>"
            f"<td>{_p(lang['ueber_5'])}</td><td>{_p(lang['ueber_10'])}</td>"
            f"<td>{_z(koord['dauer_stunden_median'][klasse] / 24, 1)}</td></tr>"
        )
    intern_med = kern["k3_koordinationstiefe"][VORGANG_INTERN]["median"]
    extern_med = kern["k3_koordinationstiefe"][VORGANG_EXTERN]["median"]
    breite_i = kern["k4_beteiligungsbreite"][VORGANG_INTERN]["median"]
    breite_e = kern["k4_beteiligungsbreite"][VORGANG_EXTERN]["median"]

    return f"""
<h2>Interne Koordinationslast</h2>
<p>Interne Vorgänge haben im Median <strong>{_z(intern_med)} Nachrichten</strong> und
<strong>{_z(breite_i)} Teilnehmer</strong>, externe <strong>{_z(extern_med)}</strong>
bzw. <strong>{_z(breite_e)}</strong>. Der Aufwandstreiber ist das Produkt aus beidem,
nicht die Mailanzahl allein.</p>
<table>
  <thead><tr><th>Klasse</th><th>Vorgänge</th><th>Nachrichten Median</th>
  <th>Nachrichten Ø</th><th>Teilnehmer Median</th><th>&gt; 5 Nachrichten</th>
  <th>&gt; 10 Nachrichten</th><th>Dauer Median (Tage)</th></tr></thead>
  <tbody>{"".join(zeilen)}</tbody>
</table>
<div class="kacheln">
  {_kachel("CC-Quote intern", _p(koord["cc_quote_intern"]),
           f'Ø {_z(koord["cc_empfaenger_mittel"])} CC-Empfänger')}
  {_kachel("Großverteiler", _p(koord["anteil_grossverteiler"]),
           "interne Nachrichten über der Empfängerschwelle")}
  {_kachel("An Verteilerlisten", _p(koord["anteil_an_verteilerlisten"]),
           "Broadcast statt Einzelabstimmung")}
  {_kachel("Interner Anteil in gemischten Vorgängen",
           _p(koord["interner_anteil_in_gemischten"]),
           "was ein Lieferantenthema intern kostet")}
</div>
<p class="leise">Empfängerzahlen sind eine Untergrenze: Verteilerlisten werden bewusst
nicht aufgelöst, weil ihr heutiger Mitgliederstand nicht zur Mail von damals passt.</p>
"""


def _seite_fachbereiche(kpi: dict, warnschwelle: float) -> str:
    fb = kpi["fachbereiche"]
    if not fb["zeilen"] or (len(fb["zeilen"]) == 1
                            and fb["zeilen"][0]["fachbereich"] == "Unbekannt/Sonstige"):
        return """
<h2>Fachbereiche</h2>
<div class="hinweis">Es ist noch keine Fachbereichszuordnung gepflegt. Die Datei
<code>mapping_personen</code> wurde erzeugt und nach Volumen sortiert — in der Regel
genügen die obersten 15 bis 25 Zeilen, um rund 80 % des Volumens abzudecken.
Nach dem Ausfüllen die Analyse einfach erneut starten.</div>
"""
    warnung = ""
    if fb["anteil_unbekannt"] > warnschwelle:
        warnung = (f'<div class="hinweis"><strong>Eingeschränkt belastbar:</strong> '
                   f'{_p(fb["anteil_unbekannt"])} der Vorgänge entfallen auf nicht '
                   f'zugeordnete Personen. Solange dieser Anteil über '
                   f'{_p(warnschwelle)} liegt, sind die Aussagen dieser Seite '
                   f'nicht tragfähig.</div>')
    zeilen = "".join(
        f"<tr><td>{_e(z['fachbereich'])}</td><td>{z['vorgaenge']}</td>"
        f"<td>{_p(z['anteil_vorgaenge'], 1)}</td><td>{z['nachrichten']}</td>"
        f"<td>{_p(z['anteil_nachrichten'], 1)}</td>"
        f"<td>{_z(z['vorgangsgroesse_median'])}</td></tr>"
        for z in fb["zeilen"]
    )
    return f"""
<h2>Fachbereiche</h2>
{warnung}
<table>
  <thead><tr><th>Fachbereich</th><th>Vorgänge</th><th>Anteil</th>
  <th>Nachrichten</th><th>Anteil</th><th>Vorgangsgröße Median</th></tr></thead>
  <tbody>{zeilen}</tbody>
</table>
<p class="leise">Ein Vorgang zählt bei jedem beteiligten Fachbereich — die Summe der
Anteile ergibt daher mehr als 100 %. Die Spalte „Vorgangsgröße“ zeigt, mit wem
Abstimmung aufwendig ist.</p>
"""


def _seite_lieferanten(kpi: dict) -> str:
    lief = kpi["lieferanten"]
    if not lief["top_domains"]:
        return "<h2>Lieferanten und Markt</h2><p class='leise'>Keine externe Kommunikation im Zeitraum.</p>"
    zeilen = "".join(
        f"<tr><td>{_e(d['domain'])}</td><td>{_e(d['kategorie'])}</td>"
        f"<td>{d['vorgaenge']}</td><td>{d['nachrichten']}</td>"
        f"<td>{_p(d['anteil'], 1)}</td><td>{d['gesendet']}</td><td>{d['empfangen']}</td></tr>"
        for d in lief["top_domains"]
    )
    return f"""
<h2>Lieferanten und Markt</h2>
<div class="kacheln">
  {_kachel("Externe Domains", str(lief["domains_gesamt"]), "im Zeitraum kontaktiert")}
  {_kachel("Konzentration Top 10", _p(lief["anteil_top10"]), "des externen Volumens")}
  {_kachel("HHI", str(round(lief["hhi"])), "Streuung des externen Volumens")}
</div>
<table>
  <thead><tr><th>Domain</th><th>Kategorie</th><th>Vorgänge</th><th>Nachrichten</th>
  <th>Anteil</th><th>gesendet</th><th>empfangen</th></tr></thead>
  <tbody>{zeilen}</tbody>
</table>
<p class="leise">Das Verhältnis gesendet zu empfangen zeigt, wer die Beziehung treibt.
Der HHI ist bewusst ohne Ampel dargestellt — es gibt keinen Zielwert für Konzentration.</p>
"""


def _seite_zeit(kpi: dict) -> str:
    zeit = kpi["zeit"]
    return f"""
<h2>Zeitliche Muster</h2>
<figure>{_saeulen_monat(zeit["monate_vorgaenge"])}
<figcaption>Vorgänge je Monat nach Klasse. Ein Vorgang zählt im Monat seiner ersten
Nachricht.</figcaption></figure>
{_legende()}
<h3>Wochentage</h3>
<figure>{_saeulen_einfach(zeit["wochentage"], WOCHENTAGE)}
<figcaption>Nachrichten je Wochentag.</figcaption></figure>
<div class="explorativ">
<h3>Tageszeit <span class="marke">explorativ</span></h3>
<figure>{_saeulen_einfach(zeit["stunden"], [f"{h}" for h in range(24)])}
<figcaption>Nachrichten je Stunde. Diese Auswertung beschreibt Verhalten und ist
deshalb nur im persönlichen Report enthalten — im Teamexport fehlt sie bewusst.</figcaption>
</figure>
</div>
"""


def _anhang(qualitaet: dict, stabilitaet: dict, kontext: dict, warnschwelle: float) -> str:
    warnung = ""
    if qualitaet["anteil_unaufgeloest"] > warnschwelle:
        warnung = (f'<div class="hinweis"><strong>Achtung:</strong> '
                   f'{_p(qualitaet["anteil_unaufgeloest"], 1)} der Nachrichten enthalten '
                   f'mindestens eine nicht auflösbare Adresse. Über {_p(warnschwelle)} '
                   f'ist die Trennung intern/extern nicht mehr belastbar.</div>')
    stab = ("stabil" if stabilitaet["stabil"] else
            "<strong>instabil — die Vorgangsebene ist entsprechend zu relativieren</strong>")
    ordner = ", ".join(_e(o) for o in kontext.get("ausgeschlossene_ordner", [])) or "keine"
    stores = ", ".join(_e(s) for s in kontext.get("stores", [])) or "—"
    return f"""
<h2>Methodik und Datenqualität</h2>
{warnung}
<table>
  <tbody>
    <tr><td>Zeitraum</td><td>{_e(kontext.get("zeitraum", "—"))}</td></tr>
    <tr><td>Ausgewertete Postfächer/Archive</td><td>{stores}</td></tr>
    <tr><td>Ausgeschlossene Ordner</td><td>{ordner}</td></tr>
    <tr><td>Nachrichten nach Deduplikation</td><td>{qualitaet["nachrichten_gesamt"]}</td></tr>
    <tr><td>Entfernte Duplikate</td><td>{qualitaet["duplikate_entfernt"]}</td></tr>
    <tr><td>Anteil unauflösbarer Adressen</td><td>{_p(qualitaet["anteil_unaufgeloest"], 1)}</td></tr>
    <tr><td>Anteil automatisierter Nachrichten</td><td>{_p(qualitaet["anteil_automatisiert"], 1)}</td></tr>
    <tr><td>Anteil Terminobjekte</td><td>{_p(qualitaet["anteil_termine"], 1)}</td></tr>
    <tr><td>Nachrichten an Verteilerlisten</td><td>{qualitaet["nachrichten_an_verteilerlisten"]}</td></tr>
    <tr><td>Vorgänge (ConversationID / Ersatzverfahren)</td>
        <td>{stabilitaet["vorgaenge_conv"]} / {stabilitaet["vorgaenge_fallback"]}</td></tr>
    <tr><td>Größte Abweichung der Kern-KPIs zwischen beiden Verfahren</td>
        <td>{_p(stabilitaet["groesste_abweichung"], 1)} — {stab}</td></tr>
  </tbody>
</table>

<h3>Was diese Zahlen nicht beweisen</h3>
<ul>
  <li><strong>Ein hoher interner Anteil ist kein Fehler.</strong> Strategischer Einkauf ist
  eine Querschnittsfunktion; Bedarfsklärung, Spezifikation und Freigaben sind Kernaufgaben.</li>
  <li><strong>Es gibt keinen Benchmark</strong> für die „richtige“ interne Quote. Vergleichbar
  ist nur dieselbe Rolle über die Zeit.</li>
  <li><strong>Volumen ist nicht Zeit.</strong> Metadaten messen Kommunikationsvolumen,
  nicht Aufwand.</li>
  <li><strong>Meetings fehlen</strong> — die vermutlich größte Koordinationslast taucht in
  dieser Auswertung gar nicht auf.</li>
  <li><strong>Keine Personenaussage.</strong> Kein Ergebnis eignet sich zur Beurteilung
  einzelner Personen.</li>
</ul>

<h3>Definitionen</h3>
<ul>
  <li><strong>Vorgang</strong> — zusammenhängender Kommunikationsstrang. Klassifiziert über
  die Vereinigungsmenge aller Teilnehmer aller Nachrichten.</li>
  <li><strong>gemischt</strong> — Vorgang mit externer Beteiligung <em>und</em> mindestens
  einer rein internen Nachricht. Bewusst eine eigene Klasse, damit
  Lieferantenvorgänge mit interner Abstimmung nicht als reine Innenbeschäftigung erscheinen.</li>
  <li><strong>Außenorientierung</strong> — Anteil der selbst gesendeten Nachrichten mit
  mindestens einem externen Empfänger. Empfangenes ist fremdbestimmt, Gesendetes ist die
  eigene Kapazitätsentscheidung.</li>
  <li><strong>Koordinationstiefe</strong> — Nachrichten je Vorgang, ohne Randvorgänge
  (Vorgänge, die vor dem Beobachtungsfenster begonnen haben).</li>
</ul>
"""


def erzeugen(kpi: dict, qualitaet: dict, stabilitaet: dict, kontext: dict,
             pfad: Path | str, hypothese: float | None = 0.80,
             warnschwelle_adressen: float = 0.05,
             warnschwelle_fachbereich: float = 0.25) -> Path:
    inhalt = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kommunikationsanalyse</title><style>{CSS}</style></head>
<body><main>
<div class="kopf">
  <h1>Kommunikationsanalyse</h1>
  <p class="leise">Wie viel Kommunikations- und Koordinationskapazität wird intern
  gebunden? — Zeitraum {_e(kontext.get("zeitraum", "—"))}, erstellt am
  {_e(datetime.now().strftime("%d.%m.%Y"))}. Ausschließlich Metadaten;
  keine Mailtexte, Betreffzeilen oder Anhangnamen.</p>
</div>
{_seite_management(kpi, hypothese)}
{_seite_koordination(kpi)}
{_seite_fachbereiche(kpi, warnschwelle_fachbereich)}
{_seite_lieferanten(kpi)}
{_seite_zeit(kpi)}
{_anhang(qualitaet, stabilitaet, kontext, warnschwelle_adressen)}
<footer>Erzeugt mit Outlook-Kommunikationsanalyse. Das Postfach wurde ausschließlich
gelesen und nicht verändert. Diese Auswertung ist eine Organisationsanalyse und
ausdrücklich keine Leistungs- oder Verhaltenskontrolle.</footer>
</main></body></html>"""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad
