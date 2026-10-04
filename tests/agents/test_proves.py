"""Pics, pesos, perfil per durada i validacions dels objectius."""

from datetime import date

import pytest

from blondswim.agents.proves import (
    competicions_control,
    perfil_prova,
    pic_actiu,
    pics_temporada,
    proves_pic,
    validar_objectius,
)
from blondswim.models.calendari import Competicio
from blondswim.models.nedador import Nedador
from blondswim.models.resultat import ResultatCompeticio

CAT = "2027-01-16_cat"
ESP = "2027-02-06_esp"
EST = "2027-05-29_cat-estiu"


def _comp(id_, data, classe, piscina="25m", proves=(), data_fi=None):
    return Competicio(
        id=id_, nom=id_, data_inici=data, data_fi=data_fi or data, classe=classe,
        piscina=piscina, proves=list(proves),
    )


def calendari_jep() -> list[Competicio]:
    pic1 = ["100m Lliure", "200m Lliure", "100m IM"]
    return [
        _comp("barceloneta", "2026-10-17", "B", proves=["100m Lliure", "100m IM"]),
        _comp("girona", "2026-10-24", "C", piscina="50m", proves=["100m Lliure"]),
        _comp("horta", "2026-11-07", "B", proves=["100m Lliure", "200m Lliure", "100m IM"]),
        _comp("sabadell", "2026-11-21", "C", proves=["200m Lliure"]),
        _comp("cnsf", "2026-12-12", "B", proves=["100m Lliure", "100m IM"]),
        _comp(CAT, "2027-01-16", "A", proves=pic1, data_fi="2027-01-17"),
        _comp(ESP, "2027-02-06", "A", proves=pic1, data_fi="2027-02-07"),
        _comp(EST, "2027-05-29", "A", piscina="50m", proves=["100m Lliure", "200m Lliure"],
              data_fi="2027-05-30"),
    ]


def _objectiu(realista, ambicios):
    return [{"competicio_id": CAT, "realista": realista, "ambicios": ambicios}]


def nedador_jep(**canvis) -> Nedador:
    proves = [
        {"prova": "100m Lliure", "prioritat": "P",
         "nivell_actual": {"millor_marca": "1:17.08", "estimacio_pessimista": "1:18.00"},
         "objectius": _objectiu("1:15.00", "1:12.00")},
        {"prova": "100m IM", "prioritat": "P",
         "nivell_actual": {"millor_marca": "1:38.00", "estimacio_pessimista": "1:40.00"},
         "objectius": _objectiu("1:37.00", "1:34.00")},
        {"prova": "200m Lliure", "prioritat": "S",
         "nivell_actual": {"millor_marca": "3:03.00", "estimacio_pessimista": "3:08.00"},
         "objectius": _objectiu("3:02.00", "2:56.00")},
    ]
    dades = {"id": "jep", "nom": "Jep", "categoria": "master", "mode_ritme": "temps",
             "proves_objectiu": proves}
    dades.update(canvis)
    return Nedador(**dades)


# --- Pics -------------------------------------------------------------------


def test_doble_pic_hivern_i_pic_estiu():
    pics = pics_temporada(calendari_jep())
    assert [p.ids for p in pics] == [[CAT, ESP], [EST]]
    assert pics[0].numero == 1 and pics[1].numero == 2
    assert pics[0].data_inici == date(2027, 1, 16)
    assert pics[0].data_fi == date(2027, 2, 7)
    assert pics[0].piscina == "25m"
    assert pics[0].proves == ["100m Lliure", "200m Lliure", "100m IM"]


def test_dues_a_separades_mes_de_4_setmanes_son_dos_pics():
    comps = [_comp("a1", "2027-01-16", "A"), _comp("a2", "2027-02-20", "A")]
    assert len(pics_temporada(comps)) == 2


def test_pic_actiu():
    pics = pics_temporada(calendari_jep())
    assert pic_actiu(pics, date(2026, 10, 5)).numero == 1
    assert pic_actiu(pics, date(2027, 2, 7)).numero == 1
    assert pic_actiu(pics, date(2027, 2, 8)).numero == 2
    assert pic_actiu(pics, date(2027, 6, 1)) is None


# --- Pesos i perfil ----------------------------------------------------------


def test_pesos_p2_s1():
    pic = pics_temporada(calendari_jep())[0]
    proves = {p.nom: p for p in proves_pic(nedador_jep(), pic)}
    assert proves["100m Lliure"].percentatge == pytest.approx(0.4)
    assert proves["100m IM"].percentatge == pytest.approx(0.4)
    assert proves["200m Lliure"].percentatge == pytest.approx(0.2)
    assert proves["200m Lliure"].prioritat == "S"


def test_perfil_per_durada_del_nedador():
    pic = pics_temporada(calendari_jep())[0]
    perfils = {p.nom: p.perfil for p in proves_pic(nedador_jep(), pic)}
    assert perfils == {"100m Lliure": "mixt", "100m IM": "mixt", "200m Lliure": "mig_fons"}


