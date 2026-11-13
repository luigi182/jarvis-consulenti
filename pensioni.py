"""Stima trasparente dell'importo pensionistico con metodo contributivo.

Non determina requisiti di accesso né ricostruisce una posizione INPS. Richiede
montante, coefficiente ufficiale applicabile e ipotesi dichiarate. Per il netto
richiede scaglioni, detrazioni e addizionali riferiti all'anno di decorrenza.
"""
from __future__ import annotations

import math


def _numero(d, key, minimo=None, massimo=None):
    try:
        value = float(d[key])
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError(f"Indicare un valore numerico valido per '{key}'.")
    if not math.isfinite(value):
        raise ValueError(f"Il valore per '{key}' deve essere finito.")
    if (minimo is not None and value < minimo) or (massimo is not None and value > massimo):
        raise ValueError(f"Valore fuori intervallo per '{key}'.")
    return value


def _irpef(imponibile, scaglioni):
    if not isinstance(scaglioni, list) or not scaglioni:
        raise ValueError("Per stimare il netto fornire gli scaglioni IRPEF dell'anno di decorrenza.")
    imposta, limite_precedente = 0.0, 0.0
    for indice, riga in enumerate(scaglioni):
        if not isinstance(riga, (list, tuple)) or len(riga) != 2:
            raise ValueError("Scaglioni IRPEF non validi: usare coppie [limite_annuo, aliquota].")
        limite, aliquota = riga
        try:
            aliquota = float(aliquota)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Aliquota IRPEF non valida.")
        if not math.isfinite(aliquota) or not 0 <= aliquota <= 1:
            raise ValueError("Le aliquote IRPEF devono essere frazioni finite tra 0 e 1.")
        if limite is None:
            if indice != len(scaglioni) - 1:
                raise ValueError("Lo scaglione senza limite deve essere l'ultimo.")
            tetto = imponibile
        else:
            try:
                limite = float(limite)
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Limite IRPEF non valido.")
            if not math.isfinite(limite) or limite <= limite_precedente:
                raise ValueError("I limiti degli scaglioni devono essere finiti e crescenti.")
            tetto = min(imponibile, limite)
        if tetto > limite_precedente:
            imposta += (tetto - limite_precedente) * aliquota
        if limite is None or imponibile <= limite:
            break
        limite_precedente = limite
    else:
        raise ValueError("Gli scaglioni IRPEF devono terminare con [null, aliquota].")
    return imposta


def stima_importo(d):
    """Calcola pensione lorda e netto condizionale da input espliciti.

    Input: montante_euro, coefficiente (frazione, es. 0.05), anni_proiezione,
    contributi_annui_euro. Facoltativi: rivalutazione_annua, mensilita,
    irpef_scaglioni (ultimo limite null), detrazione_annua, addizionali_percentuale.
    I versamenti si aggiungono a fine anno: la rivalutazione ipotizzata si applica
    al montante già accumulato prima dei nuovi versamenti.
    """
    if not isinstance(d, dict):
        raise ValueError("Fornire i dati della stima in un oggetto.")
    montante = _numero(d, "montante_euro", 0)
    coeff = _numero(d, "coefficiente", 0.000001, 1)
    anni_val = _numero(d, "anni_proiezione", 0, 70)
    if not anni_val.is_integer():
        raise ValueError("'anni_proiezione' deve essere un numero intero.")
    anni = int(anni_val)
    versamenti = _numero(d, "contributi_annui_euro", 0)
    rival = _numero(d, "rivalutazione_annua", 0, 1) if d.get("rivalutazione_annua") is not None else 0.0
    mens_val = _numero(d, "mensilita", 1, 15) if d.get("mensilita") is not None else 13
    if not mens_val.is_integer():
        raise ValueError("'mensilita' deve essere un numero intero.")
    mensilita = int(mens_val)

    montante_proiettato = montante
    for _ in range(anni):
        montante_proiettato = montante_proiettato * (1 + rival) + versamenti
    lordo_annuo = montante_proiettato * coeff
    lordo_mensile = lordo_annuo / mensilita
    risultato = {
        "metodo": "contributivo semplificato",
        "montante_iniziale_euro": round(montante, 2),
        "montante_proiettato_euro": round(montante_proiettato, 2),
        "coefficiente_trasformazione": coeff,
        "anni_proiezione": anni,
        "contributi_annui_euro": round(versamenti, 2),
        "rivalutazione_annua_ipotizzata": rival,
        "mensilita": mensilita,
        "lordo_annuo_euro": round(lordo_annuo, 2),
        "lordo_mensile_euro": round(lordo_mensile, 2),
        "netto_annuo_euro": None,
        "netto_mensile_euro": None,
        "avvisi": [
            "Stima indicativa: non sostituisce l'estratto contributivo o la simulazione INPS.",
            "Montante, contributi futuri, rivalutazione e coefficiente devono essere verificati e riferiti alla data di decorrenza.",
            "Non modella il sistema retributivo/misto, periodi figurativi, massimali, riscatti, cumulo né maggiorazioni.",
        ],
    }
    if "irpef_scaglioni" in d:
        detrazione = _numero(d, "detrazione_annua", 0) if d.get("detrazione_annua") is not None else 0.0
        addizionali = _numero(d, "addizionali_percentuale", 0, 1) if d.get("addizionali_percentuale") is not None else 0.0
        irpef_lorda = _irpef(lordo_annuo, d["irpef_scaglioni"])
        irpef_netta = max(0.0, irpef_lorda - detrazione)
        addizionali_euro = lordo_annuo * addizionali
        netto_annuo = max(0.0, lordo_annuo - irpef_netta - addizionali_euro)
        risultato.update({
            "irpef_lorda_annua_euro": round(irpef_lorda, 2),
            "detrazione_annua_euro": round(detrazione, 2),
            "addizionali_annue_stimate_euro": round(addizionali_euro, 2),
            "netto_annuo_euro": round(netto_annuo, 2),
            "netto_mensile_euro": round(netto_annuo / mensilita, 2),
        })
        risultato["avvisi"].append("Netto stimato solo in base ai parametri fiscali forniti; addizionali effettive e detrazioni dipendono da anno, regione, comune e situazione personale.")
    else:
        risultato["avvisi"].append("Netto non calcolato: fornire gli scaglioni IRPEF e le detrazioni vigenti per l'anno di decorrenza.")
    return risultato
