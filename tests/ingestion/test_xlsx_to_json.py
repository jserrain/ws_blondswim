"""Tests per al conversor XLSX → JSON."""

import pytest
from datetime import datetime

from blondswim.ingestion.xlsx_to_json import (
    DataParseError,
    InconsistentDataWarning,
    determinar_font_ritmes,
    llegir_capçaleres,
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
        piscina, skip = reconciliar_piscina_modalitat("", "piscina", 5)
        assert skip is True

    def test_inconsistencia_amb_espais(self):
        """Test amb inconsistència: piscina només amb espais."""
        piscina, skip = reconciliar_piscina_modalitat("   ", "piscina", 7)
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
        pass

    def test_header_row_per_defecte(self):
        """Test que per defecte llegeix la fila 1."""
        # Aquest test requereix un mock d'un worksheet
        # Es pot implementar quan es tingui openpyxl disponible als tests
        pass

    def test_header_row_personalitzat(self):
        """Test que pot llegir capçaleres d'una fila específica."""
        # Aquest test requereix un mock d'un worksheet
        # Es pot implementar quan es tingui openpyxl disponible als tests
        pass
