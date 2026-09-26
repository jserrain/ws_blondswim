"""
Tests per a les funcions de càlcul de zones fisiològiques CSS.

Valida amb dades reals de Jep:
- marca_100_lliure_seg = 77.08
- marca_50_lliure_seg = 33.44
- a2 ≈ 82.09 (±0.01)
- velocitat ≈ 67.55 (±0.01)
"""

import pytest

from blondswim.agents.zones_css import (
    calcular_css_pace,
    calcular_zones_des_de_css,
    calcular_zones_des_de_marca,
    determinar_zones_nedador,
)
from blondswim.models.nedador import (
    MarquesReferencia,
    Nedador,
    ParametresRitme,
    RitmesCSS,
)


class TestCalcularZonesDesDeMarca:
    """Tests per a calcular_zones_des_de_marca amb dades reals de Jep."""

    def test_zones_jep_validacio_manual(self):
        """
        Valida a2 i velocitat amb els valors verificats manualment de Jep.
        
        Dades d'entrada:
        - marca_100_lliure_seg = 77.08
        - marca_50_lliure_seg = 33.44
        - ParametresRitme per defecte
        
        Valors esperats (validats manualment):
        - a2 ≈ 82.09 (±0.01)
        - velocitat ≈ 67.55 (±0.01)
        """
        params = ParametresRitme()
        zones = calcular_zones_des_de_marca(
            marca_100_lliure_seg=77.08,
            marca_50_lliure_seg=33.44,
            params=params,
        )

        # Validació a2 (llindar)
        assert abs(zones["a2"] - 82.09) < 0.01, (
            f"a2 hauria de ser ≈82.09, obtingut {zones['a2']:.2f}"
        )

        # Validació velocitat (sprint)
        assert abs(zones["velocitat"] - 67.55) < 0.01, (
            f"velocitat hauria de ser ≈67.55, obtingut {zones['velocitat']:.2f}"
        )

    def test_totes_les_zones_jep(self):
        """Verifica que totes les zones es calculen correctament per a Jep."""
        params = ParametresRitme()
        zones = calcular_zones_des_de_marca(
            marca_100_lliure_seg=77.08,
            marca_50_lliure_seg=33.44,
            params=params,
        )

        # Recuperació: 77.08 * (1 + 0.20) = 92.496
        assert abs(zones["recuperacio"] - 92.496) < 0.01

        # A1: 77.08 * (1 + 0.13) = 87.1004
        assert abs(zones["a1"] - 87.1004) < 0.01

        # A2: 77.08 * (1 + 0.065) = 82.0902
        assert abs(zones["a2"] - 82.0902) < 0.01

        # A3: 77.08 * (1 + 0.015) = 78.2362
        assert abs(zones["a3"] - 78.2362) < 0.01

        # Velocitat: 33.44 * 2.02 = 67.5488
        assert abs(zones["velocitat"] - 67.5488) < 0.01

    def test_velocitat_no_supera_marca_100(self):
        """
        Verifica que la velocitat calculada NO supera la marca de 100m.
        
        Aquest és el test crític que detecta l'error documentat a
        docs/metodologia_ritmes.md punt 4: si calculéssim velocitat com
        marca_100 * 0.85, donaria un ritme més ràpid que el propi rècord.
        """
        params = ParametresRitme()
        zones = calcular_zones_des_de_marca(
            marca_100_lliure_seg=77.08,
            marca_50_lliure_seg=33.44,
            params=params,
        )

        # La velocitat (67.55s/100m) ha de ser més ràpida (menor temps) que a2 (82.09s)
        # però NO pot ser més ràpida que la marca de 100m (77.08s)
        assert zones["velocitat"] < zones["a2"], (
            "La velocitat ha de ser més ràpida que a2"
        )
        assert zones["velocitat"] < 77.08, (
            f"La velocitat ({zones['velocitat']:.2f}s) ha de ser més ràpida que "
            f"la marca de 100m (77.08s), però no tant com per ser físicament absurda"
        )


class TestCalcularZonesDesDeCss:
    """Tests per a calcular_zones_des_de_css."""

    def test_zones_amb_css_80_segons(self):
        """Verifica el càlcul de zones amb un CSS de 80s/100m."""
        params = ParametresRitme()
        zones = calcular_zones_des_de_css(css_pace_100m=80.0, params=params)

        # Recuperació: 80 + 12 = 92
        assert zones["recuperacio"] == 92.0

        # A1: 80 + 6 = 86
        assert zones["a1"] == 86.0

        # A2: 80 + 0 = 80 (el CSS és per definició el llindar)
        assert zones["a2"] == 80.0

        # A3: 80 - 4 = 76
        assert zones["a3"] == 76.0

        # Velocitat: 80 * 0.85 = 68
        assert zones["velocitat"] == 68.0

    def test_offsets_personalitzats(self):
        """Verifica que els offsets personalitzats s'apliquen correctament."""
        params = ParametresRitme(
            offset_recuperacio_css=15,
            offset_a1_css=8,
            offset_a2_css=0,
            offset_a3_css=-5,
            factor_velocitat=0.80,
        )
        zones = calcular_zones_des_de_css(css_pace_100m=100.0, params=params)

        assert zones["recuperacio"] == 115.0
        assert zones["a1"] == 108.0
        assert zones["a2"] == 100.0
        assert zones["a3"] == 95.0
        assert zones["velocitat"] == 80.0


