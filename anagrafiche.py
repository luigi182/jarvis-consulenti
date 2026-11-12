"""Anagrafiche dello Studio: aziende (con sedi e referenti), lavoratori e rapporti di lavoro.

Regole di conservazione dei dati:
- non esistono funzioni di cancellazione: aziende, sedi e referenti si disattivano o si chiudono con una data;
- ogni modifica è annotata nel registro con i valori precedenti;
- le condizioni di un rapporto (contratto, livello, orario...) non si modificano: ogni assunzione,
  proroga, trasformazione, variazione o cessazione è un nuovo evento che conserva la situazione
  completa da quella data. Un evento sbagliato si annulla (con motivazione) e resta visibile.
"""
from datetime import date

import calcoli
import db
import validazioni as V

# ---------- valori ammessi ----------
TIPI_DATORE = {"impresa": "Impresa / società", "professionista": "Studio professionale",
               "domestico": "Datore di lavoro domestico", "ente": "Ente / associazione", "altro": "Altro"}
TIPI_SEDE = {"legale": "Sede legale", "operativa": "Sede operativa", "amministrativa": "Sede amministrativa", "altro": "Altra sede"}
RUOLI = {"rappresentante_legale": "Rappresentante legale", "amministratore": "Amministratore", "referente": "Referente",
         "socio": "Socio", "altro": "Altro"}
TIPOLOGIE = {"tempo_indeterminato": "Tempo indeterminato", "tempo_determinato": "Tempo determinato",
             "apprendistato": "Apprendistato", "intermittente": "Intermittente", "altro": "Altro"}
QUALIFICHE = {"operaio": "Operaio", "impiegato": "Impiegato", "quadro": "Quadro", "dirigente": "Dirigente",
              "apprendista": "Apprendista", "altro": "Altro"}
ORARI = {"tempo_pieno": "Tempo pieno", "part_time_orizzontale": "Part-time orizzontale",
         "part_time_verticale": "Part-time verticale", "part_time_misto": "Part-time misto"}
EVENTI = {"assunzione": "Assunzione", "proroga": "Proroga", "trasformazione": "Trasformazione",
          "variazione": "Variazione (livello, qualifica, orario, CCNL…)", "cessazione": "Cessazione"}

# condizioni del rapporto conservate in ogni evento
CONDIZIONI = ("tipologia_contratto", "data_fine_termine", "ccnl_chiave", "ccnl_descrizione", "livello", "qualifica",
              "mansione", "tipo_orario", "ore_settimanali", "percentuale_part_time", "superminimo")


# ---------- utilità ----------
def _t(v):
    """Testo ripulito; stringa vuota -> None."""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _scelta(v, ammessi, campo, obbligatorio=False):
    v = _t(v)
    if v is None:
        if obbligatorio:
            raise ValueError(f"{campo}: valore obbligatorio.")
        return None
    if v not in ammessi:
        raise ValueError(f"{campo}: valore non ammesso '{v}'.")
    return v


def _numero(v, campo, minimo=None, massimo=None):
    if v in (None, ""):
        return None
    try:
        n = calcoli.num(v)
    except ValueError:
        raise ValueError(f"{campo}: numero non valido '{v}'.")
    if (minimo is not None and n < minimo) or (massimo is not None and n > massimo):
        raise ValueError(f"{campo}: valore fuori intervallo ({n}).")
    return n


def _id(v, campo="id"):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"{campo} mancante o non valido.")
    if n <= 0:
        raise ValueError(f"{campo} non valido.")
    return n


def _differenze(prima, dopo):
    p = {k: prima.get(k) for k in dopo if prima.get(k) != dopo[k]}
    return p, {k: dopo[k] for k in p}


def _uno(conn, sql, par=()):
    return conn.execute(sql, par).fetchone()


def _tutti(conn, sql, par=()):
    return conn.execute(sql, par).fetchall()


def _ccnl(v):
    v = _t(v)
    if v and v not in calcoli.CCNL:
        raise ValueError(f"CCNL '{v}' non presente in data/ccnl.json: indicarlo nella descrizione libera.")
    return v


def _aggiorna(conn, tabella, rid, valori, entita, azienda_id=None, lavoratore_id=None):
    prima = _uno(conn, f"SELECT * FROM {tabella} WHERE id = ?", (rid,))
    if not prima:
        raise ValueError(f"{entita}: record {rid} non trovato.")
    vecchi, nuovi = _differenze(prima, valori)
    if nuovi:
        nuovi_sql = {**nuovi, "modificato_il": db.adesso()}
        conn.execute(f"UPDATE {tabella} SET {', '.join(k + ' = ?' for k in nuovi_sql)} WHERE id = ?",
                     (*nuovi_sql.values(), rid))
        db.registra(conn, "modifica", entita, rid, vecchi, nuovi,
                    azienda_id=azienda_id if azienda_id is not None else prima.get("azienda_id"),
                    lavoratore_id=lavoratore_id)
    return prima


