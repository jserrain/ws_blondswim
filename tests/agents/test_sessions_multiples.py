"""Tests de les sessions múltiples al dia (Fase E+I): esquelet, LLM, Excel i validació."""

from datetime import date
from unittest.mock import MagicMock, patch

import openpyxl
import pytest

from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.agents.generar_microcicle import _context_sessio, generar_microcicle
from blondswim.agents.validacio import validar_franges_setmana
from blondswim.export.mesocicle_excel import exportar_setmana_excel
from blondswim.models.decisio import DecisioMetodologia
from blondswim.models.franja import SlotSessio
from blondswim.models.macrocicle import Mesocicle, Microcicle
from blondswim.models.nedador import Nedador, RitmesCSS

DIES_5 = ["dilluns", "dimarts", "dimecres", "dijous", "divendres"]


def _nat(franja: str = "mati") -> SlotSessio:
    return SlotSessio(franja=franja, modalitat="natacio")


def _gim(franja: str = "tarda", durada: int = 60) -> SlotSessio:
    return SlotSessio(franja=franja, modalitat="gimnas", durada_min=durada)


def _nedador(setmana_tipus: dict | None) -> Nedador:
    return Nedador(
        id="jep",
        nom="Jep",
        categoria="master",
        proves_objectiu=["100m lliure", "100m estils"],
        mode_ritme="temps",
        dies_disponibles=DIES_5,
        ritmes_css=RitmesCSS(font="css_test", a1=87.1, a2=82.09, a3=78.24, velocitat=67.55),
        setmana_tipus=setmana_tipus,
    )


@pytest.fixture
def nedador_amb_gimnas() -> Nedador:
    # Natació al matí de dilluns a divendres; gimnàs dilluns i dimarts a la
    # tarda, dimecres al migdia i dissabte al matí.
    tipus = {dia: [_nat("mati")] for dia in DIES_5}
    tipus["dilluns"].append(_gim("tarda", 60))
    tipus["dimarts"].append(_gim("migdia", 45))
    tipus["dimecres"].append(_gim("tarda", 45))
    tipus["dissabte"] = [_gim("mati", 50)]
    return _nedador(tipus)


def _microcicle(**kwargs) -> Microcicle:
    dades = {
        "setmana": 41,
        "dates": "05-11/10/2026",
        "mesocicle_id": "meso_1",
        "tipus_base": "carrega",
        "volum_objectiu": 13600,
        "dies_qualitat": False,
        "test_css": False,
    }
    dades.update(kwargs)
    return Microcicle(**dades)


# --- Esquelet ---


def test_esquelet_sense_setmana_tipus_no_canvia():
    sessions = generar_esquelet_sessions(_nedador(None), _microcicle())
    assert [s.dia for s in sessions] == DIES_5
    assert all(s.modalitat == "natacio" and s.franja == "tarda" for s in sessions)


def test_esquelet_afegeix_gimnas_informatiu(nedador_amb_gimnas):
    sessions = generar_esquelet_sessions(nedador_amb_gimnas, _microcicle())
    natacio = [s for s in sessions if s.modalitat == "natacio"]
    gimnas = [s for s in sessions if s.modalitat == "gimnas"]

    assert [s.dia for s in natacio] == DIES_5
    assert all(s.franja == "mati" for s in natacio)
    assert [(s.dia, s.franja, s.durada_min) for s in gimnas] == [
        ("dilluns", "tarda", 60),
        ("dimarts", "migdia", 45),
        ("dimecres", "tarda", 45),
        ("dissabte", "mati", 50),
    ]
    for g in gimnas:
        assert g.volum_total == 0
        assert g.estructura.parts == []
        assert g.rol is None
    # El volum de natació no canvia pel gimnàs.
    sense_gimnas = generar_esquelet_sessions(_nedador(None), _microcicle())
    assert [s.volum_total for s in natacio] == [s.volum_total for s in sense_gimnas]


def test_esquelet_ordenat_per_dia_i_franja(nedador_amb_gimnas):
    sessions = generar_esquelet_sessions(nedador_amb_gimnas, _microcicle())
    dilluns = [(s.franja, s.modalitat) for s in sessions if s.dia == "dilluns"]
    assert dilluns == [("mati", "natacio"), ("tarda", "gimnas")]
    assert len({s.id for s in sessions}) == len(sessions)


def test_sense_gimnas_el_dia_de_competicio(nedador_amb_gimnas):
    sessions = generar_esquelet_sessions(
        nedador_amb_gimnas, _microcicle(dia_competicio="dissabte")
    )
    assert not [s for s in sessions if s.dia == "dissabte"]


def test_respecta_sessions_des_de(nedador_amb_gimnas):
    sessions = generar_esquelet_sessions(
        nedador_amb_gimnas, _microcicle(sessions_des_de=date(2026, 10, 7))
    )
    assert {s.dia for s in sessions} == {"dimecres", "dijous", "divendres", "dissabte"}


# --- LLM ---


