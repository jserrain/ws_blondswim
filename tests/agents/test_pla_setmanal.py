"""Tests de l'organització setmanal (Fase H): rols, esquelet, pressupost i validació."""

from datetime import date

import pytest

from blondswim.agents import pla_setmanal
from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.models.calendari import Competicio
from blondswim.models.macrocicle import Microcicle
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.sessio import EstructuraSessio, Exercici, PartSessio, Sessio

DILLUNS = date(2026, 10, 5)  # setmana ISO 41


def _comp(data_inici: str, data_fi: str | None = None, classe: str = "B") -> Competicio:
    return Competicio(
        id=f"c_{data_inici}",
        nom="Competició",
        data_inici=data_inici,
        data_fi=data_fi or data_inici,
        classe=classe,
        piscina="25m",
    )


@pytest.fixture
def nedador_plantilla() -> Nedador:
    return Nedador(
        id="jep",
        nom="Jep",
        categoria="master",
        proves_objectiu=["100m lliure", "100m estils"],
        mode_ritme="temps",
        dies_disponibles=["dilluns", "dimarts", "dimecres", "dijous", "divendres"],
        ritmes_css=RitmesCSS(font="css_test", a1=87.1, a2=82.09, a3=78.24, velocitat=67.55),
    )


def _microcicle(
    tipus_base: str = "carrega",
    volum: int = 13600,
    dia_competicio: str | None = None,
    post: bool = False,
) -> Microcicle:
    return Microcicle(
        setmana=41,
        dates="05-11/10/2026",
        mesocicle_id="meso_1",
        tipus_base=tipus_base,
        volum_objectiu=volum,
        dies_qualitat=False,
        test_css=False,
        dia_competicio=dia_competicio,
        post_competicio=post,
    )


# --- Classificació de la setmana ---


def test_classificar_setmana_normal():
    assert pla_setmanal.classificar_setmana(DILLUNS, []) == (None, False)


def test_classificar_competicio_dissabte_i_diumenge():
    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-10")]) == ("dissabte", False)
    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-11")]) == ("diumenge", False)


def test_classificar_a_de_dos_dies_activa_divendres():
    comp = _comp("2026-10-10", "2026-10-11", classe="A")
    assert pla_setmanal.classificar_setmana(DILLUNS, [comp]) == ("dissabte", False)


def test_classificar_post_competicio():
    """Competició que acaba el cap de setmana anterior -> post_competicio."""
    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-04")]) == (None, True)


def test_classificar_ignora_competicions_c():
    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-10", classe="C")]) == (
        None,
        False,
    )


# --- Rols ---


def test_rols_setmana_normal_un_sol_dia_de_qualitat():
    rols = pla_setmanal.rols_setmana(None, False)
    assert rols == {
        "dilluns": "aerobica", "dimarts": "qualitat", "dimecres": "tecnica",
        "dijous": "aerobica", "divendres": "llarga",
    }
    assert list(rols.values()).count("qualitat") == 1


def test_rols_competicio_dissabte_activacio_divendres():
    rols = pla_setmanal.rols_setmana("dissabte", False)
    assert rols["divendres"] == "activacio"
    assert rols["dimarts"] == "qualitat"


def test_rols_competicio_diumenge_activacio_dissabte():
    rols = pla_setmanal.rols_setmana("diumenge", False)
    assert rols["dissabte"] == "activacio"
    assert "divendres" not in rols
    assert len(rols) == 5


def test_rols_post_competicio_recuperacio_i_qualitat_dijous():
    rols = pla_setmanal.rols_setmana(None, True)
    assert rols["dilluns"] == "recuperacio"
    assert rols["dijous"] == "qualitat"


def test_rols_post_i_competicio_sense_qualitat():
    rols = pla_setmanal.rols_setmana("dissabte", True)
    assert "qualitat" not in rols.values()
    assert rols["dilluns"] == "recuperacio"
    assert rols["divendres"] == "activacio"


# --- Esquelet amb plantilla ---


