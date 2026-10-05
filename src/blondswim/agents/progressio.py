"""
Avaluació de la progressió cap a l'objectiu A (determinista, sense LLM).

Per a cada prova del pic actiu:

1. **Banda prevista**: dues línies des de la primera competició de control (B/C,
   mateixa piscina) fins al temps *sense taper* a la data de la primera A
   (objectiu × (1 + guany_taper)):
   - línia ràpida: de la millor marca a l'objectiu ambiciós;
   - línia lenta: de l'estimació pessimista a l'objectiu realista.
2. **Zona** de cada resultat: blava (més ràpid que la ràpida), verda (dins la
   banda), groga (fins a `marge` més lent que la lenta, dins del soroll) o
   vermella (més lent).
3. **Calibratge** amb el primer resultat: millora que encara cal abans del taper.
4. **Projecció** amb >= 2 resultats: regressió lineal fins a la data de la A,
   menys el taper, amb un interval de ±1 error estàndard de predicció. El soroll
   mínim és el `marge` (amb 2-4 curses la variabilitat observada no és fiable).
5. **Temps de referència del ritme de cursa**: el realista; amb projecció, el
   temps projectat (com a molt l'ambiciós), també si el realista no és assolible.

Les **simulacions** (contrarellotges en entrenament) compten com a punts de control
(calibratge, zona i projecció), però no fan saltar l'avís «sense millora» ni
generen «nova millor marca»: sense competició, el temps sol ser una mica més lent
i no és oficial.

Mai es compara una competició amb l'anterior: el progrés previst entre dues B
és més petit que la variabilitat entre competicions (Pyne et al. 2004: ~0,8%).
"""

import math
from dataclasses import dataclass, field
from datetime import date

from blondswim.agents.proves import (
    Pic,
    competicions_control,
    pic_actiu,
    pics_temporada,
    proves_pic,
)
from blondswim.models.calendari import Competicio
from blondswim.models.nedador import (
    Nedador,
    NivellActual,
    ObjectiuProva,
    ParametresProgressio,
)
from blondswim.models.resultat import ResultatCompeticio
from blondswim.utils.proves import mateixa_prova
from blondswim.utils.temps import format_temps

ZONES = ("blava", "verda", "groga", "vermella")

ETIQUETA_CAMI = {
    "ambicios": "camí de l'ambiciós",
    "realista": "camí del realista",
    "no_arriba": "no arriba al realista",
}


def _data(text: str) -> date:
    return date.fromisoformat(text)


def banda(
    nivell: NivellActual,
    objectiu: ObjectiuProva,
    inici: date,
    fi: date,
    data: date,
    guany_taper: float,
) -> tuple[float, float]:
    """(línia ràpida, línia lenta) a `data`, interpolant entre `inici` i `fi`."""
    total = (fi - inici).days
    frac = 1.0 if total <= 0 else min(max((data - inici).days / total, 0.0), 1.0)
    fi_rapid = objectiu.ambicios * (1 + guany_taper)
    fi_lent = objectiu.realista * (1 + guany_taper)
    rapid = nivell.millor_marca + (fi_rapid - nivell.millor_marca) * frac
    lent = nivell.estimacio_pessimista + (fi_lent - nivell.estimacio_pessimista) * frac
    return rapid, lent


def zona(temps: float, rapid: float, lent: float, marge: float) -> str:
    """Zona d'un resultat respecte a la banda."""
    if temps < rapid:
        return "blava"
    if temps <= lent:
        return "verda"
    if temps <= lent * (1 + marge):
        return "groga"
    return "vermella"


@dataclass
class PuntControl:
    competicio: Competicio
    rapid: float | None
    lent: float | None
    resultat: float | None = None
    zona: str | None = None

    @property
    def data(self) -> date:
        return _data(self.competicio.data_inici)


@dataclass
class Projeccio:
    """Temps projectat a la competició A (amb taper) i interval de ±1 error estàndard."""

    temps_a: float
    minim: float
    maxim: float
    n: int
    cami: str


