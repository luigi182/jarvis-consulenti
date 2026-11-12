"""Generatore di lettere dello Studio (.docx) nello stile dei modelli dello Studio.
Aggiungere un modello = aggiungere una voce a MODELLI (campi + blocchi di testo)."""
import io
import json
import os
from datetime import date, datetime, timedelta

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
except ImportError:  # il server parte lo stesso; la generazione segnala il problema
    Document = None

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "data", "studio.json"), encoding="utf-8") as f:
    STUDIO = json.load(f)

T, D, N, A = "text", "date", "number", "textarea"
NAVY, ROSSO, GRIGIO = "1F3864", "C00000", "666666"


def S(id, label, opzioni, default=None):
    return {"id": id, "label": label, "tipo": "select", "opzioni": opzioni, "default": default or opzioni[0], "richiesto": False}


def C(id, label, tipo=T, default="", richiesto=True):
    return {"id": id, "label": label, "tipo": tipo, "default": default, "richiesto": richiesto}


DATORE = [C("azienda", "Datore di lavoro (ragione sociale)"), C("sede_azienda", "Sede legale"),
          C("piva", "P.IVA / C.F. azienda", richiesto=False), C("rappresentante", "Legale rappresentante", richiesto=False)]
LAVORATORE = [C("lavoratore", "Lavoratore (nome e cognome)"), C("cf", "Codice fiscale lavoratore", richiesto=False),
              C("residenza", "Residenza lavoratore", richiesto=False)]
COMUNI = [C("luogo", "Luogo", default="Napoli"), C("data_lettera", "Data lettera", D, "{oggi}"),
          S("invio", "Modalità di invio", ["Raccomandata A/R", "PEC", "Consegna a mani"]),
          S("intestazione", "Intestazione carta", ["Studio", "Azienda", "Nessuna"])]
RAPPORTO = [C("data_assunzione", "Data di assunzione", D, "", False), C("tipologia", "Tipologia contrattuale", T, "", False),
            C("ccnl", "CCNL applicato (denominazione completa)"), C("qualifica", "Qualifica / mansione", T, "", False),
            C("livello", "Livello di inquadramento", T, "", False), C("orario", "Orario di lavoro", T, "", False)]

TESTATA = [("Datore di lavoro", "**{azienda}** – {sede_azienda}"), ("Lavoratore", "**{lavoratore}** {cf_txt}"),
           ("Luogo e data", "{luogo}, {data_lettera}"), ("Modalità di invio", "{invio}")]

GIORNI = {5: "cinque", 6: "sei", 7: "sette", 8: "otto", 10: "dieci", 15: "quindici", 20: "venti", 30: "trenta"}

