import unittest

from pensioni import stima_importo


class TestStimaPensione(unittest.TestCase):
    def test_lordo_e_netto_con_parametri_forniti(self):
        risultato = stima_importo({
            "montante_euro": 200000, "coefficiente": 0.05,
            "anni_proiezione": 0, "contributi_annui_euro": 0,
            "mensilita": 13,
            "irpef_scaglioni": [[28000, 0.23], [50000, 0.35], [None, 0.43]],
            "detrazione_annua": 0, "addizionali_percentuale": 0,
        })
        self.assertEqual(risultato["lordo_annuo_euro"], 10000)
        self.assertEqual(risultato["lordo_mensile_euro"], round(10000 / 13, 2))
        self.assertEqual(risultato["netto_annuo_euro"], 7700)

    def test_proiezione_montante(self):
        risultato = stima_importo({"montante_euro": 100000, "coefficiente": 0.05,
                                   "anni_proiezione": 2, "contributi_annui_euro": 10000,
                                   "rivalutazione_annua": 0.02})
        self.assertEqual(risultato["montante_proiettato_euro"], 124040)
        self.assertIsNone(risultato["netto_annuo_euro"])

    def test_netto_richiede_scaglioni_completi(self):
        with self.assertRaises(ValueError):
            stima_importo({"montante_euro": 100000, "coefficiente": 0.05,
                           "anni_proiezione": 0, "contributi_annui_euro": 0,
                           "irpef_scaglioni": [[28000, 0.23]]})


if __name__ == "__main__":
    unittest.main()