def test_esquelet_plantilla_setmana_normal(nedador_plantilla):
    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle())

    assert [s.dia for s in sessions] == ["dilluns", "dimarts", "dimecres", "dijous", "divendres"]
    assert [s.rol for s in sessions] == ["aerobica", "qualitat", "tecnica", "aerobica", "llarga"]
    tecnica = sessions[2]
    assert tecnica.volum_total < 0.75 * sessions[0].volum_total  # dia de tècnica, volum baix
    assert all(s.tipus_sessio == "carrega" for s in sessions)
    assert abs(sum(s.volum_total for s in sessions) - 13600) <= 50
    for s in sessions:
        assert s.volum_min <= s.volum_total <= s.volum_max
        assert s.volum_total % 25 == 0


def test_esquelet_serie_de_control_fixa_dimecres(nedador_plantilla):
    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle())
    dimecres = next(s for s in sessions if s.dia == "dimecres")

    fixes = [p for p in dimecres.estructura.parts if p.fixa]
    assert len(fixes) == 1
    control = fixes[0]
    assert control.nom == pla_setmanal.NOM_SERIE_CONTROL
    ex = control.exercicis[0]
    assert (ex.series, ex.distancia_m, ex.intensitat) == (4, 100, "A2")
    assert ex.descans == "c/1:40"  # A2 82 s + 15 s -> 1:40 (múltiple de 5 s)
    assert dimecres.estructura.parts[1].fixa  # just després de l'escalfament
    altres = [s for s in sessions if s.dia != "dimecres"]
    assert all(not p.fixa for s in altres for p in s.estructura.parts)


def test_esquelet_competicio_diumenge_activacio_dissabte(nedador_plantilla):
    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle(dia_competicio="diumenge"))

    assert [s.dia for s in sessions] == ["dilluns", "dimarts", "dimecres", "dijous", "dissabte"]
    activacio = sessions[-1]
    assert activacio.rol == "activacio"
    assert activacio.volum_total < min(s.volum_total for s in sessions[:-1])
    assert "diumenge" in activacio.notes


def test_esquelet_post_competicio_dilluns_de_recuperacio(nedador_plantilla):
    sessions = generar_esquelet_sessions(
        nedador_plantilla, _microcicle(volum=12000, post=True)
    )

    assert sessions[0].rol == "recuperacio"
    assert sessions[0].volum_total < 0.7 * sessions[1].volum_total
    assert next(s for s in sessions if s.dia == "dijous").rol == "qualitat"
    assert abs(sum(s.volum_total for s in sessions) - 12000) <= 50


def test_esquelet_sense_plantilla_manté_la_logica_antiga():
    nedador = Nedador(
        id="x", nom="X", categoria="master", proves_objectiu=[], mode_ritme="temps"
    )  # dies per defecte: dilluns-dijous
    sessions = generar_esquelet_sessions(nedador, _microcicle())
    assert {s.rol for s in sessions} <= {"llarga", "mitjana", "qualitat"}
    assert all(s.notes is None for s in sessions)


def test_cicle_serie_control_sense_ritmes():
    nedador = Nedador(
        id="x", nom="X", categoria="master", proves_objectiu=[], mode_ritme="rpe"
    )
    assert pla_setmanal.cicle_serie_control(nedador) == "d/0:20"


# --- Pressupost i validació ---


def _sessio(rol: str, tipus: str, exercicis: list[Exercici], fixes: list[Exercici] | None = None):
    parts = [
        PartSessio(
            nom="Principal", percentatge_carrega=100, percentatge_qualitat=100,
            percentatge_descarrega=100, exercicis=exercicis,
        )
    ]
    if fixes:
        parts.append(
            PartSessio(
                nom="Control", percentatge_carrega=0, percentatge_qualitat=0,
                percentatge_descarrega=0, exercicis=fixes, fixa=True,
            )
        )
    volum = sum(e.volum_m for e in exercicis + (fixes or []))
    return Sessio(
        id="s", microcicle_setmana=41, dia="dimarts", tipus_sessio=tipus,
        volum_total=volum, estructura=EstructuraSessio(parts=parts), rol=rol,
    )


def _ex(series, dist, intensitat, execucio="Crol"):
    return Exercici(series=series, distancia_m=dist, execucio=execucio, intensitat=intensitat)