def projectar(
    punts: list[tuple[int, float]],
    x_a: int,
    objectiu: ObjectiuProva,
    params: ParametresProgressio,
) -> Projeccio | None:
    """Regressió lineal dels resultats (dies, segons) projectada a `x_a`."""
    n = len(punts)
    if n < 2:
        return None
    xs = [x for x, _ in punts]
    ys = [y for _, y in punts]
    xm, ym = sum(xs) / n, sum(ys) / n
    sxx = sum((x - xm) ** 2 for x in xs)
    if sxx == 0:
        return None
    pendent = sum((x - xm) * (y - ym) for x, y in punts) / sxx
    y_a = ym + pendent * (x_a - xm)
    residual = 0.0
    if n > 2:
        residual = math.sqrt(
            sum((y - (ym + pendent * (x - xm))) ** 2 for x, y in punts) / (n - 2)
        )
    soroll = max(residual, params.marge * ym)
    error = soroll * math.sqrt(1 + 1 / n + (x_a - xm) ** 2 / sxx)
    factor = 1 + params.guany_taper
    temps_a = y_a / factor
    if temps_a <= objectiu.ambicios:
        cami = "ambicios"
    elif temps_a <= objectiu.realista:
        cami = "realista"
    else:
        cami = "no_arriba"
    return Projeccio(
        temps_a=temps_a,
        minim=(y_a - error) / factor,
        maxim=(y_a + error) / factor,
        n=n,
        cami=cami,
    )


def temps_ritme_cursa(
    objectiu: ObjectiuProva | None,
    projeccio: Projeccio | None,
) -> float | None:
    """
    Temps de referència per a les sèries de ritme de cursa.

    Sense projecció (menys de 2 resultats): l'objectiu realista. Amb projecció:
    el temps projectat, sense passar de l'ambiciós. Si la projecció no arriba al
    realista, es fa servir la projecció (entrenar a un ritme inassolible no és
    ritme de cursa). No es fa servir la posició d'un sol resultat dins la banda:
    a l'inici, l'amplada de la banda és la incertesa del nivell, no progrés.
    """
    if objectiu is None:
        return None
    if projeccio is None:
        return objectiu.realista
    return max(projeccio.temps_a, objectiu.ambicios)


@dataclass
class EstatProva:
    nom: str
    prioritat: str
    perfil: str | None
    objectiu: ObjectiuProva | None
    nivell: NivellActual | None
    punts: list[PuntControl] = field(default_factory=list)
    exigencia_realista: float | None = None
    exigencia_ambicios: float | None = None
    projeccio: Projeccio | None = None
    ritme_cursa: float | None = None
    avisos: list[dict] = field(default_factory=list)

    @property
    def ultima_zona(self) -> str | None:
        zones = [p.zona for p in self.punts if p.zona]
        return zones[-1] if zones else None


def _millor_resultat(
    resultats: list[ResultatCompeticio], competicio_id: str, prova: str
) -> float | None:
    temps = [
        r.temps
        for r in resultats
        if r.competicio_id == competicio_id and mateixa_prova(r.prova, prova)
    ]
    return min(temps) if temps else None


def avaluar_pic(
    nedador: Nedador,
    competicions: list[Competicio],
    resultats: list[ResultatCompeticio],
    avui: date,
    pic: Pic | None = None,
) -> tuple[Pic | None, list[EstatProva]]:
    """Estat de progressió de cada prova del pic (per defecte, el pic actiu)."""
    if pic is None:
        pic = pic_actiu(pics_temporada(competicions), avui)
    if pic is None:
        return None, []
    params = nedador.parametres_progressio
    estats = []
    for prova_pic in proves_pic(nedador, pic):
        prova = prova_pic.prova
        objectiu = prova.objectiu_per(pic.ids) if prova else None
        nivell = prova.nivell_actual if prova else None
        estat = EstatProva(
            nom=prova_pic.nom,
            prioritat=prova_pic.prioritat,
            perfil=prova_pic.perfil,
            objectiu=objectiu,
            nivell=nivell,
        )
        control = competicions_control(competicions, pic, prova_pic.nom)
        inici = _data(control[0].data_inici) if control else None
        for comp in control:
            rapid = lent = None
            if objectiu and nivell and inici:
                rapid, lent = banda(
                    nivell, objectiu, inici, pic.data_inici, _data(comp.data_inici),
                    params.guany_taper,
                )
            punt = PuntControl(competicio=comp, rapid=rapid, lent=lent)
            punt.resultat = _millor_resultat(resultats, comp.id, prova_pic.nom)
            if punt.resultat is not None and rapid is not None:
                punt.zona = zona(punt.resultat, rapid, lent, params.marge)
            estat.punts.append(punt)

        amb_resultat = [p for p in estat.punts if p.resultat is not None]
        if objectiu and amb_resultat:
            primer = amb_resultat[0].resultat
            factor = 1 + params.guany_taper
            estat.exigencia_realista = (primer - objectiu.realista * factor) / primer
            estat.exigencia_ambicios = (primer - objectiu.ambicios * factor) / primer
            if estat.exigencia_realista > params.exigencia_max:
                estat.avisos.append({
                    "tipus": "objectiu_exigent_calibrat",
                    "missatge": (
                        f"{estat.nom}: amb el primer resultat ({format_temps(primer)}), "
                        f"el realista demana un {estat.exigencia_realista:.1%} abans del taper "
                        f"(màxim raonable {params.exigencia_max:.0%}): revisar l'objectiu"
                    ),
                })
        if nivell:
            millors = [
                p.resultat
                for p in amb_resultat
                if p.resultat < nivell.millor_marca and not p.competicio.es_simulacio
            ]
            if millors:
                estat.avisos.append({
                    "tipus": "nova_millor_marca",
                    "missatge": (
                        f"{estat.nom}: nova millor marca {format_temps(min(millors), 2)}; "
                        "actualitza-la a la fitxa"
                    ),
                })
        if objectiu and inici:
            x_a = (pic.data_inici - inici).days
            punts_xy = [((p.data - inici).days, p.resultat) for p in amb_resultat]
            estat.projeccio = projectar(punts_xy, x_a, objectiu, params)
        vermelles = 0
        for p in amb_resultat:
            if p.competicio.es_simulacio:
                continue
            vermelles = vermelles + 1 if p.zona == "vermella" else 0
        if vermelles >= 2:
            estat.avisos.append({
                "tipus": "sense_millora",
                "missatge": (
                    f"{estat.nom}: dos resultats seguits a la zona vermella; "
                    "recomanació: revisar l'entrenament (decisió del coach)"
                ),
            })
        estat.ritme_cursa = temps_ritme_cursa(objectiu, estat.projeccio)
        estats.append(estat)
    return pic, estats


