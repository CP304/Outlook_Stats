# 04 — Setup und Architektur

## Leitgedanke

Der Nutzer soll beim ersten Lauf **eine einzige Angabe** machen müssen: die interne Maildomain.
Alles Weitere schlägt das Programm selbst vor. Verfeinerung ist optional und lohnt sich erst,
wenn die Basiszahlen überzeugen.

## Zwei-Pass-Modell

### Pass 1 — nur die Domain

```
Analyse_starten.bat
  → Dialog: interne Domain(s), Zeitraum (Default: letzte 12 volle Monate)
  → Lauf
```

Ergebnis:
- vollständiger Basisreport (alle Kern-KPIs, intern/extern/gemischt, Zeitverlauf, Domainkonzentration)
- `mapping_personen.xlsx` — automatisch erzeugt, **nach Volumen absteigend sortiert**
- `mapping_domains.xlsx` — dito
- `messages.csv` — der lokale Metadaten-Cache

`mapping_personen.xlsx`:

| E-Mail | Anzeigename | Vorgänge | Nachrichten | Anteil kumuliert | Fachbereich | Rolle |
|---|---|---|---|---|---|---|
| … | … | 84 | 310 | 12 % | *(leer)* | *(leer)* |

Die Sortierung nach Volumen ist der eigentliche Setup-Trick: In der Praxis decken **15 bis 25 gepflegte
Zeilen rund 80 % des Volumens** ab. Der Rest bleibt "Unbekannt/Sonstige" und wird als solcher ausgewiesen.
Die Spalte "Anteil kumuliert" zeigt direkt, wann man aufhören kann zu pflegen.

`mapping_domains.xlsx` analog mit der Spalte `Kategorie` (Vorschlagswerte: Lieferant, Dienstleister,
Kunde, Behörde, Konzern/verbunden, Sonstiges).

### Pass 2 — nach optionaler Pflege

Gleicher Aufruf. Das Programm erkennt vorhandene Mapping-Dateien, liest den Cache und rechnet in Sekunden.
Zusätzlich verfügbar: Fachbereichsanalyse, Lieferantensicht, Netzwerksicht.

**Wichtig:** Bestehende Mapping-Dateien werden nie überschrieben. Neue Personen werden angehängt und
farblich als neu markiert.

## Konfiguration

Eine einzige `config.yaml`, alle Werte mit sinnvollen Defaults, alle optional außer der Domain:

```yaml
interne_domains: ["firma.de"]          # einzige Pflichtangabe
konzern_domains: []                    # optional: verbundene Unternehmen -> eigene Klasse
zeitraum_monate: 12
ordner_ausschluss: ["Junk-E-Mail", "Gelöschte Elemente", "Entwürfe", "RSS-Feeds"]
fremde_postfaecher_einbeziehen: false   # bewusster Default, siehe Kapitel 08
schwellen:
  grossverteiler_empfaenger: 8
  langlaeufer_nachrichten: 5
  langlaeufer_lang: 10
  thread_luecke_tage: 30
```

Der Punkt `konzern_domains` ist wichtiger, als er aussieht: Kommunikation mit einer Schwestergesellschaft
ist formal extern, faktisch aber interne Abstimmung. Ohne diese dritte Klasse wird die Kernkennzahl
in Konzernstrukturen systematisch geschönt.

Ausgeschlossen werden per Default: Entwürfe (nie versendet), Gelöschte Elemente (Zufallsauswahl),
Junk (kein Arbeitsverkehr). Der Ausschluss wird im Report benannt.

## Einstellungen weitergeben

Die eigentliche Pflegearbeit steckt nicht in der Konfiguration, sondern in der
Fachbereichszuordnung. Wer einmal die relevanten Kollegen ihren Abteilungen zugeordnet hat, soll das
nicht wiederholen müssen — und der nächste Nutzer erst recht nicht bei null anfangen.

```
python -m okoa export                      # schreibt Einstellungen.json
python -m okoa import Einstellungen.json   # übernimmt sie
```

**Was mitgeht** ist Organisationswissen: interne und Konzerndomains, Zeitraum und Schwellen, die
Fachbereichs- und Rollenzuordnung, die Domainkategorien.

