"""Outlook-Kommunikationsanalyse.

Metadatenbasierte Auswertung eines Outlook-Postfachs.  Liest ausschliesslich
Metadaten -- keine Mailtexte, keine Betreffzeilen, keine Anhangnamen -- und
veraendert das Postfach nicht.

Der Ablauf ist in fuenf Stufen geteilt (siehe docs/04-setup-und-architektur.md).
Nur die erste Stufe braucht Windows und Outlook; alles Weitere rechnet auf einer
lokalen Zwischendatei und ist damit ohne Postfach testbar.
"""

__version__ = "1.0.0"
