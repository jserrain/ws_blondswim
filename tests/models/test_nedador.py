from blondswim.models.nedador import Nedador

def test_nedador_es_crea_correctament():
    n = Nedador(
        id="jep",
        nom="Jep",
        categoria="master",
        proves_objectiu=["50 papallona", "100 lliure", "100 IM"],
        mode_ritme="temps",
    )
    assert n.id == "jep"
