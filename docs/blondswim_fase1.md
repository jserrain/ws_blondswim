BlondSwim — Fase 1: mòduls deterministes
Objectiu: portar a codi el que ara mateix només existeix a l'Excel i a docs/architecture.md — les fórmules de zones, la lògica de context de competició, i les regles de taper i validació. Cap d'aquests mòduls necessita LLM: són càlculs i regles fixes, per això s'implementen abans dels agents amb Claude (Fase 2).

Abast i ordre
#	Mòdul	Fitxer	Depèn de
1	Zones CSS/marca	src/blondswim/agents/zones_css.py	Nedador (Fase 0)
2	Context de competició	src/blondswim/agents/context_competicio.py	Competicio (Fase 0)
3	Taper	src/blondswim/agents/taper.py	Mòdul 2
4	Validació fisiològica/temporal	src/blondswim/agents/validacio.py	Mesocicle/Microcicle (Fase 0)
Ordre pensat perquè cada mòdul es pugui testar aïllat amb el cas de Jep com a oracle (valors ja validats manualment: A2≈82.09s, Velocitat≈67.55s) abans de dependre del següent.

Mòdul 1 — Zones CSS/marca
make aider
/add src/blondswim/agents/zones_css.py
/add src/blondswim/models/nedador.py
Prompt:

Implementa src/blondswim/agents/zones_css.py amb les funcions de càlcul de 
zones que ara mateix només existeixen com a fórmules a l'Excel (pestanya 
Ritmes). Consulta ParametresRitme, RitmesCSS i MarquesReferencia a 
src/blondswim/models/nedador.py per als noms de camp exactes.

1. calcular_zones_des_de_css(css_pace_100m: float, params: ParametresRitme) 
   -> dict[str, float]
   Retorna {recuperacio, a1, a2, a3, velocitat} en segons per 100m, aplicant 
   els offsets: recuperacio = css_pace_100m + params.offset_recuperacio_css, 
   a1 = css_pace_100m + params.offset_a1_css, a2 = css_pace_100m + 
   params.offset_a2_css, a3 = css_pace_100m + params.offset_a3_css, 
   velocitat = css_pace_100m * params.factor_velocitat.

2. calcular_zones_des_de_marca(marca_100_lliure_seg: float, 
   marca_50_lliure_seg: float, params: ParametresRitme) -> dict[str, float]
   Retorna {recuperacio, a1, a2, a3, velocitat} en segons per 100m: 
   recuperacio = marca_100 * (1 + params.increment_recuperacio), 
   a1 = marca_100 * (1 + params.increment_a1), 
   a2 = marca_100 * (1 + params.increment_a2), 
   a3 = marca_100 * (1 + params.increment_a3), 
   velocitat = marca_50_lliure_seg * params.factor_escala_50_100 
   (MAI marca_100 * factor_velocitat — donaria un ritme més ràpid que el 
   propi rècord, físicament absurd; vegeu docs/metodologia_ritmes.md si 
   necessites el raonament complet).

3. calcular_css_pace(temps_400_seg: float, temps_200_seg: float) -> float
   Fórmula de Wakayoshi: velocitat = (400-200)/(t400-t200); retorna 
   100/velocitat (ritme per 100m en segons). Llança ValueError si 
   temps_400_seg <= temps_200_seg (dada físicament impossible).

4. determinar_zones_nedador(nedador: Nedador) -> RitmesCSS
   Aplica la regla de conciliació: si nedador.ritmes_css i 
   nedador.ritmes_css.data_test existeixen I hi ha temps de test disponibles 
   (assumeix que si font ja és "css_test" al Nedador carregat, s'ha de 
   recalcular amb calcular_zones_des_de_css); altrament, fa servir 
   calcular_zones_des_de_marca amb nedador.marques_referencia. Retorna un 
   RitmesCSS complet amb el camp font correctament assignat.

   Nota: com que el Nedador carregat des del JSON ja pot tenir font i les 
   zones precalculades (vinguin del conversor Excel), aquesta funció ha de 
   poder recalcular-les des de zero donat marques_referencia o un test CSS 
   nou — no limitar-se a llegir el que ja hi ha. Pensa-la com "si tinguéssim 
   dades noves, què tocaria recalcular", no com un simple getter.

Escriu tests a tests/agents/test_zones_css.py que verifiquin, amb les dades 
reals de Jep (marca_100_lliure_seg=77.08, marca_50_lliure_seg=33.44, 
ParametresRitme per defecte): a2 ≈ 82.09 (±0.01) i velocitat ≈ 67.55 (±0.01) 
— aquests dos valors ja els tenim validats manualment i han de coincidir 
exactament. Afegeix també un test de calcular_css_pace amb un cas conegut 
(per exemple t400=330, t200=150 → velocitat=1.111.../s aprox) i un test que 
calcular_css_pace llança ValueError si t400<=t200.
Mòdul 2 — Context de competició
/add src/blondswim/agents/context_competicio.py
/add src/blondswim/models/calendari.py
Prompt:

Implementa src/blondswim/agents/context_competicio.py:

1. setmanes_entre(comp_a: Competicio, comp_b: Competicio) -> int
   Diferència en setmanes senceres entre comp_a.data_inici i 
   comp_b.data_fi (o data_inici, el que sigui més proper — usa data_fi de 
   la primera i data_inici de la segona, assumint comp_a és anterior). 
   Arrodoneix cap avall.