MODELLI = {
    "contestazione_disciplinare": {
        "titolo": "Contestazione disciplinare",
        "sottotitolo": "Ai sensi e per gli effetti dell'art. 7 della Legge 20 maggio 1970, n. 300",
        "testata": TESTATA, "firma": "datore", "ricevuta": True,
        "oggetto": "Contestazione formale di addebito disciplinare ai sensi dell'art. 7 della Legge n. 300/1970 e del {ccnl}.",
        "campi": DATORE + LAVORATORE + COMUNI + RAPPORTO + [C("tutor", "Tutor aziendale (apprendisti)", T, "", False)] + [
            x for n in (1, 2, 3) for x in (
                C(f"addebito_{n}_titolo", f"Addebito {n}: titolo", T, "", n == 1),
                C(f"addebito_{n}_testo", f"Addebito {n}: fatti (date, luoghi, circostanze; righe con '- ' = elenco)", A, "", n == 1))
        ] + [C("riferimenti", "Riferimenti normativi e contrattuali violati (uno per riga)", A),
             C("termine_giorni", "Giorni per le giustificazioni (min. 5)", N, "5")],
        "blocchi": [
            ("tab", "DATI DEL RAPPORTO DI LAVORO", [("Data di assunzione", "{data_assunzione}"), ("Tipologia contrattuale", "{tipologia}"),
                                                   ("CCNL applicato", "{ccnl}"), ("Qualifica/mansione", "{qualifica}"),
                                                   ("Livello di inquadramento", "{livello}"), ("Tutor aziendale", "{tutor}"),
                                                   ("Orario di lavoro", "{orario}")]),
            ("saluto", "Gentile **{lavoratore}**,"),
            ("p", "con la presente comunicazione, ai sensi e per gli effetti dell'art. 7 della Legge 20 maggio 1970, n. 300 (Statuto dei Lavoratori) nonché delle vigenti disposizioni del {ccnl}, intendiamo contestarLe in modo formale e circostanziato i seguenti comportamenti e fatti verificatisi in costanza di servizio."),
            ("sez", "DESCRIZIONE ANALITICA DEGLI ADDEBITI"),
            ("addebiti",),
            ("sez", "RIFERIMENTI NORMATIVI E CONTRATTUALI"),
            ("p", "Le condotte sopra descritte, ove confermate all'esito del presente procedimento, costituiscono grave inosservanza e violazione di:"),
            ("elenco_campo", "riferimenti", True),
            ("sez", "TERMINI E MODALITÀ DI ESERCIZIO DELLA DIFESA"),
            ("p", "Ai sensi dell'art. 7 della Legge n. 300/1970 e delle vigenti previsioni del CCNL applicato, La informiamo che:"),
            ("num", ["Ella dispone di un termine di {termine_txt} giorni di calendario dal ricevimento della presente contestazione per far pervenire a questa Direzione le Sue giustificazioni scritte.",
                     "Nel medesimo termine, Ella ha facoltà di richiedere di essere ascoltata/o personalmente a propria difesa, potendosi fare assistere da un rappresentante dell'associazione sindacale a cui aderisce o conferisce mandato.",
                     "Ci riserviamo di adottare gli eventuali provvedimenti disciplinari ritenuti congrui e proporzionati all'esito della valutazione delle Sue giustificazioni o, in mancanza delle stesse, decorso il termine assegnato."]),
            ("p", "La presente costituisce formale contestazione disciplinare e non anticipa alcuna determinazione in ordine all'eventuale sanzione."),
        ],
    },
    "sanzione_disciplinare": {
        "titolo": "Provvedimento disciplinare",
        "sottotitolo": "Ai sensi dell'art. 7 della Legge 20 maggio 1970, n. 300",
        "testata": TESTATA, "firma": "datore", "ricevuta": True, "controllo": "sanzione",
        "oggetto": "Provvedimento disciplinare a seguito della contestazione del {data_contestazione}.",
        "campi": DATORE + LAVORATORE + COMUNI + [
            C("ccnl", "CCNL applicato"), C("data_contestazione", "Data della contestazione", D),
            S("giustificazioni", "Giustificazioni del lavoratore", ["non sono pervenute", "sono pervenute ma non sono state ritenute accoglibili", "sono state ritenute solo parzialmente accoglibili"]),
            S("sanzione", "Sanzione", ["rimprovero verbale", "rimprovero scritto (ammonizione)", "multa", "sospensione dal servizio e dalla retribuzione"]),
            C("entita", "Entità (multa: ore, max 4 di retribuzione base; sospensione: giorni, max 10)", T, "", False),
            C("motivazione", "Motivazione", A)],
        "blocchi": [
            ("saluto", "Gentile **{lavoratore}**,"),
            ("p", "facendo seguito alla nostra contestazione del {data_contestazione}, ai sensi dell'art. 7 della Legge n. 300/1970 e del {ccnl}, Le comunichiamo quanto segue."),
            ("sez", "VALUTAZIONE DELLE GIUSTIFICAZIONI"),
            ("p", "Nel termine assegnato le Sue giustificazioni {giustificazioni}."),
            ("sez", "PROVVEDIMENTO ADOTTATO"),
            ("p", "La Società Le applica la seguente sanzione: **{sanzione}{entita_txt}**."),
            ("testo_campo", "motivazione"),
            ("sez", "TUTELE"),
            ("p", "Ai sensi dell'art. 7, comma 6, della Legge n. 300/1970, entro venti giorni dalla ricezione della presente Ella potrà promuovere, anche per mezzo dell'associazione sindacale cui aderisce o conferisce mandato, la costituzione di un collegio di conciliazione e arbitrato."),
        ],
    },
    "licenziamento_gmo": {
        "titolo": "Licenziamento per giustificato motivo oggettivo",
        "sottotitolo": "Ai sensi dell'art. 3 della Legge 15 luglio 1966, n. 604",
        "testata": TESTATA, "firma": "datore", "ricevuta": True,
        "oggetto": "Recesso dal rapporto di lavoro per giustificato motivo oggettivo ai sensi dell'art. 3 della Legge n. 604/1966.",
        "campi": DATORE + LAVORATORE + COMUNI + [
            C("ccnl", "CCNL applicato"),
            C("motivo", "Ragioni oggettive (organizzative/produttive) e impossibilità di ricollocazione (repêchage)", A),
            S("preavviso", "Preavviso", ["lavorato", "non lavorato e sostituito dalla relativa indennità"]),
            C("giorni_preavviso", "Durata del preavviso (da CCNL)"), C("data_cessazione", "Data di cessazione del rapporto", D)],
        "avvisi": [
            "Verificare il requisito dimensionale (art. 18 St. Lav. / D.Lgs. 23/2015) e la data di assunzione: per datori con più di 15 dipendenti e lavoratori assunti prima del 7/3/2015 occorre la procedura preventiva dell'art. 7 L. 604/1966 presso l'ITL.",
            "Documentare l'impossibilità di repêchage (ricollocazione in mansioni equivalenti o inferiori) prima dell'invio.",
            "Il licenziamento deve essere in forma scritta con motivazione contestuale; verificare i divieti di licenziamento (maternità, matrimonio, malattia nel comporto, ecc.).",
            "Calcolare il contributo NASpI (ticket di licenziamento) e le competenze di fine rapporto.",
        ],
        "blocchi": [
            ("saluto", "Gentile **{lavoratore}**,"),
            ("p", "con la presente, ai sensi dell'art. 3 della Legge 15 luglio 1966, n. 604 e del {ccnl}, Le comunichiamo il recesso dal rapporto di lavoro per giustificato motivo oggettivo."),
            ("sez", "MOTIVAZIONE"),
            ("testo_campo", "motivo"),
            ("sez", "PREAVVISO E CESSAZIONE"),
            ("p", "Il preavviso, pari a {giorni_preavviso}, è {preavviso}. Il rapporto cesserà in data **{data_cessazione}**."),
            ("sez", "COMPETENZE DI FINE RAPPORTO"),
            ("p", "Le competenze di fine rapporto, il TFR e le ferie e i permessi maturati e non goduti Le saranno liquidati con le modalità e nei termini previsti dal CCNL applicato."),
            ("sez", "IMPUGNAZIONE"),
            ("p", "Ai sensi dell'art. 6 della Legge n. 604/1966, il presente licenziamento può essere impugnato, a pena di decadenza, entro 60 giorni dalla ricezione della presente."),
        ],
    },
    "assunzione_indeterminato": {
        "titolo": "Lettera di assunzione a tempo indeterminato",
        "sottotitolo": "Informazioni ai sensi del D.Lgs. 27 giugno 2022, n. 104",
        "testata": TESTATA, "firma": "datore", "ricevuta": True,
        "oggetto": "Assunzione a tempo indeterminato con decorrenza dal {decorrenza}.",
        "campi": DATORE + LAVORATORE + COMUNI + [
            C("decorrenza", "Data inizio rapporto", D), C("ccnl", "CCNL applicato"), C("livello", "Livello / qualifica"),
            C("mansioni", "Mansioni"), C("sede_lavoro", "Sede di lavoro"), S("orario", "Orario", ["Tempo pieno", "Part-time"]),
            C("ore_settimanali", "Ore settimanali", N, "40"), C("distribuzione", "Distribuzione orario (part-time)", T, "", False),
            C("retribuzione", "Retribuzione lorda mensile (€)", N), C("mensilita", "Numero mensilità", N, "13"),
            C("superminimo", "Superminimo assorbibile (€, se previsto)", N, "", False),
            C("prova_mesi", "Periodo di prova (mesi)", N, "2"), C("unilav", "Data comunicazione UniLav", D, "", False)],
        "blocchi": [
            ("saluto", "Gentile **{lavoratore}**,"),
            ("p", "con la presente **{azienda}** Le conferma l'assunzione alle proprie dipendenze con contratto di lavoro subordinato a **tempo indeterminato**, con decorrenza dal {decorrenza}, alle condizioni di seguito indicate."),
            ("tab", "DATI DEL RAPPORTO DI LAVORO", [("Data di inizio", "{decorrenza}"), ("CCNL applicato", "{ccnl}"), ("Livello/qualifica", "{livello}"),
                                                   ("Mansioni", "{mansioni}"), ("Sede di lavoro", "{sede_lavoro}"),
                                                   ("Orario di lavoro", "{orario}, {ore_settimanali} ore settimanali{distribuzione_txt}"),
                                                   ("Retribuzione", "€ {retribuzione} lordi mensili per {mensilita} mensilità{superminimo_txt}"),
                                                   ("Periodo di prova", "{prova_mesi} mesi")]),
            ("sez", "ALTRE INFORMAZIONI"),
            ("num", ["Ferie, permessi e preavviso sono riconosciuti nella misura prevista dal CCNL applicato; il TFR matura ai sensi dell'art. 2120 c.c.",
                     "Il rapporto è assicurato presso INPS e INAIL e, se previsti dal CCNL, presso i fondi contrattuali di assistenza sanitaria e di previdenza complementare.",
                     "L'assunzione è stata comunicata al Centro per l'Impiego con modello UniLav{unilav_txt}.",
                     "L'informativa sul trattamento dei dati personali (artt. 13 e 14 Regolamento UE 2016/679) Le viene consegnata a parte."]),
            ("p", "Per quanto non indicato si fa rinvio alla legge e al CCNL applicato."),
        ],
    },
    "trasformazione_indeterminato": {
        "titolo": "Trasformazione a tempo indeterminato",
        "sottotitolo": "Comunicazione di trasformazione del rapporto di lavoro",
        "testata": TESTATA, "firma": "datore", "ricevuta": True,
        "oggetto": "Trasformazione del rapporto di lavoro da tempo determinato a tempo indeterminato dal {decorrenza}.",
        "campi": DATORE + LAVORATORE + COMUNI + [C("data_contratto_termine", "Data del contratto a termine", D), C("decorrenza", "Decorrenza della trasformazione", D)],
        "blocchi": [
            ("saluto", "Gentile **{lavoratore}**,"),
            ("p", "in riferimento al contratto a tempo determinato del {data_contratto_termine}, **{azienda}** Le comunica la trasformazione del rapporto di lavoro a **tempo indeterminato** con decorrenza dal {decorrenza}."),
            ("p", "Restano confermati inquadramento, mansioni, orario, retribuzione e ogni altra condizione in essere, nonché l'applicazione del CCNL già indicato. L'anzianità di servizio si computa dalla data di originaria assunzione."),
            ("p", "La trasformazione sarà comunicata al Centro per l'Impiego nei termini di legge."),
        ],
    },
    "superminimo": {
        "titolo": "Attribuzione di superminimo individuale",
        "sottotitolo": "Trattamento di miglior favore individuale assorbibile",
        "testata": TESTATA, "firma": "datore", "ricevuta": True,
        "oggetto": "Attribuzione di superminimo individuale assorbibile dal {decorrenza}.",
        "campi": DATORE + LAVORATORE + COMUNI + [C("decorrenza", "Decorrenza", D), C("importo", "Superminimo lordo mensile (€)", N), C("mensilita", "Numero mensilità", N, "13")],
        "blocchi": [
            ("saluto", "Gentile **{lavoratore}**,"),
            ("p", "**{azienda}** Le comunica l'attribuzione, con decorrenza dal {decorrenza}, di un superminimo individuale lordo mensile pari a **€ {importo}** per {mensilita} mensilità."),
            ("sez", "NATURA E ASSORBIBILITÀ"),
            ("p", "Il superminimo ha natura di trattamento di miglior favore individuale ed è espressamente **ASSORBIBILE**, fino a concorrenza, da qualsiasi futuro aumento della retribuzione, comunque denominato, derivante da contratto collettivo, da passaggi di livello o da disposizioni di legge, nonché da altri emolumenti non espressamente dichiarati non assorbibili."),
            ("p", "Il superminimo concorre alla base di calcolo del TFR e degli istituti retributivi indiretti secondo le previsioni di legge e di CCNL."),
        ],
    },
    "diffida_differenze": {
        "titolo": "Diffida e messa in mora",
        "sottotitolo": "Differenze retributive – interruzione della prescrizione (art. 2943 c.c.)",
        "testata": [("Destinatario", "**{azienda}** – {sede_azienda}"), ("Lavoratore assistito", "**{lavoratore}** {cf_txt}"),
                    ("Luogo e data", "{luogo}, {data_lettera}"), ("Modalità di invio", "{invio}")],
        "firma": "studio", "ricevuta": False,
        "oggetto": "Diffida ad adempiere e costituzione in mora – differenze retributive di {lavoratore}.",
        "campi": [C("azienda", "Destinatario (datore di lavoro)"), C("sede_azienda", "Sede del destinatario"),
                  C("lavoratore", "Lavoratore assistito"), C("cf", "Codice fiscale lavoratore", T, "", False),
                  C("periodo", "Periodo (es. gennaio 2022 - ottobre 2026)"), C("ccnl", "CCNL e livello"),
                  C("importo", "Importo lordo differenze (€)", N), C("tfr", "Differenze TFR (€)", N, "", False),
                  C("giorni", "Giorni per il pagamento", N, "15"), C("luogo", "Luogo", T, "Napoli"),
                  C("data_lettera", "Data lettera", D, "{oggi}"), S("invio", "Modalità di invio", ["PEC", "Raccomandata A/R"]),
                  S("intestazione", "Intestazione carta", ["Studio", "Nessuna"])],
        "blocchi": [
            ("saluto", "Spett.le **{azienda}**,"),
            ("p", "in nome e per conto di **{lavoratore}**{cf_txt}, in forza di apposito mandato, si rappresenta quanto segue."),
            ("sez", "FATTI"),
            ("p", "Nel periodo {periodo} il Sig. {lavoratore} ha prestato attività lavorativa alle Vostre dipendenze, con applicazione del {ccnl}. Dall'esame della documentazione retributiva risulta che le retribuzioni corrisposte sono state inferiori ai minimi tabellari e agli ulteriori elementi dovuti, con differenze lorde pari a **€ {importo}**{tfr_txt}, oltre a rivalutazione monetaria e interessi come per legge."),
            ("sez", "DIFFIDA"),
            ("p", "Con la presente Vi **DIFFIDIAMO** a corrispondere le somme indicate entro {giorni} giorni dal ricevimento e Vi **COSTITUIAMO IN MORA** a ogni effetto di legge, anche ai fini dell'interruzione della prescrizione ai sensi dell'art. 2943 c.c."),
            ("p", "In difetto, ci riserviamo di agire nelle sedi competenti, anche previo tentativo di conciliazione ai sensi degli artt. 410 e seguenti c.p.c., con aggravio di spese a Vostro carico. Si resta a disposizione per un riscontro conciliativo."),
        ],
    },
}


