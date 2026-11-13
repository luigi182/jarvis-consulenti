# Verifica, test e backup

## Ricerca
`ricerca.cerca(query, area=None, alla_data=None, ambito=None, territorio=None, limite=20)` cerca esclusivamente schede in `data/fonti/`. Schede non affidabili, scadute o non ricontrollate entro la soglia configurata sono separate e non presentate come utilizzabili. Un risultato vuoto produce `fonti_insufficienti`; non viene generato un parere né consultato automaticamente il web. Aggiungere una scheda solo dopo aver verificato il documento originale e inserire link, date e stato reali.

## Stima pensione
`pensioni.stima_importo(dati)` stima il lordo dal montante e dal coefficiente fornito, con proiezione opzionale dei contributi futuri. Stima il netto soltanto se sono forniti scaglioni IRPEF completi, detrazione e addizionali. Coefficiente, rivalutazione, montante e parametri fiscali devono essere verificati per la data di decorrenza; i dati illustrativi non costituiscono valori ufficiali. Il calcolo non determina il diritto alla pensione né tratta il sistema misto.

Esempio puramente matematico: montante €200.000 × coefficiente ipotetico 0,05 = €10.000 lordi annui, circa €769,23 su 13 mensilità. Senza parametri fiscali verificati il netto resta `null`.

## Parametri e CCNL
`data/parametri.json` conserva le strutture richieste dal calcolatore storico, ma li contrassegna come segnaposto non verificati. Non usare i calcoli di busta paga/fisco come definitivi finché ogni parametro non è verificato e corredato da anno e fonte. `data/ccnl.json` è intenzionalmente vuoto: niente minimi salariali inventati.

## Test
Eseguire `python -m unittest discover -s tests`. I test aggiunti coprono validazione input, proiezione contributiva, calcolo lordo/netto condizionale e ricerca conservativa. L'esecuzione deve avvenire nell'ambiente Python del repository.

## Backup
Prima di modifiche ampie creare un branch GitHub da `main`; dopo un insieme di modifiche convalidato, creare un nuovo branch di backup dal commit aggiornato. Un branch è una copia versionata del codice, non un backup dei dati locali o del database clienti.
