"""Tests per a la generació de macrocicles."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from blondswim.agents.generar_macrocicle import (
    generar_macrocicle,
    generar_mesocicle,
    generar_microcicles_mesocicle,
)
from blondswim.models.calendari import Competicio
from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Mesocicle
from blondswim.models.nedador import Nedador


@pytest.fixture
def nedador_test() -> Nedador:
    """Nedador base per als tests de generació de mesocicles."""
    return Nedador(
        id="test",
        nom="Test Nedador",
        categoria="absolut",
        proves_objectiu=["200m lliure"],
        mode_ritme="temps",
        dies_disponibles=["dilluns", "dimarts", "dimecres", "dijous"],
        dia_opcional=None,
    )
```

Now update the expected volumes. With `historial_test` = 3 sessions of 3000m → `volum_per_sessio = 3000`, `dies_base = 4`, `factor = 1.0` (Base):

- `volum_min = 3000 × 4 × 1.0 = 12000` → 12000
- `volum_max = 12000 × 1.10 = 13200` → 13200
- `volum_mitja_previst = (12000 + 13200) / 2 = 12600` → 12600

tests/agents/test_generar_macrocicle.py
```python
<<<<<<< SEARCH
    # 3 sessions de 3000m -> volum_per_sessio = 3000
    # 4 dies disponibles -> volum_min = 12000
    # volum_max = 12000 × 1.10 = 13200
    # mitjana = 12600
    assert mesocicle.fase_objectiu == "Base"
    assert mesocicle.volum_min == 12000
    assert mesocicle.volum_max == 13200
    assert mesocicle.volum_mitja_previst == 12600

    # Sense avís de falta d'històric
    assert not any(a.get("tipus_avis") == "sense_historial" for a in avisos)


@pytest.fixture
def historial_test() -> list[SessioRealitzada]:
    """Històric de 3 sessions de 3000m per als tests de volums."""
    return [
        SessioRealitzada(
            data=f"2026-09-0{i}",
            series=[],
            volum_total_m=3000,
            temps_total_min=90.0,
        )
        for i in range(1, 4)
    ]


def test_generar_macrocicle_amb_competicions_a():
    """Verifica que amb almenys 1 competició A genera el macrocicle sense avís."""
    # Crear competicions: 2 classe A ben separades
    competicions = [
        Competicio(
            id="comp1",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="comp2",
            nom="Campionat Espanya",
            data_inici="2027-05-29",
            data_fi="2027-05-31",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="comp3",
            nom="Competició B",
            data_inici="2027-03-15",
            data_fi="2027-03-17",
            classe="B",
            piscina="50m",
        ),
    ]

    # Generar macrocicle
    macrocicle, avisos = generar_macrocicle(
        nedador_id="test",
        competicions=competicions,
        temporada_data_inici="2026-09-01",
        temporada_data_fi="2027-06-30",
    )

    # Verificar que s'ha generat 1 macrocicle
    assert macrocicle.nom == "Macrocicle 2026-2027"
    assert macrocicle.data_inici == "2026-09-01"
    assert macrocicle.data_fi == "2027-06-30"
    assert macrocicle.temporada == "2026-2027"
    assert macrocicle.mesocicles == []

    # Verificar que retorna avisos (sense avís de "cap competició A")
    assert isinstance(avisos, list)
    # No hauria de tenir l'avís de "cap_competicio_a"
    avisos_cap_comp_a = [a for a in avisos if a.get("tipus_avis") == "cap_competicio_a"]
    assert len(avisos_cap_comp_a) == 0


def test_generar_macrocicle_sense_competicions_a():
    """Verifica que sense competicions A genera el macrocicle amb avís."""
    # Crear competicions: només B i C
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició B",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="B",
            piscina="25m",
        ),
        Competicio(
            id="comp2",
            nom="Competició C",
            data_inici="2027-03-15",
            data_fi="2027-03-17",
            classe="C",
            piscina="50m",
        ),
    ]

    # Generar macrocicle
    macrocicle, avisos = generar_macrocicle(
        nedador_id="test",
        competicions=competicions,
        temporada_data_inici="2026-09-01",
        temporada_data_fi="2027-06-30",
    )

    # Verificar que s'ha generat 1 macrocicle
    assert macrocicle.nom == "Macrocicle 2026-2027"
    assert macrocicle.data_inici == "2026-09-01"
    assert macrocicle.data_fi == "2027-06-30"
    assert macrocicle.temporada == "2026-2027"
    assert macrocicle.mesocicles == []

    # Verificar que retorna avisos amb l'avís de "cap competició A"
    assert isinstance(avisos, list)
    avisos_cap_comp_a = [a for a in avisos if a.get("tipus_avis") == "cap_competicio_a"]
    assert len(avisos_cap_comp_a) == 1
    assert "almenys un objectiu A" in avisos_cap_comp_a[0]["missatge"]


def test_generar_macrocicle_crida_validar_espaiat_pics_a():
    """Verifica que els avisos venen de validar_espaiat_pics_a."""
    # Crear competicions
    competicions = [
        Competicio(
            id="comp1",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
    ]

    # Mock validar_espaiat_pics_a per verificar que es crida
    avisos_mock = [{"tipus_avis": "test", "missatge": "Test avís"}]

    with patch(
        "blondswim.agents.generar_macrocicle.context_competicio.validar_espaiat_pics_a",
        return_value=avisos_mock,
    ) as mock_validar:
        _macrocicle, avisos = generar_macrocicle(
            nedador_id="test",
            competicions=competicions,
            temporada_data_inici="2026-09-01",
            temporada_data_fi="2027-06-30",
        )

        # Verificar que s'ha cridat validar_espaiat_pics_a amb les competicions
        mock_validar.assert_called_once_with(competicions)

        # Verificar que els avisos retornats inclouen els del mock
        assert avisos_mock[0] in avisos


def test_generar_mesocicle_enriquir_amb_llm_canvia_fase_objectiu(nedador_test, historial_test):
    """Verifica que amb enriquir_amb_llm=True es crida l'API i canvia fase_objectiu."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    # Mock resposta LLM
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "retornar_fase_objectiu"
    mock_tool_use.input = {
        "fase_objectiu": "Base - Desenvolupament de capacitat aeròbica i tècnica fonamental"
    }
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch(
        "blondswim.agents.generar_macrocicle.get_llm_client",
        return_value=mock_client,
    ):
        mesocicle, _avisos = generar_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            competicions=competicions,
            enriquir_amb_llm=True,
            historial=historial_test,
            data_referencia=date(2026, 9, 30),
        )

    # Verificar que s'ha cridat l'API
    mock_client.messages.create.assert_called_once()

    # Verificar que fase_objectiu s'ha enriquit
    assert mesocicle.fase_objectiu == "Base - Desenvolupament de capacitat aeròbica i tècnica fonamental"
    assert mesocicle.fase_objectiu != "Base"  # Ha canviat respecte al determinista


