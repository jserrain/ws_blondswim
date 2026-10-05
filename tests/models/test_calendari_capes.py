"""Tests del calendari en dues capes: catàleg comú + calendari del nedador."""

import pytest

from blondswim.models.calendari import (
    Competicio,
    CompeticioCataleg,
    InscripcioCompeticio,
    fusionar_cataleg,
    resoldre_calendari,
    separar_calendari,
)


def _cataleg() -> list[CompeticioCataleg]:
    return [
        CompeticioCataleg(
            id="girona", nom="Trofeu Girona", data_inici="2026-10-24",
            data_fi="2026-10-24", piscina="50m",
        ),
        CompeticioCataleg(
            id="cat-hivern", nom="Campionat Catalunya hivern", data_inici="2027-01-16",
            data_fi="2027-01-17", piscina="25m",
        ),
        CompeticioCataleg(
            id="barceloneta", nom="Master Barceloneta", data_inici="2026-10-17",
            data_fi="2026-10-17", piscina="25m",
        ),
    ]


def test_resoldre_calendari_combina_i_ordena():
    inscripcions = [
        InscripcioCompeticio(competicio_id="cat-hivern", classe="A", proves=["100L", "50P"]),
        InscripcioCompeticio(competicio_id="barceloneta", classe="B"),
    ]
    comps = resoldre_calendari(_cataleg(), inscripcions)
    assert [c.id for c in comps] == ["barceloneta", "cat-hivern"]
    assert comps[0].classe == "B"
    assert comps[1].classe == "A"
    assert comps[1].proves == ["100L", "50P"]
    assert comps[1].nom == "Campionat Catalunya hivern"
    assert comps[1].data_fi == "2027-01-17"


def test_mateixa_competicio_classe_diferent_per_nedador():
    jep = resoldre_calendari(
        _cataleg(), [InscripcioCompeticio(competicio_id="girona", classe="C")]
    )
    lou = resoldre_calendari(
        _cataleg(), [InscripcioCompeticio(competicio_id="girona", classe="A")]
    )
    assert jep[0].classe == "C"
    assert lou[0].classe == "A"


def test_resoldre_calendari_competicio_desconeguda():
    with pytest.raises(ValueError, match="no és al catàleg"):
        resoldre_calendari(
            _cataleg(), [InscripcioCompeticio(competicio_id="inexistent", classe="B")]
        )


def test_resoldre_calendari_competicio_repetida():
    with pytest.raises(ValueError, match="repetida"):
        resoldre_calendari(
            _cataleg(),
            [
                InscripcioCompeticio(competicio_id="girona", classe="B"),
                InscripcioCompeticio(competicio_id="girona", classe="C"),
            ],
        )


def test_separar_i_resoldre_son_inverses():
    originals = [
        Competicio(
            id="girona", nom="Trofeu Girona", data_inici="2026-10-24",
            data_fi="2026-10-24", classe="C", piscina="50m",
        ),
        Competicio(
            id="cat-hivern", nom="Campionat Catalunya hivern", data_inici="2027-01-16",
            data_fi="2027-01-17", classe="A", piscina="25m", proves=["100L"],
        ),
    ]
    cataleg, inscripcions = separar_calendari(originals)
    assert all(not hasattr(c, "classe") for c in cataleg)
    assert [i.classe for i in inscripcions] == ["C", "A"]
    assert resoldre_calendari(cataleg, inscripcions) == originals


def test_competicio_sense_proves_compatible_amb_format_antic():
    antic = {
        "id": "x", "nom": "X", "data_inici": "2026-11-07", "data_fi": "2026-11-07",
        "classe": "B", "piscina": "25m",
    }
    assert Competicio(**antic).proves == []


def test_fusionar_cataleg_afegeix_i_actualitza():
    existent = _cataleg()[:2]
    nou = [
        CompeticioCataleg(
            id="girona", nom="Trofeu Girona (nou nom)", data_inici="2026-10-24",
            data_fi="2026-10-24", piscina="50m",
        ),
        _cataleg()[2],
    ]
    fusionat = fusionar_cataleg(existent, nou)
    assert [c.id for c in fusionat] == ["barceloneta", "girona", "cat-hivern"]
    assert fusionat[1].nom == "Trofeu Girona (nou nom)"


# --- Simulacions ------------------------------------------------------------------


def test_simulacio_sobre_competicio_del_cataleg():
    ins = InscripcioCompeticio(
        competicio_id="barceloneta", classe="B", proves=["100m Lliure"], tipus="simulacio"
    )
    [c] = resoldre_calendari(_cataleg(), [ins])
    assert c.es_simulacio and c.tipus == "simulacio"
    assert c.data_inici == "2026-10-17" and c.piscina == "25m"
    assert c.nom == "Simulació — Master Barceloneta"


def test_simulacio_definida_al_calendari():
    ins = InscripcioCompeticio(
        competicio_id="tt-2026-10-21", classe="C", proves=["100m IM"], tipus="simulacio",
        data="2026-10-21", piscina="25m", nom="Contrarellotge 100 IM",
    )
    [c] = resoldre_calendari(_cataleg(), [ins])
    assert (c.id, c.nom, c.data_inici, c.data_fi, c.piscina) == (
        "tt-2026-10-21", "Contrarellotge 100 IM", "2026-10-21", "2026-10-21", "25m"
    )


def test_simulacio_fora_del_cataleg_necessita_data_i_piscina():
    ins = InscripcioCompeticio(competicio_id="tt", classe="C", tipus="simulacio")
    with pytest.raises(ValueError, match="data i piscina"):
        resoldre_calendari(_cataleg(), [ins])


def test_simulacio_no_pot_ser_a_i_competicio_no_porta_data():
    with pytest.raises(ValueError, match="classe A"):
        InscripcioCompeticio(competicio_id="x", classe="A", tipus="simulacio")
    with pytest.raises(ValueError, match="només es poden definir en una simulació"):
        InscripcioCompeticio(competicio_id="x", classe="B", data="2026-10-21")


def test_competicions_planificacio_exclou_simulacions():
    from blondswim.models.calendari import competicions_planificacio

    comps = resoldre_calendari(
        _cataleg(),
        [
            InscripcioCompeticio(competicio_id="barceloneta", classe="B", tipus="simulacio"),
            InscripcioCompeticio(competicio_id="girona", classe="C"),
        ],
    )
    assert [c.id for c in competicions_planificacio(comps)] == ["girona"]