# ---------- BIBLIOTECA: categorie ----------
CATEGORIE = ["Assunzioni", "Proroghe e trasformazioni", "Dimissioni", "Licenziamenti",
             "Contestazioni e provvedimenti disciplinari", "Variazioni contrattuali", "Accordi individuali",
             "Comunicazioni al personale", "Colf e badanti", "Vertenza e recupero crediti"]
# categorie dei modelli già esistenti (il loro testo non è stato modificato)
CATEGORIE_MODELLI = {
    "assunzione_indeterminato": ["Assunzioni"],
    "trasformazione_indeterminato": ["Proroghe e trasformazioni"],
    "licenziamento_gmo": ["Licenziamenti"],
    "contestazione_disciplinare": ["Contestazioni e provvedimenti disciplinari"],
    "sanzione_disciplinare": ["Contestazioni e provvedimenti disciplinari"],
    "superminimo": ["Variazioni contrattuali"],
    "diffida_differenze": ["Vertenza e recupero crediti"],
}

# ---------- DIMISSIONI ----------
# Fonti verificate il 09/11/2026: art. 26 D.Lgs. 151/2015 (commi 1, 2, 7, 7-bis); art. 55, c. 4, D.Lgs. 151/2001;
# art. 3 D.Lgs. 22/2015; Cass. ord. 24991/2025 e Circ. Min. Lavoro 12/2016; scheda INPS cessazione lavoro domestico.
# Le lettere sono COMUNICAZIONI: dove la procedura telematica è obbligatoria non la sostituiscono e lo dichiarano.
MITTENTE_LAV = [C("lavoratore", "Lavoratore (nome e cognome)"), C("cf", "Codice fiscale lavoratore", richiesto=False),
                C("residenza", "Residenza del lavoratore", richiesto=False)]
