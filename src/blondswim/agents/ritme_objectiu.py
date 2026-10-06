"""Sèries de ritme objectiu (decisió de l'entrenador, 06/10).

Una sèrie fixa per prova principal (p. ex. 8x50 a ritme del 100 lliure el
dimarts) que es repeteix cada setmana i acosta el ritme al de l'objectiu:

- **Inici**: l'estimació pessimista del nivell actual.
- **Final**: l'objectiu realista del pic actiu, sense el guany del taper
  (objectiu × (1 + guany_taper)). Al Peak i a la setmana de cursa, el ritme de
  cursa (objectiu realista).
- **Passos**: les setmanes útils (Base, Build1, Build2, sense descàrrega) des de
  l'inici de la sèrie fins al Peak. L'objectiu de cada pas s'interpola.

La progressió depèn dels temps registrats, no del calendari:

- temps mitjà dins de l'objectiu (marge de la fitxa, 1%) -> avança un pas;
- molt per sota (2,5% més ràpid) -> avança dos passos;
- per sobre -> repeteix; dues setmanes seguides per sobre -> retrocedeix un pas;
- setmana sense registre -> repeteix (i avisa).

L'estat no es desa: es recalcula cada vegada a partir dels registres (cada
registre porta l'objectiu que es va prescriure aquella setmana).

Forma de la sèrie per fase (palanques: ritme, densitat i volum):

| Fase | Repeticions | Descans |
|---|---|---|
| Base | 6 -> 8 (crol) / 4 -> 6 (estils) | d/1:00 |
| Build1 | 8 / 6 | d/1:00 i, a partir de la 3a setmana del bloc, d/0:45 |
| Build2 | 8 / 6 | d/0:45 |
| descàrrega | 4 | el de la fase; l'objectiu es manté |
| Peak i Cursa | 4 | d/1:30, a ritme de cursa |
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from blondswim.agents import pla_setmanal
from blondswim.agents.periodificacio import SetmanaPlan
from blondswim.agents.proves import Pic
from blondswim.models.nedador import Nedador, ProvaObjectiu, SerieObjectiu
from blondswim.models.registre import RegistreSerieObjectiu
from blondswim.models.resultat import ResultatCompeticio
from blondswim.models.sessio import Exercici, PartSessio, Sessio
from blondswim.utils.proves import mateixa_prova

NOM_PART = "Sèrie objectiu"
NOM_RECUPERACIO = "Recuperació activa"
RECUPERACIO_M = 200
DIES_PER_DEFECTE = ["dimarts", "dijous"]
FASES_UTILS = ("Base", "Build1", "Build2")
MOLT_PER_SOTA = 0.025
# Fracció del 100 IM que es neda a la primera meitat (papallona + esquena) si no
# hi ha parcials registrats.
FRACCIO_IM_PRIMERA_MEITAT = 0.47


def es_estils(prova: str) -> bool:
    text = prova.casefold()
    return "im" in text.split() or "estils" in text or text.endswith(" im")


def series_del_nedador(nedador: Nedador) -> list[SerieObjectiu]:
    """Les de la fitxa o, per defecte, una per prova P (dimarts i dijous)."""
    if nedador.series_objectiu is not None:
        return nedador.series_objectiu
    principals = [p for p in nedador.proves_objectiu if p.prioritat == "P"]
    return [
        SerieObjectiu(prova=p.prova, dia=dia)
        for p, dia in zip(principals, DIES_PER_DEFECTE, strict=False)
    ]


# --- Classificació i progressió ----------------------------------------------------


def classificar(temps_mitja: float, objectiu: float, marge: float) -> str:
    """«molt_per_sota», «dins» o «per_sobre» (temps per repetició, en segons)."""
    if temps_mitja <= objectiu * (1 - MOLT_PER_SOTA):
        return "molt_per_sota"
    if temps_mitja <= objectiu * (1 + marge):
        return "dins"
    return "per_sobre"


ETIQUETA_RESULTAT = {
    "molt_per_sota": "molt per sota de l'objectiu",
    "dins": "dins de l'objectiu",
    "per_sobre": "per sobre de l'objectiu",
}


@dataclass
class Progressio:
    pas: int = 0
    darrer: str | None = None
    darrer_temps: float | None = None
    avisos: list[str] = field(default_factory=list)


def reproduir(
    registres: list[RegistreSerieObjectiu], marge: float, passos: int
) -> Progressio:
    """Pas actual a partir dels registres d'una prova, en ordre cronològic."""
    estat = Progressio()
    fallades = 0
    for reg in sorted(registres, key=lambda r: r.data):
        resultat = classificar(reg.temps_mitja, reg.objectiu, marge)
        estat.darrer, estat.darrer_temps = resultat, reg.temps_mitja
        if resultat == "molt_per_sota":
            estat.pas += 2
            fallades = 0
        elif resultat == "dins":
            estat.pas += 1
            fallades = 0
        else:
            fallades += 1
            if fallades >= 2:
                estat.pas = max(estat.pas - 1, 0)
                fallades = 0
                estat.avisos.append(
                    f"{reg.data:%d/%m}: dues setmanes per sobre de l'objectiu; es "
                    "retrocedeix un pas. Revisa si l'objectiu del pic és realista."
                )
        estat.pas = min(estat.pas, passos)
    return estat