def _resposta(sessio) -> MagicMock:
    objectiu = round((sessio.volum_min + sessio.volum_max) / 2 / 25) * 25
    n = len(sessio.estructura.parts)
    parts = []
    for i, p in enumerate(sessio.estructura.parts):
        dist = objectiu - 25 * (n - 1) if i == 0 else 25
        parts.append({
            "nom": p.nom,
            "exercicis": [{"series": 1, "distancia_m": dist, "execucio": "Crol", "intensitat": "A1"}],
        })
    block = MagicMock(type="tool_use", input={"parts": parts})
    block.name = "retornar_contingut_sessio"
    resposta = MagicMock(content=[block], stop_reason="tool_use")
    resposta.usage = MagicMock(output_tokens=100)
    return resposta


def test_llm_nomes_per_a_natacio(nedador_amb_gimnas):
    sessions = generar_esquelet_sessions(nedador_amb_gimnas, _microcicle())
    natacio = [s for s in sessions if s.modalitat == "natacio"]
    client = MagicMock()
    client.messages.create.side_effect = [_resposta(s) for s in natacio]
    metodologia = DecisioMetodologia(
        prova="100m lliure",
        categoria="master",
        metodologia_principal="Polaritzat",
        metodologies_complementaries=[],
        forca_evidencia="moderada",
        justificacio="test",
        avisos=[],
    )

    # Sense validació de contingut: una sola crida per sessió de natació.
    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=client
    ), patch("blondswim.agents.generar_microcicle._problemes_sessio", return_value=[]):
        resultat = generar_microcicle(nedador_amb_gimnas, sessions, metodologia)

    assert client.messages.create.call_count == len(natacio)
    assert len(resultat) == len(sessions)
    prompt_dilluns = client.messages.create.call_args_list[0].kwargs["messages"][0]["content"]
    assert "gimnàs (tarda, 60 min)" in prompt_dilluns
    assert all(not s.estructura.parts for s in resultat if s.modalitat == "gimnas")


def test_context_sessio_sense_altres_sessions():
    sessions = generar_esquelet_sessions(_nedador(None), _microcicle())
    assert "gimnàs" not in _context_sessio(sessions[0], sessions)


# --- Excel ---


def test_excel_mostra_franja_i_gimnas(nedador_amb_gimnas, tmp_path):
    microcicle = _microcicle()
    sessions = generar_esquelet_sessions(nedador_amb_gimnas, microcicle)
    mesocicle = Mesocicle(
        id="meso_1",
        nom="M1 - Base",
        setmanes="41",
        dates="05-11/10/2026",
        tipus="Base",
        fase_objectiu="Base",
        metodologia_dominant="Polaritzat",
        volum_min=12000,
        volum_max=15000,
        volum_mitja_previst=13600,
        microcicles=[microcicle],
    )
    path = exportar_setmana_excel(
        nedador_amb_gimnas, mesocicle, microcicle, sessions, tmp_path / "s.xlsx"
    )
    ws = openpyxl.load_workbook(path).active
    capcaleres = [c.value for c in ws["A"] if c.value]

    assert "Dilluns 5 — matí — Aeròbic i tècnica" in capcaleres
    assert "Dilluns 5 — tarda — Gimnàs (60 min, informatiu)" in capcaleres
    assert "Dissabte 10 — matí — Gimnàs (50 min, informatiu)" in capcaleres
    # Dia de gimnàs: no hi ha rutina d'espatlla separada.
    assert not any("Rutina d'espatlla" in str(c) for c in capcaleres)


# --- Validació ---


def test_separacio_insuficient_amb_qualitat(nedador_amb_gimnas):
    sessions = generar_esquelet_sessions(nedador_amb_gimnas, _microcicle())
    avisos = validar_franges_setmana(sessions)
    tipus = {(a["tipus"], a["dia"]) for a in avisos}
    # Dimarts: qualitat al matí i gimnàs al migdia (franges contigües).
    assert ("separacio_insuficient", "dimarts") in tipus
    # Dimecres: gimnàs el dia de tècnica.
    assert ("gimnas_dia_no_recomanat", "dimecres") in tipus
    # Dilluns: aeròbic al matí i gimnàs a la tarda -> cap avís.
    assert not [a for a in avisos if a["dia"] == "dilluns"]
    # Dissabte: sense natació -> cap avís.
    assert not [a for a in avisos if a["dia"] == "dissabte"]


def test_qualitat_mati_gimnas_tarda_sense_avis():
    tipus = {dia: [_nat("mati")] for dia in DIES_5}
    tipus["dimarts"].append(_gim("tarda"))
    sessions = generar_esquelet_sessions(_nedador(tipus), _microcicle())
    assert validar_franges_setmana(sessions) == []


def test_gimnas_dia_activacio():
    tipus = {dia: [_nat("mati")] for dia in DIES_5}
    tipus["divendres"].append(_gim("tarda"))
    sessions = generar_esquelet_sessions(
        _nedador(tipus), _microcicle(dia_competicio="dissabte")
    )
    avisos = validar_franges_setmana(sessions)
    assert [(a["tipus"], a["dia"]) for a in avisos] == [
        ("gimnas_dia_no_recomanat", "divendres")
    ]