DESTINATARIO = [C("azienda", "Datore di lavoro (ragione sociale)"), C("sede_azienda", "Sede del datore di lavoro")]
COMUNI_LAV = [C("luogo", "Luogo", default="Napoli"), C("data_lettera", "Data lettera", D, "{oggi}"),
              S("invio", "Modalità di invio", ["PEC", "Raccomandata A/R", "Consegna a mani"]),
              S("intestazione", "Intestazione carta", ["Nessuna"])]
TESTATA_LAV = [("Mittente", "**{lavoratore}** {cf_txt}{residenza_txt}"), ("Destinatario", "**{azienda}** – {sede_azienda}"),
               ("Luogo e data", "{luogo}, {data_lettera}"), ("Modalità di invio", "{invio}")]
TELEMATICA = [S("telematica", "Procedura telematica (art. 26 D.Lgs. 151/2015)", ["sarà effettuata", "già effettuata"]),
              C("data_telematica", "Data di trasmissione del modulo telematico (se già effettuata)", D, "", False)]
PREAVVISO_LAV = ["sarà regolarmente lavorato",
                 "chiedo di essere esonerato/a dal prestarlo, in tutto o in parte",
                 "non sarà lavorato: prendo atto della trattenuta dell'indennità sostitutiva (art. 2118 c.c.)"]
NOTA_TELEMATICA = ("La presente lettera ha valore di comunicazione al datore di lavoro e **non sostituisce** la procedura "
                   "telematica obbligatoria prevista dall'art. 26 del D.Lgs. 14 settembre 2015, n. 151: le dimissioni hanno "
                   "effetto solo se trasmesse con il modulo telematico del Ministero del Lavoro e possono essere revocate, "
                   "con le stesse modalità, entro sette giorni dalla trasmissione.")
AVVISO_TELEMATICA = ("Le dimissioni sono efficaci solo con la trasmissione del modulo telematico (art. 26, c. 1, D.Lgs. 151/2015), "
                     "direttamente dal lavoratore o tramite un soggetto abilitato; il lavoratore può revocarle entro 7 giorni (c. 2).")
AVVISO_GENITORE = ("Dimissioni della lavoratrice in gravidanza o della lavoratrice/del lavoratore nei primi tre anni di vita del "
                   "figlio: occorre la convalida dell'Ispettorato del lavoro competente; fino alla convalida la cessazione non ha "
                   "effetto (art. 55, c. 4, D.Lgs. 151/2001).")


def _testo_telematica(v):
    if v.get("telematica") == "già effettuata":
        quando = f" in data {_it(v['data_telematica'])}" if v.get("data_telematica") else ""
        return ("Le dimissioni sono state trasmesse con la procedura telematica prevista dall'art. 26 del D.Lgs. 14 settembre "
                f"2015, n. 151{quando}.")
    return ("Le dimissioni saranno trasmesse con la procedura telematica prevista dall'art. 26 del D.Lgs. 14 settembre 2015, "
            "n. 151, dalla quale soltanto decorre la loro efficacia.")


def _derivati_dimissioni(v):
    return {"telematica_txt": _testo_telematica(v),
            "residenza_txt": f" – {v['residenza']}" if v.get("residenza") else "",
            "assunzione_txt": f", assunto/a in data {_it(v['data_assunzione'])}" if v.get("data_assunzione") else "",
            "ccnl_txt": f" con applicazione del {v['ccnl']}" if v.get("ccnl") else "",
            "qualifica_txt": f", con qualifica/livello {v['qualifica']}" if v.get("qualifica") else "",
            "durata_txt": f" della durata di {v['durata_prova']}" if v.get("durata_prova") else ""}


def _controlli_telematica(v, genitore=True):
    av = []
    if v.get("telematica") != "già effettuata":
        av.append(AVVISO_TELEMATICA)
    elif not v.get("data_telematica"):
        av.append("Indicare la data di trasmissione del modulo telematico.")
    if genitore and v.get("genitore") == "Sì":
        av.insert(0, AVVISO_GENITORE)
    if v.get("ultimo_giorno") and v.get("data_lettera") and v["ultimo_giorno"] < v["data_lettera"]:
        av.insert(0, "L'ultimo giorno di lavoro precede la data della lettera: verificare le date.")
    return av


