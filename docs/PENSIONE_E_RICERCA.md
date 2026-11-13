## Ricerca e stima pensionistica: stato e limiti

### Ricerca
`ricerca.cerca(query, area=None, alla_data=None, ambito=None, territorio=None)` cerca esclusivamente nelle schede JSON curate in `data/fonti/`. Non naviga il web e non genera pareri: quando non trova schede affidabili e in vigore restituisce `fonti_insufficienti`; le voci non verificate sono separate e non presentate come utilizzabili. Inserire una scheda solo dopo aver consultato la fonte primaria, riportando link, data di verifica e stato corretto.

### Pensione lorda e netta
`pensioni.stima_importo(dati)` stima l'importo contributivo a partire dal montante e dal coefficiente di trasformazione. Può proiettare il montante con versamenti annuali e una rivalutazione ipotizzata. Calcola il netto solo se vengono forniti scaglioni IRPEF, detrazione e addizionali applicabili all'anno di decorrenza. I dati normativi non sono precaricati intenzionalmente: vanno verificati da fonti ufficiali e aggiornati per anno.

Esempio puramente illustrativo, non usare per una pratica: montante €200.000 × coefficiente 5% = pensione lorda annua €10.000, pari a circa €769,23 su 13 mensilità. In assenza dei parametri fiscali verificati, il programma non dichiara un netto.

La stima non ricostruisce il montante INPS, non tratta la quota retributiva del sistema misto e non sostituisce `Pensami` o l'estratto contributivo. I requisiti di accesso e la decorrenza restano una stima distinta dall'importo.

Eseguire i test disponibili con `python -m unittest discover -s tests`.
