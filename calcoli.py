"""Calcolatori dello Studio: busta paga, vertenze, pensioni.
Tutti i parametri normativi stanno in data/parametri.json e data/ccnl.json."""
import calendar
import json
import os
import re
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))


def _carica(nome):
    with open(os.path.join(BASE, "data", nome), encoding="utf-8") as f:
        return json.load(f)


PAR = _carica("parametri.json")
CCNL = {k: v for k, v in _carica("ccnl.json").items() if not k.startswith("_")}


# ---------- utilità ----------
def num(v, default=0.0):
    if v is None or v == "":
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("€", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"Valore numerico non valido: '{v}'")


def importo(v):
    """Come num(), ma per importi in euro scritti a mano: "2.283" o "1.234.567"
    (solo punti a gruppi di 3 cifre, senza virgola) sono separatori delle migliaia.
    Numeri già numerici restano invariati; vuoto o None valgono 0."""
    if v is None or isinstance(v, (int, float)):
        return num(v)
    s = str(v).strip().replace("€", "").replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    return num(s)


def data(v, nome="data"):
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{nome}: formato non valido (atteso AAAA-MM-GG): '{v}'")


def add_months(d, n):
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def fine_mese(y, m):
    return date(y, m, calendar.monthrange(y, m)[1])


def primo_mese_successivo(d):
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def eur(x):
    return round(x + 1e-9, 2)


# ---------- fisco ----------
def irpef_lorda(imponibile):
    tot, prec = 0.0, 0.0
    for lim, aliquota in PAR["irpef"]["scaglioni"]:
        tetto = imponibile if lim is None else min(imponibile, lim)
        if tetto > prec:
            tot += (tetto - prec) * aliquota
        if lim is None or imponibile <= lim:
            break
        prec = lim
    return tot


def detrazione_lavoro_dipendente(r, tempo_determinato=False):
    p = PAR["detrazione_lavoro_dipendente"]
    if r <= 0:
        return 0.0
    if r <= p["soglia1"]:
        d = p["max"]
        return max(d, p["minimo_tempo_determinato"] if tempo_determinato else p["minimo"])
    if r <= p["soglia2"]:
        return p["base2"] + p["extra2"] * (p["soglia2"] - r) / (p["soglia2"] - p["soglia1"])
    if r <= p["soglia3"]:
        return p["base2"] * (p["soglia3"] - r) / (p["soglia3"] - p["soglia2"])
    return 0.0


def inps_dipendente(imponibile_mensile):
    i = PAR["inps"]
    soglia_m = i["soglia_prima_fascia_annua"] / 12
    c = imponibile_mensile * i["aliquota_dipendente"]
    if imponibile_mensile > soglia_m:
        c += (imponibile_mensile - soglia_m) * i["aliquota_aggiuntiva"]
    return c


# ---------- CCNL ----------
def elenco_ccnl():
    out = []
    for k, c in CCNL.items():
        ultima = max(c["tabelle"], key=lambda t: t["dal"])
        out.append({
            "chiave": k, "nome": c["nome"], "stato": c["stato"], "fonte": c["fonte"],
            "mensilita": c["mensilita"], "livelli": list(ultima["minimi"].keys()),
            "scatti": c["scatti"],
        })
    return out


def _tabella(chiave, periodo):
    if chiave not in CCNL:
        raise ValueError(f"CCNL sconosciuto: {chiave}")
    c = CCNL[chiave]
    valide = [t for t in c["tabelle"] if t["dal"] <= periodo + "-01"]
    if not valide:
        primo = min(t["dal"] for t in c["tabelle"])
        raise ValueError(
            f"Nessuna tabella caricata per {periodo} (la prima disponibile decorre dal {primo}). "
            "Aggiungere la tabella storica in data/ccnl.json oppure usare l'inserimento manuale.")
    return c, max(valide, key=lambda t: t["dal"])


