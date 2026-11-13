"""Ricerca locale nelle schede delle fonti, con filtri conservativi di ambito, validità e affidabilità.

La ricerca usa esclusivamente schede curate in data/fonti: nessun accesso web e nessuna
produzione automatica di contenuti legali. Una scheda stantia, modificata o senza
validità temporale non viene proposta come risultato utilizzabile.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

import fonti


def _normalizza_testo(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(c for c in value if not unicodedata.combining(c))


def _termini(testo):
    return {t for t in re.findall(r"[a-z0-9]+", _normalizza_testo(testo)) if len(t) > 1}


def cerca(query, area=None, alla_data=None, ambito=None, territorio=None, limite=20):
    """Cerca schede, dando priorità alle corrispondenze complete.

    La data di riferimento filtra la vigenza; l'attualità della verifica è valutata
    rispetto a oggi. Voci non affidabili o non aggiornate restano visibili solo
    nell'elenco separato `fonti_da_verificare`.
    """
    q = _termini(query)
    if not q:
        raise ValueError("Inserire almeno un termine di ricerca.")
    if area is not None and area not in fonti.AREE:
        raise ValueError(f"Area sconosciuta: {area}")
    if ambito is not None and ambito not in fonti.AMBITI:
        raise ValueError(f"Ambito non valido: {ambito}")
    if territorio is not None and not str(territorio).strip():
        raise ValueError("Il territorio non può essere vuoto.")
    if not isinstance(limite, int) or isinstance(limite, bool) or not 1 <= limite <= 100:
        raise ValueError("Il limite deve essere un intero compreso tra 1 e 100.")
    try:
        rif = date.fromisoformat(alla_data) if isinstance(alla_data, str) else (alla_data or date.today())
    except (TypeError, ValueError):
        raise ValueError("La data di riferimento non è valida (usare AAAA-MM-GG).")
    if not isinstance(rif, date):
        raise ValueError("La data di riferimento non è valida.")

    risultati, non_affidabili = [], []
    for voce in fonti.carica_cartella():
        if area and area not in voce.get("aree", []):
            continue
        if ambito and voce.get("ambito") != ambito:
            continue
        if territorio and (voce.get("territorio") or "").casefold() != str(territorio).strip().casefold():
            continue
        testo = " ".join(str(voce.get(k) or "") for k in ("tema", "testo", "riferimenti", "fonte_nome"))
        presenti = q & _termini(testo)
        if not presenti:
            continue
        stato_validita = fonti.validita(voce, alla_data=rif)
        verifica = fonti.stato_verifica(voce)
        affidabile = voce.get("stato") in fonti.STATI_AFFIDABILI
        aggiornata = verifica.get("codice") == "aggiornata"
        utilizzabile = affidabile and aggiornata and stato_validita["codice"] == "in_vigore"
        elemento = {
            "id": voce.get("id"), "tema": voce.get("tema"), "estratto": voce.get("testo"),
            "riferimenti": voce.get("riferimenti"), "fonte_nome": voce.get("fonte_nome"),
            "fonte_url": voce.get("fonte_url"), "stato": voce.get("stato"),
            "ambito": fonti.etichetta_ambito(voce), "validita": stato_validita,
            "verifica": verifica, "termini_trovati": sorted(presenti),
            "punteggio": round(len(presenti) / len(q), 3),
        }
        (risultati if utilizzabile else non_affidabili).append(elemento)

    ordinamento = lambda x: (-x["punteggio"], x["tema"] or "", x["id"] or "")
    risultati.sort(key=ordinamento)
    non_affidabili.sort(key=ordinamento)
    risultati = risultati[:limite]
    return {
        "query": query, "data_riferimento": rif.isoformat(),
        "stato": "risultati_presenti" if risultati else "fonti_insufficienti",
        "risultati": risultati,
        "fonti_da_verificare": non_affidabili[:limite],
        "avviso": "Ricerca nelle sole schede locali: verificare sempre il testo integrale e la vigenza presso la fonte ufficiale.",
    }
