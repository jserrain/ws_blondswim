from typing import Literal

from pydantic import BaseModel


class RitmesCSS(BaseModel):
    """
    Zones fisiològiques de ritme basades en CSS test o estimació per marca.
    
    Regla de conciliació de fonts:
    - "css_test" té prioritat quan a1/a2/a3 provenen d'un test CSS recent
    - "estimat_marca" s'utilitza quan no hi ha test CSS disponible
    
    Aquesta regla es resol al conversor, no en aquest model.
    """
    recuperacio: float | None = None
    a1: float | None = None
    a2: float | None = None
    a3: float | None = None
    velocitat: float | None = None
    data_test: str | None = None
    font: Literal["css_test", "estimat_marca"] = "estimat_marca"

class MarquesReferencia(BaseModel):
    marca_100_lliure_seg: float
    marca_50_lliure_seg: float
    marca_50_papallona: str | None = None
    marca_200_lliure: str | None = None
    marca_100_im: str | None = None

class ParametresRitme(BaseModel):
    """
    Paràmetres del model de càlcul de zones fisiològiques.
    Compartits per defecte entre nedadors, però sobreescrivibles per nedador.
    """
    increment_a3: float = 0.015
    increment_a2: float = 0.065
    increment_a1: float = 0.13
    increment_recuperacio: float = 0.20
    factor_velocitat: float = 0.85
    factor_escala_50_100: float = 2.02
    factor_escala_100_200: float = 2.04
    ajust_esquena_min: float = 0.10
    ajust_esquena_max: float = 0.11
    ajust_braca_min: float = 0.15
    ajust_braca_max: float = 0.20
    offset_recuperacio_css: float = 12
    offset_a1_css: float = 6
    offset_a2_css: float = 0
    offset_a3_css: float = -4

class RitmeCursaObjectiu(BaseModel):
    """
    Ritme objectiu per a una prova específica (independent de zones fisiològiques).
    Utilitzat per a sèries USRPT.
    """
    prova: str
    distancia_m: int
    temps_objectiu_seg: float | None = None

class Nedador(BaseModel):
    id: str
    nom: str
    edat: int | None = None
    categoria: Literal["absolut", "master", "junior"]
    proves_objectiu: list[str]
    pics_prioritzats: list[str] = []
    mode_ritme: Literal["temps", "rpe"]
    marques_referencia: MarquesReferencia | None = None
    ritmes_css: RitmesCSS | None = None
    parametres_ritme: ParametresRitme = ParametresRitme()
    ritmes_cursa_objectiu: list[RitmeCursaObjectiu] = []
    dies_disponibles: list[str] = ["dilluns", "dimarts", "dimecres", "dijous"]
    dia_opcional: str | None = None
    piscina_m: int = 25
    # Terra de volum setmanal (càrrega/qualitat/descàrrega; no taper ni transició).
    volum_setmanal_min: int = 12000
    # Durada màxima d'una sessió (F7, encara no validat).
    minuts_max_sessio: int = 105
