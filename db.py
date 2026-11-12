"""Archivio dello Studio (SQLite locale).

- Il file del database sta in archivio/jarvis.db (cartella esclusa da Git).
  Per i test si può indicare un'altra cartella con la variabile JARVIS_ARCHIVIO.
- Lo schema è versionato: ogni modifica futura si aggiunge in MIGRAZIONI,
  senza toccare quelle già applicate (i dati esistenti non vengono riscritti).
- Ogni inserimento o modifica viene annotato nella tabella 'registro'
  con i valori precedenti e successivi: nessuna informazione va persa.
- backup_giornaliero() crea al massimo una copia al giorno in archivio/backup
  e non cancella mai le copie precedenti.
"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
UTENTE_PREDEFINITO = "titolare"  # predisposto per più collaboratori in futuro

_lock = threading.Lock()
_inizializzati = set()


def cartella_archivio():
    return os.environ.get("JARVIS_ARCHIVIO") or os.path.join(BASE, "archivio")


def percorso_db():
    return os.path.join(cartella_archivio(), "jarvis.db")


def adesso():
    return datetime.now().isoformat(timespec="seconds")


# ---------- schema ----------
MIGRAZIONI = {
    1: """
    CREATE TABLE aziende (
        id INTEGER PRIMARY KEY,
        denominazione TEXT NOT NULL,
        forma_giuridica TEXT,
        tipo_datore TEXT NOT NULL DEFAULT 'impresa',
        codice_fiscale TEXT UNIQUE,
        partita_iva TEXT,
        codice_ateco TEXT,
        matricola_inps TEXT,
        pat_inail TEXT,
        cassa_edile TEXT,
        email TEXT, pec TEXT, telefono TEXT, sito TEXT,
        ccnl_chiave TEXT,
        ccnl_descrizione TEXT,
        ccnl_codice_cnel TEXT,
        info_contrattuali TEXT,
        note TEXT,
        attiva INTEGER NOT NULL DEFAULT 1,
        fonte TEXT NOT NULL DEFAULT 'manuale',
        creato_il TEXT NOT NULL,
        modificato_il TEXT NOT NULL
    );
    CREATE INDEX ix_aziende_denominazione ON aziende(denominazione COLLATE NOCASE);
    CREATE INDEX ix_aziende_piva ON aziende(partita_iva);

    CREATE TABLE sedi (
        id INTEGER PRIMARY KEY,
        azienda_id INTEGER NOT NULL REFERENCES aziende(id),
        tipo TEXT NOT NULL CHECK (tipo IN ('legale','operativa','amministrativa','altro')),
        denominazione TEXT,
        indirizzo TEXT, cap TEXT, comune TEXT, provincia TEXT, nazione TEXT NOT NULL DEFAULT 'IT',
        telefono TEXT, email TEXT,
        dal TEXT, al TEXT,
        attiva INTEGER NOT NULL DEFAULT 1,
        note TEXT,
        creato_il TEXT NOT NULL, modificato_il TEXT NOT NULL
    );
    CREATE INDEX ix_sedi_azienda ON sedi(azienda_id);

    CREATE TABLE referenti (
        id INTEGER PRIMARY KEY,
        azienda_id INTEGER NOT NULL REFERENCES aziende(id),
        ruolo TEXT NOT NULL CHECK (ruolo IN ('rappresentante_legale','amministratore','referente','socio','altro')),
        cognome TEXT NOT NULL, nome TEXT,
        codice_fiscale TEXT,
        carica TEXT,
        email TEXT, telefono TEXT,
        dal TEXT, al TEXT,
        attivo INTEGER NOT NULL DEFAULT 1,
        note TEXT,
        creato_il TEXT NOT NULL, modificato_il TEXT NOT NULL
    );
    CREATE INDEX ix_referenti_azienda ON referenti(azienda_id);

    CREATE TABLE lavoratori (
        id INTEGER PRIMARY KEY,
        codice_fiscale TEXT NOT NULL UNIQUE,
        cognome TEXT NOT NULL,
        nome TEXT NOT NULL,
        sesso TEXT CHECK (sesso IN ('M','F') OR sesso IS NULL),
        data_nascita TEXT,
        comune_nascita TEXT, provincia_nascita TEXT, stato_nascita TEXT,
        cittadinanza TEXT,
        res_indirizzo TEXT, res_cap TEXT, res_comune TEXT, res_provincia TEXT,
        dom_indirizzo TEXT, dom_cap TEXT, dom_comune TEXT, dom_provincia TEXT,
        email TEXT, telefono TEXT,
        note TEXT,
        fonte TEXT NOT NULL DEFAULT 'manuale',
        creato_il TEXT NOT NULL, modificato_il TEXT NOT NULL
    );
    CREATE INDEX ix_lavoratori_cognome ON lavoratori(cognome COLLATE NOCASE, nome COLLATE NOCASE);

    -- Un rapporto = un periodo di lavoro presso un'azienda (dall'assunzione alla cessazione).
    -- Le condizioni (contratto, livello, orario...) stanno negli eventi: ogni evento conserva
    -- la situazione completa da quella data, così lo storico non viene mai sovrascritto.
    CREATE TABLE rapporti (
        id INTEGER PRIMARY KEY,
        lavoratore_id INTEGER NOT NULL REFERENCES lavoratori(id),
        azienda_id INTEGER NOT NULL REFERENCES aziende(id),
        sede_id INTEGER REFERENCES sedi(id),
        matricola TEXT,
        data_assunzione TEXT NOT NULL,
        data_cessazione TEXT,
        annullato INTEGER NOT NULL DEFAULT 0,
        motivo_annullamento TEXT,
        fonte TEXT NOT NULL DEFAULT 'manuale',
        creato_il TEXT NOT NULL, modificato_il TEXT NOT NULL
    );
    CREATE INDEX ix_rapporti_azienda ON rapporti(azienda_id);
    CREATE INDEX ix_rapporti_lavoratore ON rapporti(lavoratore_id);

    CREATE TABLE eventi_rapporto (
        id INTEGER PRIMARY KEY,
        rapporto_id INTEGER NOT NULL REFERENCES rapporti(id),
        tipo TEXT NOT NULL CHECK (tipo IN ('assunzione','proroga','trasformazione','variazione','cessazione')),
        data_effetto TEXT NOT NULL,
        tipologia_contratto TEXT,
        data_fine_termine TEXT,
        ccnl_chiave TEXT, ccnl_descrizione TEXT,
        livello TEXT, qualifica TEXT, mansione TEXT,
        tipo_orario TEXT,
        ore_settimanali REAL,
        percentuale_part_time REAL,
        superminimo REAL,
        motivo_cessazione TEXT,
        note TEXT,
        annullato INTEGER NOT NULL DEFAULT 0,
        motivo_annullamento TEXT,
        annullato_il TEXT,
        fonte TEXT NOT NULL DEFAULT 'manuale',
        creato_il TEXT NOT NULL
    );
    CREATE INDEX ix_eventi_rapporto ON eventi_rapporto(rapporto_id, data_effetto);

    -- Chi ha fatto cosa, con i valori prima e dopo.
    CREATE TABLE registro (
        id INTEGER PRIMARY KEY,
        quando TEXT NOT NULL,
        utente TEXT NOT NULL,
        azione TEXT NOT NULL,
        entita TEXT NOT NULL,
        entita_id INTEGER,
        azienda_id INTEGER,
        lavoratore_id INTEGER,
        prima TEXT,
        dopo TEXT
    );
    CREATE INDEX ix_registro_azienda ON registro(azienda_id);
    CREATE INDEX ix_registro_lavoratore ON registro(lavoratore_id);

    CREATE TABLE importazioni (
        id INTEGER PRIMARY KEY,
        quando TEXT NOT NULL,
        utente TEXT NOT NULL,
        importatore TEXT NOT NULL,
        nome_file TEXT,
        impronta_sha256 TEXT,
        esito TEXT NOT NULL,
        riepilogo TEXT
    );
    """,
}


MIGRAZIONI[2] = """
    -- importazioni: stato, backup preso prima, intervallo del registro (per l'annullamento), impostazioni usate
    ALTER TABLE importazioni ADD COLUMN stato TEXT NOT NULL DEFAULT 'completata';
    ALTER TABLE importazioni ADD COLUMN registro_da INTEGER;
    ALTER TABLE importazioni ADD COLUMN registro_a INTEGER;
    ALTER TABLE importazioni ADD COLUMN backup TEXT;
    ALTER TABLE importazioni ADD COLUMN impostazioni TEXT;
    ALTER TABLE importazioni ADD COLUMN annullata_il TEXT;
    ALTER TABLE importazioni ADD COLUMN esito_annullamento TEXT;

    -- mappature delle colonne salvate dall'utente (es. "Estrazione anagrafiche del nostro gestionale")
    CREATE TABLE mappature (
        id INTEGER PRIMARY KEY,
        nome TEXT NOT NULL UNIQUE,
        importatore TEXT NOT NULL,
        mappa TEXT NOT NULL,
        separatore TEXT,
        creato_il TEXT NOT NULL,
        modificato_il TEXT NOT NULL
    );
    """


def _migra(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS schema_versione (versione INTEGER PRIMARY KEY, applicata_il TEXT NOT NULL)")
    attuale = conn.execute("SELECT COALESCE(MAX(versione), 0) AS v FROM schema_versione").fetchone()["v"]
    da_applicare = [v for v in sorted(MIGRAZIONI) if v > attuale]
    if attuale and da_applicare:
        # archivio già esistente: copia di sicurezza prima di cambiarne la struttura
        _copia(conn, f"jarvis_pre_schema_v{da_applicare[0]}_{datetime.now():%Y-%m-%d_%H%M%S}.db")
    for v in da_applicare:
        conn.executescript("BEGIN;" + MIGRAZIONI[v] +
                           f"INSERT INTO schema_versione VALUES ({v}, '{adesso()}');COMMIT;")


def _riga_dict(cursore, riga):
    return {c[0]: riga[i] for i, c in enumerate(cursore.description)}


def connetti():
    percorso = percorso_db()
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    conn = sqlite3.connect(percorso, timeout=15)
    conn.row_factory = _riga_dict
    conn.execute("PRAGMA foreign_keys = ON")
    if percorso not in _inizializzati:
        with _lock:
            if percorso not in _inizializzati:
                conn.execute("PRAGMA journal_mode = WAL")
                _migra(conn)
                _inizializzati.add(percorso)
    return conn


_locale = threading.local()


def attiva():
    """Connessione della transazione in corso in questo thread (o None)."""
    return getattr(_locale, "conn", None)


@contextmanager
def transazione(simula=False):
    """Apre una transazione: conferma tutto alla fine o annulla tutto in caso di errore.
    Se una transazione è già aperta nello stesso thread la riusa: le operazioni diventano parte di
    quella più esterna (così un'importazione intera è 'tutto o niente').
    simula=True: esegue tutto e alla fine annulla comunque (usata per le anteprime)."""
    esistente = attiva()
    if esistente is not None:
        yield esistente
        return
    conn = connetti()
    _locale.conn = conn
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        if simula:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _locale.conn = None
        conn.close()


def versione_schema():
    conn = connetti()
    try:
        return conn.execute("SELECT MAX(versione) AS v FROM schema_versione").fetchone()["v"]
    finally:
        conn.close()


def registra(conn, azione, entita, entita_id, prima=None, dopo=None, azienda_id=None, lavoratore_id=None,
             utente=UTENTE_PREDEFINITO):
    cur = conn.execute(
        "INSERT INTO registro (quando, utente, azione, entita, entita_id, azienda_id, lavoratore_id, prima, dopo) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (adesso(), utente, azione, entita, entita_id, azienda_id, lavoratore_id,
         json.dumps(prima, ensure_ascii=False) if prima is not None else None,
         json.dumps(dopo, ensure_ascii=False) if dopo is not None else None))
    return cur.lastrowid


# ---------- copie di sicurezza (mai sovrascritte, mai cancellate) ----------
def _cartella_backup():
    cartella = os.path.join(cartella_archivio(), "backup")
    os.makedirs(cartella, exist_ok=True)
    return cartella


def _copia(sorgente, nome):
    """Copia coerente dell'archivio con il metodo di backup di SQLite. Se il nome esiste, aggiunge un suffisso."""
    base, est = os.path.splitext(os.path.join(_cartella_backup(), nome))
    dest, n = base + est, 1
    while os.path.exists(dest):
        n += 1
        dest = f"{base}_{n}{est}"
    copia = sqlite3.connect(dest)
    try:
        sorgente.backup(copia)
    finally:
        copia.close()
    return dest


def _copia_archivio(nome):
    # connessione diretta, senza aggiornare lo schema: la copia rispecchia l'archivio così com'è
    sorgente = sqlite3.connect(percorso_db(), timeout=15)
    try:
        return _copia(sorgente, nome)
    finally:
        sorgente.close()


def backup_giornaliero():
    """Copia in archivio/backup/jarvis_AAAA-MM-GG.db (una al giorno). Restituisce il percorso o None."""
    if not os.path.exists(percorso_db()):
        return None
    nome = f"jarvis_{date.today().isoformat()}.db"
    if os.path.exists(os.path.join(_cartella_backup(), nome)):
        return None
    return _copia_archivio(nome)


def backup_con_motivo(motivo):
    """Copia immediata con data, ora e motivo nel nome (es. prima di un'importazione)."""
    connetti().close()  # assicura che l'archivio esista
    return _copia_archivio(f"jarvis_{datetime.now():%Y-%m-%d_%H%M%S}_{motivo}.db")