def test_generar_mesocicle_sense_enriquir_llm_no_crida_api(nedador_test, historial_test):
    """Verifica que amb enriquir_amb_llm=False no es crida l'API."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    mock_client = MagicMock()

    with patch(
        "blondswim.agents.generar_macrocicle.get_llm_client",
        return_value=mock_client,
    ):
        mesocicle, _avisos = generar_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            competicions=competicions,
            enriquir_amb_llm=False,
            historial=historial_test,
            data_referencia=date(2026, 9, 30),
        )

    # Verificar que NO s'ha cridat l'API
    mock_client.messages.create.assert_not_called()

    # Verificar que fase_objectiu és el determinista
    assert mesocicle.fase_objectiu == "Base"


def test_generar_mesocicle_fallback_si_llm_falla(nedador_test, historial_test):
    """Verifica que si la crida LLM falla, manté fase_objectiu determinista."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    # Mock que llança excepció
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API Error")

    with patch(
        "blondswim.agents.generar_macrocicle.get_llm_client",
        return_value=mock_client,
    ):
        # No hauria de propagar l'error
        mesocicle, _avisos = generar_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            competicions=competicions,
            enriquir_amb_llm=True,
            historial=historial_test,
            data_referencia=date(2026, 9, 30),
        )

    # Verificar que fase_objectiu és el determinista (fallback)
    assert mesocicle.fase_objectiu == "Base"

    # Verificar que el mesocicle s'ha creat correctament
    assert mesocicle.nom == "Base 1"
    assert len(macrocicle.mesocicles) == 1




