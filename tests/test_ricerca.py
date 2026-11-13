import tempfile
import unittest
from pathlib import Path

import ricerca


class TestRicerca(unittest.TestCase):
    def test_fonti_insufficienti_senza_dati(self):
        with tempfile.TemporaryDirectory() as cartella:
            vecchia = ricerca.fonti.carica_cartella
            ricerca.fonti.carica_cartella = lambda: []
            try:
                self.assertEqual(ricerca.cerca("licenziamento")["stato"], "fonti_insufficienti")
            finally:
                ricerca.fonti.carica_cartella = vecchia

    def test_query_vuota_rifiutata(self):
        with self.assertRaises(ValueError):
            ricerca.cerca("  ")

    def test_limite_convalidato(self):
        with self.assertRaises(ValueError):
            ricerca.cerca("fisco", limite=0)


if __name__ == "__main__":
    unittest.main()