# --- Objectius i forma de la sèrie ------------------------------------------------


def passos_fins_al_pic(plans: list[SetmanaPlan], inici: date) -> int:
    """Setmanes útils (Base/Build, sense descàrrega) des d'`inici` fins al Peak."""
    n = 0
    for plan in sorted(plans, key=lambda p: p.dilluns):
        if plan.dilluns < inici:
            continue
        if plan.fase in ("Peak", "Cursa", "Transicio"):
            break
        if plan.fase in FASES_UTILS and not plan.es_descarrega:
            n += 1
    return max(n, 1)


def temps_per_repeticio(temps_100: float, distancia: int) -> float:
    return temps_100 * distancia / 100


def objectiu_pas(inici: float, final: float, pas: int, passos: int) -> float:
    return inici - (inici - final) * min(pas, passos) / passos


def forma(plan: SetmanaPlan, pas: int, estils: bool) -> tuple[int, str]:
    """(repeticions, descans) segons la fase."""
    maxim = 6 if estils else 8
    if plan.fase in ("Peak", "Cursa"):
        return 4, "d/1:30"
    if plan.es_descarrega:
        return 4, "d/1:00" if plan.fase == "Base" else "d/0:45"
    if plan.fase == "Base":
        return min(maxim - 2 + pas, maxim), "d/1:00"
    if plan.fase == "Build1":
        return maxim, "d/1:00" if plan.index_dins_bloc < 2 else "d/0:45"
    return maxim, "d/0:45"


def fraccio_im(resultats: list[ResultatCompeticio], prova: str) -> float:
    """Fracció del 100 IM a la primera meitat, dels parcials de 25 registrats."""
    fraccions = [
        sum(r.parcials_25[:2]) / r.temps
        for r in resultats
        if mateixa_prova(r.prova, prova) and len(r.parcials_25) == 4
    ]
    return sum(fraccions) / len(fraccions) if fraccions else FRACCIO_IM_PRIMERA_MEITAT


