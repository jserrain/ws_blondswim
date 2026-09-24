"""Tests per al conversor XLSX → JSON."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from blondswim.ingestion.xlsx_to_json import (
    DataParseError,
    convertir_calendari,
    convertir_macrocicle_jep,
    convertir_nedador_ritmes,
    determinar_font_ritmes,
    parsejar_data,
    reconciliar_piscina_modalitat,
)


class TestParsejarData:
    """Tests per a la funció parsejar_data."""

    def test_datetime_unic(self):
        """Test amb un datetime únic."""
        data = datetime(2027, 1, 15)
        inici, fi = parsejar_data(data, 2)
        assert inici == "2027-01-15"
        assert fi == "2027-01-15"

    def test_rang_text(self):
        """Test amb un rang en format text."""
        data = "2027-01-16 a 2027-01-17"
        inici, fi = parsejar_data(data, 2)
        assert inici == "2027-01-16"
        assert fi == "2027-01-17"

    def test_data_unica_text(self):
        """Test amb una data única en format text."""
        data = "2027-01-15"
        inici, fi = parsejar_data(data, 2)
        assert inici == "2027-01-15"
        assert fi == "2027-01-15"

    def test_format_no_reconegut(self):
        """Test que el format no reconegut llança error."""
        with pytest.raises(DataParseError) as exc_info:
            parsejar_data("15/01/2027", 5)
        assert "Fila 5" in str(exc_info.value)
        assert "format de data no reconegut" in str(exc_info.value)

    def test_valor_buit(self):
        """Test amb valor buit."""
        with pytest.raises(DataParseError):
            parsejar_data(None, 3)


class TestReconciliarPiscinaModalitat:
    """Tests per a la funció reconciliar_piscina_modalitat."""

    def test_piscina_normal(self):
        """Test amb piscina normal."""
        piscina, skip = reconciliar_piscina_modalitat("25m", "piscina", 2)
        assert piscina == "25m"
        assert skip is False

    def test_piscina_amb_espais(self):
        """Test amb piscina amb espais."""
        piscina, skip = reconciliar_piscina_modalitat("  50m  ", "piscina", 2)
        assert piscina == "50m"
        assert skip is False

    def test_aigues_obertes(self):
        """Test amb aigües obertes (piscina buida, modalitat aaoo)."""
        piscina, skip = reconciliar_piscina_modalitat("", "aaoo", 2)
        assert piscina == "aaoo"
        assert skip is False

    def test_aigues_obertes_amb_espais(self):
        """Test amb aigües obertes (piscina amb espais)."""
        piscina, skip = reconciliar_piscina_modalitat("   ", "aaoo", 2)
        assert piscina == "aaoo"
        assert skip is False

    def test_inconsistencia_piscina_modalitat(self):
        """Test amb inconsistència: modalitat=piscina però piscina buida."""
        _piscina, skip = reconciliar_piscina_modalitat("", "piscina", 5)
        assert skip is True

    def test_inconsistencia_amb_espais(self):
        """Test amb inconsistència: piscina només amb espais."""
        _piscina, skip = reconciliar_piscina_modalitat("   ", "piscina", 7)
        assert skip is True


class TestDeterminarFontRitmes:
    """Tests per a la funció determinar_font_ritmes."""

    def test_css_test_amb_temps(self):
        """Test amb temps CSS i text que indica test."""
        font = determinar_font_ritmes(300.5, 150.2, "Test CSS (2027-01-15)")
        assert font == "css_test"

    def test_estimat_sense_temps(self):
        """Test sense temps CSS."""
        font = determinar_font_ritmes(None, None, "Estimat per millor marca")
        assert font == "estimat_marca"

    def test_estimat_amb_text_diferent(self):
        """Test amb temps però text que no conté 'Test CSS'."""
        font = determinar_font_ritmes(300.5, 150.2, "Estimat provisional")
        assert font == "estimat_marca"

    def test_estimat_sense_text(self):
        """Test sense temps ni text."""
        font = determinar_font_ritmes(None, None, None)
        assert font == "estimat_marca"


class TestLlegirCapçaleres:
    """Tests per a la funció llegir_capçaleres."""

    def test_normalitzacio_capçaleres(self):
        """Test que les capçaleres es normalitzen correctament."""
        # Verificar que "Fase / Objectiu" es normalitza a "fase/objectiu"
        # i "Metodologia dominant" a "metodologiadominant"
        # Aquest test requereix un mock d'un worksheet
        # Es pot implementar quan es tingui openpyxl disponible als tests

    def test_header_row_per_defecte(self):
        """Test que per defecte llegeix la fila 1."""
        # Aquest test requereix un mock d'un worksheet
        # Es pot implementar quan es tingui openpyxl disponible als tests

    def test_header_row_personalitzat(self):
        """Test que pot llegir capçaleres d'una fila específica."""
        # Aquest test requereix un mock d'un worksheet
        # Es pot implementar quan es tingui openpyxl disponible als tests