@pytest.mark.parametrize(
    ("temps", "perfil"),
    [(38.9, "velocitat"), (44.9, "velocitat"), (45.0, "mixt"), (119.0, "mixt"),
     (183.0, "mig_fons"), (300.0, "fons"), (None, None)],
)
def test_perfil_prova(temps, perfil):
    assert perfil_prova(temps) == perfil


def test_prova_del_calendari_que_no_es_a_la_fitxa_compta_com_s():
    calendari = calendari_jep()
    calendari[5].proves.append("50m Papallona")
    pic = pics_temporada(calendari)[0]
    papallona = next(p for p in proves_pic(nedador_jep(), pic) if p.nom == "50m Papallona")
    assert papallona.prova is None and papallona.prioritat == "S"


# --- Competicions de control --------------------------------------------------


def test_competicions_control_mateixa_piscina_i_abans_del_pic():
    calendari = calendari_jep()
    pic = pics_temporada(calendari)[0]
    assert [c.id for c in competicions_control(calendari, pic, "100 lliures")] == [
        "barceloneta", "horta", "cnsf"
    ]  # Girona (50 m) queda fora
    assert [c.id for c in competicions_control(calendari, pic, "200m Lliure")] == [
        "horta", "sabadell"
    ]


def test_competicions_control_del_pic_2_comencen_despres_del_pic_1():
    calendari = calendari_jep() + [
        _comp("cornella", "2027-04-17", "C", piscina="50m", proves=["100m Lliure"]),
    ]
    pic2 = pics_temporada(calendari)[1]
    # Girona (24/10, 50 m) és del cicle del pic 1: no compta per al pic 2.
    assert [c.id for c in competicions_control(calendari, pic2, "100m Lliure")] == ["cornella"]


# --- Validacions ---------------------------------------------------------------


def _tipus(avisos):
    return [a["tipus"] for a in avisos]


def test_jep_complet_sense_avisos_abans_de_la_temporada():
    avisos = validar_objectius(nedador_jep(), calendari_jep(), [], date(2026, 10, 4))
    assert avisos == []


def test_objectiu_exigent():
    n = nedador_jep()
    n.proves_objectiu[0].nivell_actual.estimacio_pessimista = 80.0  # 1'20" -> 1'15": -4,4%
    avisos = validar_objectius(n, calendari_jep(), [], date(2026, 10, 4))
    assert _tipus(avisos) == ["objectiu_exigent"]
    assert "4.4%" in avisos[0]["missatge"]


def test_falten_dades_de_la_fitxa():
    n = nedador_jep(proves_objectiu=[{"prova": "100m Lliure", "prioritat": "P"}])
    tipus = _tipus(validar_objectius(n, calendari_jep(), [], date(2026, 10, 4)))
    assert "sense_nivell" in tipus
    assert "sense_objectiu" in tipus
    assert tipus.count("prova_no_fitxa") == 2  # 200 lliure i 100 IM


def test_a_sense_proves_i_sense_principal():
    calendari = calendari_jep()
    calendari[5].proves = []
    calendari[6].proves = ["200m Lliure"]
    tipus = _tipus(validar_objectius(nedador_jep(), calendari, [], date(2026, 10, 4)))
    assert "a_sense_proves" in tipus
    assert "a_sense_principal" in tipus


def test_per_defecte_nomes_valida_el_pic_actiu():
    avui = date(2026, 10, 4)
    assert validar_objectius(nedador_jep(), calendari_jep(), [], avui) == []
    tipus = _tipus(validar_objectius(nedador_jep(), calendari_jep(), [], avui, tots_els_pics=True))
    assert "sense_objectiu" in tipus  # pic 2 (estiu) encara sense objectius
    assert "poques_competicions_control" in tipus  # cap B/C de 50 m al calendari de prova


def test_100_im_en_piscina_de_50():
    calendari = calendari_jep()
    calendari[7].proves.append("100m IM")
    assert "im100_piscina_50" in _tipus(
        validar_objectius(nedador_jep(), calendari, [], date(2026, 10, 4))
    )


def test_poques_competicions_de_control():
    calendari = [c for c in calendari_jep() if c.id != "sabadell"]  # 200 lliure: només Horta
    avisos = validar_objectius(nedador_jep(), calendari, [], date(2026, 10, 4))
    assert _tipus(avisos) == ["poques_competicions_control"]
    assert "200m Lliure" in avisos[0]["missatge"]


def test_resultat_pendent_nomes_de_competicions_passades():
    resultats = [ResultatCompeticio(competicio_id="barceloneta", prova="100 lliures", temps=78.4)]
    avisos = validar_objectius(nedador_jep(), calendari_jep(), resultats, date(2026, 10, 20))
    assert _tipus(avisos) == ["resultat_pendent"]
    assert "100m IM" in avisos[0]["missatge"]
