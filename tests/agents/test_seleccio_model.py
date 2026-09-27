"""Tests per a la selecció de metodologia d'entrenament."""

import pytest

from blondswim.agents.seleccio_model import seleccionar_metodologia
from blondswim.models.nedador import Nedador


@pytest.fixture
def nedador_base() -> Nedador:
    """Nedador bàsic per a tests."""
    return Nedador(
        id="test",
        nom="Test Nedador",
        edat=25,
        categoria="absolut",
        proves_objectiu=["100m lliure"],
        mode_ritme="temps",
    )


class TestSeleccioMetodologia50m:
    """Tests per a proves de 50m."""

    def test_50m_absolut(self, nedador_base):
        """50m absolut: Sprint/Tècnica amb evidència pràctica documentada."""
        decisio = seleccionar_metodologia(nedador_base, "50m lliure", "absolut")

        assert decisio.prova == "50m lliure"
        assert decisio.categoria == "absolut"
        assert decisio.metodologia_principal == "Sprint/Tècnica"
        assert decisio.forca_evidencia == "practica_documentada"
        assert len(decisio.avisos) == 0

    def test_50m_master(self, nedador_base):
        """50m master: mateix que absolut."""
        decisio = seleccionar_metodologia(nedador_base, "50m lliure", "master")

        assert decisio.metodologia_principal == "Sprint/Tècnica"
        assert decisio.categoria == "master"
        assert decisio.forca_evidencia == "practica_documentada"


class TestSeleccioMetodologia100m:
    """Tests per a proves de 100m."""

    def test_100m_absolut(self, nedador_base):
        """100m absolut: Sprint/Tècnica amb avís sobre USRPT."""
        decisio = seleccionar_metodologia(nedador_base, "100m lliure", "absolut")

        assert decisio.prova == "100m lliure"
        assert decisio.metodologia_principal == "Sprint/Tècnica"
        assert decisio.forca_evidencia == "moderada"
        assert len(decisio.avisos) == 1
        assert "USRPT no és recomanat" in decisio.avisos[0]

    def test_100m_usrpt_no_principal(self, nedador_base):
        """USRPT no hauria de ser metodologia principal per 100m."""
        decisio = seleccionar_metodologia(nedador_base, "100m lliure", "absolut")

        assert decisio.metodologia_principal != "USRPT"
        assert "USRPT" not in decisio.metodologies_complementaries


class TestSeleccioMetodologia200m:
    """Tests per a proves de 200m."""

    def test_200m_absolut(self, nedador_base):
        """200m absolut: Polaritzat amb evidència forta."""
        decisio = seleccionar_metodologia(nedador_base, "200m lliure", "absolut")

        assert decisio.prova == "200m lliure"
        assert decisio.metodologia_principal == "Polaritzat"
        assert decisio.forca_evidencia == "forta"
        assert len(decisio.avisos) == 0

    def test_200m_master(self, nedador_base):
        """200m master: Polaritzat amb evidència moderada i avís d'extrapolació."""
        decisio = seleccionar_metodologia(nedador_base, "200m lliure", "master")

        assert decisio.metodologia_principal == "Polaritzat"
        assert decisio.categoria == "master"
        assert decisio.forca_evidencia == "moderada"
        assert len(decisio.avisos) == 1
        assert "extrapolació" in decisio.avisos[0].lower()
        assert "juvenils/elit" in decisio.avisos[0].lower()


class TestSeleccioMetodologia400m:
    """Tests per a proves de 400m."""

    def test_400m_absolut(self, nedador_base):
        """400m absolut: Polaritzat amb evidència forta."""
        decisio = seleccionar_metodologia(nedador_base, "400m lliure", "absolut")

        assert decisio.prova == "400m lliure"
        assert decisio.metodologia_principal == "Polaritzat"
        assert decisio.forca_evidencia == "forta"
        assert len(decisio.avisos) == 0

    def test_400m_master(self, nedador_base):
        """400m master: Polaritzat amb evidència moderada i avís."""
        decisio = seleccionar_metodologia(nedador_base, "400m lliure", "master")

        assert decisio.metodologia_principal == "Polaritzat"
        assert decisio.forca_evidencia == "moderada"
        assert len(decisio.avisos) == 1
        assert "extrapolació" in decisio.avisos[0].lower()


class TestSeleccioMetodologia800_1500m:
    """Tests per a proves de 800-1500m."""

    def test_800m_absolut(self, nedador_base):
        """800m: Polaritzat + USRPT complementari."""
        decisio = seleccionar_metodologia(nedador_base, "800m lliure", "absolut")

        assert decisio.metodologia_principal == "Polaritzat"
        assert "USRPT" in decisio.metodologies_complementaries
        assert decisio.forca_evidencia == "moderada"

    def test_1500m_absolut(self, nedador_base):
        """1500m: Polaritzat + USRPT complementari."""
        decisio = seleccionar_metodologia(nedador_base, "1500m lliure", "absolut")

        assert decisio.metodologia_principal == "Polaritzat"
        assert "USRPT" in decisio.metodologies_complementaries
        assert decisio.forca_evidencia == "moderada"

    def test_usrpt_complementari_no_principal(self, nedador_base):
        """USRPT és complementari, no principal per 800-1500m."""
        decisio = seleccionar_metodologia(nedador_base, "1500m lliure", "absolut")

        assert decisio.metodologia_principal != "USRPT"
        assert "USRPT" in decisio.metodologies_complementaries