class TestConvertirCalendari:
    """Tests per a la funció convertir_calendari amb fitxers reals."""

    def test_calendari_provisional_26_27(self, tmp_path):
        """Test que convertir_calendari processa correctament el fitxer real."""
        # Localitzar fitxer d'entrada
        base_dir = Path(__file__).parent.parent.parent
        fitxer_entrada = base_dir / "data" / "raw" / "Provisional26-27.xlsx"
        fitxer_sortida = tmp_path / "calendari_test.json"

        # Executar conversió
        stats = convertir_calendari(fitxer_entrada, fitxer_sortida)

        # Verificar estadístiques
        assert stats["total"] == 17, f"Esperat 17 competicions, obtingut {stats['total']}"
        assert stats["classe_a"] == 2, f"Esperat 2 competicions classe A, obtingut {stats['classe_a']}"

        # Verificar que el fitxer JSON s'ha creat
        assert fitxer_sortida.exists()

        # Verificar contingut del JSON
        with open(fitxer_sortida, "r", encoding="utf-8") as f:
            competicions = json.load(f)

        assert len(competicions) == 17
        
        # Verificar que hi ha exactament 2 competicions de classe A
        classe_a = [c for c in competicions if c["classe"] == "A"]
        assert len(classe_a) == 2


class TestConvertirMacrocicleJep:
    """Tests per a la funció convertir_macrocicle_jep amb fitxers reals."""

    def test_macrocicle_jep(self, tmp_path):
        """Test que convertir_macrocicle_jep processa correctament el fitxer real."""
        # Localitzar fitxer d'entrada
        base_dir = Path(__file__).parent.parent.parent
        fitxer_entrada = base_dir / "data" / "raw" / "Planificacio_Mesocicles_Jep.xlsx"
        fitxer_sortida = tmp_path / "macrocicle_jep_test.json"

        # Executar conversió
        stats = convertir_macrocicle_jep(fitxer_entrada, fitxer_sortida)

        # Verificar estadístiques - hauria de ser 5 mesocicles, no 8
        assert stats["mesocicles"] == 5, f"Esperat 5 mesocicles, obtingut {stats['mesocicles']}"

        # Verificar que el fitxer JSON s'ha creat
        assert fitxer_sortida.exists()

        # Verificar contingut del JSON
        with open(fitxer_sortida, "r", encoding="utf-8") as f:
            macrocicle = json.load(f)

        assert len(macrocicle["mesocicles"]) == 5
        
        # Verificar que els ids són slugs (minúscules, sense espais ni accents)
        for mesocicle in macrocicle["mesocicles"]:
            mesocicle_id = mesocicle["id"]
            # Verificar que és minúscules
            assert mesocicle_id == mesocicle_id.lower(), f"ID '{mesocicle_id}' no és minúscules"
            # Verificar que no té espais
            assert " " not in mesocicle_id, f"ID '{mesocicle_id}' conté espais"
            # Verificar que el nom original es manté
            assert mesocicle["nom"] != mesocicle_id or mesocicle_id.islower()


class TestConvertirNedadorRitmes:
    """Tests per a la funció convertir_nedador_ritmes amb fitxers reals."""

    def test_nedador_jep(self, tmp_path):
        """Test que convertir_nedador_ritmes processa correctament Jep."""
        # Localitzar fitxer d'entrada
        base_dir = Path(__file__).parent.parent.parent
        fitxer_entrada = base_dir / "data" / "raw" / "Planificacio_Mesocicles_Jep.xlsx"

        # Executar conversió
        stats = convertir_nedador_ritmes(fitxer_entrada, tmp_path)

        # Verificar que s'ha processat 1 nedador
        assert len(stats["nedadors"]) == 1

        nedador_info = stats["nedadors"][0]
        
        # Verificar que el fitxer JSON s'ha creat
        fitxer_sortida = tmp_path / nedador_info["fitxer"]
        assert fitxer_sortida.exists()

        # Carregar i verificar contingut
        with open(fitxer_sortida, "r", encoding="utf-8") as f:
            nedador = json.load(f)

        # Verificar categoria
        assert nedador["categoria"] == "master", f"Esperat categoria='master', obtingut '{nedador['categoria']}'"

        # Verificar mode_ritme
        assert nedador["mode_ritme"] == "temps", f"Esperat mode_ritme='temps', obtingut '{nedador['mode_ritme']}'"

        # Verificar ritmes_cursa_objectiu té 3 elements
        assert len(nedador["ritmes_cursa_objectiu"]) == 3, \
            f"Esperat 3 ritmes_cursa_objectiu, obtingut {len(nedador['ritmes_cursa_objectiu'])}"

        # Verificar ritmes_css.a2 està proper a 82.09 (±0.01)
        a2_valor = nedador["ritmes_css"]["a2"]
        assert abs(a2_valor - 82.09) <= 0.01, \
            f"Esperat ritmes_css.a2 ≈ 82.09, obtingut {a2_valor}"