def test_qualitat_base_no_admet_lactic():
    s = _sessio("qualitat", "carrega", [_ex(30, 100, "A1"), _ex(4, 25, "MPLA")])
    assert any("MPLA/TOLA" in p for p in pla_setmanal.problemes_contingut(s))


def test_qualitat_build_admet_lactic_dins_pressupost():
    s = _sessio("qualitat", "qualitat", [_ex(28, 100, "A1"), _ex(6, 50, "MPLA")])
    assert pla_setmanal.problemes_contingut(s) == []


def test_tecnica_no_admet_a3():
    s = _sessio("tecnica", "carrega", [_ex(28, 100, "A1"), _ex(4, 100, "A3")])
    assert any("A3/AeM" in p for p in pla_setmanal.problemes_contingut(s))


def test_papallona_per_sobre_del_maxim():
    s = _sessio(
        "tecnica", "carrega",
        [_ex(25, 100, "A1"), _ex(8, 50, "A1", "Pap tècnica, un braç")],
    )
    assert any("Papallona" in p for p in pla_setmanal.problemes_contingut(s))


def test_estils_compten_un_quart_de_papallona():
    s = _sessio("aerobica", "carrega", [_ex(2, 100, "A1", "IM per estils")])
    assert pla_setmanal.metres_papallona(s) == 50


def test_estils_125_invalid_i_a3_en_25():
    s = _sessio(
        "qualitat", "carrega",
        [_ex(28, 100, "A1"), _ex(1, 125, "A2", "IM complet"), _ex(4, 25, "A3")],
    )
    problemes = pla_setmanal.problemes_contingut(s)
    assert any("125 m" in p for p in problemes)
    assert any("llindar" in p for p in problemes)


def test_parts_fixes_no_compten_al_pressupost():
    """La sèrie de control (A2) no trenca el pressupost de la recuperació."""
    s = _sessio(
        "recuperacio", "carrega",
        [_ex(16, 100, "A1")],
        fixes=[_ex(4, 100, "A2")],
    )
    assert pla_setmanal.problemes_contingut(s) == []


def test_recuperacio_no_admet_a2_variable():
    s = _sessio("recuperacio", "carrega", [_ex(16, 100, "A1"), _ex(4, 100, "A2")])
    assert any(p.startswith("A2") for p in pla_setmanal.problemes_contingut(s))


def test_dofi_de_cames_no_compta_com_a_papallona():
    s = _sessio(
        "tecnica", "carrega",
        [_ex(20, 100, "A1"), _ex(8, 25, "A1", "Ps Pap dofí ventral"),
         _ex(4, 25, "A1", "Papallona un braç")],
    )
    assert pla_setmanal.metres_papallona(s) == 100  # només els 4x25 de braços


# --- Estructura de la sessió (bloc de cada part) ---


def test_etiquetes_parts_numera_blocs_principals():
    etiquetes = pla_setmanal.etiquetes_parts(
        [
            ("Escalfament", "Escalfament"),
            ("Tècnica+Subaquàtic", "Tècnica"),
            ("Qualitat", "Bloc principal"),
            ("Aeròbic", "Bloc principal"),
            ("Tornada a la calma", "Tornada a la calma"),
        ]
    )
    assert etiquetes == [
        "Escalfament",
        "Tècnica+Subaquàtic",
        "Bloc principal 1 — Qualitat",
        "Bloc principal 2 — Aeròbic",
        "Tornada a la calma",
    ]


def test_etiquetes_un_sol_bloc_principal_sense_numero():
    etiquetes = pla_setmanal.etiquetes_parts(
        [("Escalfament", "Escalfament"), ("Aeròbic", "Bloc principal")]
    )
    assert etiquetes[1] == "Bloc principal — Aeròbic"


@pytest.mark.parametrize("rol", list(pla_setmanal.PARTS_ROL))
def test_estructura_recomanada_per_rol(rol):
    """Escalfament primer, tornada a la calma última, tècnica abans dels blocs principals."""
    blocs = [pla_setmanal.bloc_part(nom) for nom, _ in pla_setmanal.PARTS_ROL[rol]]
    assert None not in blocs
    assert blocs[0] == "Escalfament"
    assert blocs[-1] == "Tornada a la calma"
    assert "Bloc principal" in blocs
    if "Tècnica" in blocs:
        assert blocs.index("Tècnica") < blocs.index("Bloc principal")