def _seg(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + " s"


# --- Prescripció ------------------------------------------------------------------


@dataclass
class Prescripcio:
    prova: str
    dia: str
    series: int
    distancia: int
    descans: str
    objectiu: float  # segons per repetició (mitjana)
    execucio: str
    pas: int
    passos: int
    resum: str
    avisos: list[str] = field(default_factory=list)


def prescriure(
    nedador: Nedador,
    serie: SerieObjectiu,
    pic: Pic | None,
    plans: list[SetmanaPlan],
    dilluns: date,
    registres: list[RegistreSerieObjectiu],
    resultats: list[ResultatCompeticio] | None = None,
    des_de: date | None = None,
) -> Prescripcio | None:
    """Sèrie de ritme objectiu de la setmana de `dilluns`, o None si no toca.

    `des_de`: final del pic anterior; els registres d'abans no compten.
    """
    prova: ProvaObjectiu | None = nedador.prova_objectiu(serie.prova)
    plan = next((p for p in plans if p.dilluns == dilluns), None)
    if prova is None or pic is None or plan is None or plan.fase == "Transicio":
        return None
    objectiu_pic = prova.objectiu_per(pic.ids)
    if prova.nivell_actual is None or objectiu_pic is None:
        return None

    # Només els registres d'aquest pic (posteriors al pic anterior) i anteriors a avui.
    propis = [
        r for r in registres
        if mateixa_prova(r.prova, serie.prova) and r.data < dilluns
        and (des_de is None or r.data > des_de)
    ]
    inici_serie = min((r.data for r in propis), default=dilluns)
    inici_serie -= timedelta(days=inici_serie.weekday())
    passos = passos_fins_al_pic(plans, inici_serie)
    marge = nedador.parametres_progressio.marge
    estat = reproduir(propis, marge, passos)
    setmanes_sense = [
        p.dilluns for p in plans
        if inici_serie <= p.dilluns < dilluns and p.fase in FASES_UTILS
        and not any(p.dilluns <= r.data <= p.diumenge for r in propis)
    ]
    if propis and setmanes_sense:
        estat.avisos.append(
            f"{len(setmanes_sense)} setmana(es) sense temps registrats: l'objectiu no "
            "avança si no hi ha registre"
        )

    guany = nedador.parametres_progressio.guany_taper
    inici = temps_per_repeticio(prova.nivell_actual.estimacio_pessimista, serie.distancia)
    # Si l'objectiu ja és el nivell actual (p. ex. 100 IM 1:38 = 1:38), la sèrie
    # consolida el ritme: mai no es fa més lenta que l'inici.
    final = min(temps_per_repeticio(objectiu_pic.realista * (1 + guany), serie.distancia), inici)
    if plan.fase in ("Peak", "Cursa"):
        objectiu = min(temps_per_repeticio(objectiu_pic.realista, serie.distancia), inici)
    else:
        objectiu = objectiu_pas(inici, final, estat.pas, passos)

    estils = es_estils(serie.prova)
    series, descans = forma(plan, estat.pas, estils)
    nom_prova = serie.prova
    if estils:
        f = fraccio_im(resultats or [], serie.prova)
        primera, segona = 2 * objectiu * f, 2 * objectiu * (1 - f)
        execucio = (
            f"50 alternant papallona-esquena ({_seg(primera)}) i braça-crol "
            f"({_seg(segona)}) a ritme del {nom_prova}, amb viratges de competició. "
            "Anota el temps de cada 50 al registre"
        )
    else:
        execucio = (
            f"Crol a ritme del {nom_prova}: {_seg(objectiu)} per {serie.distancia}, "
            "sortida des de l'aigua. Anota el temps de cada repetició al registre"
        )
    darrer = (
        f"; darrer: {ETIQUETA_RESULTAT[estat.darrer]} ({_seg(estat.darrer_temps)})"
        if estat.darrer else ""
    )
    resum = (
        f"{nom_prova} ({serie.dia}): {series}x{serie.distancia} {descans}, objectiu "
        f"{_seg(objectiu)} per {serie.distancia} · pas {estat.pas}/{passos}{darrer}"
    )
    return Prescripcio(
        prova=serie.prova, dia=serie.dia, series=series, distancia=serie.distancia,
        descans=descans, objectiu=round(objectiu, 1), execucio=execucio,
        pas=estat.pas, passos=passos, resum=resum, avisos=estat.avisos,
    )


# --- Inserció a les sessions -------------------------------------------------------


def part_serie_objectiu(prescripcio: Prescripcio) -> PartSessio:
    return PartSessio(
        nom=NOM_PART,
        bloc="Bloc principal",
        percentatge_carrega=0,
        percentatge_qualitat=0,
        percentatge_descarrega=0,
        fixa=True,
        exercicis=[
            Exercici(
                series=prescripcio.series,
                distancia_m=prescripcio.distancia,
                execucio=prescripcio.execucio,
                descans=prescripcio.descans,
                intensitat="TOLA",
                objectiu=f"Ritme objectiu {prescripcio.prova}",
            )
        ],
    )


def part_recuperacio() -> PartSessio:
    """200 m suaus després de la sèrie objectiu, abans del bloc principal (la
    recuperació activa suau manté millor el rendiment següent que la passiva)."""
    return PartSessio(
        nom=NOM_RECUPERACIO, bloc="Bloc principal", percentatge_carrega=0,
        percentatge_qualitat=0, percentatge_descarrega=0, fixa=True,
        exercicis=[Exercici(series=1, distancia_m=RECUPERACIO_M,
                            execucio="Nedar suau, estil complet", intensitat="Recuperació",
                            objectiu="Recuperació activa entre sèries")],
    )


def afegir_series_objectiu(
    sessions: list[Sessio], prescripcions: list[Prescripcio]
) -> list[str]:
    """
    Insereix cada sèrie objectiu com a part fixa de la sessió del seu dia, després
    de la tècnica (abans del primer bloc principal), i torna a repartir els metres
    de les parts. Si el dia no té sessió de natació apta (activació o
    recuperació), no s'insereix. Retorna els avisos.
    """
    avisos = []
    for presc in prescripcions:
        sessio = next(
            (s for s in sessions if s.dia == presc.dia and s.modalitat == "natacio"), None
        )
        if sessio is None or sessio.rol in ("activacio", "recuperacio"):
            avisos.append(
                f"Sèrie objectiu {presc.prova}: el {presc.dia} no hi ha sessió apta; "
                "aquesta setmana no es fa"
            )
            continue
        parts = sessio.estructura.parts
        posicio = next(
            (i for i, p in enumerate(parts) if p.bloc == "Bloc principal" and not p.fixa),
            len(parts) - 1,
        )
        parts.insert(posicio, part_serie_objectiu(presc))
        parts.insert(posicio + 1, part_recuperacio())
        pla_setmanal.assignar_metres_parts(sessio)
    return avisos