**Was bewusst nicht mitgeht**, sind die Volumenspalten der Zuordnungsdatei. „Vorgänge: 84" sieht
harmlos aus, ist aber eine Aussage darüber, mit wem der Ersteller wie viel zu tun hatte — also seine
Postfachdaten und nicht die des Unternehmens. Sie werden beim Export entfernt; `enthaelt_volumendaten()`
erlaubt dem Empfänger, das selbst nachzuprüfen. Ebenso fallen ungepflegte Zeilen heraus: Eine Adresse
ohne Zuordnung wäre beim Empfänger nur eine Liste fremder Kollegen.

**Beim Zusammenführen gewinnt die eigene Zuordnung.** Neue Einträge kommen hinzu, eigene leere Felder
werden ergänzt, aber ein Widerspruch wird nicht stillschweigend überschrieben — sonst verliert jemand
seine Arbeit, weil ihm jemand eine Datei geschickt hat. Der Bericht zählt auf, was passiert ist;
`--ueberschreiben` dreht die Regel bewusst um, `--nur-zuordnungen` lässt die eigene Konfiguration
unangetastet. Zweimal einlesen erzeugt keine Dubletten.

## Pipeline

```
extract      COM-Zugriff, rekursiv über alle freigegebenen Stores      [nur Windows + Outlook]
   ↓         Ausgabe: Rohmetadaten je Element
normalize    Adressauflösung (SMTP), Identitätsauflösung, Deduplikation
   ↓         Klassifikation intern/konzern/extern/automatisiert/unaufgelöst
threads      Vorgangsbildung mit beiden Verfahren (ConversationID + Fallback)
   ↓
metrics      KPI-Berechnung auf dem Cache
   ↓
report       HTML-Dashboard, Excel-Rohwerte, team_export.json
```

Nur `extract` benötigt Windows und Outlook. Alle weiteren Stufen arbeiten auf dem Cache und sind
plattformunabhängig, testbar und ohne Postfachzugriff nachvollziehbar. Das hat drei Vorteile:

1. **Testbarkeit** — die gesamte Logik lässt sich mit synthetischen Daten prüfen, ohne Postfach
2. **Reproduzierbarkeit** — dieselbe Cache-Datei liefert immer dasselbe Ergebnis
3. **Prüfbarkeit** — ein Datenschutzbeauftragter kann sich den Cache ansehen und sieht: keine Inhalte

## Der Metadaten-Cache

`messages.csv`, eine Zeile je deduplizierter Nachricht. Bewusst ein Textformat: Wer prüfen
soll, dass keine Inhalte gespeichert werden, muss die Datei ohne Werkzeug öffnen können.

```
msg_hash, zeitstempel, richtung, absender_id, absender_klasse, absender_domain,
empfaenger_ids, empfaenger_klassen,
n_to, n_cc, n_to_intern, n_to_extern, n_cc_intern, n_cc_extern, n_verteilerlisten,
klasse (normal|automatisiert|termin), hat_anhang, ist_antwort, ordner, store,
thread_id_conv, thread_id_fallback
```

**Nicht enthalten:** Betreff, Body, Anhangnamen, BCC-Details, Roh-EntryIDs, ConversationID.
Der Betreff existiert nur als flüchtiger Hash während der Vorgangsbildung und wird nicht gespeichert;
deshalb stehen die fertigen Vorgangs-IDs in der Datei, und ein erneuter Lauf übernimmt sie unverändert,
statt die Vorgänge zu zerlegen.

Optionaler Schalter `--pseudonymisiert`: Adressen werden durch einen gesalzenen Hash ersetzt,
das Salz bleibt lokal. Für Prüfungen durch Dritte gedacht.

## Was bewusst nicht gebaut wird

- **keine Datenbank** — eine Datei, ein Ordner, kein Server, keine IT-Freigabe nötig
- **kein Outlook-Add-in** — Installation und Freigabeprozess wären teurer als die ganze Analyse
- **keine Graph-API-Variante in Stufe 1** — braucht Admin-Consent und damit genau die
  Organisationsdiskussion, die man am Anfang nicht führen will
- **keine Cloud, kein Upload** — alles bleibt auf dem Rechner