def test_qualitat_i_velocitat_en_fresc():
    """El treball exigent va just després de la tècnica (primer bloc principal)."""
    def primer_principal(rol):
        return next(
            nom for nom, _ in pla_setmanal.PARTS_ROL[rol]
            if pla_setmanal.bloc_part(nom) == "Bloc principal"
        )

    assert primer_principal("qualitat") == "Qualitat"
    assert primer_principal("llarga") == "Velocitat alàctica"


def test_esquelet_assigna_bloc_a_cada_part(nedador_plantilla):
    nedador_plantilla.rutina_espatlla_dia = "dissabte"
    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle())
    for sessio in sessions:
        assert all(p.bloc is not None for p in sessio.estructura.parts)
    dimecres = next(s for s in sessions if s.dia == "dimecres")
    assert [p.bloc for p in dimecres.estructura.parts][:2] == ["Escalfament", "Sèrie de control"]


# --- Normes de l'entrenador comprovables pel text ---------------------------------


@pytest.mark.parametrize(
    ("execucio", "n"),
    [
        ("Crol arrossegant el polze per l'aigua a la recuperació", 1),
        ("Crol amb els dits arrossegant per l'aigua", 1),
        ("Crol amb Ei", 1),
        ("Crol, focus en la captura", 0),
        ("Eix del cos estable", 0),
    ],
)
def test_problemes_normes(execucio, n):
    from blondswim.agents.pla_setmanal import problemes_normes
    from blondswim.models.sessio import Exercici

    assert len(problemes_normes(Exercici(series=4, distancia_m=50, execucio=execucio))) == n


# --- Papallona: detall per exercici i nota per rol (W41) ---------------------------


def _sessio_pap(rol: str, *exercicis):
    from blondswim.models.sessio import EstructuraSessio, PartSessio, Sessio

    part = PartSessio(nom="Aeròbic", percentatge_carrega=100, percentatge_qualitat=100,
                      percentatge_descarrega=100, exercicis=list(exercicis))
    return Sessio(id="s", microcicle_setmana=41, dia="dilluns", tipus_sessio="carrega",
                  volum_total=3000, estructura=EstructuraSessio(parts=[part]), rol=rol)


def test_papallona_per_exercici_i_missatge_amb_el_detall():
    from blondswim.models.sessio import Exercici

    tecnica_pap = Exercici(series=4, distancia_m=50, execucio="Pap 1 braç")
    estils = Exercici(series=2, distancia_m=100, execucio="IM per estils")
    dofi = Exercici(series=6, distancia_m=25, execucio="Cames de dofí")
    sessio = _sessio_pap("aerobica", tecnica_pap, estils, dofi)
    assert [(ex.execucio, m) for ex, m in pla_setmanal.papallona_per_exercici(sessio)] == [
        ("Pap 1 braç", 200), ("IM per estils", 50)
    ]
    [problema] = [p for p in pla_setmanal.problemes_contingut(sessio) if "Papallona" in p]
    assert "250 m" in problema and "«4x50 Pap 1 braç» 200 m" in problema
    assert "cames de dofí" in problema


def test_un_100_im_compta_25_m_de_papallona():
    from blondswim.models.sessio import Exercici

    sessio = _sessio_pap("aerobica", Exercici(series=2, distancia_m=100,
                                              execucio="IM, papallona amb respiració cada 2"))
    assert pla_setmanal.metres_papallona(sessio) == 50


def test_nota_papallona_per_rol():
    aerobica = pla_setmanal.nota_papallona(_sessio_pap("aerobica"), "dimecres")
    assert "sessió de tècnica (el dimecres)" in aerobica and "Entre 100 i 150 m" in aerobica
    tecnica = pla_setmanal.nota_papallona(_sessio_pap("tecnica"), "dimecres")
    assert "Aquesta és la sessió de la papallona tècnica" in tecnica and "entre 200 i 300 m" in tecnica