def _ft(segons: float | None) -> str:
    return format_temps(segons) if segons is not None else "—"


def format_informe(
    pic: Pic | None, estats: list[EstatProva], avisos_validacio: list[dict] | None = None
) -> list[str]:
    """Línies de text de l'informe de progressió."""
    linies: list[str] = []
    if pic is None:
        return ["Cap competició A pendent al calendari."]
    noms = " + ".join(c.nom for c in pic.competicions)
    linies.append(f"Pic {pic.numero}: {noms} ({pic.data_inici:%d/%m/%Y}, {pic.piscina})")
    for estat in estats:
        perfil = f", {estat.perfil}" if estat.perfil else ""
        if estat.objectiu:
            objectiu = (
                f"objectiu {_ft(estat.objectiu.realista)} (realista) – "
                f"{_ft(estat.objectiu.ambicios)} (ambiciós)"
            )
        else:
            objectiu = "sense objectiu"
        linies.append("")
        linies.append(f"  {estat.nom} ({estat.prioritat}{perfil}) · {objectiu}")
        if not estat.punts:
            linies.append("    Cap competició de control (B/C, mateixa piscina) abans del pic.")
        else:
            linies.append(f"    {'Competició':<34} {'Data':<6} {'Banda prevista':<17} "
                          f"{'Resultat':<9} Zona")
            for p in estat.punts:
                banda_txt = (
                    f"{_ft(p.rapid)} – {_ft(p.lent)}" if p.rapid is not None else "—"
                )
                nom = ("[S] " if p.competicio.es_simulacio else "") + p.competicio.nom
                linies.append(
                    f"    {nom[:34]:<34} {p.data:%d/%m} {banda_txt:<17} "
                    f"{_ft(p.resultat):<9} {p.zona or ''}"
                )
        if estat.exigencia_realista is not None:
            linies.append(
                f"    Calibratge: el realista demana {estat.exigencia_realista:+.1%} i "
                f"l'ambiciós {estat.exigencia_ambicios:+.1%} abans del taper"
            )
        if estat.projeccio:
            pr = estat.projeccio
            linies.append(
                f"    Projecció a la A: {_ft(pr.temps_a)} ({_ft(pr.minim)} – {_ft(pr.maxim)}, "
                f"±1σ, {pr.n} curses) → {ETIQUETA_CAMI[pr.cami]}"
            )
        if estat.ritme_cursa is not None:
            linies.append(f"    Ritme de cursa de referència: {_ft(estat.ritme_cursa)}")
        for avis in estat.avisos:
            linies.append(f"    ⚠ {avis['missatge']}")
    if any(p.competicio.es_simulacio for e in estats for p in e.punts):
        linies.append("")
        linies.append("  [S] = simulació (contrarellotge en entrenament): no altera la planificació")
    if avisos_validacio:
        linies.append("")
        linies.append("  Dades pendents o incoherents:")
        for avis in avisos_validacio:
            linies.append(f"    ⚠ {avis['missatge']}")
    return linies