def _inserisci(conn, tabella, valori, entita, azienda_id=None, lavoratore_id=None):
    ora = db.adesso()
    valori = {**valori, "creato_il": ora}
    if tabella != "eventi_rapporto":
        valori["modificato_il"] = ora
    cur = conn.execute(f"INSERT INTO {tabella} ({', '.join(valori)}) VALUES ({', '.join('?' * len(valori))})",
                       tuple(valori.values()))
    rid = cur.lastrowid
    db.registra(conn, "inserimento", entita, rid, None,
                {k: v for k, v in valori.items() if v is not None and k not in ("creato_il", "modificato_il")},
                azienda_id=azienda_id if azienda_id is not None else (rid if tabella == "aziende" else None),
                lavoratore_id=lavoratore_id if lavoratore_id is not None else (rid if tabella == "lavoratori" else None))
    return rid


def _con_esistente(tabella, d):
    """In modifica, i campi non inviati restano quelli già salvati (mai azzerati per omissione)."""
    if not d.get("id"):
        return d
    conn = db.attiva() or db.connetti()
    try:
        esistente = _uno(conn, f"SELECT * FROM {tabella} WHERE id = ?", (_id(d["id"]),))
    finally:
        if conn is not db.attiva():
            conn.close()
    if not esistente:
        raise ValueError("Record da modificare non trovato.")
    return {**esistente, **d}


def _unico(conn, tabella, campo, valore, escludi_id, messaggio):
    if valore and _uno(conn, f"SELECT id FROM {tabella} WHERE {campo} = ? AND id != ?", (valore, escludi_id or 0)):
        raise ValueError(messaggio)


# ---------- AZIENDE ----------
def _valori_azienda(d):
    v = {
        "denominazione": _t(d.get("denominazione")),
        "forma_giuridica": _t(d.get("forma_giuridica")),
        "tipo_datore": _scelta(d.get("tipo_datore") or "impresa", TIPI_DATORE, "Tipo datore"),
        "codice_fiscale": V.controlla_cf_azienda(d["codice_fiscale"]) if _t(d.get("codice_fiscale")) else None,
        "partita_iva": V.controlla_piva(d["partita_iva"]) if _t(d.get("partita_iva")) else None,
        "codice_ateco": _t(d.get("codice_ateco")),
        "matricola_inps": V.pulisci(d.get("matricola_inps")) or None,
        "pat_inail": V.pulisci(d.get("pat_inail")) or None,
        "cassa_edile": _t(d.get("cassa_edile")),
        "email": V.controlla_email(d.get("email")),
        "pec": V.controlla_email(d.get("pec"), "PEC"),
        "telefono": _t(d.get("telefono")),
        "sito": _t(d.get("sito")),
        "ccnl_chiave": _ccnl(d.get("ccnl_chiave")),
        "ccnl_descrizione": _t(d.get("ccnl_descrizione")),
        "ccnl_codice_cnel": V.pulisci(d.get("ccnl_codice_cnel")) or None,
        "info_contrattuali": _t(d.get("info_contrattuali")),
        "note": _t(d.get("note")),
        "attiva": 0 if d.get("attiva") in (False, 0, "0", "false") else 1,
    }
    if not v["denominazione"]:
        raise ValueError("Denominazione / ragione sociale obbligatoria.")
    return v


def salva_azienda(d, fonte="manuale"):
    d = _con_esistente("aziende", d)
    v = _valori_azienda(d)
    rid = d.get("id")
    avvisi = []
    if not v["codice_fiscale"] and not v["partita_iva"]:
        avvisi.append("Codice fiscale e partita IVA non indicati: l'azienda non potrà essere riconosciuta nelle importazioni.")
    with db.transazione() as conn:
        _unico(conn, "aziende", "codice_fiscale", v["codice_fiscale"], rid,
               f"Esiste già un'azienda con codice fiscale {v['codice_fiscale']}.")
        if v["partita_iva"] and _uno(conn, "SELECT id FROM aziende WHERE partita_iva = ? AND id != ?", (v["partita_iva"], rid or 0)):
            avvisi.append(f"Attenzione: un'altra azienda ha la stessa partita IVA {v['partita_iva']}.")
        if rid:
            rid = _id(rid)
            _aggiorna(conn, "aziende", rid, v, "azienda", azienda_id=rid)
        else:
            rid = _inserisci(conn, "aziende", {**v, "fonte": fonte}, "azienda")
    return {"id": rid, "avvisi": avvisi}