def test_esquelet_piscina_50_volums_multiples_de_50(nedador_plantilla):
    piscina50 = nedador_plantilla.model_copy(update={"piscina_m": 50})
    sessions = generar_esquelet_sessions(piscina50, _microcicle())
    for s in sessions:
        assert s.volum_total % 50 == 0 and s.volum_min % 50 == 0 and s.volum_max % 50 == 0
    assert abs(sum(s.volum_total for s in sessions) - 13600) <= 150


@pytest.mark.parametrize(
    ("execucio", "metres"),
    [
        # W41: comptats de més abans del 2b
        ("Estils (Crol + Esquena + Braça + cames de dofí en lloc de papallona)", 0),
        ("Estils (25 Pap cames dofí substituint braçada + 25 Esquena + 25 Braça + 25 Crol)", 0),
        ("IM complet (25 cames dofí substituint papallona + 25 Esquena + 25 Braça + 25 Crol)", 0),
        ("Cames de papallona (dofí) amb braços estirats, ondulació de tot el cos", 0),
        ("Cames de dofí amb braços estirats, treball de papallona sense braçada", 0),
        # Continuen comptant
        ("IM complet, transicions suaus entre estils", 50),
        ("Pap 1 braç", 200),
        ("Papallona completa amb aletes", 200),
    ],
)
def test_comptador_de_papallona_casos_w41(execucio, metres):
    from blondswim.models.sessio import Exercici

    n = 2 if "IM" in execucio or "Estils" in execucio else 4
    d = 100 if n == 2 else 50
    sessio = _sessio_pap("aerobica", Exercici(series=n, distancia_m=d, execucio=execucio))
    assert pla_setmanal.metres_papallona(sessio) == metres


# --- Conveni de metres: sessió i parts a 100 m, l'última part fa la resta --------


