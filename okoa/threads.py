"""Vorgangsbildung mit zwei unabhaengigen Verfahren.

Weil die ConversationID bei Betreffaenderungen, ueber Store-Grenzen und bei
extern zurueckkommenden Threads bricht, wird jeder Vorgang zusaetzlich ueber
einen Ersatzweg gebildet.  Beide Ergebnisse werden im Report gegeneinander
gestellt: weichen die Kern-KPIs deutlich ab, ist die Vorgangsebene instabil
und muss relativiert werden.  Das ist unbequem, aber ehrlich.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .model import Nachricht, Vorgang


VERFAHREN_CONV = "conversation"
VERFAHREN_FALLBACK = "fallback"


def _fallback_zuordnen(nachrichten: list[Nachricht], luecke_tage: int) -> None:
    """Gruppiert ueber Betreff-Hash + Teilnehmerueberlappung + Zeitfenster.

    Ohne das Zeitfenster wuerde ein wiederkehrender Betreff ("Wochenbericht")
    ueber Jahre zu einem einzigen Endlosvorgang verschmelzen.
    """
    luecke = timedelta(days=luecke_tage)
    # Je Betreff-Hash eine Liste offener Ketten: (letzter Zeitpunkt, Beteiligte, id)
    offen: dict[str, list[tuple[datetime, set[str], str]]] = {}
    zaehler = 0

    for n in sorted(nachrichten, key=lambda x: x.zeitstempel):
        if not n.betreff_hash:
            # Ohne Betreff keine Kette -- die Nachricht bleibt fuer sich.
            zaehler += 1
            n.thread_id_fallback = f"fb-einzeln-{zaehler}"
            continue

        beteiligte = n.alle_beteiligten
        ketten = offen.setdefault(n.betreff_hash, [])
        treffer = None
        for i, (letzter, teilnehmer, kette_id) in enumerate(ketten):
            if n.zeitstempel - letzter > luecke:
                continue
            # Mindestens eine gemeinsame Person -- sonst ist es trotz gleichem
            # Betreff ein anderer Vorgang (typisch bei Serienbetreffen).
            if not (teilnehmer & beteiligte):
                continue
            treffer = i
            break

        if treffer is None:
            zaehler += 1
            kette_id = f"fb-{zaehler}"
            ketten.append((n.zeitstempel, set(beteiligte), kette_id))
        else:
            letzter, teilnehmer, kette_id = ketten[treffer]
            ketten[treffer] = (n.zeitstempel, teilnehmer | beteiligte, kette_id)
        n.thread_id_fallback = kette_id


def zuordnen(nachrichten: list[Nachricht], luecke_tage: int = 30) -> None:
    """Setzt thread_id_conv und thread_id_fallback auf allen Nachrichten.

    Aus der Zwischendatei gelesene Nachrichten bringen ihre Vorgangs-IDs bereits
    mit -- ConversationID und Betreff-Hash werden dort bewusst nicht gespeichert.
    Ein erneutes Zuordnen wuerde deshalb jede Nachricht zu einem eigenen Vorgang
    machen; darum wird eine fertige Zuordnung unveraendert uebernommen.
    """
    if nachrichten and all(n.thread_id_conv and n.thread_id_fallback for n in nachrichten):
        return
    zaehler = 0
    ersatz: dict[str, str] = {}
    for n in nachrichten:
        if n.conversation_id:
            n.thread_id_conv = "cv-" + n.conversation_id
        else:
            # Keine ConversationID (kommt bei aelteren oder importierten
            # Elementen vor): auf den Ersatzweg zurueckfallen statt zu raten.
            schluessel = n.betreff_hash or n.msg_hash
            if schluessel not in ersatz:
                zaehler += 1
                ersatz[schluessel] = f"cv-ersatz-{zaehler}"
            n.thread_id_conv = ersatz[schluessel]
    _fallback_zuordnen(nachrichten, luecke_tage)


def vorgaenge_bilden(
    nachrichten: list[Nachricht],
    verfahren: str = VERFAHREN_CONV,
    fensterbeginn: datetime | None = None,
) -> list[Vorgang]:
    """Fasst Nachrichten zu Vorgaengen zusammen.

    Vorgaenge, deren erste Nachricht vor dem Beobachtungsfenster liegt, werden
    als Randvorgang markiert -- sie sind systematisch abgeschnitten und gehen
    nicht in Dauer- und Tiefenkennzahlen ein.
    """
    schluessel = "thread_id_conv" if verfahren == VERFAHREN_CONV else "thread_id_fallback"
    gruppen: dict[str, list[Nachricht]] = {}
    for n in nachrichten:
        gruppen.setdefault(getattr(n, schluessel), []).append(n)

    vorgaenge = []
    for thread_id, gruppe in gruppen.items():
        gruppe.sort(key=lambda x: x.zeitstempel)
        v = Vorgang(thread_id=thread_id, nachrichten=gruppe)
        if fensterbeginn is not None and v.beginn < fensterbeginn:
            v.randvorgang = True
        vorgaenge.append(v)
    vorgaenge.sort(key=lambda v: v.beginn)
    return vorgaenge