MODELLI.update({
    "dimissioni_lavoratore": {
        "titolo": "Comunicazione di dimissioni",
        "sottotitolo": "Comunicazione al datore di lavoro – efficacia con la procedura telematica (art. 26 D.Lgs. 151/2015)",
        "categorie": ["Dimissioni"],
        "testata": TESTATA_LAV, "firma": "lavoratore", "ricevuta": "datore", "pie_studio": False,
        "oggetto": "Comunicazione di dimissioni dal rapporto di lavoro – ultimo giorno di lavoro {ultimo_giorno}.",
        "campi": MITTENTE_LAV + DESTINATARIO + COMUNI_LAV + [
            C("data_assunzione", "Data di assunzione", D, "", False), C("ccnl", "CCNL applicato", T, "", False),
            C("qualifica", "Qualifica e livello", T, "", False),
            C("giorni_preavviso", "Preavviso previsto dal CCNL (es. 15 giorni di calendario)"),
            S("preavviso", "Preavviso", PREAVVISO_LAV), C("ultimo_giorno", "Ultimo giorno di lavoro", D)] + TELEMATICA + [
            S("genitore", "Lavoratrice in gravidanza o genitore con figlio fino a 3 anni", ["No", "Sì"]),
            C("note", "Altre comunicazioni (es. restituzione di beni aziendali, ferie residue)", A, "", False)],
        "avvisi": ["Verificare la durata del preavviso nel CCNL applicato (in base a livello e anzianità)."],
        "derivati": _derivati_dimissioni, "controlli_extra": _controlli_telematica,
        "blocchi": [
            ("saluto", "Spett.le **{azienda}**,"),
            ("p", "il/la sottoscritto/a **{lavoratore}** {cf_txt}, dipendente di codesta azienda{assunzione_txt}{ccnl_txt}{qualifica_txt}, con la presente comunica di rassegnare le proprie dimissioni dal rapporto di lavoro."),
            ("sez", "PROCEDURA TELEMATICA"),
            ("p", "{telematica_txt}"),
            ("sez", "PREAVVISO E CESSAZIONE"),
            ("p", "Il preavviso previsto dal contratto collettivo applicato è pari a {giorni_preavviso}: {preavviso}. L'ultimo giorno di lavoro sarà il **{ultimo_giorno}**."),
            ("testo_campo", "note"),
            ("p", "Chiede che le competenze di fine rapporto e il TFR siano corrisposti, e la documentazione di legge consegnata, nei termini previsti."),
            ("nota", NOTA_TELEMATICA),
        ],
    },
    "dimissioni_prova": {
        "titolo": "Dimissioni durante il periodo di prova",
        "sottotitolo": "Recesso del lavoratore durante il periodo di prova (art. 2096 c.c.)",
        "categorie": ["Dimissioni"],
        "testata": TESTATA_LAV, "firma": "lavoratore", "ricevuta": "datore", "pie_studio": False,
        "oggetto": "Recesso dal rapporto di lavoro durante il periodo di prova – ultimo giorno di lavoro {ultimo_giorno}.",
        "campi": MITTENTE_LAV + DESTINATARIO + COMUNI_LAV + [
            C("data_assunzione", "Data di assunzione", D),
            C("durata_prova", "Durata del periodo di prova (come da contratto)", T, "", False),
            C("ultimo_giorno", "Ultimo giorno di lavoro", D)] + TELEMATICA,
        "avvisi": ["Procedura telematica durante la prova: la Circolare del Ministero del Lavoro n. 12/2016 la escludeva, ma la "
                   "Cassazione (ord. 11/09/2025, n. 24991) ha ritenuto tassative le esclusioni dell'art. 26 D.Lgs. 151/2015 e valida "
                   "la revoca entro 7 giorni anche in prova. Per prudenza, trasmettere comunque il modulo telematico.",
                   "Verificare nel contratto individuale e nel CCNL la durata del periodo di prova e le eventuali regole sul recesso."],
        "derivati": _derivati_dimissioni, "controlli_extra": lambda v: _controlli_telematica(v, genitore=False),
        "blocchi": [
            ("saluto", "Spett.le **{azienda}**,"),
            ("p", "il/la sottoscritto/a **{lavoratore}** {cf_txt}, assunto/a in data {data_assunzione} con patto di prova{durata_txt}, con la presente comunica di recedere dal rapporto di lavoro durante il periodo di prova, ai sensi dell'art. 2096 del codice civile."),
            ("p", "L'ultimo giorno di lavoro sarà il **{ultimo_giorno}**. Chiede che le competenze maturate siano corrisposte nei termini previsti."),
            ("sez", "PROCEDURA TELEMATICA"),
            ("p", "{telematica_txt}"),
            ("nota", "Sull'obbligo della procedura telematica durante il periodo di prova le indicazioni non sono univoche: la Circolare "
                     "del Ministero del Lavoro n. 12/2016 lo escludeva, mentre la Corte di Cassazione (ord. n. 24991/2025) ha ritenuto "
                     "tassative le esclusioni previste dall'art. 26 del D.Lgs. 151/2015. Per prudenza le dimissioni vengono trasmesse "
                     "anche con il modulo telematico; la presente lettera non lo sostituisce."),
        ],
    },
    "dimissioni_giusta_causa": {
        "titolo": "Dimissioni per giusta causa",
        "sottotitolo": "Recesso senza preavviso ai sensi dell'art. 2119 c.c.",
        "categorie": ["Dimissioni"],
        "testata": TESTATA_LAV, "firma": "lavoratore", "ricevuta": "datore", "pie_studio": False,
        "oggetto": "Dimissioni per giusta causa con effetto dal {data_effetto}.",
        "campi": MITTENTE_LAV + DESTINATARIO + COMUNI_LAV + [
            C("data_assunzione", "Data di assunzione", D, "", False), C("ccnl", "CCNL applicato", T, "", False),
            C("qualifica", "Qualifica e livello", T, "", False),
            C("fatti", "Fatti che costituiscono la giusta causa (date e circostanze; righe con '- ' = elenco)", A),
            C("data_effetto", "Data di cessazione (effetto immediato)", D),
            C("richieste", "Ulteriori richieste (es. retribuzioni non corrisposte, con periodi e importi)", A, "", False)] + TELEMATICA + [
            S("genitore", "Lavoratrice in gravidanza o genitore con figlio fino a 3 anni", ["No", "Sì"])],
        "avvisi": ["Anche le dimissioni per giusta causa si trasmettono con la procedura telematica (art. 26 D.Lgs. 151/2015).",
                   "Le dimissioni per giusta causa consentono l'accesso alla NASpI se ricorrono gli altri requisiti (art. 3, c. 2, D.Lgs. 22/2015).",
                   "Descrivere fatti specifici e documentabili e valutarne la gravità e la tempestività della reazione prima dell'invio."],
        "derivati": _derivati_dimissioni, "controlli_extra": _controlli_telematica,
        "blocchi": [
            ("saluto", "Spett.le **{azienda}**,"),
            ("p", "il/la sottoscritto/a **{lavoratore}** {cf_txt}, dipendente di codesta azienda{assunzione_txt}{ccnl_txt}{qualifica_txt}, con la presente comunica di rassegnare le proprie dimissioni per giusta causa, ai sensi dell'art. 2119 del codice civile, senza preavviso e con effetto dal **{data_effetto}**, per i motivi di seguito indicati."),
            ("sez", "MOTIVI"),
            ("testo_campo", "fatti"),
            ("p", "Le circostanze descritte non consentono la prosecuzione, neppure provvisoria, del rapporto di lavoro."),
            ("sez", "RICHIESTE"),
            ("p", "Il/la sottoscritto/a chiede la corresponsione delle competenze di fine rapporto, del TFR e dell'indennità sostitutiva del preavviso prevista dall'art. 2119 c.c., oltre a quanto eventualmente indicato di seguito."),
            ("testo_campo", "richieste"),
            ("sez", "PROCEDURA TELEMATICA"),
            ("p", "{telematica_txt}"),
            ("p", "Si riserva ogni azione a tutela dei propri diritti."),
            ("nota", NOTA_TELEMATICA),
        ],
    },
    "dimissioni_domestico": {
        "titolo": "Dimissioni del lavoratore domestico",
        "sottotitolo": "Rapporto di lavoro domestico – escluso dalla procedura telematica (art. 26, c. 7, D.Lgs. 151/2015)",
        "categorie": ["Dimissioni", "Colf e badanti"],
        "testata": TESTATA_LAV, "firma": "lavoratore", "ricevuta": "datore", "pie_studio": False,
        "oggetto": "Dimissioni dal rapporto di lavoro domestico – ultimo giorno di lavoro {ultimo_giorno}.",
        "campi": MITTENTE_LAV + [C("azienda", "Datore di lavoro domestico (nome e cognome)"),
                                 C("sede_azienda", "Indirizzo del datore di lavoro")] + COMUNI_LAV + [
            C("data_assunzione", "Data di assunzione", D, "", False),
            C("qualifica", "Mansione e livello (CCNL lavoro domestico)", T, "", False),
            C("giorni_preavviso", "Preavviso previsto dal CCNL del lavoro domestico"),
            S("preavviso", "Preavviso", PREAVVISO_LAV), C("ultimo_giorno", "Ultimo giorno di lavoro", D)],
        "avvisi": ["Il rapporto di lavoro domestico è escluso dalla procedura telematica delle dimissioni (art. 26, c. 7, D.Lgs. 151/2015).",
                   "Il datore di lavoro deve comunicare la cessazione all'INPS entro 5 giorni dall'evento, in via telematica (scheda INPS \"Cessazione lavoratore domestico\").",
                   "Verificare la durata del preavviso nel CCNL del lavoro domestico (in base ad anzianità e orario)."],
        "derivati": _derivati_dimissioni,
        "controlli_extra": lambda v: ["L'ultimo giorno di lavoro precede la data della lettera: verificare le date."]
        if v.get("ultimo_giorno") and v.get("data_lettera") and v["ultimo_giorno"] < v["data_lettera"] else [],
        "blocchi": [
            ("saluto", "Gentile **{azienda}**,"),
            ("p", "il/la sottoscritto/a **{lavoratore}** {cf_txt}, alle Sue dipendenze con rapporto di lavoro domestico{assunzione_txt}{qualifica_txt}, con la presente comunica di rassegnare le proprie dimissioni."),
            ("sez", "PREAVVISO E CESSAZIONE"),
            ("p", "Il preavviso previsto dal contratto collettivo del lavoro domestico è pari a {giorni_preavviso}: {preavviso}. L'ultimo giorno di lavoro sarà il **{ultimo_giorno}**."),
            ("p", "Chiede che le competenze di fine rapporto e il TFR siano corrisposti, e la documentazione di legge consegnata, nei termini previsti."),
            ("nota", "Il rapporto di lavoro domestico è escluso dalla procedura telematica delle dimissioni (art. 26, comma 7, "
                     "D.Lgs. 151/2015). Si consiglia di consegnare la presente con modalità che ne attestino la ricezione."),
        ],
    },
    "preavviso_comunicazione": {
        "titolo": "Comunicazione relativa al preavviso",
        "sottotitolo": "Dimissioni del lavoratore – periodo di preavviso (art. 2118 c.c. e CCNL)",
        "categorie": ["Dimissioni"],
        "testata": TESTATA, "firma": "datore", "ricevuta": True,
        "oggetto": "Dimissioni del {data_dimissioni} – periodo di preavviso e data di cessazione del rapporto.",
        "campi": DATORE + LAVORATORE + COMUNI + [
            C("data_dimissioni", "Data delle dimissioni (trasmissione del modulo telematico)", D),
            C("ccnl", "CCNL applicato"), C("giorni_preavviso", "Preavviso previsto dal CCNL"),
            S("caso", "Situazione", ["Preavviso da lavorare", "Preavviso non lavorato: trattenuta dell'indennità sostitutiva",
                                     "Esonero dal preavviso su richiesta del lavoratore"]),
            C("data_cessazione", "Data di cessazione del rapporto", D),
            C("giorni_non_lavorati", "Preavviso non lavorato (es. 10 giorni) – solo in caso di trattenuta", T, "", False)],
        "avvisi": ["Verificare la durata del preavviso nel CCNL (livello e anzianità) e che le dimissioni siano state trasmesse con "
                   "la procedura telematica (art. 26 D.Lgs. 151/2015) o rientrino in un caso escluso.",
                   "In caso di esonero, conservare la richiesta scritta del lavoratore e far firmare la presente per accettazione."],
        "derivati": lambda v: {"caso_txt": {
            "Preavviso da lavorare": "Il preavviso dovrà essere regolarmente prestato: il rapporto di lavoro cesserà pertanto in data **{0}**, ultimo giorno di lavoro.",
            "Preavviso non lavorato: trattenuta dell'indennità sostitutiva":
                "Il preavviso non è stato prestato{1}. Ai sensi dell'art. 2118, secondo comma, c.c. e del CCNL applicato, l'indennità sostitutiva del preavviso non lavorato sarà trattenuta dalle competenze di fine rapporto. Il rapporto di lavoro cessa in data **{0}**.",
            "Esonero dal preavviso su richiesta del lavoratore":
                "Accogliendo la Sua richiesta, la Società La esonera dal prestare il preavviso: il rapporto di lavoro cesserà in data **{0}** e le parti concordano che per il periodo di preavviso non lavorato non sarà dovuta indennità sostitutiva da alcuna di esse.",
        }.get(v.get("caso"), "").format(_it(v.get("data_cessazione", "")),
                                         f" (preavviso non lavorato: {v['giorni_non_lavorati']})" if v.get("giorni_non_lavorati") else "")},
        "blocchi": [
            ("saluto", "Gentile **{lavoratore}**,"),
            ("p", "con riferimento alle Sue dimissioni del {data_dimissioni}, **{azienda}** Le comunica quanto segue in merito al periodo di preavviso previsto dal {ccnl}, pari a {giorni_preavviso}."),
            ("p", "{caso_txt}"),
            ("p", "Le competenze di fine rapporto e il TFR Le saranno corrisposti nei termini previsti, unitamente alla documentazione di legge."),
        ],
    },
})