def _sessio_parts(volum_total, pcts, fix=0):
    parts = [PartSessio(nom=f"P{i}", percentatge_carrega=p, percentatge_qualitat=p,
                        percentatge_descarrega=p) for i, p in enumerate(pcts)]
    if fix:
        parts.insert(1, PartSessio(
            nom="Sèrie de control", percentatge_carrega=0, percentatge_qualitat=0,
            percentatge_descarrega=0, fixa=True,
            exercicis=[Exercici(series=fix // 100, distancia_m=100, execucio="Crol")]))
    return Sessio(id="s", microcicle_setmana=41, dia="dilluns", tipus_sessio="carrega",
                  volum_total=volum_total, estructura=EstructuraSessio(parts=parts))


def test_metres_parts_exemple_de_l_entrenador():
    # 2.800 m: 15/15/48/12/10% -> 400/400/1.400/300 i la resta (300)
    sessio = _sessio_parts(2800, [15, 15, 48, 12, 10])
    pla_setmanal.assignar_metres_parts(sessio)
    assert [p.metres_objectiu for p in sessio.estructura.parts] == [400, 400, 1400, 300, 300]


def test_metres_parts_sense_les_parts_fixes():
    sessio = _sessio_parts(1900, [15, 45, 15, 15, 10], fix=400)
    pla_setmanal.assignar_metres_parts(sessio)
    variables = [p for p in sessio.estructura.parts if not p.fixa]
    assert sum(p.metres_objectiu for p in variables) == 1500
    assert all(p.metres_objectiu % 100 == 0 for p in variables)
    assert sessio.estructura.parts[1].metres_objectiu is None


def test_esquelet_volums_a_100_i_parts_assignades(nedador_plantilla):
    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle())
    for s in sessions:
        assert s.volum_total % 100 == 0 and s.volum_min % 100 == 0 and s.volum_max % 100 == 0
        fix = sum(e.volum_m for p in s.estructura.parts if p.fixa for e in p.exercicis)
        assert sum(p.metres_objectiu for p in s.estructura.parts if not p.fixa) == (
            s.volum_total - fix
        )


# --- Papallona: opció intermèdia (06/10) ----------------------------------------


@pytest.mark.parametrize(
    ("execucio", "metres"),
    [
        ("Estils (IM) per 25 m: Esquena-Braça-Crol-Esquena (sense papallona)", 0),
        ("Nedar per estils: 1 llarg d'Esquena + 1 de Braça + 1 de Crol + 1 d'Esquena", 0),
        ("Estils (IM) complet, focus coordinació", 50),
        ("Per estils: 25 Pap + 25 Esq + 25 Bra + 25 Crol", 50),
    ],
)
def test_estils_sense_papallona_no_compten(execucio, metres):
    sessio = _sessio_pap("aerobica", Exercici(series=2, distancia_m=100, execucio=execucio))
    assert pla_setmanal.metres_papallona(sessio) == metres


def test_limits_de_papallona_intermedis():
    assert pla_setmanal.PAPALLONA_MAX_ROL["aerobica"] == 150
    assert pla_setmanal.PAPALLONA_MAX_ROL["tecnica"] == 300
    assert pla_setmanal.PAPALLONA_SETMANA == (600, 900)


def test_papallona_en_repeticions_llargues_o_a_la_calma():
    from blondswim.models.sessio import EstructuraSessio, PartSessio, Sessio

    principal = PartSessio(nom="Aeròbic", percentatge_carrega=90, percentatge_qualitat=90,
                           percentatge_descarrega=90, exercicis=[
                               Exercici(series=1, distancia_m=100, execucio="Papallona")])
    calma = PartSessio(nom="Tornada a la calma", percentatge_carrega=10,
                       percentatge_qualitat=10, percentatge_descarrega=10, exercicis=[
                           Exercici(series=1, distancia_m=25, execucio="Pap suau"),
                           Exercici(series=1, distancia_m=100, execucio="IM suau")])
    sessio = Sessio(id="s", microcicle_setmana=41, dia="dilluns", tipus_sessio="carrega",
                    volum_total=3000, rol="aerobica",
                    estructura=EstructuraSessio(parts=[principal, calma]))
    problemes = pla_setmanal.problemes_contingut(sessio)
    assert any("repeticions de 100 m" in p for p in problemes)
    assert any("'Pap suau': papallona a la tornada a la calma" in p for p in problemes)
    assert not any("'IM suau'" in p for p in problemes)


def test_metres_estils_objectiu():
    aerobica = _sessio_pap("aerobica")
    assert pla_setmanal.metres_estils_objectiu(aerobica, 2900) == {
        "crol": 2900 - 450 - 450 - 150, "esquena": 450, "braca": 450, "papallona": 150
    }
    tecnica = _sessio_pap("tecnica")
    m = pla_setmanal.metres_estils_objectiu(tecnica, 1500)
    assert m["esquena"] == 300 and m["papallona"] == 300
    assert "crol ~" in pla_setmanal.text_estils(aerobica, 2900)


def test_metres_per_estil_de_la_setmana():
    sessio = _sessio_pap(
        "aerobica",
        Exercici(series=8, distancia_m=100, execucio="Crol"),
        Exercici(series=4, distancia_m=100, execucio="Estils complet"),
        Exercici(series=4, distancia_m=50, execucio="Esquena"),
        Exercici(series=6, distancia_m=50, execucio="Cames de crol amb taula"),
    )
    assert pla_setmanal.metres_per_estil([sessio]) == {
        "crol": 900, "esquena": 300, "braca": 100, "papallona": 100, "cames": 300
    }


# --- Sprint 2e ------------------------------------------------------------------


def test_franges_al_prompt():
    text = pla_setmanal.text_estils(_sessio_pap("aerobica"), 2900)
    assert "esquena 300-450 m" in text and "papallona 100-150 m" in text
    assert pla_setmanal.papallona_minima(_sessio_pap("tecnica")) == 200
    assert pla_setmanal.papallona_minima(_sessio_pap("recuperacio")) == 0


def test_avisos_estils_setmana():
    poca = _sessio_pap("aerobica", Exercici(series=28, distancia_m=100, execucio="Crol"))
    poca.volum_total = 2800
    avisos = pla_setmanal.avisos_estils_setmana([poca])
    assert any(a.startswith("Esquena de la setmana 0m") for a in avisos)
    assert any("Papallona de la setmana 0m: per sota" in a for a in avisos)