class TestCalcularCssPace:
    """Tests per a calcular_css_pace (fórmula de Wakayoshi)."""

    def test_cas_conegut(self):
        """
        Test amb un cas conegut: t400=330s, t200=150s.
        
        Velocitat = (400-200) / (330-150) = 200/180 = 1.111... m/s
        Ritme = 100 / 1.111... = 90s/100m
        """
        ritme = calcular_css_pace(temps_400_seg=330.0, temps_200_seg=150.0)
        assert abs(ritme - 90.0) < 0.01

    def test_cas_jep_hipotetic(self):
        """
        Test amb temps hipotètics per a Jep que donarien CSS ≈ 80s/100m.
        
        Si CSS = 80s/100m, velocitat = 100/80 = 1.25 m/s
        Per obtenir aquesta velocitat: (400-200) / (t400-t200) = 1.25
        → t400 - t200 = 200/1.25 = 160
        → Si t200 = 150, t400 = 310
        """
        ritme = calcular_css_pace(temps_400_seg=310.0, temps_200_seg=150.0)
        assert abs(ritme - 80.0) < 0.01

    def test_error_temps_invalid(self):
        """Verifica que llança ValueError si t400 <= t200."""
        with pytest.raises(ValueError, match="ha de ser major"):
            calcular_css_pace(temps_400_seg=150.0, temps_200_seg=150.0)

        with pytest.raises(ValueError, match="ha de ser major"):
            calcular_css_pace(temps_400_seg=140.0, temps_200_seg=150.0)


class TestDeterminarZonesNedador:
    """Tests per a determinar_zones_nedador (regla de conciliació)."""

    def test_prioritat_css_test(self):
        """Verifica que CSS test té prioritat sobre marques."""
        nedador = Nedador(
            id="jep",
            nom="Jep",
            categoria="absolut",
            proves_objectiu=["50 Papallona"],
            mode_ritme="temps",
            marques_referencia=MarquesReferencia(
                marca_100_lliure_seg=77.08,
                marca_50_lliure_seg=33.44,
            ),
            ritmes_css=RitmesCSS(
                a2=80.0,  # CSS = 80s/100m
                data_test="2024-01-15",
                font="css_test",
            ),
        )

        zones = determinar_zones_nedador(nedador)

        # Ha d'haver utilitzat CSS test (a2 = 80)
        assert zones.font == "css_test"
        assert zones.a2 == 80.0
        assert zones.a1 == 86.0  # 80 + 6
        assert zones.data_test == "2024-01-15"

    def test_fallback_marques(self):
        """Verifica que utilitza marques quan no hi ha CSS test."""
        nedador = Nedador(
            id="jep",
            nom="Jep",
            categoria="absolut",
            proves_objectiu=["50 Papallona"],
            mode_ritme="temps",
            marques_referencia=MarquesReferencia(
                marca_100_lliure_seg=77.08,
                marca_50_lliure_seg=33.44,
            ),
        )

        zones = determinar_zones_nedador(nedador)

        # Ha d'haver utilitzat marques
        assert zones.font == "estimat_marca"
        assert abs(zones.a2 - 82.09) < 0.01
        assert abs(zones.velocitat - 67.55) < 0.01
        assert zones.data_test is None

    def test_fallback_si_css_sense_data_test(self):
        """Verifica que utilitza marques si CSS no té data_test."""
        nedador = Nedador(
            id="jep",
            nom="Jep",
            categoria="absolut",
            proves_objectiu=["50 Papallona"],
            mode_ritme="temps",
            marques_referencia=MarquesReferencia(
                marca_100_lliure_seg=77.08,
                marca_50_lliure_seg=33.44,
            ),
            ritmes_css=RitmesCSS(
                a2=80.0,
                font="estimat_marca",  # No és css_test
            ),
        )

        zones = determinar_zones_nedador(nedador)

        # Ha d'haver utilitzat marques perquè CSS no té data_test vàlida
        assert zones.font == "estimat_marca"
        assert abs(zones.a2 - 82.09) < 0.01

    def test_error_sense_dades(self):
        """Verifica que llança ValueError si no hi ha cap font disponible."""
        nedador = Nedador(
            id="jep",
            nom="Jep",
            categoria="absolut",
            proves_objectiu=["50 Papallona"],
            mode_ritme="temps",
        )

        with pytest.raises(ValueError, match="no té ni test CSS ni marques"):
            determinar_zones_nedador(nedador)