# ---------- compilazione ----------
class _Fmt(dict):
    def __missing__(self, k):
        return ""


def _it(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return s


def _importo(s):
    if not s:
        return s
    try:
        n = float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
        return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return s


def _val(mod, valori):
    oggi = date.today().isoformat()
    out = {}
    for c in mod["campi"]:
        v = str(valori.get(c["id"], c.get("default", ""))).strip()
        out[c["id"]] = oggi if v == "{oggi}" else v
    return out


def _fmt(mod, v):
    f = _Fmt()
    for c in mod["campi"]:
        x = v[c["id"]]
        if c["tipo"] == D:
            x = _it(x)
        elif c["tipo"] == N and c["id"] in ("retribuzione", "importo", "superminimo", "tfr"):
            x = _importo(x)
        f[c["id"]] = x
    f["cf_txt"] = f"(C.F. {v['cf']})" if v.get("cf") else ""
    f["distribuzione_txt"] = f", con la seguente distribuzione: {v['distribuzione']}" if v.get("distribuzione") else ""
    f["superminimo_txt"] = f", oltre a un superminimo individuale assorbibile di € {_importo(v['superminimo'])} lordi mensili" if v.get("superminimo") else ""
    f["unilav_txt"] = f" in data {_it(v['unilav'])}" if v.get("unilav") else ""
    f["entita_txt"] = f" ({v['entita']})" if v.get("entita") else ""
    f["tfr_txt"] = f" e differenze di TFR pari a € {_importo(v['tfr'])}" if v.get("tfr") else ""
    try:
        n = int(float(v.get("termine_giorni") or 5))
    except ValueError:
        n = 5
    f["termine_txt"] = f"{n} ({GIORNI[n]})" if n in GIORNI else str(n)
    if mod.get("derivati"):  # testi che dipendono dalle scelte (solo nei modelli che li prevedono)
        f.update(mod["derivati"](v))
    return f


def controlli(tipo, v):
    mod = MODELLI[tipo]
    avvisi = list(mod.get("avvisi", []))
    mancanti = [c["label"] for c in mod["campi"] if c.get("richiesto") and not v.get(c["id"])]
    if mancanti:
        avvisi.insert(0, "Campi non compilati (restano vuoti nel documento): " + "; ".join(mancanti))
    try:
        if tipo == "contestazione_disciplinare" and int(float(v.get("termine_giorni") or 0)) < 5:
            avvisi.insert(0, "Il termine per le giustificazioni non può essere inferiore a 5 giorni (art. 7 L. 300/1970).")
        if mod.get("controllo") == "sanzione" and v.get("data_contestazione") and v.get("data_lettera"):
            lim = datetime.strptime(v["data_contestazione"], "%Y-%m-%d").date() + timedelta(days=5)
            if datetime.strptime(v["data_lettera"], "%Y-%m-%d").date() < lim:
                avvisi.insert(0, f"ATTENZIONE: la sanzione non può essere applicata prima di 5 giorni dalla contestazione (art. 7, c. 5): non prima del {lim.strftime('%d/%m/%Y')}.")
    except ValueError:
        pass
    if mod.get("controlli_extra"):
        avvisi = mod["controlli_extra"](v) + avvisi
    return avvisi


def categorie_di(tipo):
    return MODELLI[tipo].get("categorie") or CATEGORIE_MODELLI.get(tipo, [])


def elenco():
    return [{"tipo": k, "titolo": m["titolo"], "campi": m["campi"], "categorie": categorie_di(k),
             "sottotitolo": m.get("sottotitolo", "")} for k, m in MODELLI.items()]


def biblioteca():
    """Categorie nell'ordine stabilito, con i modelli di ciascuna (le categorie vuote sono 'in preparazione')."""
    return [{"categoria": c, "modelli": [{"tipo": k, "titolo": m["titolo"]} for k, m in MODELLI.items() if c in categorie_di(k)]}
            for c in CATEGORIE]


# ---------- rendering .docx ----------
def _rgb(h):
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _bordi(cell, **lati):
    tcPr = cell._tc.get_or_add_tcPr()
    b = OxmlElement("w:tcBorders")
    for lato in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{lato}")
        if lato in lati:
            sz, col = lati[lato]
            el.set(qn("w:val"), "single"); el.set(qn("w:sz"), str(sz)); el.set(qn("w:color"), col)
        else:
            el.set(qn("w:val"), "nil")
        b.append(el)
    tcPr.append(b)


def _bordo_basso(p, col=NAVY):
    pPr = p._p.get_or_add_pPr()
    pb = OxmlElement("w:pBdr")
    el = OxmlElement("w:bottom")
    el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "8"); el.set(qn("w:space"), "4"); el.set(qn("w:color"), col)
    pb.append(el); pPr.append(pb)


