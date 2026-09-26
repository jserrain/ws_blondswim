BlondSwim — Fase 1: Mòduls deterministes

Estat: Mòdul 1 implementat i testat (zones_css.py, 12 tests, part del total de 34). Mòduls 2 i 3 revisats segons la metodologia TrainingPeaks/Joe Friel (document compartit 2026-09-26) — pendents d'implementació. Mòdul 4 no iniciat.

Mòdul 1 — zones_css.py ✅ Fet

Funcions: calcular_zones_des_de_marca, calcular_zones_des_de_css, calcular_css_pace, determinar_zones_nedador.

12 tests, inclosos test_zones_jep_validacio_manual, test_velocitat_no_supera_marca_100 (guarda contra el bug físic on Velocitat sortia més ràpida que el PB de 100m), test_prioritat_css_test, test_fallback_marques.

Commits: 8b1c00f, 6c3d842.

Mòdul 2 — context_competicio.py (revisat)
Per què es revisa

El document TrainingPeaks/Joe Friel confirma retrospectivament una decisió ja presa: Espanya (4-7 feb), a ~3 setmanes de Catalunya Hivern, és classe B i no A — exactament el "conflict management" que descriu el document (dues A massa properes → la segona es tracta de facto com a B). No calia canviar-ho, però ara tenim la justificació metodològica explícita.

El que sí falta és una validació explícita d'aquesta regla, que ara mateix no es comprova enlloc al codi.

Canvi 1 — Validació de separació entre pics A

Regles quantitatives del document:

Màxim 1-3 competicions classe A per temporada.
Mínim 8-12 setmanes de separació entre A consecutives (12-16 setmanes per a esports de resistència llarga — natació d'aigües obertes inclosa, si aplica).
Si dues A cauen més a prop del mínim, la segona s'ha de tractar de facto com a B (flag, no reclassificació automàtica silenciosa — l'entrenador decideix).
Funcions del mòdul
python
def setmanes_entre(comp_a: Competicio, comp_b: Competicio) -> float:
    """Setmanes entre data_fi de comp_a i data_inici de comp_b (pot ser negatiu si se solapen)."""

def validar_espaiat_pics_a(
    competicions: list[Competicio],
    min_setmanes: int = 8,
    max_setmanes: int = 12,
) -> list[dict]:
    """
    Filtra les competicions classe A, les ordena per data, i comprova
    la separació entre A consecutives.

    Retorna una llista d'avisos (dict amb: comp_a_id, comp_b_id,
    setmanes_separacio, tipus_avis) per a cada parell d'A consecutives
    que no compleix min_setmanes <= separacio.

    tipus_avis:
      - "separacio_insuficient": setmanes_separacio < min_setmanes
        → recomanació: tractar la segona com a B de facto.
      - "massa_pics_a": si el total de competicions classe A > 3
        → recomanació: revisar prioritats amb el nedador/entrenador.

    No llança excepció — retorna avisos perquè la decisió final és de
    l'entrenador, no automàtica. Llista buida = tot correcte.
    """

def detectar_candidats_retaper(
    competicions: list[Competicio],
    pics_prioritzats: list[str],
    finestra_setmanes: int = 4,
) -> list[dict]:
    """
    (Sense canvis respecte al disseny original.)
    Detecta parelles de competicions dins de `finestra_setmanes` on la
    segona és candidata a re-taper — típicament una A seguida de prop
    per una B marcada com a pic_prioritzat pel nedador.
    """

def classificar_pics(competicions: list[Competicio]) -> dict:
    """
    (Sense canvis respecte al disseny original.)
    Retorna un resum per nedador: quines competicions són A/B/C,
    quines estan marcades com a pic_prioritzat, i quines han generat
    avisos de validar_espaiat_pics_a.
    """
Prompt aider per al Mòdul 2
Implementa src/blondswim/agents/context_competicio.py amb les funcions
setmanes_entre, validar_espaiat_pics_a, detectar_candidats_retaper i
classificar_pics, seguint exactament les signatures i docstrings
d'aquest document (docs del projecte Neda'm, secció "Mòdul 2").

Casos reals a validar amb tests:
- Catalunya Hivern (16-17 gen 2027, classe A) i Catalunya Estiu
  (29-30 maig 2027, classe A): separació ~19 setmanes → sense avís.
- Catalunya Hivern (A) i Espanya (4-7 feb, classe B): NO forma part
  d'aquesta validació perquè Espanya ja és classe B als dades d'origen
  (Provisional26-27.xlsx) — la funció valida només parells A-A.
- Si es reclassifiqués Espanya com a A (cas de test sintètic, no real),
  separacio_setmanes respecte a Catalunya Hivern és ~3 setmanes →
  ha de generar avís "separacio_insuficient" (min_setmanes=8 per
  defecte).

Escriu tests a tests/agents/test_context_competicio.py cobrint:
- setmanes_entre amb dates reals del calendari.
- validar_espaiat_pics_a amb el calendari real (0 avisos esperats,
  ja que només hi ha 2 classe A ben separades) i amb un calendari
  sintètic amb 2 A properes (ha de generar avís).
- validar_espaiat_pics_a amb >3 competicions classe A (avís
  "massa_pics_a").
- detectar_candidats_retaper i classificar_pics amb el cas real
  (Catalunya Hivern + Espanya properes, Espanya no marcada com a
  pic_prioritzat per defecte).

No llancis excepcions per avisos — són warnings informatius perquè
l'entrenador decideixi, no errors bloquejants.
Mòdul 3 — taper.py (revisat)
Per què es revisa

El disseny original tenia 3 regles, però la Regla 3 ("B/C sense prioritzar → cap taper") era massa simplista i no reflectia la pràctica estàndard de periodització:

Abans: només les competicions B marcades com a pic_prioritzat rebien algun tipus d'ajust pre-competició; la resta (B no prioritzades, totes les C) no rebien res.
Ara (TrainingPeaks/Friel): totes les B reben un micro-taper lleuger, siguin o no prioritzades — només les C van sense cap ajust pre-competició. A més, falta la recuperació post-competició obligatòria, que no existia enlloc al disseny original.
Regles de taper i recuperació (definitives)
Classe	Taper pre-competició	Recuperació post-competició
A	Progressiu, 7-21 dies (durada exacta segons volum/intensitat de la fase prèvia i judici de l'entrenador)	1-3 setmanes
B	Lleuger, 2-4 dies — s'aplica a totes les B, prioritzades o no	2-5 dies, activa
C	Cap ajust	1-2 dies, estàndard
Regla de re-taper (sense canvis)

Si una competició B està marcada com a pic_prioritzat i cau dins la finestra de re-taper (≤4 setmanes) després d'una A, s'activa sempre un re-taper (bloc dedicat de descàrrega + afinat), amb la càrrega de la setmana de re-càrrega determinada per checkpoint subjectiu (son, DOMS, motivació, RPE) 4-5 dies post-pic A — no pel resultat d'un test objectiu únicament.

Funcions del mòdul
python
def calcular_taper(competicio: Competicio) -> dict:
    """
    Retorna {dies_taper_pre: int, tipus_taper: str, dies_recuperacio_post: int,
    tipus_recuperacio: str} segons la classe de la competició:

      - classe A: dies_taper_pre=14 (punt mig del rang 7-21, ajustable),
        tipus_taper="progressiu", dies_recuperacio_post=14
        (punt mig de 1-3 setmanes), tipus_recuperacio="activa_llarga".
      - classe B: dies_taper_pre=3 (punt mig de 2-4), tipus_taper="lleuger",
        dies_recuperacio_post=3 (punt mig de 2-5), tipus_recuperacio="activa".
      - classe C: dies_taper_pre=0, tipus_taper="cap",
        dies_recuperacio_post=1, tipus_recuperacio="estandard".

    Els valors numèrics per defecte són el punt mig de cada rang;
    ha de ser possible sobreescriure'ls (paràmetres opcionals) perquè
    l'entrenador ajusti segons el cas concret.
    """

def detectar_retaper(
    competicio_a: Competicio,
    competicio_b: Competicio,
    pics_prioritzats: list[str],
    finestra_setmanes: int = 4,
) -> bool:
    """
    (Sense canvis respecte al disseny original.)
    True si competicio_b és pic_prioritzat, ve després de competicio_a
    (classe A), i la separació és <= finestra_setmanes.
    """

def generar_pla_taper_temporada(
    competicions: list[Competicio],
    pics_prioritzats: list[str],
) -> list[dict]:
    """
    Aplica calcular_taper a cada competició de la temporada i afegeix
    el flag de re-taper quan detectar_retaper ho indiqui. Retorna una
    llista ordenada per data amb el pla complet de taper/recuperació
    de tota la temporada per a un nedador.
    """
Prompt aider per al Mòdul 3
Implementa src/blondswim/agents/taper.py amb les funcions calcular_taper,
detectar_retaper i generar_pla_taper_temporada, seguint exactament les
signatures, docstrings i la taula de regles d'aquest document (docs del
projecte Neda'm, secció "Mòdul 3").

Punt important: calcular_taper ha d'aplicar el mateix taper lleuger
(2-4 dies) a TOTES les competicions classe B, independentment de si
estan marcades com a pic_prioritzat — això corregeix un disseny previ
on només les B prioritzades rebien algun ajust. La distinció
pic_prioritzat només afecta detectar_retaper (si activa un re-taper
dedicat després d'una A propera), no si una B rep o no el seu taper
lleuger estàndard.

Casos reals a testar amb tests/agents/test_taper.py:
- Catalunya Hivern (A, 16-17 gen 2027): taper progressiu ~14 dies,
  recuperació activa_llarga ~14 dies.
- Espanya (B, 4-7 feb 2027): taper lleuger ~3 dies (encara que no
  estigui marcada com a pic_prioritzat), recuperació activa ~3 dies.
- Si Espanya estigués marcada com a pic_prioritzat per un nedador
  concret: detectar_retaper ha de tornar True (separació ~3 setmanes
  respecte a Catalunya Hivern, dins la finestra de 4).
- Una competició classe C qualsevol del calendari real: dies_taper_pre=0,
  dies_recuperacio_post=1.
- generar_pla_taper_temporada amb el calendari complet real (17
  competicions): ha de retornar 17 entrades ordenades per data,
  cadascuna amb el seu taper/recuperació segons classe.
Mòdul 4 — validacio.py (no iniciat)

Pendent de disseny detallat. Ha d'incloure com a mínim:

Coherència temporal: cap microcicle sense descàrrega durant més de 2-3 setmanes seguides.
Coherència fisiològica: volums i intensitats dins de rangs raonables per categoria/edat del nedador.
Coherència amb els avisos generats pel Mòdul 2 (validar_espaiat_pics_a) i el pla del Mòdul 3.

Es dissenyarà un cop implementats i validats els Mòduls 2 i 3.

Pendent general
Implementar Mòduls 2 i 3 amb aider (prompts d'aquest document).
Dissenyar i implementar Mòdul 4.
Un cop tinguis el resultat del test CSS (aquest dijous) i el calendari amb totes les B/C confirmades, es podrà demanar la planificació completa del mesocicle — això correspon a la Fase 2 (Agent de Selecció de Model + Agent de Microcicle), que depèn de tenir els Mòduls 2-4 tancats.