# ---------- BUSTA PAGA ----------
def verifica_busta(d):
    avvisi = []
    periodo = str(d.get("periodo", ""))[:7]
    if len(periodo) != 7:
        raise ValueError("Indicare il mese di competenza (AAAA-MM).")
    anno_m = int(periodo[:4]), int(periodo[5:7])
    chiave = d.get("ccnl", "manuale")
    scatti = int(num(d.get("scatti"), 0))
    pt = num(d.get("percentuale_part_time"), 100) / 100
    if not 0 < pt <= 1:
        raise ValueError("Percentuale part-time non valida.")
    mens = int(num(d.get("mensilita"), 13))

    if chiave == "manuale":
        minimo = num(d.get("minimo_manuale"))
        v_scatto = num(d.get("valore_scatto_manuale"))
        fonte = "Valori inseriti manualmente"
        if minimo <= 0:
            raise ValueError("Inserire il minimo tabellare (CCNL manuale).")
    else:
        c, t = _tabella(chiave, periodo)
        liv = str(d.get("livello"))
        if liv not in t["minimi"]:
            raise ValueError(f"Livello '{liv}' non presente nella tabella.")
        minimo, v_scatto = t["minimi"][liv], t["valore_scatto"].get(liv, 0)
        fonte = f"{c['nome']} – tabella dal {t['dal']} – {c['fonte']}"
        if not d.get("mensilita"):
            mens = c["mensilita"]
        if c["stato"] != "fonte_secondaria":
            avvisi.append("TABELLA NON VERIFICATA: i minimi di questo CCNL provengono dal vecchio file e non sono stati controllati. Non usare l'esito come riscontro definitivo.")
        else:
            avvisi.append("Tabella tratta da fonte secondaria: confrontarla con il testo ufficiale del CCNL prima di contestare differenze.")
        sc = c["scatti"]
        if sc["max"] and scatti > sc["max"]:
            avvisi.append(f"Scatti indicati ({scatti}) superiori al massimo previsto ({sc['max']}).")
        if d.get("data_assunzione") and sc["ogni_anni"]:
            ass = data(d["data_assunzione"], "data assunzione")
            fine = fine_mese(*anno_m)
            anni = fine.year - ass.year - ((fine.month, fine.day) < (ass.month, ass.day))
            maturati = min(sc["max"], max(0, anni // sc["ogni_anni"]))
            if maturati != scatti:
                avvisi.append(f"Dall'anzianità ({anni} anni) risulterebbero {maturati} scatti maturati, ne sono stati indicati {scatti}. Verificare eventuali assorbimenti o date di maturazione.")

    superminimo = num(d.get("superminimo"))
    altre = num(d.get("altre_voci_fisse"))
    base = (minimo + scatti * v_scatto) * pt
    dovuto = base + superminimo + altre
    lordo = num(d.get("lordo_busta"))
    if lordo <= 0:
        raise ValueError("Inserire la retribuzione lorda mensile risultante in busta.")
    diff = lordo - dovuto

    if diff < -0.01:
        esito = f"INFERIORE al dovuto di € {eur(-diff):.2f} lordi nel mese."
        livello = "errore"
    elif diff > 0.01:
        esito = f"SUPERIORE al dovuto di € {eur(diff):.2f}: verificare altre voci (superminimo non indicato, straordinari, premi) o assorbimenti."
        livello = "attenzione"
    else:
        esito = "CONFORME al dovuto indicato."
        livello = "ok"

    # contributi
    inps_atteso = inps_dipendente(lordo)
    inps_tratt = d.get("inps_trattenuto")
    conf_inps = None
    if inps_tratt not in (None, ""):
        t_inps = num(inps_tratt)
        scost = t_inps - inps_atteso
        conf_inps = {"trattenuto": eur(t_inps), "atteso": eur(inps_atteso), "scostamento": eur(scost),
                     "ok": abs(scost) <= 0.05}
        if not conf_inps["ok"]:
            avvisi.append(f"Contributo INPS trattenuto diverso dall'atteso di € {eur(scost):.2f}: verificare imponibile (straordinari, arretrati, mensilità aggiuntive) o aliquote speciali.")

    # TFR e stima netto
    annuo = lordo * mens
    tfr = annuo / PAR["tfr"]["divisore"]
    i = PAR["inps"]
    inps_annuo = annuo * i["aliquota_dipendente"] + max(0, annuo - i["soglia_prima_fascia_annua"]) * i["aliquota_aggiuntiva"]
    imp = annuo - inps_annuo
    td = bool(d.get("tempo_determinato"))
    irpef = max(0.0, irpef_lorda(imp) - detrazione_lavoro_dipendente(imp, td))
    netto_medio = (annuo - inps_annuo - irpef) / mens
    avvisi.append("Il netto è una STIMA annualizzata: esclude addizionali, trattamento integrativo/ulteriore detrazione, detrazioni familiari, conguagli e ratei.")

    return {
        "periodo": periodo, "fonte": fonte, "mensilita": mens,
        "dovuto": {"minimo_tabellare": eur(minimo), "scatti": scatti, "valore_scatto": eur(v_scatto),
                   "base_proporzionata": eur(base), "superminimo": eur(superminimo),
                   "altre_voci": eur(altre), "totale": eur(dovuto)},
        "lordo_busta": eur(lordo), "differenza": eur(diff), "esito": esito, "livello": livello,
        "inps": conf_inps, "inps_atteso": eur(inps_atteso),
        "tfr_quota_annua": eur(tfr), "stima": {
            "lordo_annuo": eur(annuo), "inps_annuo": eur(inps_annuo), "irpef_netta_annua": eur(irpef),
            "netto_medio_mensile": eur(netto_medio)},
        "avvisi": avvisi,
    }


# ---------- VERTENZE ----------
def interessi_legali(capitale, da, a, avvisi):
    """Interessi legali semplici sul capitale, dal giorno successivo a 'da' fino ad 'a' compreso."""
    tassi = PAR["interessi_legali"]
    tot = 0.0
    for y in range(da.year, a.year + 1):
        ini = max(da, date(y - 1, 12, 31))
        fin = min(a, date(y, 12, 31))
        giorni = (fin - ini).days
        if giorni <= 0:
            continue
        if str(y) not in tassi:
            ultimo = max(tassi, key=int)
            msg = f"Tasso legale {y} non presente in parametri.json: usato quello del {ultimo}."
            if msg not in avvisi:
                avvisi.append(msg)
            tasso = tassi[ultimo]
        else:
            tasso = tassi[str(y)]
        tot += capitale * tasso / 100 * giorni / (366 if calendar.isleap(y) else 365)
    return tot


def vertenza(d):
    avvisi = []
    righe_in = d.get("righe") or []
    if not righe_in:
        raise ValueError("Inserire almeno una riga (periodo; dovuto; percepito).")
    mens = num(d.get("mensilita"), 13)
    data_calc = data(d.get("data_calcolo") or date.today().isoformat(), "data calcolo")
    interr = d.get("data_interruzione")
    interr = data(interr, "data messa in mora") if interr else None
    riv_pct = num(d.get("rivalutazione_pct"), 0)
    taglio = None
    if interr:
        try:
            taglio = interr.replace(year=interr.year - 5)
        except ValueError:
            taglio = interr.replace(year=interr.year - 5, day=28)
    else:
        avvisi.append("Data di messa in mora non indicata: la prescrizione quinquennale NON è stata verificata.")

    righe, tot = [], {"diff_mensile": 0.0, "con_ratei": 0.0, "interessi": 0.0, "prescritto": 0.0}
    for r in righe_in:
        per = str(r["periodo"])[:7]
        y, m = int(per[:4]), int(per[5:7])
        dov, perc = importo(r["dovuto"]), importo(r["percepito"])
        diff = dov - perc
        con_ratei = diff * mens / 12
        scad = fine_mese(y, m)
        presc = bool(taglio and scad < taglio)
        inte = interessi_legali(con_ratei, scad, data_calc, avvisi) if con_ratei > 0 else 0.0
        righe.append({"periodo": per, "dovuto": eur(dov), "percepito": eur(perc), "differenza": eur(diff),
                      "con_ratei": eur(con_ratei), "interessi": eur(inte), "prescritto": presc})
        tot["diff_mensile"] += diff
        tot["con_ratei"] += con_ratei
        tot["interessi"] += inte
        if presc:
            tot["prescritto"] += con_ratei
    tfr = tot["con_ratei"] / PAR["tfr"]["divisore"]
    netto_presc = tot["con_ratei"] - tot["prescritto"]
    riv = netto_presc * riv_pct / 100
    avvisi += [
        "Ratei di 13ª/14ª calcolati pro quota mensile (differenza × mensilità / 12).",
        "Interessi legali semplici sul capitale non rivalutato; rivalutazione monetaria (ex art. 429, c. 3 c.p.c.) solo se indicata come % complessiva, ricavata dagli indici ISTAT FOI.",
        "TFR: differenze con ratei ÷ 13,5, senza rivalutazione né imposta sostitutiva; la prescrizione del TFR decorre dalla cessazione del rapporto.",
        "Verificare sempre la giurisprudenza sul decorso della prescrizione in corso di rapporto (regime di stabilità).",
    ]
    return {
        "righe": righe,
        "totali": {"differenze_mensili": eur(tot["diff_mensile"]), "con_ratei": eur(tot["con_ratei"]),
                   "prescritto": eur(tot["prescritto"]), "esigibile": eur(netto_presc),
                   "interessi_totali": eur(tot["interessi"]),
                   "interessi_su_esigibile": eur(sum(x["interessi"] for x in righe if not x["prescritto"])),
                   "rivalutazione": eur(riv), "tfr_differenza": eur(tfr)},
        "data_calcolo": data_calc.isoformat(),
        "limite_prescrizione": taglio.isoformat() if taglio else None,
        "avvisi": avvisi,
    }


# ---------- PENSIONI ----------
def _eta_mesi(nascita, d):
    """Età in mesi interi compiuti (conteggio anagrafico, usato per i dati mostrati)."""
    return (d.year - nascita.year) * 12 + d.month - nascita.month - (1 if d.day < nascita.day else 0)


def _mesi_maturati(inizio, d):
    """Mesi interi trascorsi ai fini della maturazione dei requisiti: se nel mese manca
    il giorno corrispondente (es. 31), il mese si compie l'ultimo giorno del mese (art. 2963 c.c.)."""
    incompleto = d.day < inizio.day and d.day != calendar.monthrange(d.year, d.month)[1]
    return (d.year - inizio.year) * 12 + d.month - inizio.month - (1 if incompleto else 0)


def _primo_anno_requisiti(P):
    return max(min(int(k) for k in P["vecchiaia_eta_mesi"]),
               min(int(k) for k in P["anticipata_contributi_mesi"]))


def _req(tabella, anno):
    """Requisito dell'anno; dopo l'ultimo anno in tabella vale l'ultimo (con avviso).
    Gli anni precedenti al primo anno in tabella non sono gestiti."""
    anni = [int(k) for k in tabella]
    if anno < min(anni):
        raise ValueError(f"Requisiti pensionistici per il {anno} non presenti in parametri.json.")
    return tabella[str(min(anno, max(anni)))]


def _fmt_mesi(m):
    return f"{m // 12} anni" + (f" e {m % 12} mesi" if m % 12 else "")


def pensione(d):
    P = PAR["pensioni"]
    sesso = str(d.get("sesso", "")).upper()[:1]
    if sesso not in ("M", "F"):
        raise ValueError("Indicare il sesso (M/F).")
    nascita = data(d.get("data_nascita"), "data di nascita")
    rif = data(d.get("data_riferimento") or date.today().isoformat(), "data di riferimento")
    primo = _primo_anno_requisiti(P)
    if rif.year < primo:
        raise ValueError(
            f"Data di riferimento {rif.strftime('%d/%m/%Y')} non gestita: i requisiti pensionistici "
            f"verificati in parametri.json partono dal {primo}. Per date precedenti "
            "verificare i requisiti sulle circolari INPS.")
    c0 = int(num(d.get("contributi_anni"))) * 12 + int(num(d.get("contributi_mesi")))
    puro = bool(d.get("contributivo_puro"))
    avvisi = [
        "Ipotesi: contribuzione continuativa di 12 mesi l'anno dalla data di riferimento, senza carriera discontinua né maggiorazioni.",
        f"Requisiti: {P['fonte']}",
        "Non considerati: lavori gravosi/usuranti, precoci, invalidità, APE sociale, quote, Opzione Donna, riscatti, cumulo e totalizzazione.",
    ]

    def cerca(ok):
        # giorno per giorno: età e contributi maturano in giorni del mese diversi
        for g in range(0, 366 * 45):
            dt = rif + timedelta(days=g)
            if ok(dt, c0 + _mesi_maturati(rif, dt)):
                return dt
        return None

    # vecchiaia
    v_eta = P["vecchiaia_eta_mesi"]
    vecc = cerca(lambda dt, c: _mesi_maturati(nascita, dt) >= _req(v_eta, dt.year) and c >= P["vecchiaia_contributi_mesi"])
    # anticipata
    a_con = P["anticipata_contributi_mesi"]
    anti = cerca(lambda dt, c: c >= _req(a_con, dt.year)[sesso])
    ris = {"vecchiaia": None, "anticipata": None, "alternativa_contributiva": None}
    if vecc:
        ris["vecchiaia"] = {"maturazione": vecc.isoformat(), "decorrenza": primo_mese_successivo(vecc).isoformat(),
                            "requisito": f"{_fmt_mesi(_req(v_eta, vecc.year))} di età e 20 anni di contributi"}
    if anti:
        fin = add_months(anti, P["finestra_anticipata_mesi"])
        ris["anticipata"] = {"maturazione": anti.isoformat(), "decorrenza": primo_mese_successivo(fin).isoformat(),
                             "requisito": f"{_fmt_mesi(_req(a_con, anti.year)[sesso])} di contributi (finestra {P['finestra_anticipata_mesi']} mesi)"}
    if puro:
        alt = P["contributiva_alternativa"]
        a = cerca(lambda dt, c: _mesi_maturati(nascita, dt) >= _req(v_eta, dt.year) + alt["eta_extra_mesi"] and c >= alt["contributi_effettivi_mesi"])
        if a:
            ris["alternativa_contributiva"] = {"maturazione": a.isoformat(), "decorrenza": primo_mese_successivo(a).isoformat(),
                                               "requisito": f"{_fmt_mesi(_req(v_eta, a.year) + alt['eta_extra_mesi'])} di età e 5 anni di contributi effettivi"}
        avvisi.append("Contributivo puro (primo versamento dal 1/1/1996): la vecchiaia ordinaria richiede un assegno almeno pari all'assegno sociale; verificare l'importo con la simulazione INPS.")
    anni_prov = [a for a in P["provvisori"] if (vecc and str(vecc.year) >= a) or (anti and str(anti.year) >= a)]
    if anni_prov:
        avvisi.append("Il calcolo usa requisiti PROVVISORI (2028) o stimati: dal 2029 gli adeguamenti non sono ancora noti.")
    return {"eta_attuale_mesi": _eta_mesi(nascita, rif), "contributi_attuali_mesi": c0, "risultati": ris, "avvisi": avvisi}
