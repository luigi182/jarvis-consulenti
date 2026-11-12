"""Modello delle fonti usate dalla ricerca (v2.5).

Ogni voce della base dati viene normalizzata con:
- aree:        una o più delle cinque aree professionali (data/aree.json);
- tipo_fonte:  normativa | circolare | prassi | ccnl | giurisprudenza | procedura_studio | scheda_studio;
- ente:        chi ha emanato la fonte (Parlamento/Governo, INPS, INAIL, Agenzia delle Entrate, CNCE, Cassa Edile...);
- ambito:      nazionale | territoriale | da_definire  (+ territorio, es. "Napoli");
- validità temporale: data_atto, pubblicato_il, in_vigore_dal, testo_vigente_dal, modifiche[], vigente_fino_al,
                      abrogato_il / abrogato_da, verificato_il.

Questo modulo NON contiene contenuti normativi: solo regole per classificare le voci, valutarne la validità a una data
e controllare che i file dei dati siano completi. Le date mancanti restano mancanti e vengono mostrate come "non indicata".
"""
import glob
import json
import os
import re
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")


def _json(percorso):
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


AREE_CFG = _json(os.path.join(DATA, "aree.json"))
AREE = {a["id"]: a for a in AREE_CFG["aree"]}
REGISTRO = _json(os.path.join(DATA, "fonti_ufficiali.json"))

# tipi di fonte: l'ordine è quello di presentazione dei risultati
TIPI = {
    "normativa": "Normativa (leggi, decreti, codice civile)",
    "circolare": "Circolari e messaggi (INPS, INAIL, Agenzia delle Entrate, Ministero, INL, Casse Edili)",
    "prassi": "Prassi (interpelli, risoluzioni, note, schede e FAQ degli enti)",
    "ccnl": "CCNL e accordi collettivi",
    "giurisprudenza": "Giurisprudenza",
    "procedura_studio": "Procedure e automazioni dello Studio",
    "scheda_studio": "Schede di sintesi dello Studio (da validare)",
}
# vecchi tipi (v2.4) ricondotti ai nuovi: l'ente resta indicato
TIPI_VECCHI = {"inps": ("prassi", "INPS"), "inail": ("prassi", "INAIL")}

STATI = {
    "verificata": "verificata sulla fonte",
    "procedura_approvata": "procedura approvata dallo Studio",
    "fonte_secondaria": "da fonte secondaria: leggere il provvedimento",
    "scheda_da_validare": "scheda dello Studio da validare",
    "da_verificare": "DA VERIFICARE (vecchio file)",
    "non_verificato": "NON VERIFICATO (vecchio file)",
}
STATI_AFFIDABILI = {"verificata", "procedura_approvata"}
AMBITI = {"nazionale", "territoriale", "da_definire"}
CAMPI_DATA = ("data_atto", "pubblicato_il", "in_vigore_dal", "testo_vigente_dal", "vigente_fino_al", "abrogato_il", "verificato_il")
CAMPI_OBBLIGATORI = ("id", "aree", "tipo_fonte", "ambito", "settore", "tema", "testo", "riferimenti", "fonte_nome", "fonte_url",
                     "verificato_il", "stato")


def data_iso(s):
    """Data ISO (AAAA-MM-GG) -> date; None se assente o non valida."""
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def fd(d):
    return d.strftime("%d/%m/%Y") if d else "non indicata"