2. detectar_candidats_retaper(competicions: list[Competicio], 
   pics_prioritzats: list[str]) -> list[tuple[Competicio, Competicio, int]]
   Recorre les competicions ordenades per data. Per cada parella 
   consecutiva on la primera és classe "A" (o el seu id és a 
   pics_prioritzats) i la segona (classe "A" O el seu id és a 
   pics_prioritzats) està a <= 4 setmanes de distància (via setmanes_entre), 
   retorna la tripleta (competicio_1, competicio_2, setmanes_distancia). 
   Aquesta és la implementació de la regla 2 del taper que ja tenim 
   documentada a docs/architecture.md — no inventis cap regla nova, 
   només tradueix-la a codi.

3. classificar_pics(competicions: list[Competicio]) -> dict amb claus 
   "classe_a", "classe_b", "classe_c" i com a valor la llista de 
   competicions de cada classe, ordenades per data.

Escriu tests a tests/agents/test_context_competicio.py usant el calendari 
real (data/raw/Provisional26-27.xlsx via convertir_calendari, o el 
calendari.json ja generat — el que sigui més senzill). Verifica que 
detectar_candidats_retaper identifica la parella Catalunya Hivern (16-17 
gen) + Espanya (4-7 feb) — són ~2-3 setmanes de distància — encara que 
Espanya sigui classe B (només detecta si el nedador la té a 
pics_prioritzats; verifica els dos casos: amb i sense el pic prioritzat).
Mòdul 3 — Taper
/add src/blondswim/agents/taper.py
Prompt:

Implementa src/blondswim/agents/taper.py amb calcular_taper() que 
implementa exactament les 3 regles ja documentades a docs/architecture.md:

def calcular_taper(pic_actual: Competicio, pic_anterior: Competicio | None, 
                    nedador: Nedador) -> dict

Retorna {"tipus": "complet" | "retaper" | "cap", "dies": int | None, 
"reduccio_volum_pct": tuple[int, int] | None}

Regla 1 (complet): si pic_actual.classe == "A" i (pic_anterior és None o 
setmanes_entre(pic_anterior, pic_actual) > 6) → dies entre 10-15 (usa 12 
com a valor per defecte), reduccio_volum_pct=(40, 60).

Regla 2 (retaper): si hi ha pic_anterior, setmanes_entre <= 4, pic_anterior 
va tenir taper complet (assumeix que sí si era classe A), i (pic_actual és 
classe A o el seu id és a nedador.pics_prioritzats) → dies entre 5-7 (usa 6 
per defecte), reduccio_volum_pct=(20, 30).

Regla 3 (cap): qualsevol altre cas (classe B/C sense estar prioritzat) → 
tipus="cap", dies=None, reduccio_volum_pct=None.

Reutilitza setmanes_entre() de context_competicio.py, no la reimplementis.

Escriu tests a tests/agents/test_taper.py que verifiquin els 3 casos amb 
dades del calendari real: Catalunya Hivern com a primer pic A de la 
temporada (→ complet), Espanya com a segon pic si Jep la marca prioritzada 
(→ retaper), i Espanya sense marcar-la prioritzada (→ cap).
Mòdul 4 — Validació fisiològica/temporal
/add src/blondswim/agents/validacio.py
/add src/blondswim/models/macrocicle.py
Prompt:

Implementa src/blondswim/agents/validacio.py amb dues funcions:

1. validar_descarrega(microcicles: list[Microcicle]) -> list[str]
   Regla universal ja documentada: no més de 2-3 setmanes de càrrega 
   consecutiva sense setmana de descàrrega. Recorre microcicles en ordre, 
   compta setmanes consecutives amb tipus_base="carrega" (o "qualitat"), i 
   retorna una llista d'avisos (strings) per cada tram de 4+ setmanes 
   consecutives sense un tipus_base="descarrega" entremig. Llista buida si 
   tot és correcte.

2. validar_coherencia_temporal(mesocicles: list[Mesocicle]) -> list[str]
   Verifica que els mesocicles no se solapen en dates i que no hi ha buits 
   (la data_fi d'un mesocicle hauria de ser el dia abans de la data_inici 
   del següent, o com a màxim coincidir). Retorna avisos per a cada 
   incoherència trobada. Nota: dates de Mesocicle són text tipus "21/09 - 
   18/10/2026", no ISO — parseja-les amb el mateix criteri de robustesa que 
   ja fem servir al conversor (no assumeixis format únic).

Escriu tests a tests/agents/test_validacio.py. Per a validar_coherencia_temporal, 
usa el macrocicle real de Jep (data/processed/macrocicle_jep.json) com a 
cas que hauria de passar sense avisos (les 5 mesocicles ja són consecutives 
per disseny). Per a validar_descarrega, crea un microcicle sintètic de 5 
setmanes seguides de "carrega" sense descàrrega i confirma que genera un 
avís.
Tancament de la Fase 1
make test
make lint
Un cop els 4 mòduls tinguin tests en verd i lint net:

git add .
git commit -m "Fase 1: mòduls deterministes (zones CSS, context competició, taper, validació)"
Amb això, totes les regles que fins ara vivien a l'Excel i a la documentació passen a ser codi testejat. La Fase 2 (Selecció de Model i Microcicle, amb LLM) parteix d'aquesta base.