def _testo(p, testo, size=None, color=None, bold=False, italic=False):
    for i, parte in enumerate(testo.split("**")):
        if not parte:
            continue
        r = p.add_run(parte)
        r.bold = bold or i % 2 == 1
        r.italic = italic
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = _rgb(color)


def _p(doc, testo="", align=None, size=None, color=None, bold=False, italic=False, before=0, after=6, keep=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before, pf.space_after, pf.line_spacing = Pt(before), Pt(after), 1.12
    pf.keep_with_next = keep
    if align is not None:
        p.alignment = align
    _testo(p, testo, size, color, bold, italic)
    return p


def _numero_pagina(p):
    for tipo, testo in (("begin", None), (None, " PAGE "), ("end", None)):
        r = p.add_run()
        r.font.size = Pt(8)
        if tipo:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), tipo)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = testo
        r._r.append(el)


def _tabella_kv(doc, righe):
    t = doc.add_table(rows=0, cols=2)
    t.autofit = False
    for k, val in righe:
        cells = t.add_row().cells
        cells[0].width, cells[1].width = Cm(5.2), Cm(11.3)
        _shade(cells[0], "EEF2F7")
        for c in cells:
            _bordi(c, bottom=(4, "D5DBE3"), top=(4, "D5DBE3"))
        for c, txt, b in ((cells[0], k, True), (cells[1], val, False)):
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(2); p.paragraph_format.space_before = Pt(2)
            _testo(p, txt, size=10, bold=b, color=NAVY if b else None)
    return t


