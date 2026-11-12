# Studio Cacace – Assistente CDL

Avvio (una volta sola: `pip install -r requirements.txt`):

    python server.py        # poi aprire http://127.0.0.1:5173

Windows: doppio clic su `avvia.bat`. Mac: `avvia.command`.
Test: `python -m unittest discover -s tests`
Controllo delle fonti della ricerca: `controlla_fonti.bat` (oppure `python strumenti/controlla_fonti.py`)

## Cosa fa
- **Aziende** (dalla v2.2): anagrafica aziende con sedi, rappresentante legale e referenti, CCNL e informazioni contrattuali; dipendenti collegati con rapporti di lavoro (assunzione, proroga, trasformazione, variazione, cessazione) e storico completo. Ricerca per denominazione, codice fiscale e partita IVA.
- **Ricerca** (v2.5): cinque aree (lavoro e CCNL, previdenza INPS/INAIL e pensioni, fisco, Cassa Edile nazionale e di Napoli, procedure dello Studio); fonti distinte per tipo (normativa, circolari, prassi, CCNL, giurisprudenza) e per ambito (nazionale/territoriale); validità alla data di riferimento (decorrenza, testo vigente, modifiche, abrogazione) e data dell'ultima verifica; risposta costruita solo sul testo delle fonti con l'elenco delle fonti usate e del loro stato; "fonti insufficienti" quando mancano. Modello locale (Ollama) facoltativo, con controllo delle citazioni. Vedi `docs/RICERCA_PROFESSIONALE.md` e `docs/RICERCA_E_LETTERE.md`.
- **Lettere** (v2.4): biblioteca in 10 categorie, 12 modelli .docx (assunzione, trasformazione, superminimo, contestazione, sanzione, licenziamento GMO, diffida differenze e 5 modelli di dimissioni/preavviso) con controlli (es. 5 giorni art. 7 L. 300/70, procedura telematica delle dimissioni) e compilazione dai dati dell'archivio.
- **Busta paga**: dovuto da CCNL (minimo + scatti + superminimo) contro lordo in busta, controllo INPS, quota TFR, netto stimato.
- **Vertenze**: differenze mensili con ratei 13ª/14ª, prescrizione quinquennale, interessi legali, TFR.
- **Pensioni**: vecchiaia e anticipata 2026–2028 con decorrenza.

## Dati da mantenere (file JSON in `data/`)
- `ccnl.json`: tabelle retributive. Aggiungere una tabella con data `dal` a ogni rinnovo. Solo Terziario è popolato con valori da fonte secondaria; gli altri CCNL sono **non verificati**.
- `parametri.json`: IRPEF, INPS, interessi legali, requisiti pensionistici. Controllare a ogni legge di bilancio.
- `studio.json`: intestazione delle lettere (aggiungere indirizzo e telefono).
- `schede_verificate.json` e `fonti/*.json`: schede della ricerca, una per fonte letta (procedura in `docs/RICERCA_PROFESSIONALE.md`).
- `aree.json` (aree e tempi di ricontrollo), `fonti_ufficiali.json` (siti ufficiali; completare gli indirizzi territoriali di Napoli), `sinonimi.json` (parole collegate).

## Archivio (aziende, lavoratori, rapporti)
- I dati stanno in `archivio/jarvis.db` (SQLite, un solo file). La cartella `archivio/` è esclusa da Git: i dati dei clienti non entrano mai nello storico del codice.
- **Backup**: a ogni avvio del server, se non c'è ancora la copia del giorno, viene creata `archivio/backup/jarvis_AAAA-MM-GG.db`. Le copie precedenti non vengono mai cancellate. Per sicurezza copiare periodicamente la cartella `archivio/` anche su un disco esterno.
- **Nessuna cancellazione**: aziende, sedi e referenti si disattivano o si chiudono con una data. Ogni modifica è annotata nello "Storico delle modifiche" con il valore precedente.
- **Rapporti di lavoro**: ogni evento registra la situazione completa da quella data, quindi la storia non viene sovrascritta. Gli eventi vanno inseriti in ordine di data; un errore si corregge annullando l'ultimo evento (con motivazione, resta visibile) e registrandolo di nuovo. Un rapporto inserito per errore si annulla e resta in archivio.
- Codici fiscali e partite IVA vengono controllati con il carattere di controllo; sesso e data di nascita, se non indicati, si ricavano dal codice fiscale.

## Importazioni (scheda "Importa dati", dalla v2.3)
Importazione di aziende, dipendenti e rapporti di lavoro da file **CSV**: scelta del file, associazione delle colonne (salvabile per i file successivi), anteprima completa senza scrivere nulla, scelta esplicita per ogni dato esistente da aggiornare, copia di sicurezza prima di ogni importazione, importazione "tutto o niente", riepilogo finale, storico e **annullamento**. Istruzioni dettagliate e file di prova: `docs/IMPORTAZIONE.md` e `docs/esempi/`.
Architettura in `importazione/`: un file per ogni formato. **UniEmens** è predisposto ma non ancora realizzato; i tracciati dei gestionali paghe non sono pubblici (vedi lo stesso documento).

## Riservatezza
Il server ascolta solo su 127.0.0.1, non salva né registra i dati inseriti e i documenti vengono scaricati dal browser. L'unica uscita verso altri programmi è Ollama in locale (se acceso).
