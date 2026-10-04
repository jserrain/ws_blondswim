"""
Proves objectiu dins la temporada: pics, pesos, perfil per durada i validacions.

- **Pic**: una competició A, o un grup de competicions A a <= SETMANES_DOBLE_PIC
  setmanes (doble pic: Catalunya + Espanya d'hivern). Es calcula del calendari.
- **Proves del pic**: les que el nedador neda a les competicions A del pic
  (camp `proves` del calendari). El pes surt de la prioritat de la fitxa
  (P = 2, S = 1).
- **Perfil per durada**: classifica cada prova pel temps del nedador (no per la
  distància), segons l'aportació aeròbica/anaeròbica de l'esforç màxim
  (encreuament a ~79 s). Font: Sports Medicine 2026 (102 estudis), Gastin 2001.
"""

from dataclasses import dataclass, field
from datetime import date

from blondswim.agents.periodificacio import SETMANES_DOBLE_PIC
from blondswim.models.calendari import Competicio
from blondswim.models.nedador import Nedador, ProvaObjectiu
from blondswim.models.resultat import ResultatCompeticio
from blondswim.utils.proves import clau_prova, mateixa_prova

PES_PRIORITAT = {"P": 2, "S": 1}

# (límit superior en segons, perfil). Per sobre de l'últim: "fons".
LLINDARS_PERFIL = [(45.0, "velocitat"), (120.0, "mixt"), (240.0, "mig_fons")]


def _data(text: str) -> date:
    return date.fromisoformat(text)


@dataclass
class Pic:
    """Competicions A que formen un pic de forma (1 o més si és un doble pic)."""

    numero: int
    competicions: list[Competicio]

    @property
    def ids(self) -> list[str]:
        return [c.id for c in self.competicions]

    @property
    def data_inici(self) -> date:
        return _data(self.competicions[0].data_inici)

    @property
    def data_fi(self) -> date:
        return _data(self.competicions[-1].data_fi)

    @property
    def piscina(self) -> str:
        return self.competicions[0].piscina

    @property
    def proves(self) -> list[str]:
        """Proves que es neden a alguna competició del pic (sense repetir)."""
        resultat: list[str] = []
        for comp in self.competicions:
            for prova in comp.proves:
                if not any(mateixa_prova(prova, p) for p in resultat):
                    resultat.append(prova)
        return resultat


def pics_temporada(competicions: list[Competicio]) -> list[Pic]:
    """Agrupa les competicions A en pics (doble pic si són a <= 4 setmanes)."""
    competicions_a = sorted(
        (c for c in competicions if c.classe == "A"), key=lambda c: (c.data_inici, c.id)
    )
    grups: list[list[Competicio]] = []
    for comp in competicions_a:
        if grups:
            anterior = grups[-1][-1]
            dies = (_data(comp.data_inici) - _data(anterior.data_inici)).days
            if 0 < dies <= SETMANES_DOBLE_PIC * 7:
                grups[-1].append(comp)
                continue
        grups.append([comp])
    return [Pic(numero=i, competicions=g) for i, g in enumerate(grups, start=1)]


def pic_actiu(pics: list[Pic], data: date) -> Pic | None:
    """Primer pic que encara no s'ha acabat a `data`."""
    for pic in pics:
        if pic.data_fi >= data:
            return pic
    return None


def perfil_prova(temps_s: float | None) -> str | None:
    """«velocitat» (< 45 s), «mixt» (45-120 s), «mig_fons» (120-240 s) o «fons»."""
    if temps_s is None:
        return None
    for limit, perfil in LLINDARS_PERFIL:
        if temps_s < limit:
            return perfil
    return "fons"


def temps_referencia(prova: ProvaObjectiu | None) -> float | None:
    """Temps per classificar el perfil: l'extrem pessimista del nivell actual."""
    if prova is None or prova.nivell_actual is None:
        return None
    return prova.nivell_actual.estimacio_pessimista


@dataclass
class ProvaPic:
    """Una prova del pic amb la seva prioritat, pes i perfil."""

    nom: str
    prova: ProvaObjectiu | None
    prioritat: str
    pes: int
    percentatge: float = 0.0
    perfil: str | None = None


def proves_pic(nedador: Nedador, pic: Pic) -> list[ProvaPic]:
    """Proves del pic amb el pes relatiu (P = 2, S = 1). Les que no són a la
    fitxa es tracten com a S (i `validar_objectius` ho avisa)."""
    resultat = []
    for nom in pic.proves:
        prova = nedador.prova_objectiu(nom)
        prioritat = prova.prioritat if prova else "S"
        resultat.append(
            ProvaPic(
                nom=prova.prova if prova else nom,
                prova=prova,
                prioritat=prioritat,
                pes=PES_PRIORITAT[prioritat],
                perfil=perfil_prova(temps_referencia(prova)),
            )
        )
    total = sum(p.pes for p in resultat)
    for p in resultat:
        p.percentatge = p.pes / total if total else 0.0
    return resultat


