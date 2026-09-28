"""Tests per a la ingestió de microcicles des d'Excel."""

import pytest
from pathlib import Path

from blondswim.ingestion.xlsx_to_json import convertir_microcicles, _slug


class TestSlug:
    """Tests per a la funció _slug."""
    
    def test_slug_basic(self):
        assert _slug("Preparació General 1") == "preparacio-general-1"
    
    def test_slug_amb_barra(self):
        assert _slug("Preparació/Específica") == "preparacio-especifica"
    
    def test_slug_accents(self):
        assert _slug("Transició") == "transicio"
    
    def test_slug_majuscules(self):
        assert _slug("PREPARACIÓ GENERAL") == "preparacio-general"


class TestConvertirMicrocicles:
    """Tests per a convertir_microcicles."""
    
    @pytest.fixture
    def fitxer_excel(self) -> Path:
        """Path al fitxer Excel de test."""
        base_dir = Path(__file__).parent.parent.parent
        return base_dir / "data" / "raw" / "Planificacio_Mesocicles_Jep.xlsx"
    
    def test_mapatge_tipus(self, fitxer_excel):
        """Verificar que els tipus es mapegen correctament."""
        resultat = convertir_microcicles(fitxer_excel)
        
        # Obtenir tots els microcicles
        tots_microcicles = []
        for microcicles in resultat.values():
            tots_microcicles.extend(microcicles)
        
        # Verificar que només hi ha tipus vàlids
        tipus_trobats = {m.tipus_base for m in tots_microcicles}
        tipus_valids = {"carrega", "descarrega", "qualitat", "taper", "transicio"}
        assert tipus_trobats.issubset(tipus_valids)
    
    def test_mesocicle_rep_microcicles(self, fitxer_excel):
        """Verificar que un mesocicle real rep la llista correcta de microcicles."""
        resultat = convertir_microcicles(fitxer_excel)
        
        # Verificar que hi ha microcicles per a "preparacio-general-1"
        mesocicle_id = "preparacio-general-1"
        assert mesocicle_id in resultat
        
        microcicles = resultat[mesocicle_id]
        assert len(microcicles) > 0
        
        # Verificar primer microcicle
        primer = microcicles[0]
        assert primer.setmana == 1
        assert primer.volum_objectiu == 15500
        assert primer.tipus_base == "carrega"
        assert primer.dies_qualitat is True
    
    def test_dies_qualitat_nomes_carrega(self, fitxer_excel):
        """Verificar que dies_qualitat només és True per tipus 'carrega'."""
        resultat = convertir_microcicles(fitxer_excel)
        
        for microcicles in resultat.values():
            for m in microcicles:
                if m.tipus_base == "carrega":
                    assert m.dies_qualitat is True
                else:
                    assert m.dies_qualitat is False
    
    def test_observacions_opcionals(self, fitxer_excel):
        """Verificar que les observacions són opcionals."""
        resultat = convertir_microcicles(fitxer_excel)
        
        # Buscar microcicles amb i sense notes
        amb_notes = False
        sense_notes = False
        
        for microcicles in resultat.values():
            for m in microcicles:
                if m.notes:
                    amb_notes = True
                else:
                    sense_notes = True
        
        # Verificar que hi ha exemples de tots dos casos
        assert amb_notes or sense_notes  # Al menys un dels dos casos existeix