def cerca_aziende(d):
    q = _t(d.get("q")) or ""
    solo_attive = bool(d.get("solo_attive"))
    sql = ("SELECT a.id, a.denominazione, a.codice_fiscale, a.partita_iva, a.attiva, a.ccnl_chiave, a.ccnl_descrizione, "
           "(SELECT s.comune FROM sedi s WHERE s.azienda_id = a.id AND s.tipo = 'legale' AND s.attiva = 1 ORDER BY s.id DESC LIMIT 1) AS comune, "
           "(SELECT COUNT(*) FROM rapporti r WHERE r.azienda_id = a.id AND r.annullato = 0 AND r.data_cessazione IS NULL) AS in_forza "
           "FROM aziende a WHERE 1=1")
    par = []
    if q:
        sql += " AND (a.denominazione LIKE ? COLLATE NOCASE OR a.codice_fiscale LIKE ? OR a.partita_iva LIKE ?)"
        par += [f"%{q}%", f"{V.pulisci(q)}%", f"{V.pulisci(q)}%"]
    if solo_attive:
        sql += " AND a.attiva = 1"
    sql += " ORDER BY a.denominazione COLLATE NOCASE LIMIT 200"
    conn = db.connetti()
    try:
        return {"aziende": _tutti(conn, sql, par)}
    finally:
        conn.close()


def scheda_azienda(d):
    aid = _id(d.get("id"))
    conn = db.connetti()
    try:
        az = _uno(conn, "SELECT * FROM aziende WHERE id = ?", (aid,))
        if not az:
            raise ValueError("Azienda non trovata.")
        sedi = _tutti(conn, "SELECT * FROM sedi WHERE azienda_id = ? ORDER BY attiva DESC, tipo = 'legale' DESC, id", (aid,))
        referenti = _tutti(conn, "SELECT * FROM referenti WHERE azienda_id = ? ORDER BY attivo DESC, ruolo = 'rappresentante_legale' DESC, cognome", (aid,))
        rapporti = _tutti(conn, "SELECT r.*, l.cognome, l.nome, l.codice_fiscale FROM rapporti r JOIN lavoratori l ON l.id = r.lavoratore_id "
                                "WHERE r.azienda_id = ? AND r.annullato = 0 ORDER BY r.data_cessazione IS NOT NULL, l.cognome, l.nome", (aid,))
        for r in rapporti:
            r["condizioni"] = _condizioni(conn, r["id"])
        registro = _tutti(conn, "SELECT quando, utente, azione, entita, entita_id, prima, dopo FROM registro "
                                "WHERE azienda_id = ? ORDER BY id DESC LIMIT 100", (aid,))
    finally:
        conn.close()
    return {"azienda": az, "sedi": sedi, "referenti": referenti,
            "in_forza": [r for r in rapporti if not r["data_cessazione"]],
            "cessati": [r for r in rapporti if r["data_cessazione"]], "registro": registro}


def _azienda_esiste(conn, aid):
    if not _uno(conn, "SELECT id FROM aziende WHERE id = ?", (aid,)):
        raise ValueError("Azienda non trovata.")


# ---------- SEDI ----------
def salva_sede(d):
    d = _con_esistente("sedi", d)
    v = {
        "tipo": _scelta(d.get("tipo"), TIPI_SEDE, "Tipo sede", True),
        "denominazione": _t(d.get("denominazione")),
        "indirizzo": _t(d.get("indirizzo")),
        "cap": V.controlla_cap(d.get("cap")),
        "comune": _t(d.get("comune")),
        "provincia": V.controlla_provincia(d.get("provincia")),
        "nazione": V.pulisci(d.get("nazione")) or "IT",
        "telefono": _t(d.get("telefono")),
        "email": V.controlla_email(d.get("email")),
        "dal": V.controlla_data(d.get("dal"), "Attiva dal"),
        "al": V.controlla_data(d.get("al"), "Attiva fino al"),
        "note": _t(d.get("note")),
    }
    if not (v["indirizzo"] or v["comune"]):
        raise ValueError("Indicare almeno indirizzo o comune della sede.")
    if v["dal"] and v["al"] and v["al"] < v["dal"]:
        raise ValueError("La data di chiusura della sede precede quella di inizio.")
    v["attiva"] = 0 if v["al"] and v["al"] <= date.today().isoformat() else 1
    avvisi = []
    with db.transazione() as conn:
        if d.get("id"):
            rid = _id(d["id"])
            prima = _uno(conn, "SELECT azienda_id FROM sedi WHERE id = ?", (rid,))
            if not prima:
                raise ValueError("Sede non trovata.")
            _aggiorna(conn, "sedi", rid, v, "sede", azienda_id=prima["azienda_id"])
        else:
            aid = _id(d.get("azienda_id"), "azienda_id")
            _azienda_esiste(conn, aid)
            if v["tipo"] == "legale" and v["attiva"]:
                # una sola sede legale attiva: la precedente viene chiusa, non cancellata
                for s in _tutti(conn, "SELECT id FROM sedi WHERE azienda_id = ? AND tipo = 'legale' AND attiva = 1", (aid,)):
                    _aggiorna(conn, "sedi", s["id"], {"attiva": 0, "al": v["dal"] or date.today().isoformat()}, "sede", azienda_id=aid)
                    avvisi.append("La sede legale precedente è stata chiusa e resta nello storico.")
            rid = _inserisci(conn, "sedi", {**v, "azienda_id": aid}, "sede", azienda_id=aid)
    return {"id": rid, "avvisi": avvisi}


