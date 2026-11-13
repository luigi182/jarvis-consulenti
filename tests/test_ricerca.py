import unittest
from unittest.mock import patch

import ricerca


class TestRicerca(unittest.TestCase):
    def test_fonti_insufficienti_senza_dati(self):
        with patch.object(ricerca.fonti, "carica_cartella", return_value=[]):
            self.assertEqual(ricerca.cerca("licenziamento")["stato"], "fonti_insufficienti")

    def test_query_vuota_rifiutata(self):
        with self.assertRaises(ValueError):
            ricerca.cerca("  ")

    def test_limite_convalidato(self):
        for limite in (0, 101, True, 1.5):
            with self.subTest(limite=limite), self.assertRaises(ValueError):
                ricerca.cerca("fisco", limite=limite)

    def test_data_non_valida(self):
        with self.assertRaises(ValueError):
            ricerca.cerca("fisco", alla_data="2026-02-31")

    def test_fonte_vecchia_non_e_usabile(self):
        voce = {
            "id": "x", "aree": ["lavoro"], "ambito": "nazionale", "territorio": None,
            "tema": "licenziamento", "testo": "licenziamento individuale", "riferimenti": "articolo",
            "fonte_nome": "Normattiva", "fonte_url": "https://www.normattiva.it", "stato": "verificata",
            "in_vigore_dal": "2020-01-01", "verificato_il": "2020-01-01", "modifiche": [],
            "tipo_fonte": "normativa",
        }
        with patch.object(ricerca.fonti, "carica_cartella", return_value=[voce]):
            risultato = ricerca.cerca("licenziamento", alla_data="2026-01-01")
        self.assertEqual(risultato["stato"], "fonti_insufficienti")
        self.assertEqual(len(risultato["fonti_da_verificare"]), 1)


if __name__ == "__main__":
    unittest.main()