def competicions_control(
    competicions: list[Competicio], pic: Pic, prova: str
) -> list[Competicio]:
    """Competicions B/C abans del pic, a la mateixa piscina, on es neda la prova."""
    return sorted(
        (
            c
            for c in competicions
            if c.classe in ("B", "C")
            and c.piscina == pic.piscina
            and _data(c.data_fi) < pic.data_inici
            and any(mateixa_prova(prova, p) for p in c.proves)
        ),
        key=lambda c: (c.data_inici, c.id),
    )


@dataclass
class _Avisos:
    llista: list[dict] = field(default_factory=list)

    def afegir(self, tipus: str, missatge: str) -> None:
        self.llista.append({"tipus": tipus, "missatge": missatge})


def validar_objectius(
    nedador: Nedador,
    competicions: list[Competicio],
    resultats: list[ResultatCompeticio],
    avui: date,
    tots_els_pics: bool = False,
) -> list[dict]:
    """
    Comprova que les dades dels objectius són completes i coherents.

    Per defecte, només valida el pic actiu (els següents encara no cal tenir-los
    a punt); `tots_els_pics=True` els valida tots.

    Avisos (`tipus`): a_sense_proves, a_sense_principal, im100_piscina_50,
    prova_no_fitxa, sense_nivell, sense_objectiu, poques_competicions_control,
    objectiu_exigent, resultat_pendent. Cap avís atura res: decideix el coach.
    """
    avisos = _Avisos()
    params = nedador.parametres_progressio

    for comp in competicions:
        if any(clau_prova(p) == "100 estils" for p in comp.proves) and comp.piscina == "50m":
            avisos.afegir(
                "im100_piscina_50",
                f"{comp.nom}: el 100 IM no es neda en piscina de 50 m",
            )

    pics = pics_temporada(competicions)
    if not tots_els_pics:
        actiu = pic_actiu(pics, avui)
        pics = [actiu] if actiu else []
    for pic in pics:
        for comp in pic.competicions:
            if not comp.proves:
                avisos.afegir(
                    "a_sense_proves",
                    f"{comp.nom} (A): falten les proves al calendari del nedador",
                )
        proves = proves_pic(nedador, pic)
        if proves and not any(p.prioritat == "P" for p in proves):
            avisos.afegir(
                "a_sense_principal",
                f"Pic {pic.numero}: cap prova principal (P) a les competicions A",
            )
        for p in proves:
            etiqueta = f"Pic {pic.numero}, {p.nom}"
            if p.prova is None:
                avisos.afegir("prova_no_fitxa", f"{etiqueta}: la prova no és a la fitxa")
                continue
            if p.prova.nivell_actual is None:
                avisos.afegir("sense_nivell", f"{etiqueta}: falta el nivell actual")
            objectiu = p.prova.objectiu_per(pic.ids)
            if objectiu is None:
                avisos.afegir("sense_objectiu", f"{etiqueta}: falta l'objectiu (realista/ambiciós)")
            control = competicions_control(competicions, pic, p.nom)
            if len(control) < params.min_competicions_control:
                avisos.afegir(
                    "poques_competicions_control",
                    f"{etiqueta}: {len(control)} competicions B/C de {pic.piscina} abans del pic "
                    f"(mínim {params.min_competicions_control})",
                )
            if objectiu is not None and p.prova.nivell_actual is not None:
                sense_taper = objectiu.realista * (1 + params.guany_taper)
                pessimista = p.prova.nivell_actual.estimacio_pessimista
                exigencia = (pessimista - sense_taper) / pessimista
                if exigencia > params.exigencia_max:
                    avisos.afegir(
                        "objectiu_exigent",
                        f"{etiqueta}: l'objectiu realista demana un {exigencia:.1%} de millora "
                        f"abans del taper des de l'estimació pessimista "
                        f"(màxim raonable {params.exigencia_max:.0%})",
                    )

    for comp in competicions:
        if comp.classe not in ("B", "C") or _data(comp.data_fi) >= avui:
            continue
        for prova in comp.proves:
            if not any(
                r.competicio_id == comp.id and mateixa_prova(r.prova, prova) for r in resultats
            ):
                avisos.afegir(
                    "resultat_pendent",
                    f"{comp.nom} ({comp.data_inici}): falta el resultat de {prova}",
                )
    return avisos.llista