def _intestazione(doc, scelta, v):
    if scelta == "Nessuna":
        return
    if scelta == "Azienda":
        nome = v.get("azienda", "").upper()
        riga = " – ".join(x for x in (v.get("sede_azienda"), f"P.IVA/C.F. {v['piva']}" if v.get("piva") else "") if x)
        qual = ""
    else:
        nome = f"{STUDIO['nome']} – {STUDIO['qualifica']}"
        qual = STUDIO.get("albo", "")
        riga = " | ".join(x for x in (STUDIO.get("indirizzo"), f"Tel. {STUDIO['telefono']}" if STUDIO.get("telefono") else "",
                                      f"P.IVA {STUDIO['piva']}" if STUDIO.get("piva") else "") if x)
    _p(doc, nome, WD_ALIGN_PARAGRAPH.CENTER, 14, NAVY, True, after=0)
    if qual:
        _p(doc, qual, WD_ALIGN_PARAGRAPH.CENTER, 9, GRIGIO, after=0)
    p = _p(doc, riga, WD_ALIGN_PARAGRAPH.CENTER, 9, GRIGIO, after=0)
    if scelta == "Studio":
        p2 = _p(doc, " | ".join(x for x in (f"PEC: {STUDIO['pec']}" if STUDIO.get("pec") else "", STUDIO.get("web", "")) if x),
                WD_ALIGN_PARAGRAPH.CENTER, 9, GRIGIO, after=10)
        _bordo_basso(p2)
    else:
        _bordo_basso(p)
        p.paragraph_format.space_after = Pt(10)


def genera(tipo, valori):
    if Document is None:
        raise ValueError("Manca il componente python-docx: eseguire  pip install python-docx  e riavviare.")
    if tipo not in MODELLI:
        raise ValueError("Modello di lettera sconosciuto.")
    mod = MODELLI[tipo]
    v = _val(mod, valori)
    avvisi = controlli(tipo, v)
    f = _fmt(mod, v)
    fill = lambda s: s.format_map(f)

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.3)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

    # piè di pagina
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # le lettere scritte dal lavoratore non riportano i dati dello Studio
    r = fp.add_run(f"{STUDIO['nome']} – {STUDIO['qualifica']} – Albo di Napoli n. 3645  |  Pag. " if mod.get("pie_studio", True) else "Pag. ")
    r.font.size = Pt(8); r.font.color.rgb = _rgb(GRIGIO)
    _numero_pagina(fp)

    _intestazione(doc, v.get("intestazione", "Studio"), v)
    _p(doc, mod["titolo"].upper(), WD_ALIGN_PARAGRAPH.CENTER, 16, NAVY, True, before=6, after=2)
    _p(doc, mod["sottotitolo"], WD_ALIGN_PARAGRAPH.CENTER, 10, GRIGIO, italic=True, after=10)

    righe = [(k, fill(t)) for k, t in mod["testata"]]
    _tabella_kv(doc, [(k, t) for k, t in righe if t.strip()])

    # riquadro oggetto
    _p(doc, "", after=4)
    ob = doc.add_table(rows=1, cols=1)
    c = ob.rows[0].cells[0]
    _shade(c, "E8F0F8")
    _bordi(c, left=(36, NAVY))
    p = c.paragraphs[0]
    p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(5)
    _testo(p, "**Oggetto:** " + fill(mod["oggetto"]), size=10.5, color=NAVY)
    _p(doc, "", after=4)

    def addebiti():
        for n in (1, 2, 3):
            tit, txt = v.get(f"addebito_{n}_titolo", ""), v.get(f"addebito_{n}_testo", "")
            if not (tit or txt):
                continue
            _p(doc, f"{n}.  {tit}", size=11.5, color=ROSSO, bold=True, before=6, after=3, keep=True)
            testo(txt)

    def testo(txt):
        for riga in txt.split("\n"):
            riga = riga.strip()
            if not riga:
                continue
            if riga.startswith("- "):
                p = _p(doc, "•  " + riga[2:], WD_ALIGN_PARAGRAPH.JUSTIFY, after=2)
                p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Cm(0.9), Cm(-0.5)
            else:
                _p(doc, riga, WD_ALIGN_PARAGRAPH.JUSTIFY)

    J = WD_ALIGN_PARAGRAPH.JUSTIFY
    for b in mod["blocchi"]:
        k = b[0]
        if k == "saluto":
            _p(doc, fill(b[1]), after=8)
        elif k == "sez":
            _p(doc, b[1], size=12, color=NAVY, bold=True, before=10, after=4, keep=True)
        elif k == "p":
            _p(doc, fill(b[1]), J)
        elif k == "testo_campo":
            testo(v.get(b[1], ""))
        elif k == "elenco_campo":
            for riga in [x.strip() for x in v.get(b[1], "").split("\n") if x.strip()]:
                p = _p(doc, "•  " + riga, J, after=3, bold=b[2])
                p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Cm(0.9), Cm(-0.5)
        elif k == "num":
            for i, t in enumerate(b[1], 1):
                p = _p(doc, f"{i}.  " + fill(t), J, after=4)
                p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Cm(0.9), Cm(-0.6)
        elif k == "tab":
            rr = [(a, fill(t)) for a, t in b[2]]
            rr = [(a, t) for a, t in rr if t.strip(" ,")]
            if rr:
                _p(doc, b[1], size=12, color=NAVY, bold=True, before=4, after=4, keep=True)
                _tabella_kv(doc, rr)
                _p(doc, "", after=2)
        elif k == "addebiti":
            addebiti()
        elif k == "nota":  # riquadro di avvertenza nel documento
            _p(doc, "", after=2)
            nb = doc.add_table(rows=1, cols=1)
            cn = nb.rows[0].cells[0]
            _shade(cn, "FFF6DD")
            _bordi(cn, left=(36, "C9731A"))
            pn = cn.paragraphs[0]
            pn.paragraph_format.space_before = pn.paragraph_format.space_after = Pt(5)
            _testo(pn, "**Avvertenza.** " + fill(b[1]), size=9.5)
            _p(doc, "", after=2)

    _p(doc, "Distinti saluti,", before=12, after=26, keep=True)
    if mod["firma"] == "studio":
        _p(doc, f"{STUDIO['nome']}\n{STUDIO['qualifica']}", WD_ALIGN_PARAGRAPH.RIGHT, after=4)
    elif mod["firma"] == "lavoratore":
        _p(doc, f"___________________________________________\nFirma del lavoratore ({v.get('lavoratore', '')})", WD_ALIGN_PARAGRAPH.RIGHT, after=4)
    else:
        rapp = f" ({v['rappresentante']})" if v.get("rappresentante") else ""
        _p(doc, f"___________________________________________\nFirma del Datore di Lavoro{rapp}", WD_ALIGN_PARAGRAPH.RIGHT, after=4)
    if mod.get("ricevuta") == "datore":
        _p(doc, "Per ricevuta:\n\nData ____________________      Timbro e firma del datore di lavoro ______________________________", size=10, before=14)
    elif mod.get("ricevuta"):
        _p(doc, "Per ricevuta e presa visione:\n\nData ____________________      Firma del lavoratore ______________________________", size=10, before=14)

    buf = io.BytesIO()
    doc.save(buf)
    nome = f"{tipo}_{(v.get('lavoratore') or 'lavoratore').replace(' ', '_')}.docx"
    return nome, buf.getvalue(), avvisi
