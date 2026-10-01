"""Tests dels models de la Fase E+I: setmana tipus, franges i registres."""

from datetime import date

import pytest
from pydantic import ValidationError

from blondswim.models.franja import SlotSessio, franges_consecutives
from blondswim.models.historial import SessioRealitzada
from blondswim.models.nedador import Nedador
from blondswim.models.registre import (
    RegistreSerieControl,
    RegistreSRSS,
    etiqueta_cr10,
)
from blondswim.models.sessio import EstructuraSessio, Sessio


def _nedador(**kwargs) -> Nedador:
    return Nedador(
        id="jep",
        nom="Jep",
        categoria="master",
        proves_objectiu=["100m lliure"],
        mode_ritme="temps",
        **kwargs,
    )


def _nat(franja: str = "mati") -> SlotSessio:
    return SlotSessio(franja=franja, modalitat="natacio")


def _gim(franja: str = "tarda", durada: int = 60) -> SlotSessio:
    return SlotSessio(franja=franja, modalitat="gimnas", durada_min=durada)


# --- SlotSessio ---


def test_slot_gimnas_sense_durada_falla():
    with pytest.raises(ValidationError, match="durada_min"):
        SlotSessio(franja="tarda", modalitat="gimnas")


def test_slot_natacio_sense_durada_ok():
    assert _nat().durada_min is None


def test_franges_consecutives():
    assert franges_consecutives("mati", "migdia")
    assert franges_consecutives("tarda", "migdia")
    assert not franges_consecutives("mati", "tarda")


# --- Nedador.setmana_tipus ---


def test_sense_setmana_tipus_es_compatible():
    n = _nedador(dies_disponibles=["dilluns", "dimarts"])
    assert n.setmana_tipus is None
    assert n.dies_disponibles == ["dilluns", "dimarts"]
    assert n.slots_dia("dilluns") == [SlotSessio(franja="tarda", modalitat="natacio")]
    assert n.slots_dia("dimecres") == []
    assert n.franja_natacio("dilluns") == "tarda"


def test_setmana_tipus_deriva_dies_disponibles():
    n = _nedador(
        dies_disponibles=["dissabte"],  # s'ignora: mana setmana_tipus
        setmana_tipus={
            "dimecres": [_nat("tarda")],
            "dilluns": [_gim("tarda"), _nat("mati")],
            "dissabte": [_gim("mati")],
        },
    )
    assert n.dies_disponibles == ["dilluns", "dimecres"]
    assert [s.franja for s in n.slots_dia("dilluns")] == ["mati", "tarda"]
    assert n.franja_natacio("dilluns") == "mati"


def test_setmana_tipus_des_de_json():
    n = Nedador.model_validate(
        {
            "id": "jep",
            "nom": "Jep",
            "categoria": "master",
            "proves_objectiu": ["100m lliure"],
            "mode_ritme": "temps",
            "setmana_tipus": {
                "dilluns": [
                    {"franja": "mati", "modalitat": "natacio"},
                    {"franja": "tarda", "modalitat": "gimnas", "durada_min": 45},
                ]
            },
        }
    )
    assert n.dies_disponibles == ["dilluns"]
    assert n.slots_dia("dilluns")[1].durada_min == 45


def test_maxim_tres_sessions_al_dia():
    slots = [_nat("mati"), _gim("migdia"), _gim("tarda"), _gim("tarda")]
    with pytest.raises(ValidationError, match="màxim 3"):
        _nedador(setmana_tipus={"dilluns": slots})


def test_franja_repetida_falla():
    with pytest.raises(ValidationError, match="mateixa franja"):
        _nedador(setmana_tipus={"dilluns": [_nat("mati"), _gim("mati")]})


def test_dues_sessions_de_natacio_el_mateix_dia_falla():
    with pytest.raises(ValidationError, match="més d'una sessió de natació"):
        _nedador(setmana_tipus={"dilluns": [_nat("mati"), _nat("tarda")]})


def test_dia_desconegut_falla():
    with pytest.raises(ValidationError, match="dia desconegut"):
        _nedador(setmana_tipus={"festiu": [_nat()]})


# --- Sessio ---


def test_sessio_per_defecte_es_natacio_a_la_tarda():
    s = Sessio(
        id="x",
        microcicle_setmana=1,
        dia="dilluns",
        tipus_sessio="carrega",
        volum_total=3000,
        estructura=EstructuraSessio(parts=[]),
    )
    assert (s.franja, s.modalitat, s.durada_min) == ("tarda", "natacio", None)


# --- SessioRealitzada ---


def test_sessio_realitzada_antiga_es_compatible():
    s = SessioRealitzada(data="2026-09-01", series=[], volum_total_m=3000, temps_total_min=65)
    assert s.modalitat == "natacio"
    assert s.rpe_sessio is None
    assert s.carrega is None


def test_carrega_srpe():
    s = SessioRealitzada(
        data="2026-10-05", modalitat="gimnas", franja="tarda", temps_total_min=45, rpe_sessio=6
    )
    assert s.volum_total_m == 0
    assert s.carrega == 270


@pytest.mark.parametrize("rpe", [-1, 11])
def test_rpe_fora_de_rang(rpe):
    with pytest.raises(ValidationError, match="CR-10"):
        SessioRealitzada(data="2026-10-05", temps_total_min=60, rpe_sessio=rpe)


def test_assoliment_fora_de_rang():
    with pytest.raises(ValidationError, match="assoliment"):
        SessioRealitzada(data="2026-10-05", temps_total_min=60, assoliment=0)


def test_etiqueta_cr10():
    assert etiqueta_cr10(0) == "Descans"
    assert etiqueta_cr10(5) == "Dur"
    assert etiqueta_cr10(10) == "Màxim"


# --- Registres ---


def test_registre_srss_mitjanes():
    r = RegistreSRSS(
        nedador_id="jep", data=date(2026, 10, 5), recuperacio=[5, 4, 5, 4], estres=[1, 2, 1, 2]
    )
    assert r.mitjana_recuperacio == 4.5
    assert r.mitjana_estres == 1.5


@pytest.mark.parametrize(
    "recuperacio",
    [[5, 4, 5], [5, 4, 5, 7], [5, 4, 5, -1]],
)
def test_registre_srss_invalid(recuperacio):
    with pytest.raises(ValidationError):
        RegistreSRSS(
            nedador_id="jep", data=date(2026, 10, 5), recuperacio=recuperacio, estres=[1] * 4
        )


def test_registre_serie_control():
    r = RegistreSerieControl(
        nedador_id="jep",
        data=date(2026, 10, 7),
        temps_100=[100.0, 99.0, 99.5, 98.5],
        bracades_llargada=[18, 18, 19, 19],
        rpe=4,
    )
    assert r.temps_mitja == pytest.approx(99.25)
    assert r.bracades_mitja == 18.5


def test_registre_serie_control_sense_temps_falla():
    with pytest.raises(ValidationError):
        RegistreSerieControl(nedador_id="jep", data=date(2026, 10, 7), temps_100=[])