# ---------- normalizzazione ----------
def _testo_vigente_da_nome(nome):
    """Le schede v2.4 riportano nella fonte "testo in vigore dal GG/MM/AAAA" (data della versione letta su Normattiva)."""
    m = re.search(r"in vigore dal (\d{2})/(\d{2})/(\d{4})", nome or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def normalizza(v, origine):
    """Completa i campi della voce senza aggiungere contenuti: solo classificazione e valori di default espliciti."""
    v = dict(v)
    v["origine"] = origine
    tipo = v.get("tipo_fonte") or "scheda_studio"
    if tipo in TIPI_VECCHI:
        tipo, ente = TIPI_VECCHI[tipo]
        v.setdefault("ente", ente)
    v["tipo_fonte"] = tipo
    aree = v.get("aree") or v.get("area") or []
    v["aree"] = [aree] if isinstance(aree, str) else list(aree)
    v["ambito"] = v.get("ambito") or "nazionale"
    v.setdefault("territorio", None)
    v.setdefault("ente", None)
    v.setdefault("modifiche", [])
    if not v.get("testo_vigente_dal"):
        v["testo_vigente_dal"] = _testo_vigente_da_nome(v.get("fonte_nome"))
    for c in CAMPI_DATA:
        v.setdefault(c, None)
    return v


def etichetta_ambito(v):
    if v["ambito"] == "territoriale":
        return "Territoriale – " + (v.get("territorio") or "territorio non indicato")
    if v["ambito"] == "da_definire":
        return "Ambito da definire (nazionale o territoriale)"
    return "Nazionale"


# ---------- validità temporale ----------
def soglia_verifica(v):
    """Giorni entro cui ricontrollare la voce: valore della voce o il più breve tra quelli delle sue aree."""
    if v.get("verifica_entro_giorni"):
        return int(v["verifica_entro_giorni"])
    giorni = [AREE[a]["verifica_entro_giorni"] for a in v.get("aree", []) if a in AREE]
    return min(giorni) if giorni else AREE_CFG["verifica_entro_giorni_default"]


def stato_verifica(v, oggi=None):
    oggi = oggi or date.today()
    d = data_iso(v.get("verificato_il"))
    if not d:
        return {"codice": "assente", "etichetta": "mai verificata sulla fonte", "verificato_il": None}
    giorni = (oggi - d).days
    soglia = soglia_verifica(v)
    if giorni > soglia:
        return {"codice": "da_ricontrollare", "verificato_il": d.isoformat(), "giorni": giorni,
                "etichetta": f"ultima verifica il {fd(d)} ({giorni} giorni fa, oltre i {soglia} previsti): ricontrollare la fonte"}
    return {"codice": "aggiornata", "verificato_il": d.isoformat(), "giorni": giorni, "etichetta": f"verificata il {fd(d)}"}


def validita(v, alla_data=None, oggi=None):
    """Validità della voce alla data di riferimento, in base alle sole date registrate.
    Codici: abrogata, non_ancora_in_vigore, testo_successivo, modificata_dopo_verifica, in_vigore, decorrenza_non_indicata."""
    oggi = oggi or date.today()
    alla = alla_data or oggi
    avvisi = []
    abrogata = data_iso(v.get("abrogato_il"))
    decorrenza = data_iso(v.get("in_vigore_dal"))
    testo_dal = data_iso(v.get("testo_vigente_dal"))
    verificata = data_iso(v.get("verificato_il"))
    fino = data_iso(v.get("vigente_fino_al"))
    modifiche_dopo = [m for m in v.get("modifiche", []) if verificata and (data_iso(m.get("data")) or date.min) > verificata]
    if fino and fino < alla:
        avvisi.append(f"efficacia indicata fino al {fd(fino)}: verificare rinnovo, proroga o ultrattività")
    if abrogata and abrogata <= alla:
        parola = "abrogata" if v["tipo_fonte"] == "normativa" else "superata / non più applicabile"
        da = f" ({v['abrogato_da']})" if v.get("abrogato_da") else ""
        return {"codice": "abrogata", "etichetta": f"{parola} dal {fd(abrogata)}{da}", "avvisi": avvisi}
    if abrogata:
        avvisi.append(f"cesserà di avere effetto dal {fd(abrogata)}")
    if decorrenza and decorrenza > alla:
        return {"codice": "non_ancora_in_vigore", "etichetta": f"non ancora in vigore alla data di riferimento (decorrenza {fd(decorrenza)})",
                "avvisi": avvisi}
    if testo_dal and testo_dal > alla:
        return {"codice": "testo_successivo", "avvisi": avvisi,
                "etichetta": (f"il testo riportato è in vigore dal {fd(testo_dal)}: per il {fd(alla)} "
                              "leggere la versione precedente (Normattiva: 'versioni' dell'atto)")}
    if modifiche_dopo:
        ultima = max(modifiche_dopo, key=lambda m: m.get("data") or "")
        return {"codice": "modificata_dopo_verifica", "avvisi": avvisi,
                "etichetta": f"modifica registrata il {fd(data_iso(ultima.get('data')))} ({ultima.get('atto') or 'atto non indicato'}) "
                             "dopo l'ultima verifica: la sintesi può non essere aggiornata"}
    if decorrenza or testo_dal:
        return {"codice": "in_vigore", "avvisi": avvisi,
                "etichetta": f"in vigore alla data di riferimento secondo l'ultima verifica (testo dal {fd(testo_dal or decorrenza)})"}
    return {"codice": "decorrenza_non_indicata", "etichetta": "decorrenza non indicata", "avvisi": avvisi}


# ---------- caricamento e controlli ----------
def carica_cartella(cartella=None):
    """Voci dei file data/fonti/*.json (uno per area o per ente). File senza voci: infrastruttura pronta, nessun dato."""
    cartella = cartella or os.path.join(DATA, "fonti")
    voci = []
    for p in sorted(glob.glob(os.path.join(cartella, "*.json"))):
        d = _json(p)
        for v in d.get("voci", []):
            voci.append(normalizza(v, "fonti/" + os.path.basename(p)))
    return voci


def controlla_voce(v):
    """Errori di completezza e coerenza di una voce già normalizzata (lista vuota = voce corretta)."""
    e = []
    nome = v.get("id") or v.get("tema") or "?"
    for c in CAMPI_OBBLIGATORI:
        if c == "fonte_url" and v.get("tipo_fonte") == "procedura_studio":
            continue  # le procedure interne non hanno un indirizzo web
        if v.get(c) in (None, "", []):
            e.append(f"{nome}: campo '{c}' mancante")
    for a in v.get("aree", []):
        if a not in AREE:
            e.append(f"{nome}: area '{a}' sconosciuta")
    if v.get("tipo_fonte") not in TIPI:
        e.append(f"{nome}: tipo di fonte '{v.get('tipo_fonte')}' sconosciuto")
    if v.get("stato") not in STATI:
        e.append(f"{nome}: stato '{v.get('stato')}' sconosciuto")
    if v.get("ambito") not in AMBITI:
        e.append(f"{nome}: ambito '{v.get('ambito')}' non valido")
    if v.get("ambito") == "territoriale" and not v.get("territorio"):
        e.append(f"{nome}: fonte territoriale senza territorio")
    if v.get("ambito") == "nazionale" and v.get("territorio"):
        e.append(f"{nome}: fonte nazionale con territorio indicato")
    if v.get("fonte_url") and not str(v["fonte_url"]).startswith("https://"):
        e.append(f"{nome}: indirizzo della fonte non https")
    for c in CAMPI_DATA:
        if v.get(c) and not data_iso(v[c]):
            e.append(f"{nome}: data '{c}' non valida ({v[c]})")
    for m in v.get("modifiche", []):
        if not data_iso(m.get("data")):
            e.append(f"{nome}: modifica senza data valida")
    d1, d2 = data_iso(v.get("in_vigore_dal")), data_iso(v.get("abrogato_il"))
    if d1 and d2 and d2 < d1:
        e.append(f"{nome}: abrogazione precedente alla decorrenza")
    if data_iso(v.get("verificato_il")) and data_iso(v["verificato_il"]) > date.today():
        e.append(f"{nome}: data di verifica nel futuro")
    if v.get("tipo_fonte") == "procedura_studio" and v.get("aree") != ["studio"]:
        e.append(f"{nome}: le procedure dello Studio vanno nell'area 'studio'")
    if v.get("stato") == "procedura_approvata" and v.get("tipo_fonte") != "procedura_studio":
        e.append(f"{nome}: stato 'procedura_approvata' valido solo per le procedure dello Studio")
    return e


def controlla(voci):
    errori = []
    visti = set()
    for v in voci:
        errori += controlla_voce(v)
        if v.get("id") in visti:
            errori.append(f"{v.get('id')}: identificativo duplicato")
        visti.add(v.get("id"))
    return errori


def fonti_ufficiali(area=None):
    """Registro dei siti ufficiali da consultare (solo indirizzi e competenze, nessun contenuto)."""
    out = [f for f in REGISTRO["fonti"] if area is None or area in f["aree"]]
    return out


def dove_verificare(area, tipo):
    """Nomi delle fonti ufficiali per un'area e un tipo di fonte."""
    return [f["nome"] for f in REGISTRO["fonti"] if (area is None or area in f["aree"]) and tipo in f["tipi"]]