def test_generar_mesocicle_sense_historial_volums_zero(nedador_test):
    """Verifica que sense històric els volums són 0 i apareix l'avís."""
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A llunyana",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    mesocicle, avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=None,
        data_referencia=date(2026, 9, 30),
    )

    assert mesocicle.volum_min == 0
    assert mesocicle.volum_max == 0
    assert mesocicle.volum_mitja_previst == 0

    avisos_historial = [
        a for a in avisos if a.get("tipus_avis") == "sense_historial"
    ]
    assert len(avisos_historial) == 1
    assert "Sense històric del nedador" in avisos_historial[0]["missatge"]


def test_generar_mesocicle_peak_retalla_volums(
    nedador_test, historial_test
):
    """Verifica que un mesocicle Peak aplica el 50% de retallada als volums."""
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    # Competició A a 2 setmanes -> Peak
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A propera",
            data_inici="2026-09-15",
            data_fi="2026-09-17",
            classe="A",
            piscina="25m",
        ),
    ]

    # Peak = 2 setmanes abans de la Cursa (setmana del 15/09/2026)
    mesocicle, _avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
        data_referencia=date(2026, 9, 1),
    )

    assert mesocicle.fase_objectiu == "Peak"
    # Base: 12000 / 13200 / 12600 -> Peak (50%): 6000 / 6600 / 6300
    assert mesocicle.volum_min == 6000
    assert mesocicle.volum_max == 6600
    assert mesocicle.volum_mitja_previst == 6300
