from typing import Literal

from pydantic import BaseModel, field_validator

from blondswim.models.franja import Franja, Modalitat


class Exercici(BaseModel):
    """
    Un exercici concret (una sèrie) dins d'una part de sessió. El volum
    (series x distancia_m) es calcula sempre en codi -- mai el redacta
    el LLM -- per evitar totals que no siguin múltiples de 25m.
    """
    series: int
    distancia_m: int  # validat múltiple de 25
    execucio: str
    descans: str | None = None  # notació "c/X'Y''" o "d/Ns"
    material: str | None = None
    intensitat: Literal[
        "Recuperació", "A1", "A2", "A3", "Velocitat", "MPLA", "TOLA", "AeM"
    ] | None = None
    objectiu: str | None = None
    # Id de l'exercici de la biblioteca de tècnica, si n'és un.
    id_biblioteca: str | None = None

    @field_validator("distancia_m")
    @classmethod
    def validar_multiple_25(cls, v: int) -> int:
        if v % 25 != 0:
            raise ValueError(f"distancia_m ha de ser múltiple de 25m (rebut: {v})")
        return v

    @property
    def volum_m(self) -> int:
        return self.series * self.distancia_m


BlocSessio = Literal[
    "Escalfament", "Tècnica", "Bloc principal", "Tornada a la calma", "Sèrie de control"
]


class PartSessio(BaseModel):
    """
    Representa una part de la sessió d'entrenament amb els seus percentatges
    segons el tipus de setmana.
    """
    nom: str  # Ex: "Escalfament", "Tècnica+Subaquàtic", etc.
    percentatge_carrega: float
    percentatge_qualitat: float
    percentatge_descarrega: float
    contingut: str | None = None
    exercicis: list[Exercici] = []
    # Part fixada pel codi (p.ex. la sèrie de control): l'LLM no la genera
    # ni la modifica, i no compta per al pressupost d'intensitat.
    fixa: bool = False
    # Bloc de l'estructura de la sessió (escalfament, tècnica, bloc principal,
    # tornada a la calma o sèrie de control). None en sessions antigues.
    bloc: BlocSessio | None = None
    # Metres que ha de fer la part (múltiple de 100; l'última part, la resta
    # fins al total de la sessió). None en sessions antigues.
    metres_objectiu: int | None = None

class EstructuraSessio(BaseModel):
    """
    Estructura fixa de 5 parts d'una sessió d'entrenament amb percentatges
    segons tipus de setmana (Càrrega / Qualitat / Descàrrega-Test).
    
    Parts estàndard:
    1. Escalfament (10%/10%/15%)
    2. Tècnica+Subaquàtic (20%/15%/15%)
    3. Aeròbic/Llindar (50%/30%/20%)
    4. Específic/Qualitat (10%/35%/40%)
    5. Tornada a la calma (10%/10%/10%)
    """
    parts: list[PartSessio]

class Sessio(BaseModel):
    """
    Representa una sessió d'entrenament concreta dins d'un microcicle.
    """
    id: str
    microcicle_setmana: int
    dia: Literal["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"]
    tipus_sessio: Literal["carrega", "qualitat", "descarrega", "taper", "transicio"]
    volum_total: int  # metres
    estructura: EstructuraSessio
    es_dia_opcional: bool = False  # True si correspon al dia opcional del nedador
    notes: str | None = None
    rol: Literal[
        "llarga", "mitjana", "qualitat",
        "aerobica", "tecnica", "activacio", "recuperacio",
    ] | None = None
    volum_min: int | None = None
    volum_max: int | None = None
    # Ids de la biblioteca de tècnica que la sessió ha d'incloure.
    exercicis_tecnica: list[str] = []
    # Franja i modalitat (Fase E+I). Les sessions de gimnàs són informatives:
    # sense parts ni contingut LLM, amb durada_min i volum_total = 0.
    franja: Franja = "tarda"
    modalitat: Modalitat = "natacio"
    durada_min: int | None = None