# ---------- REFERENTI ----------
def salva_referente(d):
    d = _con_esistente("referenti", d)
    v = {
        "ruolo": _scelta(d.get("ruolo"), RUOLI, "Ruolo", True),
        "cognome": _t(d.get("cognome")),
        "nome": _t(d.get("nome")),
        "codice_fiscale": V.controlla_cf_persona(d["codice_fiscale"]) if _t(d.get("codice_fiscale")) else None,
        "carica": _t(d.get("carica")),
        "email": V.controlla_email(d.get("email")),
        "telefono": _t(d.get("telefono")),
        "dal": V.controlla_data(d.get("dal"), "Dal"),
        "al": V.controlla_data(d.get("al"), "Al"),
        "note": _t(d.get("note")),
    }
    if not v["cognome"]:
        raise ValueError("Cognome (o denominazione) del referente obbligatorio.")
    v["attivo"] = 0 if v["al"] and v["al"] <= date.today().isoformat() else 1
    with db.transazione() as conn:
        if d.get("id"):
            rid = _id(d["id"])
            prima = _uno(conn, "SELECT azienda_id FROM referenti WHERE id = ?", (rid,))
            if not prima:
                raise ValueError("Referente non trovato.")
            _aggiorna(conn, "referenti", rid, v, "referente", azienda_id=prima["azienda_id"])
        else:
            aid = _id(d.get("azienda_id"), "azienda_id")
            _azienda_esiste(conn, aid)
            rid = _inserisci(conn, "referenti", {**v, "azienda_id": aid}, "referente", azienda_id=aid)
    return {"id": rid, "avvisi": []}


# ---------- LAVORATORI ----------
def _valori_lavoratore(d):
    v = {
        "codice_fiscale": V.controlla_cf_persona(d.get("codice_fiscale")),
        "cognome": _t(d.get("cognome")),
        "nome": _t(d.get("nome")),
        "sesso": _scelta(V.pulisci(d.get("sesso")) or None, {"M": 1, "F": 1}, "Sesso"),
        "data_nascita": V.controlla_data(d.get("data_nascita"), "Data di nascita"),
        "comune_nascita": _t(d.get("comune_nascita")),
        "provincia_nascita": V.controlla_provincia(d.get("provincia_nascita")),
        "stato_nascita": _t(d.get("stato_nascita")),
        "cittadinanza": _t(d.get("cittadinanza")),
        "res_indirizzo": _t(d.get("res_indirizzo")), "res_cap": V.controlla_cap(d.get("res_cap")),
        "res_comune": _t(d.get("res_comune")), "res_provincia": V.controlla_provincia(d.get("res_provincia")),
        "dom_indirizzo": _t(d.get("dom_indirizzo")), "dom_cap": V.controlla_cap(d.get("dom_cap")),
        "dom_comune": _t(d.get("dom_comune")), "dom_provincia": V.controlla_provincia(d.get("dom_provincia")),
        "email": V.controlla_email(d.get("email")),
        "telefono": _t(d.get("telefono")),
        "note": _t(d.get("note")),
    }
    if not v["cognome"] or not v["nome"]:
        raise ValueError("Cognome e nome del lavoratore obbligatori.")
    avvisi = []
    dcf = V.dati_da_cf(v["codice_fiscale"])
    if dcf:
        if not v["sesso"]:
            v["sesso"] = dcf["sesso"]
        elif v["sesso"] != dcf["sesso"]:
            avvisi.append(f"Il sesso indicato ({v['sesso']}) non corrisponde al codice fiscale ({dcf['sesso']}).")
        if not v["data_nascita"]:
            v["data_nascita"] = dcf["data_nascita"]
        elif v["data_nascita"] != dcf["data_nascita"]:
            avvisi.append(f"La data di nascita indicata non corrisponde al codice fiscale ({dcf['data_nascita']}).")
    return v, avvisi


