"""Stima trasparente dell'importo pensionistico con metodo contributivo.

Non determina i requisiti di accesso e non ricostruisce autonomamente una posizione
INPS. Richiede montante, coefficiente ufficiale applicabile e ipotesi dichiarate.
Per il netto richiede anche parametri IRPEF e addizionali dell'anno di decorrenza.
"""
from __future__ import annotations


def _numero(d, key, minimo=None, massimo=None):
    try:
        value = float(d[key])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Indicare un valore numerico valido per '{key}'.")
    if minimo is not None and value < minimo or massimo is not None and value > massimo:
        raise ValueError(f"Valore fuori intervallo per '{key}'.")
    return value


def _irpef(imponibile, scaglioni):
    if not isinstance(scaglioni, list) or not scaglioni:
        raise ValueError("Per stimare il netto fornire gli scaglioni IRPEF dell'anno di decorrenza.")
    imposta, limite_precedente = 0.0, 0.0
    for riga in scaglioni:
        if not isinstance(riga, (list, tuple)) or len(riga) != 2:
            raise ValueError("Scaglioni IRPEF non validi: usare coppie [limite_annuo, aliquota].")
        limite, aliquota = riga
        aliquota = float(aliquota)
        if not 0 <= aliquota <= 1:
            raise ValueError("Le aliquote IRPEF devono essere espresse come frazioni tra 0 e 1.")
        tetto = imponibile if limite is None else min(imponibile, float(limite))
        if tetto > limite_precedente:
            imposta += (tetto - limite_precedente) * aliquota
        if limite is None or imponibile <= float(limite):
            break
        limite_precedente = float(limite)
    else:
        raise ValueError("Gli scaglioni IRPEF non coprono l'intero imponibile.")
    return imposta


def stima_importo(d):
    """Restituisce pensione lorda annua/mensile e, con parametri fiscali, netta.

    Input obbligatori: montante_euro, coefficiente (es. 0.05, non 5),
    anni_proiezione e contributi_annui_euro. Facoltativi: rivalutazione_annua
    (frazione), mensilita, irpef_scaglioni, detrazione_annua,
    addizionali_percentuale (frazione complessiva).
    """
    montante = _numero(d, "montante_euro", 0)
    coeff = _numero(d, "coefficiente", 0.000001, 1)
    anni = int(_numero(d, "anni_proiezione", 0, 70))
    versamenti = _numero(d, "contributi_annui_euro", 0)
    rival = _numero(d, "rivalutazione_annua", 0, 1) if d.get("rivalutazione_annua") is not None else 0.0
    mensilita = int(_numero(d, "mensilita", 1, 15)) if d.get("mensilita") is not None else 13

    montante_proiettato = montante
    for _ in range(anni):
        # Ipotesi dichiarata: rivalutazione del montante e versamento a fine anno.
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