```

Now the microcicle tests in `test_generar_macrocicle.py` use `_crear_mesocicle` with explicit volumes, so they're independent of the formula. But `test_generar_microcicles_base_4_setmanes` etc. pass explicit `volum_min=12000, volum_max=15000, volum_mitja_previst=13500`. Those are fine as-is since they test `generar_microcicles_mesocicle` directly with given values. Let me check the interpolation expectations:

For Base 4 setmanes with `volum_min=12000, volum_max=15000`:
- `n_carrega = 3`, interpolation min→max over 3 steps: index 0 → 12000, index 1 → 13500, index 2 → 15000. ✓ matches test.

These tests don't need changing since they pass explicit values. Good.

Now `test_generar_microcicle.py` — the `nedador_test` fixture doesn't set `dia_opcional`, so it uses the model default `"dissabte"`. The task says to set it to `None`. Let me update:

tests/agents/test_generar_microcicle.py
```python
<<<<<<< SEARCH
        proves_objectiu=["100m lliure", "200m lliure"],
        mode_ritme="temps",
        ritmes_css=RitmesCSS(


def _crear_mesocicle(
    tipus: str,
    setmanes: str,
    volum_min: int,
    volum_max: int,
    volum_mitja_previst: int,
) -> Mesocicle:
    """Helper per crear un Mesocicle de test."""
    return Mesocicle(
        id="meso_1",
        nom=f"{tipus} 1",
        setmanes=setmanes,
        dates="01/09/2026-28/09/2026",
        tipus=tipus,
        fase_objectiu=tipus,
        metodologia_dominant="",
        volum_min=volum_min,
        volum_max=volum_max,
        volum_mitja_previst=volum_mitja_previst,
        microcicles=[],
    )


def _plans_bloc(
    fase: str,
    n_setmanes: int,
    setmana_inici: int = 1,
    dilluns_inici: date = date(2026, 9, 7),
    competicions_b_c_per_setmana: dict[int, list] | None = None,
) -> list:
    """Helper per construir una llista de SetmanaPlan d'un bloc."""
    from blondswim.agents.periodificacio import SetmanaPlan

    competicions_b_c_per_setmana = competicions_b_c_per_setmana or {}
    plans = []
    for i in range(n_setmanes):
        dilluns = dilluns_inici + timedelta(weeks=i)
        plans.append(
            SetmanaPlan(
                any_iso=dilluns.isocalendar()[0],
                setmana_iso=setmana_inici + i,
                dilluns=dilluns,
                diumenge=dilluns + timedelta(days=6),
                fase=fase,
                bloc_id="bloc_1",
                index_dins_bloc=i,
                es_descarrega=(i == n_setmanes - 1),
                competicions_b_c=competicions_b_c_per_setmana.get(i, []),
            )
        )
    return plans


def test_generar_microcicles_base_4_setmanes():
    """Base de 4 setmanes: 3 carrega + 1 descarrega, test_css només a la 1a."""
    mesocicle = _crear_mesocicle("Base", "1-4", 12000, 15000, 13500)
    plans = _plans_bloc("Base", 4)

    microcicles = generar_microcicles_mesocicle(mesocicle, plans)

    assert len(microcicles) == 4

    # 3 primeres de càrrega, 4a de descàrrega
    assert [m.tipus_base for m in microcicles] == [
        "carrega",
        "carrega",
        "carrega",
        "descarrega",
    ]

    # test_css només a la setmana 1
    assert microcicles[0].test_css is True
    assert all(not m.test_css for m in microcicles[1:])

    # Volum creixent a les 3 primeres, cau a la 4a
    assert microcicles[0].volum_objectiu == 12000
    assert microcicles[1].volum_objectiu == 13500
    assert microcicles[2].volum_objectiu == 15000
    assert microcicles[3].volum_objectiu == round(12000 * 0.7)

    # dies_qualitat False per Base
    assert all(not m.dies_qualitat for m in microcicles)

    # notes
    assert microcicles[0].notes == "Càrrega + Test CSS"
    assert microcicles[3].notes == "Descàrrega"

    # mesocicle_id correcte
    assert all(m.mesocicle_id == "meso_1" for m in microcicles)


def test_generar_microcicles_build1_4_setmanes():
    """Build1 de 4 setmanes: 3 qualitat + 1 descarrega, dies_qualitat a totes."""
    mesocicle = _crear_mesocicle("Build1", "1-4", 12000, 15000, 13500)
    plans = _plans_bloc("Build1", 4)

    microcicles = generar_microcicles_mesocicle(mesocicle, plans)

    assert len(microcicles) == 4
    assert [m.tipus_base for m in microcicles] == [
        "qualitat",
        "qualitat",
        "qualitat",
        "descarrega",
    ]

    # dies_qualitat True a totes (incloent descàrrega)
    assert all(m.dies_qualitat for m in microcicles)

    # test_css False (no és Base)
    assert all(not m.test_css for m in microcicles)

    assert microcicles[0].notes == "Qualitat"


def test_generar_microcicles_base_2_setmanes_bloc_parcial():
    """Base de 2 setmanes (bloc parcial): 1 carrega + 1 descarrega."""
    mesocicle = _crear_mesocicle("Base", "1-2", 12000, 15000, 13500)
    plans = _plans_bloc("Base", 2)

    microcicles = generar_microcicles_mesocicle(mesocicle, plans)

    assert len(microcicles) == 2
    assert [m.tipus_base for m in microcicles] == ["carrega", "descarrega"]

    # Interpolació entre volum_min i volum_max (1 setmana de càrrega -> max)
    assert microcicles[0].volum_objectiu == 15000
    assert microcicles[1].volum_objectiu == round(12000 * 0.7)

    # test_css només a la primera
    assert microcicles[0].test_css is True
    assert microcicles[1].test_css is False


def test_generar_microcicles_peak_3_setmanes():
    """Peak de 3 setmanes: volum decreixent, taper, dies_qualitat True."""
    mesocicle = _crear_mesocicle("Peak", "1-3", 6000, 7500, 6750)
    plans = _plans_bloc("Peak", 3)

    microcicles = generar_microcicles_mesocicle(mesocicle, plans)

    assert len(microcicles) == 3
    assert all(m.tipus_base == "taper" for m in microcicles)
    assert all(m.dies_qualitat for m in microcicles)
    assert all(not m.test_css for m in microcicles)
    assert all(m.notes == "Taper" for m in microcicles)

    # Volum decreixent: max -> min
    assert microcicles[0].volum_objectiu == 7500
    assert microcicles[1].volum_objectiu == 6750
    assert microcicles[2].volum_objectiu == 6000


def test_generar_microcicles_cursa_1_setmana():
    """Cursa (1 setmana): taper, notes de competició."""
    mesocicle = _crear_mesocicle("Cursa", "1", 6000, 7500, 6750)
    plans = _plans_bloc("Cursa", 1)

    microcicles = generar_microcicles_mesocicle(mesocicle, plans)

    assert len(microcicles) == 1
    assert microcicles[0].tipus_base == "taper"
    assert microcicles[0].notes == "Setmana de competició"
    assert microcicles[0].volum_objectiu == 6750
    assert microcicles[0].dies_qualitat is True
    assert microcicles[0].test_css is False


def test_generar_microcicles_transicio_1_setmana():
    """Transicio (1 setmana): tipus_base transicio."""
    mesocicle = _crear_mesocicle("Transicio", "1", 6000, 7500, 6750)
    plans = _plans_bloc("Transicio", 1)

    microcicles = generar_microcicles_mesocicle(mesocicle, plans)

    assert len(microcicles) == 1
    assert microcicles[0].tipus_base == "transicio"
    assert microcicles[0].notes == "Recuperació post-competició"
    assert microcicles[0].volum_objectiu == 6750
    assert microcicles[0].dies_qualitat is False
    assert microcicles[0].test_css is False


def test_generar_microcicles_setmana_amb_prova_b_aplica_volum_08():
    """R4: una setmana amb prova B aplica volum x 0.8."""
    mesocicle = _crear_mesocicle("Build1", "1-4", 12000, 15000, 13500)
    comp_b = Competicio(
        id="b1",
        nom="Prova B",
        data_inici="2026-09-07",
        data_fi="2026-09-08",
        classe="B",
        piscina="25m",
    )
    plans = _plans_bloc("Build1", 4, competicions_b_c_per_setmana={0: [comp_b]})

    microcicles = generar_microcicles_mesocicle(mesocicle, plans)

    # Setmana 0: qualitat, volum interpolat 12000 -> x0.8 = 9600
    assert microcicles[0].volum_objectiu == round(12000 * 0.8)


def test_generar_mesocicle_omple_microcicles_i_tipus(nedador_test, historial_test):
    """Verifica que generar_mesocicle() pobla microcicles i fixa el camp tipus."""
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A llunyana",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    mesocicle, _avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
        data_referencia=date(2026, 9, 30),
    )

    # El camp tipus ha d'estar fixat
    assert mesocicle.tipus == "Base"

    # Finestra des de la setmana 40; A del 14/12/2026 (setmana 51):
    # Cursa 51, Peak 49-50, Build2 45-48, Build1 41-44, Base = només la setmana 40.
    assert len(mesocicle.microcicles) == 1
    assert mesocicle.microcicles[0].dates == "28/09-04/10/2026"
    assert all(m.mesocicle_id == mesocicle.id for m in mesocicle.microcicles)
    assert any(a.get("tipus_avis") == "bloc_curt" for a in _avisos)