class TestSeleccioMetodologiaIM:
    """Tests per a proves d'estils (IM)."""

    def test_200m_im_absolut(self, nedador_base):
        """200m IM: Bowman/Escola australiana."""
        decisio = seleccionar_metodologia(nedador_base, "200m IM", "absolut")

        assert decisio.prova == "200m IM"
        assert decisio.metodologia_principal == "Bowman/Escola australiana multi-estil"
        assert decisio.forca_evidencia == "practica_documentada"

    def test_400m_im_master(self, nedador_base):
        """400m IM master: mateix enfocament."""
        decisio = seleccionar_metodologia(nedador_base, "400m estils", "master")

        assert decisio.metodologia_principal == "Bowman/Escola australiana multi-estil"
        assert decisio.categoria == "master"


class TestSeleccioMetodologiaAAOO:
    """Tests per a aigües obertes."""

    def test_aaoo_5km(self, nedador_base):
        """AAOO 5km: sense evidència controlada."""
        decisio = seleccionar_metodologia(nedador_base, "AAOO 5km", "absolut")

        assert decisio.prova == "AAOO 5km"
        assert decisio.forca_evidencia == "sense_evidencia"
        assert len(decisio.avisos) == 1
        assert "judici d'entrenador" in decisio.avisos[0].lower()

    def test_aaoo_10km_master(self, nedador_base):
        """AAOO 10km master: pràctica documentada."""
        decisio = seleccionar_metodologia(
            nedador_base, "Aigües obertes 10km", "master"
        )

        assert decisio.forca_evidencia == "sense_evidencia"
        assert "AAOO" in decisio.metodologia_principal


class TestDiferenciesAbsolutMaster:
    """Tests per verificar diferències entre absolut i master."""

    def test_200m_diferencia_avisos(self, nedador_base):
        """200m: absolut sense avisos, master amb avís d'extrapolació."""
        decisio_absolut = seleccionar_metodologia(
            nedador_base, "200m lliure", "absolut"
        )
        decisio_master = seleccionar_metodologia(
            nedador_base, "200m lliure", "master"
        )

        assert len(decisio_absolut.avisos) == 0
        assert len(decisio_master.avisos) == 1
        assert decisio_absolut.forca_evidencia == "forta"
        assert decisio_master.forca_evidencia == "moderada"

    def test_400m_diferencia_evidencia(self, nedador_base):
        """400m: evidència forta per absolut, moderada per master."""
        decisio_absolut = seleccionar_metodologia(
            nedador_base, "400m lliure", "absolut"
        )
        decisio_master = seleccionar_metodologia(
            nedador_base, "400m lliure", "master"
        )

        assert decisio_absolut.forca_evidencia == "forta"
        assert decisio_master.forca_evidencia == "moderada"


class TestUSRPTNoRecomanatSprint:
    """Tests per verificar que USRPT no surt per sprint."""

    @pytest.mark.parametrize("prova", ["50m lliure", "100m lliure"])
    def test_usrpt_no_principal_sprint(self, nedador_base, prova):
        """USRPT no hauria de ser principal per 50-100m."""
        decisio = seleccionar_metodologia(nedador_base, prova, "absolut")

        assert decisio.metodologia_principal != "USRPT"

    @pytest.mark.parametrize("prova", ["50m lliure", "100m lliure"])
    def test_usrpt_no_complementari_sprint(self, nedador_base, prova):
        """USRPT no hauria de ser complementari per 50-100m."""
        decisio = seleccionar_metodologia(nedador_base, prova, "absolut")

        assert "USRPT" not in decisio.metodologies_complementaries


class TestForcaEvidencia:
    """Tests per verificar força d'evidència correcta."""

    def test_50m_practica_documentada(self, nedador_base):
        """50m: pràctica documentada."""
        decisio = seleccionar_metodologia(nedador_base, "50m lliure", "absolut")
        assert decisio.forca_evidencia == "practica_documentada"

    def test_100m_moderada(self, nedador_base):
        """100m: evidència moderada."""
        decisio = seleccionar_metodologia(nedador_base, "100m lliure", "absolut")
        assert decisio.forca_evidencia == "moderada"

    def test_200m_absolut_forta(self, nedador_base):
        """200m absolut: evidència forta."""
        decisio = seleccionar_metodologia(nedador_base, "200m lliure", "absolut")
        assert decisio.forca_evidencia == "forta"

    def test_400m_absolut_forta(self, nedador_base):
        """400m absolut: evidència forta."""
        decisio = seleccionar_metodologia(nedador_base, "400m lliure", "absolut")
        assert decisio.forca_evidencia == "forta"

    def test_800_1500m_moderada(self, nedador_base):
        """800-1500m: evidència moderada."""
        decisio = seleccionar_metodologia(nedador_base, "1500m lliure", "absolut")
        assert decisio.forca_evidencia == "moderada"

    def test_im_practica_documentada(self, nedador_base):
        """IM: pràctica documentada."""
        decisio = seleccionar_metodologia(nedador_base, "200m IM", "absolut")
        assert decisio.forca_evidencia == "practica_documentada"

    def test_aaoo_sense_evidencia(self, nedador_base):
        """AAOO: sense evidència controlada."""
        decisio = seleccionar_metodologia(nedador_base, "AAOO 5km", "absolut")
        assert decisio.forca_evidencia == "sense_evidencia"