def salva_lavoratore(d, fonte="manuale"):
    d = _con_esistente("lavoratori", d)
    v, avvisi = _valori_lavoratore(d)
    with db.transazione() as conn:
        rid = _salva_lavoratore(conn, d.get("id"), v, fonte)
    return {"id": rid, "avvisi": avvisi}


def _salva_lavoratore(conn, rid, v, fonte):
    _unico(conn, "lavoratori", "codice_fiscale", v["codice_fiscale"], rid,
           f"Esiste già un lavoratore con codice fiscale {v['codice_fiscale']}.")
    if rid:
        rid = _id(rid)
        _aggiorna(conn, "lavoratori", rid, v, "lavoratore", lavoratore_id=rid)
        return rid
    return _inserisci(conn, "lavoratori", {**v, "fonte": fonte}, "lavoratore")


def cerca_lavoratori(d):
    q = _t(d.get("q")) or ""
    sql = ("SELECT l.id, l.cognome, l.nome, l.codice_fiscale, l.data_nascita, "
           "(SELECT GROUP_CONCAT(a.denominazione, ', ') FROM rapporti r JOIN aziende a ON a.id = r.azienda_id "
           " WHERE r.lavoratore_id = l.id AND r.annullato = 0 AND r.data_cessazione IS NULL) AS aziende_in_forza "
           "FROM lavoratori l WHERE 1=1")
    par = []
    if q:
        sql += " AND (l.codice_fiscale LIKE ? OR (l.cognome || ' ' || l.nome) LIKE ? COLLATE NOCASE OR (l.nome || ' ' || l.cognome) LIKE ? COLLATE NOCASE)"
        par += [f"{V.pulisci(q)}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY l.cognome COLLATE NOCASE, l.nome COLLATE NOCASE LIMIT 200"
    conn = db.connetti()
    try:
        return {"lavoratori": _tutti(conn, sql, par)}
    finally:
        conn.close()


def scheda_lavoratore(d):
    lid = _id(d.get("id"))
    conn = db.connetti()
    try:
        lav = _uno(conn, "SELECT * FROM lavoratori WHERE id = ?", (lid,))
        if not lav:
            raise ValueError("Lavoratore non trovato.")
        rapporti = _tutti(conn, "SELECT r.*, a.denominazione AS azienda FROM rapporti r JOIN aziende a ON a.id = r.azienda_id "
                                "WHERE r.lavoratore_id = ? ORDER BY r.annullato, r.data_assunzione DESC", (lid,))
        for r in rapporti:
            r["eventi"] = _tutti(conn, "SELECT * FROM eventi_rapporto WHERE rapporto_id = ? ORDER BY data_effetto, id", (r["id"],))
            r["condizioni"] = _condizioni(conn, r["id"])
        registro = _tutti(conn, "SELECT quando, utente, azione, entita, entita_id, prima, dopo FROM registro "
                                "WHERE lavoratore_id = ? ORDER BY id DESC LIMIT 100", (lid,))
    finally:
        conn.close()
    return {"lavoratore": lav, "rapporti": rapporti, "registro": registro}


# ---------- RAPPORTI DI LAVORO ----------
def _condizioni(conn, rapporto_id, alla_data=None):
    """Situazione del rapporto all'ultima data (o alla data indicata): ultimo evento valido."""
    sql = "SELECT * FROM eventi_rapporto WHERE rapporto_id = ? AND annullato = 0"
    par = [rapporto_id]
    if alla_data:
        sql += " AND data_effetto <= ?"
        par.append(alla_data)
    ev = _uno(conn, sql + " ORDER BY data_effetto DESC, id DESC LIMIT 1", par)
    if not ev:
        return None
    return {k: ev[k] for k in CONDIZIONI} | {"dal": ev["data_effetto"], "evento": ev["tipo"]}


def condizioni_alla_data(rapporto_id, alla_data):
    """Per i moduli futuri (paghe, vertenze): condizioni contrattuali vigenti a una data."""
    conn = db.connetti()
    try:
        return _condizioni(conn, _id(rapporto_id, "rapporto_id"), V.controlla_data(alla_data, "Data"))
    finally:
        conn.close()


def _valori_condizioni(d, base=None):
    """Nuova situazione completa = situazione precedente + campi indicati."""
    c = dict(base or {k: None for k in CONDIZIONI})
    lettori = {
        "tipologia_contratto": lambda x: _scelta(x, TIPOLOGIE, "Tipologia contrattuale"),
        "data_fine_termine": lambda x: V.controlla_data(x, "Data di fine del termine"),
        "ccnl_chiave": _ccnl,
        "ccnl_descrizione": _t, "livello": _t, "mansione": _t,
        "qualifica": lambda x: _scelta(x, QUALIFICHE, "Qualifica"),
        "tipo_orario": lambda x: _scelta(x, ORARI, "Tipo di orario"),
        "ore_settimanali": lambda x: _numero(x, "Ore settimanali", 0, 168),
        "percentuale_part_time": lambda x: _numero(x, "Percentuale part-time", 0, 100),
        "superminimo": lambda x: _numero(x, "Superminimo", 0),
    }
    for k, f in lettori.items():
        if k in d:
            c[k] = f(d[k])
    if c["tipo_orario"] == "tempo_pieno":
        c["percentuale_part_time"] = 100.0
    return {k: c[k] for k in CONDIZIONI}


def _avvisi_condizioni(c):
    avvisi = []
    if c["tipo_orario"] and c["tipo_orario"] != "tempo_pieno" and not (c["percentuale_part_time"] or c["ore_settimanali"]):
        avvisi.append("Part-time senza percentuale né ore settimanali: indicarle per i controlli in busta paga.")
    if not c["ccnl_chiave"] and not c["ccnl_descrizione"]:
        avvisi.append("CCNL non indicato.")
    return avvisi


def condizioni_assunzione(d, data_ass, predefiniti=None):
    """Controlla le condizioni iniziali di un rapporto senza scrivere nulla (usata anche dalle anteprime)."""
    c = _valori_condizioni(d, {k: None for k in CONDIZIONI} | (predefiniti or {}))
    if not c["tipologia_contratto"]:
        raise ValueError("Tipologia contrattuale obbligatoria.")
    if c["tipologia_contratto"] == "tempo_determinato" and not c["data_fine_termine"]:
        raise ValueError("Per il tempo determinato indicare la data di fine del termine.")
    if c["data_fine_termine"] and c["data_fine_termine"] <= data_ass:
        raise ValueError("La data di fine del termine deve essere successiva all'assunzione.")
    if c["tipologia_contratto"] == "tempo_indeterminato":
        c["data_fine_termine"] = None
    return c, _avvisi_condizioni(c)


def assumi(d, fonte="manuale"):
    """Crea il rapporto con l'evento di assunzione. Il lavoratore si indica con 'lavoratore_id'
    oppure con i dati anagrafici in 'lavoratore' (se il codice fiscale esiste già si usa quello)."""
    aid = _id(d.get("azienda_id"), "azienda_id")
    data_ass = V.controlla_data(d.get("data_assunzione"), "Data di assunzione")
    if not data_ass:
        raise ValueError("Data di assunzione obbligatoria.")
    avvisi = []
    with db.transazione() as conn:
        _azienda_esiste(conn, aid)
        az = _uno(conn, "SELECT ccnl_chiave, ccnl_descrizione FROM aziende WHERE id = ?", (aid,))
        if d.get("lavoratore_id"):
            lid = _id(d["lavoratore_id"], "lavoratore_id")
            if not _uno(conn, "SELECT id FROM lavoratori WHERE id = ?", (lid,)):
                raise ValueError("Lavoratore non trovato.")
        else:
            v, av = _valori_lavoratore(d.get("lavoratore") or {})
            esistente = _uno(conn, "SELECT id FROM lavoratori WHERE codice_fiscale = ?", (v["codice_fiscale"],))
            if esistente:
                lid = esistente["id"]
                avvisi.append("Lavoratore già presente in archivio: è stato collegato quello esistente senza modificarne i dati.")
            else:
                lid = _salva_lavoratore(conn, None, v, fonte)
                avvisi += av
        if _uno(conn, "SELECT id FROM rapporti WHERE lavoratore_id = ? AND azienda_id = ? AND annullato = 0 AND "
                      "(data_cessazione IS NULL OR data_cessazione >= ?)", (lid, aid, data_ass)):
            raise ValueError("Il lavoratore ha già un rapporto in corso con questa azienda in quella data.")
        sede_id = d.get("sede_id") or None
        if sede_id:
            sede_id = _id(sede_id, "sede_id")
            if not _uno(conn, "SELECT id FROM sedi WHERE id = ? AND azienda_id = ?", (sede_id, aid)):
                raise ValueError("La sede indicata non appartiene all'azienda.")
        c, av = condizioni_assunzione(d, data_ass, {"ccnl_chiave": az["ccnl_chiave"], "ccnl_descrizione": az["ccnl_descrizione"]})
        avvisi += av
        rid = _inserisci(conn, "rapporti", {"lavoratore_id": lid, "azienda_id": aid, "sede_id": sede_id,
                                            "matricola": _t(d.get("matricola")), "data_assunzione": data_ass,
                                            "fonte": fonte}, "rapporto", azienda_id=aid, lavoratore_id=lid)
        _inserisci(conn, "eventi_rapporto", {"rapporto_id": rid, "tipo": "assunzione", "data_effetto": data_ass,
                                             **c, "note": _t(d.get("note")), "fonte": fonte},
                   "evento_rapporto", azienda_id=aid, lavoratore_id=lid)
    return {"id": rid, "lavoratore_id": lid, "avvisi": avvisi}


def _rapporto(conn, rid):
    r = _uno(conn, "SELECT * FROM rapporti WHERE id = ?", (rid,))
    if not r:
        raise ValueError("Rapporto di lavoro non trovato.")
    if r["annullato"]:
        raise ValueError("Il rapporto è stato annullato.")
    return r


def _ultimo_evento(conn, rid):
    return _uno(conn, "SELECT * FROM eventi_rapporto WHERE rapporto_id = ? AND annullato = 0 "
                      "ORDER BY data_effetto DESC, id DESC LIMIT 1", (rid,))


def _mesi(da, a):
    d1, d2 = date.fromisoformat(da), date.fromisoformat(a)
    return (d2.year - d1.year) * 12 + d2.month - d1.month + (d2.day - d1.day) / 31


def aggiungi_evento(d):
    rid = _id(d.get("rapporto_id"), "rapporto_id")
    tipo = _scelta(d.get("tipo"), EVENTI, "Tipo di evento", True)
    if tipo == "assunzione":
        raise ValueError("L'assunzione si registra creando un nuovo rapporto.")
    data_ev = V.controlla_data(d.get("data_effetto"), "Data di effetto")
    if not data_ev:
        raise ValueError("Data di effetto obbligatoria.")
    avvisi = []
    with db.transazione() as conn:
        r = _rapporto(conn, rid)
        if r["data_cessazione"]:
            raise ValueError("Il rapporto è cessato: per registrare altri eventi annullare prima la cessazione.")
        ultimo = _ultimo_evento(conn, rid)
        if data_ev < ultimo["data_effetto"]:
            raise ValueError(f"La data di effetto non può precedere l'ultimo evento registrato ({ultimo['data_effetto']}). "
                             "Per correggere un evento precedente, annullare gli eventi successivi e registrarli di nuovo.")
        prec = {k: ultimo[k] for k in CONDIZIONI}
        campi = {k: d[k] for k in CONDIZIONI if k in d}
        motivo = None
        if tipo == "proroga":
            if prec["tipologia_contratto"] != "tempo_determinato":
                raise ValueError("La proroga è possibile solo per un rapporto a tempo determinato.")
            c = _valori_condizioni({"data_fine_termine": d.get("data_fine_termine")}, prec)
            if not c["data_fine_termine"] or c["data_fine_termine"] <= (prec["data_fine_termine"] or ""):
                raise ValueError("Indicare la nuova data di fine, successiva a quella attuale "
                                 f"({prec['data_fine_termine'] or 'non indicata'}).")
            n_proroghe = _uno(conn, "SELECT COUNT(*) AS n FROM eventi_rapporto WHERE rapporto_id = ? AND tipo = 'proroga' AND annullato = 0", (rid,))["n"] + 1
            if n_proroghe > 4:
                avvisi.append(f"Questa è la proroga n. {n_proroghe}: verificare il limite di 4 proroghe (art. 21 D.Lgs. 81/2015).")
            durata = _mesi(r["data_assunzione"], c["data_fine_termine"])
            if durata > 24:
                avvisi.append("Durata complessiva oltre 24 mesi: verificare i limiti dell'art. 19 D.Lgs. 81/2015 e del CCNL.")
            elif durata > 12:
                avvisi.append("Durata complessiva oltre 12 mesi: verificare la presenza delle condizioni (causali) dell'art. 19 D.Lgs. 81/2015.")
        elif tipo == "trasformazione":
            nuova = _scelta(d.get("tipologia_contratto"), TIPOLOGIE, "Nuova tipologia contrattuale", True)
            if nuova == prec["tipologia_contratto"]:
                raise ValueError("La trasformazione richiede una tipologia contrattuale diversa da quella attuale.")
            c = _valori_condizioni(campi, prec)
            if nuova == "tempo_indeterminato":
                c["data_fine_termine"] = None
            elif nuova == "tempo_determinato" and not c["data_fine_termine"]:
                raise ValueError("Per il tempo determinato indicare la data di fine del termine.")
        elif tipo == "variazione":
            campi.pop("tipologia_contratto", None)
            campi.pop("data_fine_termine", None)
            c = _valori_condizioni(campi, prec)
            if c == prec:
                raise ValueError("Nessuna condizione modificata rispetto alla situazione attuale.")
        else:  # cessazione
            motivo = _t(d.get("motivo_cessazione"))
            if not motivo:
                raise ValueError("Indicare il motivo della cessazione.")
            if data_ev < r["data_assunzione"]:
                raise ValueError("La cessazione non può precedere l'assunzione.")
            c = prec
        avvisi += _avvisi_condizioni(c) if tipo != "cessazione" else []
        eid = _inserisci(conn, "eventi_rapporto", {"rapporto_id": rid, "tipo": tipo, "data_effetto": data_ev, **c,
                                                   "motivo_cessazione": motivo, "note": _t(d.get("note"))},
                         "evento_rapporto", azienda_id=r["azienda_id"], lavoratore_id=r["lavoratore_id"])
        if tipo == "cessazione":
            _aggiorna(conn, "rapporti", rid, {"data_cessazione": data_ev}, "rapporto",
                      azienda_id=r["azienda_id"], lavoratore_id=r["lavoratore_id"])
    return {"id": eid, "avvisi": avvisi}


def annulla_evento(d):
    """Annulla l'ultimo evento valido (mai l'assunzione): l'evento resta visibile come annullato."""
    eid = _id(d.get("evento_id"), "evento_id")
    motivo = _t(d.get("motivo"))
    if not motivo:
        raise ValueError("Indicare il motivo dell'annullamento.")
    with db.transazione() as conn:
        ev = _uno(conn, "SELECT * FROM eventi_rapporto WHERE id = ?", (eid,))
        if not ev or ev["annullato"]:
            raise ValueError("Evento non trovato o già annullato.")
        r = _rapporto(conn, ev["rapporto_id"])
        if ev["tipo"] == "assunzione":
            raise ValueError("L'assunzione non si annulla come evento: annullare l'intero rapporto.")
        if _ultimo_evento(conn, r["id"])["id"] != eid:
            raise ValueError("Si può annullare solo l'ultimo evento valido del rapporto.")
        # gli eventi non hanno 'modificato_il': si aggiornano solo i campi dell'annullamento
        prima = {"annullato": 0}
        conn.execute("UPDATE eventi_rapporto SET annullato = 1, motivo_annullamento = ?, annullato_il = ? WHERE id = ?",
                     (motivo, db.adesso(), eid))
        db.registra(conn, "annullamento", "evento_rapporto", eid, prima, {"annullato": 1, "motivo": motivo},
                    azienda_id=r["azienda_id"], lavoratore_id=r["lavoratore_id"])
        if ev["tipo"] == "cessazione":
            _aggiorna(conn, "rapporti", r["id"], {"data_cessazione": None}, "rapporto",
                      azienda_id=r["azienda_id"], lavoratore_id=r["lavoratore_id"])
    return {"id": eid, "avvisi": []}


def annulla_rapporto(d):
    """Per un rapporto inserito per errore: resta in archivio, marcato come annullato."""
    rid = _id(d.get("rapporto_id"), "rapporto_id")
    motivo = _t(d.get("motivo"))
    if not motivo:
        raise ValueError("Indicare il motivo dell'annullamento.")
    with db.transazione() as conn:
        r = _rapporto(conn, rid)
        _aggiorna(conn, "rapporti", rid, {"annullato": 1, "motivo_annullamento": motivo}, "rapporto",
                  azienda_id=r["azienda_id"], lavoratore_id=r["lavoratore_id"])
    return {"id": rid, "avvisi": []}


# ---------- opzioni per l'interfaccia ----------
def opzioni(_=None):
    return {"tipi_datore": TIPI_DATORE, "tipi_sede": TIPI_SEDE, "ruoli": RUOLI, "tipologie": TIPOLOGIE,
            "qualifiche": QUALIFICHE, "orari": ORARI, "eventi": EVENTI,
            "ccnl": {c["chiave"]: c["nome"] for c in calcoli.elenco_ccnl()},
            "schema": db.versione_schema()}


ROTTE = {
    "/api/anagrafiche/opzioni": opzioni,
    "/api/aziende/cerca": cerca_aziende,
    "/api/aziende/scheda": scheda_azienda,
    "/api/aziende/salva": salva_azienda,
    "/api/sedi/salva": salva_sede,
    "/api/referenti/salva": salva_referente,
    "/api/lavoratori/cerca": cerca_lavoratori,
    "/api/lavoratori/scheda": scheda_lavoratore,
    "/api/lavoratori/salva": salva_lavoratore,
    "/api/rapporti/assumi": assumi,
    "/api/rapporti/evento": aggiungi_evento,
    "/api/rapporti/annulla_evento": annulla_evento,
    "/api/rapporti/annulla": annulla_rapporto,
}
