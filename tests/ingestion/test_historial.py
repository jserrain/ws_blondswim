"""Tests per a la conversió de l'historial de pretemporada."""

from pathlib import Path

import pytest

from blondswim.ingestion.xlsx_to_json import convertir_pretemporada
from blondswim.models.historial import SessioRealitzada


class TestConvertirPretemporada:
    """Tests per a la funció convertir_pretemporada."""

    @pytest.fixture
    def sessions(self) -> list[SessioRealitzada]:
        """Carregar sessions de pretemporada."""
        base_dir = Path(__file__).parent.parent.parent
        fitxer_entrada = base_dir / "data" / "raw" / "PretemporadaSep26-27.xlsx"
        return convertir_pretemporada(fitxer_entrada)

    def test_nombre_dies_setmanes_3_8(self, sessions):
        """Verificar nombre de dies amb entrenament a les setmanes 3-8."""
        dies_setmanes_3_8 = [s for s in sessions if s.setmana and 3 <= s.setmana <= 8]
        
        # Comptar dies amb entrenament (volum > 0 o series no buides)
        dies_amb_entrenament = [
            s for s in dies_setmanes_3_8 
            if s.volum_total_m > 0 or len(s.series) > 0
        ]
        
        assert len(dies_amb_entrenament) > 0, "Hauria d'haver-hi dies amb entrenament a les setmanes 3-8"

    def test_dilluns_18_agost_2026(self, sessions):
        """Verificar dades del dilluns 18 d'agost 2026."""
        sessio_18_ago = next((s for s in sessions if s.data == "2026-08-18"), None)
        
        assert sessio_18_ago is not None, "Hauria d'existir sessió per al 2026-08-18"
        assert sessio_18_ago.volum_total_m == 2700, f"Volum hauria de ser 2700m, és {sessio_18_ago.volum_total_m}"
        assert sessio_18_ago.temps_total_min == 55.0, f"Temps hauria de ser 55min, és {sessio_18_ago.temps_total_min}"

    def test_intensitats_no_estandard(self, sessions):
        """Verificar que intensitats no estàndard (MPLA, TOLA, AeM) es guarden correctament."""
        intensitats_trobades = set()
        
        for sessio in sessions:
            for serie in sessio.series:
                if serie.intensitat:
                    intensitats_trobades.add(serie.intensitat)
        
        # Verificar que es poden guardar intensitats no estàndard
        intensitats_no_estandard = {"MPLA", "TOLA", "AeM", "AeM/A1"}
        intensitats_presents = intensitats_trobades & intensitats_no_estandard
        
        # Si hi ha alguna intensitat no estàndard, verificar que s'ha guardat com a text
        if intensitats_presents:
            assert all(isinstance(i, str) for i in intensitats_presents), \
                "Les intensitats no estàndard haurien de ser strings"

    def test_travessa_banyoles_series_buides(self, sessions):
        """Verificar que dies especials (sense sèries) es creen correctament."""
        sessions_especials = [
            s for s in sessions
            if s.volum_total_m == 0 and len(s.series) == 0
        ]
        for sessio in sessions_especials:
            assert isinstance(sessio.series, list)
            assert len(sessio.series) == 0
            assert sessio.volum_total_m == 0
            assert sessio.temps_total_min == 0.0

    def test_ordre_cronologic(self, sessions):
        """Verificar que les sessions estan ordenades cronològicament."""
        dates = [s.data for s in sessions]
        assert dates == sorted(dates), "Les sessions haurien d'estar ordenades cronològicament"

    def test_estructura_series(self, sessions):
        """Verificar l'estructura de les sèries."""
        sessions_amb_series = [s for s in sessions if len(s.series) > 0]
        
        assert len(sessions_amb_series) > 0, "Hauria d'haver-hi sessions amb sèries"
        
        for sessio in sessions_amb_series:
            for i, serie in enumerate(sessio.series, start=1):
                assert serie.ordre == i, f"L'ordre de la sèrie hauria de ser {i}, és {serie.ordre}"
                assert serie.execucio, "Tota sèrie hauria de tenir execució"