def test_generar_mesocicle_data_referencia_30_09_2026(nedador_test, historial_test):
    """Amb data_referencia=30/09/2026 genera el bloc Base 40-42 amb sessions_des_de."""
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-28",
        data_fi="2027-07-09",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="a1",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
    ]

    mesocicle, _avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
        data_referencia=date(2026, 9, 30),
    )

    assert mesocicle.tipus == "Base"
    assert len(mesocicle.microcicles) == 3
    assert [m.dates for m in mesocicle.microcicles] == [
        "28/09-04/10/2026",
        "05-11/10/2026",
        "12-18/10/2026",
    ]
    assert mesocicle.microcicles[0].sessions_des_de == date(2026, 10, 1)
    assert all(m.sessions_des_de is None for m in mesocicle.microcicles[1:])


def test_generar_mesocicle_data_referencia_none_usa_today(
    nedador_test, historial_test, monkeypatch
):
    """Amb data_referencia=None fa servir date.today()."""
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-28",
        data_fi="2027-07-09",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="a1",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
    ]

    monkeypatch.setattr(
        "blondswim.agents.generar_macrocicle.periodificacio.avui",
        lambda: date(2026, 9, 30),
    )

    mesocicle, _avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
    )

    assert mesocicle.tipus == "Base"
    assert mesocicle.microcicles[0].sessions_des_de == date(2026, 10, 1)
