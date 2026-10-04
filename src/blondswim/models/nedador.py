from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from blondswim.models.franja import (
    DIES_SETMANA,
    FRANJA_PER_DEFECTE,
    MAX_SESSIONS_DIA,
    ORDRE_FRANJA,
    SlotSessio,
)
from blondswim.utils.proves import mateixa_prova
from blondswim.utils.temps import parsejar_temps


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

class NivellActual(BaseModel):
    """
    Nivell actual en una prova, com a rang: la millor marca (extrem optimista) i
    el temps que el coach estima que faria ara (extrem pessimista). Els temps
    s'accepten en segons o com a text («1:17.08», «1'20\"00»).
    """

    millor_marca: float
    estimacio_pessimista: float

    @field_validator("millor_marca", "estimacio_pessimista", mode="before")
    @classmethod
    def _temps(cls, v):
        return parsejar_temps(v)

    @model_validator(mode="after")
    def _ordre(self) -> "NivellActual":
        if self.millor_marca > self.estimacio_pessimista:
            raise ValueError(
                "nivell_actual: la millor marca no pot ser més lenta que l'estimació pessimista"
            )
        return self


class ObjectiuProva(BaseModel):
    """Objectiu d'una prova en una competició A, com a rang (realista ≥ ambiciós)."""

    competicio_id: str
    realista: float
    ambicios: float

    @field_validator("realista", "ambicios", mode="before")
    @classmethod
    def _temps(cls, v):
        return parsejar_temps(v)

    @model_validator(mode="after")
    def _ordre(self) -> "ObjectiuProva":
        if self.ambicios > self.realista:
            raise ValueError(
                f"objectiu {self.competicio_id}: l'ambiciós no pot ser més lent que el realista"
            )
        return self


class ProvaObjectiu(BaseModel):
    """
    Prova objectiu del nedador: prioritat P (principal) o S (secundària),
    piscina, nivell actual i objectius per competició A.
    """

    prova: str
    prioritat: Literal["P", "S"] = "P"
    piscina: Literal["25m", "50m"] = "25m"
    nivell_actual: NivellActual | None = None
    objectius: list[ObjectiuProva] = []

    def objectiu_per(self, competicio_ids: list[str]) -> ObjectiuProva | None:
        """Primer objectiu definit per a alguna de les competicions (p. ex. un doble pic)."""
        for comp_id in competicio_ids:
            for objectiu in self.objectius:
                if objectiu.competicio_id == comp_id:
                    return objectiu
        return None


class ParametresProgressio(BaseModel):
    """Paràmetres de l'avaluació de la progressió (calibrables per nedador)."""

    # Millora esperada pel taper de la competició A (Mujika: ~2-3%).
    guany_taper: float = 0.02
    # Marge de soroll entre competicions (elit ~0,8%; màsters, més).
    marge: float = 0.01
    # Millora màxima raonable abans del taper (fins a la A) abans d'avisar.
    exigencia_max: float = 0.04
    # Competicions de control (B/C) mínimes per prova abans de la A.
    min_competicions_control: int = 2


class Nedador(BaseModel):
    id: str
    nom: str
    edat: int | None = None
    categoria: Literal["absolut", "master", "junior"]
    # Proves objectiu. També accepta la llista antiga de textos (-> prioritat P).
    proves_objectiu: list[ProvaObjectiu]
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
    # Dia de descans amb rutina d'espatlla fora de l'aigua (opcional, 15 min).
    rutina_espatlla_dia: str | None = None
    # Famílies de la biblioteca de tècnica a prioritzar (punts febles del nedador).
    prioritats_tecniques: list[str] = []
    # Setmana tipus (Fase E+I): per a cada dia, les sessions previstes per franja
    # (màxim 3 al dia, una per franja; com a molt una de natació). Si hi és,
    # dies_disponibles es deriva d'aquí (dies amb sessió de natació).
    setmana_tipus: dict[str, list[SlotSessio]] | None = None
    parametres_progressio: ParametresProgressio = ParametresProgressio()

    @field_validator("proves_objectiu", mode="before")
    @classmethod
    def _proves_text(cls, v):
        if isinstance(v, list):
            return [{"prova": p} if isinstance(p, str) else p for p in v]
        return v

    @property
    def noms_proves(self) -> list[str]:
        """Noms de les proves objectiu, en l'ordre de la fitxa."""
        return [p.prova for p in self.proves_objectiu]

    def prova_objectiu(self, nom: str) -> ProvaObjectiu | None:
        """Prova objectiu per nom («100m Lliure» = «100 lliures» = «100 crol»)."""
        for prova in self.proves_objectiu:
            if mateixa_prova(prova.prova, nom):
                return prova
        return None

    @model_validator(mode="after")
    def _validar_setmana_tipus(self) -> "Nedador":
        if self.setmana_tipus is None:
            return self
        for dia, slots in self.setmana_tipus.items():
            if dia not in DIES_SETMANA:
                raise ValueError(f"setmana_tipus: dia desconegut '{dia}'")
            if len(slots) > MAX_SESSIONS_DIA:
                raise ValueError(
                    f"setmana_tipus: {dia} té {len(slots)} sessions "
                    f"(màxim {MAX_SESSIONS_DIA})"
                )
            franges = [s.franja for s in slots]
            if len(set(franges)) != len(franges):
                raise ValueError(f"setmana_tipus: {dia} té dues sessions a la mateixa franja")
            if sum(1 for s in slots if s.modalitat == "natacio") > 1:
                raise ValueError(
                    f"setmana_tipus: {dia} té més d'una sessió de natació "
                    "(encara no suportat)"
                )
        self.dies_disponibles = [
            dia
            for dia in DIES_SETMANA
            if any(s.modalitat == "natacio" for s in self.setmana_tipus.get(dia, []))
        ]
        return self

    def slots_dia(self, dia: str) -> list[SlotSessio]:
        """Sessions previstes un dia, ordenades per franja."""
        if self.setmana_tipus is None:
            if dia in self.dies_disponibles:
                return [SlotSessio(franja=FRANJA_PER_DEFECTE, modalitat="natacio")]
            return []
        return sorted(self.setmana_tipus.get(dia, []), key=lambda s: ORDRE_FRANJA[s.franja])

    def franja_natacio(self, dia: str) -> str:
        """Franja de la sessió de natació d'un dia (per defecte, tarda)."""
        for slot in self.slots_dia(dia):
            if slot.modalitat == "natacio":
                return slot.franja
        return FRANJA_PER_DEFECTE
