# BlondSwim — Fase 3: Orquestració i sortida

Prerequisit complert: Fase 2 tancada (144 tests, `actualitzar_microcicle()` fet com a composició de 4 primitives — vegeu `fase2.md`). Aquesta fase connecta els mòduls existents en entry points d'ús real: generar contingut per blocs de temporada, i exportar el resultat a un format que el coach pugui llegir fora del codi.

---

## Estat actual (actualitzat 2026-10-01)

**226 tests (sense `ingestion`; 36 més que depenen de `data/raw`), lint net.** Jerarquia de 3 nivells completa. Fetes: Fase A, Fase B+C+D, Etapa 4 (primera setmana real generada), F1, F2, G1, G2, G5, G6, **Fase H** (organització setmanal, pressupost d'intensitat i control de la recuperació) i **Fase H2** (5 dies, biblioteca de tècnica, doble pic). Pendents: test CSS (dissabte 03/10) i recàlcul de zones, re-verificació de l'Etapa 4 amb la Fase H2, **Fase E+I** (càrrega real, SRSS i sessions múltiples — dissenyada 2026-10-01, s'implementa tot alhora), F3-F7 i G3-G4.

**Canvi de flux de treball (2026-09-30):** aider ha fallat repetidament en canvis multi-fitxer (commits només amb tests, blocs SEARCH/REPLACE no aplicats, fitxers corromputs). Per als canvis grans, Claude escriu el codi en un entorn propi amb els tests i lliura **patches `git am`** (un commit per pas); el Jep els aplica i executa `pytest -q && ruff check .`. Aider queda per a canvis petits d'un sol fitxer.

## Pla en curs

- **Fase A** — Classificació A/B a `generar_mesocicle()`. ✅
- **Fase B+C+D** — Model `Exercici`, generació estructurada, exportador. ✅ Etapa 4 feta (vegeu "Etapa 4" més avall).
- **Fase F** — Volum setmanal amb evidència. ✅ F1, F2. Pendents F3-F7.
- **Fase G** — Contingut setmana a setmana. ✅ G1, G2, G5, G6. Pendents G3, G4.
- **Fase H** — Organització setmanal, pressupost d'intensitat i control de la recuperació. ✅
- **Fase H2** — 5 dies, biblioteca de tècnica (64 exercicis, 18 famílies), doble pic d'hivern. ✅ Implementada; pendent test CSS i regenerar la setmana 41 real.
- **Fase E+I** — Càrrega real (sRPE CR-10), benestar (SRSS), sèrie de control, sessions múltiples per dia (natació + gimnàs informatiu) i regla de decisió. Dissenyada; s'implementa en un sol bloc de 7 patches (vegeu secció pròpia). Substitueix l'antiga "Fase E".

---

## Jerarquia de 3 nivells (fet, 2026-09-28)

Validat contra fonts fiables (TrainingPeaks Help Center, article de periodització de TrainingPeaks, estudi de 20 anys sobre 127 nedadors d'elit a Frontiers in Physiology) i contra la convenció pròpia del projecte:

1. **`generar_macrocicle(nedador_id, ...)`** ✅ → macrocicle de tota la temporada, dates fixades per l'usuari (**convenció TrainingPeaks**: el macrocicle és la temporada sencera). Requereix almenys una competició classe A.
2. **`generar_mesocicle(nedador, ...)`** ✅ → periodització (ATP enrere des de la competició A), volums i microcicles del bloc que conté la setmana objectiu. NO genera contingut.
3. **Contingut** ✅ → `generar_contingut_setmana()` (una setmana, ús normal, G1) i `generar_contingut_mesocicle()` (embolcall per setmanes, G5).

**Evidència que valida el disseny**:
- TrainingPeaks: ATP amb dates explícites i almenys una competició A. [How do I set up my ATP? — TrainingPeaks](https://help.trainingpeaks.com/hc/en-us/articles/204073724-How-do-I-set-up-my-Annual-Training-Plan-ATP)
- Mesocicles de 3-6 setmanes, ritme 3+1. [Macrocycle, Mesocycle and Microcycle — TrainingPeaks](https://www.trainingpeaks.com/blog/macrocycles-mesocycles-and-microcycles-understanding-the-3-cycles-of-periodization/) / [Swimming Season Planning — Padlie](https://padlie.com/en/blog/swimming-season-planning)
- 2 pics de càrrega per macrocicle en 127 nedadors d'elit → Build1/Build2. [Frontiers in Physiology](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2019.00363/full)
- Patró 3-5 setmanes + 1 de recuperació. [Training Periodization — TrainingPeaks](https://www.trainingpeaks.com/blog/what-is-training-periodization/)
- Taper: −30-40% la primera setmana, −20% addicional la segona, mantenint la intensitat. [Swim Tapering Guide — Padlie](https://padlie.com/en/blog/tapering-swimming-coach-guide)

---

## `generar_macrocicle()` (fet, 2026-09-28)

```python
def generar_macrocicle(
    nedador_id: str,
    competicions: list[Competicio],
    temporada_data_inici: str,
    temporada_data_fi: str,
) -> tuple[Macrocicle, list[dict]]:
```

`src/blondswim/agents/generar_macrocicle.py`. Reutilitza `context_competicio.validar_espaiat_pics_a()`. `Macrocicle.data_inici`/`data_fi` opcionals per no trencar `convertir_macrocicle_jep()`.

---

## `generar_mesocicle()` — periodització, volums i microcicles

```python
def generar_mesocicle(
    nedador: Nedador,
    macrocicle: Macrocicle,
    competicions: list[Competicio],
    enriquir_amb_llm: bool = True,
    historial: list[SessioRealitzada] | None = None,
    data_referencia: date | None = None,
) -> tuple[Mesocicle, list[dict]]:
```

- **Periodització (ATP enrere des de la A)**: `periodificacio.periodificar_temporada()` calcula tots els `SetmanaPlan` (Cursa, Peak de 2 setmanes, Build2, Build1, Base) en blocs de fins a 4 setmanes, amb descàrrega a l'última setmana de cada bloc. **Un bloc d'1 setmana és de càrrega** (corregit 2026-09-30). Proves B/C s'assignen a la seva setmana (`competicions_b_c`).
- **Inici = proper dilluns (G2, fet 2026-09-30)**: `inici_generacio = seguent_dilluns(data_referencia)`; mai es comença a mitja setmana. `dies_marge` eliminat.
- `Mesocicle.tipus` és el camp determinista; `fase_objectiu` el pot reescriure l'LLM (fallback silenciós).

**Volums (taula per fase, 2026-09-30)** — `VOLUM_SETMANAL_CARREGA`: Base 13.600-15.000, Build1/Build2 12.000-13.600 (interpolació al llarg de les setmanes de càrrega de la fase; **una sola setmana de càrrega → mínim de la fase**). Descàrrega = 0,7 × setmana de càrrega anterior. Peak = 13.000 × [0,60, 0,45] (Bosquet). Cursa/Transició = 13.000 × 0,5. Setmana amb prova B = × 0,8.

**Terra de volum (F2)** — `Nedador.volum_setmanal_min` (12.000 per defecte): cap setmana de càrrega, qualitat o descàrrega per sota. **Excepcions**: taper (Peak/Cursa), transició i setmanes amb prova B (taper B de 3 dies). Si el terra aixeca una descàrrega → avís `descarrega_insuficient` (la descàrrega es fa per intensitat). El guard ACWR mai retalla per sota del terra (ACWR = avís, no regla).

**Setmana posterior a una competició (Fase H)** — objectiu = `volum_setmanal_min` (prioritat recuperació, complint el mínim).

**Classificació de la setmana (Fase H)** — `Microcicle.dia_competicio` ("dissabte"/"diumenge") i `Microcicle.post_competicio` via `pla_setmanal.classificar_setmana()` (només competicions A i B).

---

## Contingut — `generar_contingut_setmana()` / `generar_contingut_mesocicle()`

`src/blondswim/agents/generar_microcicle.py`.

- **G1 (fet)**: `generar_contingut_setmana(nedador, macrocicle, categoria, dilluns, pla_taper, avisos_pics_a, historial=None, metodologia=None) -> (mesocicle, microcicle, sessions, avisos)`. Troba el microcicle pel dilluns (`parsejar_rang_dates`) i genera només aquella setmana.
- **G5 (fet)**: `generar_contingut_mesocicle()` manté la signatura i fa bucle per setmanes; la metodologia es tria un cop (`_seleccionar_metodologia_nedador`).
- **Una crida LLM per sessió**, tool-use forçat (`retornar_contingut_sessio`), `max_tokens=4096`; reintent si `max_tokens` o `parts` buit.
- **Validació i reintent únic (Fase H)**: `_problemes_sessio()` combina volum fora del rang (±10%), pressupost d'intensitat, papallona i regles de natació; si hi ha problemes, un sol reintent amb la llista. Si persisteixen → avís al log.
- **Parts fixes** (`PartSessio.fixa`): no es demanen a l'LLM, no es sobreescriuen i no compten al pressupost.

---

## Exportador Excel

`src/blondswim/export/mesocicle_excel.py`.

- `exportar_mesocicle_excel(nedador, mesocicle, resultats, output_path)` — tot el mesocicle en una pestanya.
- `exportar_setmana_excel(nedador, mesocicle, microcicle, sessions, output_path)` (**G6, fet**) — una pestanya "Setmana N"; és el full per a la piscina. Tots dos comparteixen `_escriure_setmana()` (refactor verificat: cel·les, fonts i amplades idèntiques).
- Capçalera de setmana: `"<Mes(os)> <Any> — Setmana <ISO> (<dates>) — <mesocicle>, Fase <tipus>"`. Capçalera de dia: `"Dilluns 5 — <rol>"` (etiqueta de rol només amb la plantilla setmanal). Una fila per `Exercici`; fila `Total`; `Temps (min)` en blanc (Etapa 3b).
- **Rutina d'espatlla (Fase H)**: si `Nedador.rutina_espatlla_dia` és un dia de descans de la setmana, bloc "Descans a l'aigua. Rutina d'espatlla (opcional, 15 min)" en ordre cronològic.

## Script `scripts/generar_temporada_jep.py`

Per defecte: estructura de la temporada + contingut **només de la setmana del proper dilluns** → `setmana_<nom>_<YYYY>-W<ww>.xlsx`. Opcions: `--dilluns YYYY-MM-DD`, `--mesocicle-sencer` (comportament antic), `--data-referencia`. Avisa si el nedador no fa servir la plantilla setmanal.

**Dades del Jep (`data/processed/nedador_jep.json`, gitignored)**: cal `"dies_disponibles": ["dilluns","dimarts","dijous","divendres"]` i `"rutina_espatlla_dia": "dimecres"`.

---

## Etapa 4 — Primera setmana real (2026-09-30)

Setmana 41 (05-11/10/2026) generada amb crides reals: 4 sessions, cap truncament, cap exercici descartat, 14.300 m (objectiu 13.600, +5%). Format correcte. **Contingut no apte per a Base**, que va motivar la Fase H:

| Zona | m | % |
|---|---|---|
| Recuperació + A1 + A2 | 10.175 | 71% |
| A3 | 1.425 | 10% |
| Velocitat | 1.625 | 11% |
| MPLA + TOLA | 1.075 | 8% |

- Làctic els 4 dies i la mateixa estructura cada dia (causa: esquelet amb "Específic/Qualitat" a totes les sessions i rols sense límit d'intensitat).
- Papallona cada dia (425-1.300 m) i ondulació amb aletes 4 dies (causa probable: `proves_objectiu[0]` usat com a estil preferent).
- Exercicis impossibles o sense sentit: "125 IM", "5x25 A3 llindar", "surar fins a bandera", 25 m de farciment.
- Volums per sessió fora dels rangs acordats (dijous 4.150, dimarts 3.100).
- Cicle massa curt: 5x100 IM A3 a c/1'50" (~8" de descans amb marca de 1'38").

Observacions del calendari: avís `cap_competicio_a_restant` confús (es refereix a les setmanes 23-27 de 2027, després de l'última A); el Mundial de Budapest surt duplicat a la setmana 26; el Campionat d'Espanya d'Hivern (setmana 5) és B dins d'un bloc de Base. **Decisió pendent del Jep: classe del Mundial de Budapest i del Campionat d'Espanya.**

---

## Fase H — Organització setmanal, pressupost d'intensitat i control de la recuperació (acordat i implementat 2026-09-30)

### Decisions del coach (Jep)

1. **1 sol dia de qualitat per setmana**; s'avalua amb tests de seguiment abans d'afegir-ne un segon.
2. **Papallona 300-600 m/setmana**, equilibri entre tècnica i nedar papallona.
3. **4 sessions no consecutives: dilluns, dimarts, dijous, divendres** (mai 3 dies seguits sense nedar).
4. **Competicions**: dissabte o diumenge; els dos dies només en proves A (segons les proves).
5. **Prioritat recuperació**, però **complint sempre el mínim** setmanal; tests per avaluar la recuperació.
6. **Dia abans de competir: activació. Dies de descans: descans total a l'aigua.**
7. **Sèrie de control** 4x100 crol A2 cada dilluns; **rutina d'espatlla** opcional de 15 min el dimecres.

### Plantilla setmanal (`pla_setmanal.rols_setmana`)

| Dia | Normal | Competició dissabte | Competició diumenge | Post-competició |
|---|---|---|---|---|
| Dl | Aeròbic i tècnica + sèrie de control | Aeròbic i tècnica + control | Aeròbic i tècnica + control | **Recuperació activa** (~60% del volum) + control |
| Dt | **Qualitat** | **Qualitat** | **Qualitat** | Aeròbic i tècnica |
| Dc | Descans (rutina d'espatlla) | Descans | Descans | Descans |
| Dj | Tècnica (papallona tècnica) | Tècnica | Tècnica | **Qualitat** |
| Dv | Aeròbica llarga + velocitat alàctica | **Activació** | Descans | Tècnica |
| Ds | Descans | 🏁 | **Activació** | Descans |
| Dg | Descans | Descans | 🏁 | Descans |

Post-competició i competició el mateix cap de setmana: sense dia de qualitat (les curses fan d'estímul intens). Setmana de Cursa (A): mateixa lògica d'activació; la Transició posterior és setmana post-competició.

### Volum i parts per rol

Pesos de volum (`PES_ROL`): aeròbica 1,0 · llarga 1,1 · qualitat 0,95 · tècnica 0,95 · activació 0,5 · recuperació 0,6. Rang de cada sessió = objectiu ± 5%, limitat a `minuts_max_sessio × 40 m/min`. Parts pròpies per rol (`PARTS_ROL`); la sèrie de control (400 m) és una part fixa després de l'escalfament del dilluns, amb cicle = ritme A2 + 15" arrodonit a 5" (Jep: c/1'40").

### Pressupost d'intensitat per sessió (validat en codi)

| Rol / fase | A3+AeM | Velocitat | Làctic (MPLA/TOLA) |
|---|---|---|---|
| Qualitat — Base | ≤ 25% | ≤ 300 m | 0 |
| Qualitat — Build | ≤ 20% | ≤ 300 m | ≤ 400 m |
| Qualitat — Descàrrega | ≤ 10% | ≤ 200 m | 0 |
| Qualitat — Taper | ≤ 15% | ≤ 300 m | ≤ 200 m |
| Qualitat — Transició | 0 | ≤ 100 m | 0 |
| Aeròbica | ≤ 5% | 0 | 0 |
| Llarga | ≤ 5% | ≤ 200 m (alàctic) | 0 |
| Tècnica | 0 | 0 | 0 |
| Activació | 0 | ≤ 150 m (ritme de cursa) | 0 |
| Recuperació | 0 (i A2 = 0) | 0 | 0 |

Papallona per sessió: tècnica ≤ 350, qualitat ≤ 150, la resta ≤ 50, recuperació 0 (setmana ≤ 600 m). Els exercicis d'estils compten el 25% com a papallona. Regles: estils complets de 100/200 m; A3 només en repeticions ≥ 50 m. Al prompt, a més: velocitat amb recuperació completa, cicles coherents amb la zona, sense metres de farciment.

### Indicadors de recuperació (s'implementen a la Fase E+I)

| Indicador | Quan | Alerta |
|---|---|---|
| sRPE (CR-10 × minuts) | Cada sessió (natació i gimnàs) | Càrrega setmanal +15% no planificada |
| Benestar SRSS (8 ítems, 0-6) | Cada dia d'entrenament, abans de la primera sessió | Vegeu Fase E+I (línia base individual) |
| Sèrie de control 4x100 A2 (temps, braçades/llargada, esforç) | Cada setmana (dimecres des de la Fase H2) | Mateix temps amb més esforç o més braçades |
| Test CSS (inici de cada bloc) i temps de proves B | ~4 setmanes | Estancament 2 blocs |

**Regla de decisió**: 2 alertes en una setmana → la setmana següent manté el mínim i la qualitat passa a només velocitat alàctica. 2 blocs sense alertes i CSS millorant → es pot afegir un segon dia de qualitat al Build. (El sistema la **recomana** com a avís; la decisió és del coach.)

### Evidència

- **Freqüència de làctic**: 1 sessió de tolerància/setmana sol ser suficient (en velocistes, a vegades cada 15 dies); 2 només en fases específiques; recuperació completa ≥ 48 h. [British Swimming — A guide to anaerobic training](https://oswestryotters.co.uk/wp-content/uploads/2021/01/Lactate-Tolerance.pdf)
- **Velocistes**: no poden passar llargs períodes sense alta intensitat; polaritzat amb 7-12% de zona alta en un cas; distribució més intensa = hipòtesi no validada. [Papadimitriou et al. 2025 — EJAP](https://www.fisiologiadelejercicio.com/wp-content/uploads/2025/11/Training-intensity-distribution-for-sprinter-swimmers.pdf)
- **Màsters**: recuperació més lenta que els joves (53 vs 27 anys). [Bond University / JSAMS](https://research.bond.edu.au/en/publications/masters-athletes-take-longer-to-recover-from-high-intensity-exerc/). Bloc de volum i després d'intensitat millor que fer sempre el mateix. [Pugliese et al. 2015 — IJSPP](https://pubmed.ncbi.nlm.nih.gov/25710182/)
- **Espatlla**: factors de risc amb evidència = poca força-resistència posterior, càrrega irregular i tècnica deficient (l'estil no). [Swimmer's Shoulder — Springer 2025](https://link.springer.com/article/10.1007/s40141-025-00506-5)
- **Activació 24 h abans**: sessió curta a l'aigua o fora de l'aigua, 50 m crol ~2,5% més ràpid (adolescents entrenats). [Sports 2022](https://www.mdpi.com/2075-4663/10/4/52). Priming amb resistències més eficaç 6-33 h abans. [Science for Sport](https://www.scienceforsport.com/practical-recommendations-for-priming-exercise-when-what-and-how/)
- **Taper**: mantenir intensitat, reduir volum 40-60%, reduir freqüència com a màxim un 20%; càrrega forta 4-5 dies abans de competir. [Baltic J. Health & Physical Activity](https://www.balticsportscience.com/cgi/viewcontent.cgi?article=1221&context=journal) / [Bosquet et al. 2007](https://www.semanticscholar.org/paper/Effects-of-tapering-on-performance:-a-Bosquet-Montpetit/a41517ab5fa06b92568b861e2b1aa32b3003d214)
- **Descans**: cap estratègia de recuperació entre sessions és millor que el descans passiu (la recuperació activa només baixa el lactat). [Sports Medicine – Open 2024](https://link.springer.com/article/10.1186/s40798-024-00724-6). Recuperació post-competició amb ritmes variats elimina més lactat (joves, mateix dia). [JSSM 2023](https://www.jssm.org/researchjssm-22-739.xml.xml)
- **Control de la fatiga**: el qüestionari de Hooper no és vàlid com a únic mètode. [Meta-anàlisi 2025](https://www.medicinadoesporte.org.br/wp-content/uploads/2025/11/Hooper-Questionnaire-in-Training-Load-Control-in-High-Performance-Athletes-Systematic-Review-with-Meta-Analysis.pdf). Els entrenadors d'elit britànics combinen conversa, qüestionari diari i observació de la tècnica. [JSSM 2019](https://www.jssm.org/jssm-18-577.xml%3EFulltext)

**Limitacions**: l'activació i la recuperació post-competició s'han estudiat en joves; els pressupostos d'intensitat són decisions del coach coherents amb l'evidència, no xifres validades per a màsters. Es calibren amb els indicadors de recuperació.

---

## Fase E+I — Càrrega real, benestar i sessions múltiples (dissenyat 2026-10-01, no implementat)

Fusiona l'antiga **Fase E** (càrrega real i KPI per sessió, dissenyada 2026-09-29/30) amb la nova **Fase I** (fins a 3 sessions per dia). S'implementen alhora perquè comparteixen el model (`SessioRealitzada`, càrrega diària) i la regla de decisió de la Fase H.

### Decisions del coach (Jep, 2026-10-01)

1. **Màxim 3 sessions per dia**, en franges `matí` / `migdia` / `tarda` (una sessió per franja). La fitxa del nedador defineix la setmana tipus: per a cada dia, quines franges tenen sessió i de quina modalitat (exemple: Dilluns → matí natació, migdia res, tarda gimnàs).
2. **Esforç: sRPE amb escala CR-10 de Foster i etiquetes verbals en català** (no l'escala de 5 nivells "cap/poc/mig/alt/molt alt": no és validada ni sumable). Es guarda el número; la interfície mostra l'etiqueta.
3. **Gimnàs només informatiu**: es planifica (franja + durada) i es registra (minuts + RPE), compta a la **càrrega** (sRPE) però **no** al volum en metres, i l'LLM no en genera contingut.
4. **Benestar: SRSS** (Short Recovery and Stress Scale, Kellmann et al.), un cop al dia abans de la primera sessió. Substitueix el qüestionari propi de 4 ítems.

### Com ho fa TrainingPeaks (referència)

- La unitat és el workout; el PMC suma el TSS de tots els workouts del dia en un sol punt diari, i ATL/CTL són mitjanes exponencials de 7 i 42 dies del TSS diari. [PMC — TrainingPeaks](https://www.trainingpeaks.com/learn/articles/what-is-the-performance-management-chart/) / [Fitness (CTL) — TP Help](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL)
- Sense sensors, TP estima el TSS amb durada × RPE; per al gimnàs, proposa RPE (+ tonatge). [Estimating TSS — TP](https://www.trainingpeaks.com/learn/articles/estimating-training-stress-score-tss/) / [Strength TSS — TP](https://www.trainingpeaks.com/blog/cycling-strength-training-tss/)
- **Adaptació a BlondSwim**: mateix patró (sessió → suma diària → mitjanes mòbils) però amb sRPE, que, a diferència del TSS de natació, és comú a aigua i gimnàs.

### Evidència

- **sRPE en natació**: correlaciona amb mesures de FC (r = 0,55-0,94) i volum (r = 0,37-0,81). [Wallace et al. 2009 — JSCR](https://journals.lww.com/nsca-jscr/fulltext/2009/01000/the_ecological_validity_and_application_of_the.6.aspx)
- **sRPE en gimnàs**: viable i comparable a l'aeròbic. [Sweet et al. 2004](https://pubmed.ncbi.nlm.nih.gov/15574104/); [Day et al. 2004](http://formacion.ferugby.es/wp-content/uploads/2019/04/Monitoring-Exercise-Intensity-During-Resistance-Training_RPE.pdf); revisió: [Haddad et al. 2017](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2017.00612/full)
- **Moment del registre**: dissenyat per a ~30 min després, però robust d'1 min a 14 dies → es poden registrar totes les sessions del dia al vespre. [Revisió sRPE](https://www.researchgate.net/publication/397204895_Can_young_swimmers_guide_their_pace_through_the_rating_of_perceived_exertion)
- **sRPE vs ACWR en nedadors d'elit**: l'sRPE, no l'ACWR, s'associa amb el rendiment abans de competir. [JHK 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC13112164/)
- **Subjectiu > objectiu**: les mesures autoinformades responen millor a la càrrega aguda i crònica que les objectives (revisió de 56 estudis). [Saw et al. 2016 — BJSM](https://doi.org/10.1136/bjsports-2015-094758)
- **SRSS**: 8 ítems, apta per a ús diari, validada en alemany, anglès i neerlandès. [Kellmann et al. — EJSS 2017](https://www.tandfonline.com/doi/abs/10.1080/17461391.2017.1318180) / [Brink et al. 2024](https://www.tandfonline.com/doi/full/10.1080/02640414.2024.2325783). Recomanada com a part d'un seguiment multidimensional, no sola. [Convergent validity — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9797012/). Per a natació: sRPE + escales de recuperació-estrès, amb **línia base individual**. [Frontiers in Physiology 2018](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2018.00845/full)
- **Separació natació/gimnàs**: ≥ 6 h per minimitzar la interferència; ≥ 3 h si la resistència va primer; la natació interfereix menys que la cursa. [Sports 2024 — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11359207/) / [Frontiers 2025](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1692399/full)

**Limitacions**: la traducció catalana de la SRSS i de les etiquetes CR-10 és pròpia (no validada); els llindars d'alerta són provisionals i es calibren amb 3-4 setmanes de dades reals del Jep.

### Escala CR-10 (etiquetes)

| Valor | Etiqueta |
|---|---|
| 0 | Descans |
| 1 | Molt, molt suau |
| 2 | Suau |
| 3 | Moderat |
| 4 | Una mica dur |
| 5 | Dur |
| 6 | (dur+) |
| 7 | Molt dur |
| 8-9 | (molt dur+) |
| 10 | Màxim |

### SRSS (0 = gens, 6 = totalment)

- **Escala de recuperació**: capacitat de rendiment físic, capacitat de rendiment mental, equilibri emocional, recuperació global.
- **Escala d'estrès**: estrès muscular, manca d'activació, estat emocional negatiu, estrès global.
- Puntuació: mitjana de recuperació i mitjana d'estrès (es guarden els 8 ítems).

### Model de dades

```python
Franja = Literal["mati", "migdia", "tarda"]
Modalitat = Literal["natacio", "gimnas", "altres"]

class SlotSessio(BaseModel):
    franja: Franja
    modalitat: Modalitat
    durada_min: int | None = None   # obligatori per a gimnàs
    opcional: bool = False

class Nedador(BaseModel):
    ...
    setmana_tipus: dict[str, list[SlotSessio]] | None = None
    # validació: ≤ 3 slots/dia, franges úniques
    # si és None → es deriva de dies_disponibles (1 slot de natació, franja "tarda")
    # dies_disponibles passa a ser derivable (dies amb algun slot de natació)

class Sessio(BaseModel):
    ...
    franja: Franja = "tarda"
    modalitat: Modalitat = "natacio"
    durada_min: int | None = None   # gimnàs informatiu

class SessioRealitzada(BaseModel):
    ...
    franja: Franja = "tarda"
    modalitat: Modalitat = "natacio"
    minuts: int | None = None
    rpe_sessio: int | None = None   # 0-10, CR-10
    assoliment: int | None = None   # 1-5, independent de l'RPE
    @property
    def carrega(self) -> int | None: ...   # rpe_sessio × minuts

class RegistreSRSS(BaseModel):
    nedador_id: str
    data: date
    recuperacio: tuple[int, int, int, int]   # 0-6
    estres: tuple[int, int, int, int]        # 0-6

class RegistreSerieControl(BaseModel):
    nedador_id: str
    data: date
    temps_100: list[float]          # 4 valors, segons
    bracades_llargada: list[int] | None = None
    rpe: int | None = None          # CR-10
```

Tots els camps nous tenen valors per defecte → `historial_jep.json` i els nedadors existents (Lou, Cris, Pere) no es trenquen.

### Regles

- **Planificació**: les sessions de natació segueixen la plantilla de la Fase H2 (rols, pesos, volum). Els slots de gimnàs s'afegeixen com a `Sessio` informativa (`modalitat="gimnas"`, sense parts ni crida LLM).
- **Separació** (franges com a aproximació d'hores): natació de **qualitat** i gimnàs en franges consecutives (matí-migdia o migdia-tarda) → avís `separacio_insuficient`; matí-tarda → OK. Criteri del coach configurable: gimnàs el mateix dia que la qualitat ("dies durs, durs"), mai el dia de tècnica en estat fresc ni el dia d'activació → avís si no es compleix.
- **Càrrega**: `carrega_dia = Σ carrega` de totes les sessions (aigua + gimnàs); `carrega_setmana`; mitjanes exponencials 7 i 28 dies (anàlegs a ATL/CTL; temps 28 en lloc de 42 per la durada dels blocs). **Alerta**: càrrega setmanal > 1,15 × mitjana de les 4 setmanes anteriors (excloent descàrrega, taper i transició) sense que el pla ho prevegi.
- **SRSS (línia base individual)**: mitjana i DE de les últimes 28 dades (mínim 10 per activar alertes). **Alerta**: recuperació mitjana < línia base − 1 DE, o estrès mitjà > línia base + 1 DE, **2 dies seguits**. Substitueix la regla "2 punts pitjor" de la Fase H (pensada per a una escala 1-5).
- **Sèrie de control**: alerta si el temps mitjà és igual (±1") a la referència i l'RPE o les braçades/llargada pugen (≥ +1 RPE o ≥ +1 braçada).
- **Regla de decisió (Fase H)**: ≥ 2 alertes en una setmana → avís `recomanacio_setmana_seguent` (mantenir mínim, qualitat només alàctica). Mai s'aplica sola.

### Passos d'implementació (patches `git am`, un commit per pas)

1. **E+I-1 Models**: `Franja`, `Modalitat`, `SlotSessio`, `Nedador.setmana_tipus` (+ validació i derivació), camps nous a `Sessio` i `SessioRealitzada`, `RegistreSRSS`, `RegistreSerieControl`. Tests de compatibilitat amb JSON existents.
2. **E+I-2 Esquelet per slots**: `pla_setmanal`/`generar_esquelet_sessions()` iteren slots; gimnàs = `Sessio` informativa; volum en metres només a natació; `generar_contingut_setmana()` salta les sessions que no són de natació.
3. **E+I-3 Validació de la setmana**: separació de franges i regles de col·locació del gimnàs (`validacio.py`).
4. **E+I-4 Càrrega**: `carrega_diaria()`, `carrega_setmanal()`, mitjanes 7/28, alerta +15% (`agents/carrega.py`).
5. **E+I-5 Indicadors i regla de decisió**: alertes SRSS (línia base), sèrie de control, recompte setmanal i `recomanacio_setmana_seguent` (`agents/recuperacio.py`).
6. **E+I-6 Exportador i plantilla de registre**: capçalera `"Dilluns 5 — matí — <rol>"`, fila informativa de gimnàs; nou `exportar_registre_setmana()` (Excel amb RPE/minuts/assoliment per sessió, SRSS diària i sèrie de control) i la seva ingestió (`convertir_registre_setmana()` → `SessioRealitzada`, `RegistreSRSS`, `RegistreSerieControl`).
7. **E+I-7 Integració**: `generar_mesocicle()` rep la càrrega real i n'emet avisos (ACWR de càrrega com a avís, mai com a regla); `scripts/generar_temporada_jep.py` genera el full de registre al costat del full de la piscina.

---

## Volum setmanal — criteris amb evidència (acordat 2026-09-30)

**Context del Jep**: A = 100 crol i 100 estils; B = alguna prova de 200 crol; 4 dies/setmana sense dia opcional; sessió màxima 1:30-1:45 h; sense molèsties d'espatlla; **12.000 m/setmana = mínim normal** (no aplica a taper ni transició).

**Evidència (resum)**: no hi ha criteri científic de volum absolut; la distribució per zones pesa més que els metres ([Nugent et al. 2017](https://pubmed.ncbi.nlm.nih.gov/27465628/); [Kilen et al.](https://onlinelibrary.wiley.com/doi/10.1080/17461391.2015.1028466)); en màsters, bloc de volum → bloc d'intensitat ([IJSPP 2015](https://pubmed.ncbi.nlm.nih.gov/25710182/)); l'edat i el volum prediuen el rendiment màster ([Lapierre et al. 2018](https://pubmed.ncbi.nlm.nih.gov/30130814/); [Zamparo et al. 2012](https://link.springer.com/article/10.1007/s00421-012-2376-y)); lesió associada a càrrega aguda i ACWR alts, però ACWR qüestionat → avís, no regla ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9205558/); [Impellizzeri et al. 2020](https://www.researchgate.net/publication/341936245_AcuteChronic_Workload_Ratio_Conceptual_Issues_and_Fundamental_Pitfalls)); taper de 2 setmanes amb −41-60% de volum ([Bosquet et al. 2007](https://www.semanticscholar.org/paper/Effects-of-tapering-on-performance:-a-Bosquet-Montpetit/a41517ab5fa06b92568b861e2b1aa32b3003d214)).

**Dades històriques** (`Provisional26-27.xlsx`, planificat 25-26, 5 dies): 2.800 m/sessió de mitjana (p25-p75 2.700-2.900), ~62 min/sessió, ~45 m/min, 13.930 m/setmana.

**Rangs per tipus de setmana (4 dies)**: càrrega 13.600-15.000 · qualitat 12.000-13.600 · descàrrega 12.000-12.400 · taper A setmana 1: 8.400-9.800 · taper A setmana 2: 5.600-8.200 · taper B: 10.400-12.000. Provisionals: recalibrar amb F3.

### Millores (Fase F)

- **F1** ✅ `Nedador.volum_setmanal_min=12000`, `minuts_max_sessio=105`, `dia_opcional=None`; taula `VOLUM_SETMANAL_CARREGA` ajustada.
- **F2** ✅ Terra de volum i avís `descarrega_insuficient` (vegeu `generar_mesocicle()`).
- **F3** Base de volum mòbil (EWMA 4-6 setmanes realitzades, excloent descàrrega/taper/transició). Pendent (pot reutilitzar les mitjanes de E+I-4).
- **F4** Taper exponencial alineat amb Bosquet sobre el volum mitjà de Build2. Pendent.
- **F5** Avís de salt agut de volum a `validacio.py`. Pendent.
- **F6** Distribució d'intensitat: **avançada per la Fase H a nivell de sessió** (pressupost per rol). Pendent: control agregat per mesocicle.
- **F7** Cota de volum per temps de sessió: aproximada a la Fase H (40 m/min); l'exacta depèn de l'Etapa 3b.

---

## Fase G — Contingut setmana a setmana (acordat 2026-09-30)

Estructura de temporada sencera (determinista), contingut LLM setmana a setmana: menys crides malgastades amb el pla dinàmic, setmanes sempre dilluns-diumenge i adaptació a dades reals.

- **G1** ✅ `generar_contingut_setmana()`.
- **G2** ✅ Inici al proper dilluns (`utils/dates.py`: `dilluns_setmana`, `seguent_dilluns`, `parsejar_rang_dates`; corregit el parseig de setmanes que creuen d'any, p.ex. `28/12-03/01/2027`).
- **G3** Context de continuïtat al prompt (setmana anterior, posició dins el mesocicle, dades reals). Pendent (les dades reals arriben amb E+I).
- **G4** Previsualització N+1 com a esborrany. Pendent.
- **G5** ✅ `generar_contingut_mesocicle()` com a embolcall per setmanes.
- **G6** ✅ `exportar_setmana_excel()` i script per setmana.

---

## Pendent (no bloquejant)

1. Pendents heretats de Fase 2: revertir `tipus_base` obsolet després d'`eliminar_competicio()`; cablejat opcional de `guardar_log_ajust()`.
2. **Model configurable com a "judge"** (`BLONDSWIM_LLM_PROVIDER`, client compatible OpenAI). No implementat.
3. **Temps (min) per exercici** (Etapa 3b): ritme per zona + parseig de `descans`. Prerequisit exacte de F7.
4. **Missatge de `cap_competicio_a_restant`**: indicar a partir de quina setmana s'aplica.
5. **Esquelet antic** (dies diferents de la plantilla): es manté per a Lou, Cris i Pere fins que tinguin plantilla pròpia.
6. **Contingut de gimnàs generat** (fora d'abast de E+I; ara és informatiu).

## Pendent general

- Fase 4: validació golden-reference — la temporada 25-26 real no serveix com a referència de periodització; cal un altre criteri (candidat: els indicadors de recuperació i rendiment de la Fase H, alimentats per E+I).
- Fase 5: extensió a Lou (CSS real), Cris i Pere (RPE fins al primer test).

---

## Fase H2 — 5 dies, biblioteca de tècnica i doble pic (acordat i implementat 2026-10-01)

### Decisions del coach (Jep)

1. **5 sessions (dilluns a divendres).** Dimecres = **tècnica en estat fresc**, volum baix (~2.000 m), Recuperació/A1, sense qualitat. Les altres sessions baixen ~15% (volum setmanal igual). Cap de setmana sense nedar.
2. **Sèrie de control 4x100 A2 a dimecres** (sense la fatiga de la qualitat de dimarts). **Rutina d'espatlla a dissabte** (no surt si hi ha competició aquell dia).
3. **Catalunya (16-17/01/2027) i Espanya (06-07/02/2027) d'hivern, totes dues A**, una prova per dia.
4. **50 papallona continua sent prova objectiu.** Límit de papallona 300-600 m/setmana; el dofí de cames no hi compta.
5. **Cames de tots els estils** (amb taula, sense taula i amb aletes) a les sessions aeròbiques, llargues, de tècnica i de recuperació.
6. Material disponible: tot (paletes de puny, tub frontal, bastó, aletes, taula).

### Plantilla setmanal (5 dies)

| Dia | Normal | Competició dissabte | Competició diumenge | Post-competició |
|---|---|---|---|---|
| Dl | Aeròbic + cames | Aeròbic | Aeròbic | Recuperació activa |
| Dt | **Qualitat** | **Qualitat** | **Qualitat** | Aeròbic |
| Dc | Tècnica + sèrie de control | Tècnica + control | Tècnica + control | Tècnica + control |
| Dj | Aeròbic + tècnica de crol | Aeròbic | Aeròbic | **Qualitat** |
| Dv | Aeròbica llarga + velocitat alàctica | **Activació** | Descans | Aeròbica llarga |
| Ds | Rutina d'espatlla | 🏁 | **Activació** | Rutina d'espatlla |

Pesos de volum: aeròbica 1,0 · llarga 1,05 · qualitat 0,95 · tècnica 0,65 · recuperació 0,6 · activació 0,5. Base 13.600 m → ~2.925 / 2.800 / 1.900 / 2.925 / 3.075.

**Evidència**: practicar cansat empitjora l'execució però poc l'aprenentatge (Lee & Genovese 1988, [revisió](https://www.krigolsonteaching.com/uploads/4/3/8/4/43848243/massedversusdistributedpracticewhichisbetter.pdf)) → la tècnica, en un dia fresc. La recuperació activa no supera el descans passiu ([Sports Med – Open 2024](https://link.springer.com/article/10.1186/s40798-024-00724-6)) → el dia es justifica per la tècnica, no per la recuperació. El factor de risc d'espatlla és la càrrega irregular ([Springer 2025](https://link.springer.com/article/10.1007/s40141-025-00506-5)). La temporada 25-26 el Jep ja va fer 5 dies (2.800 m/sessió).

### Biblioteca de tècnica

`src/blondswim/tecnica/biblioteca_tecnica.json` + `agents/tecnica.py`. **64 exercicis en 18 famílies** (41 de la v0 + 23 de federacions i entrenadors d'elit), cadascun amb format exercici → nedar, consigna, indicador, material, proves, fases, nivell (Base/Intermedi/Refinament), restriccions i font. Revisió del coach pendent (`Biblioteca_tecnica_v1_families.xlsx`); document de suport: «Exercicis de tècnica recomanats per prova».

**Selector determinista**: famílies per rol (`FAMILIES_ROL`), puntuació = proves objectiu cobertes + 2 si és a `Nedador.prioritats_tecniques`; 3 famílies a la tècnica, 2 a aeròbica/llarga/qualitat, 1 a activació/recuperació. La família es manté al bloc (rotació per número de mesocicle) i la variant canvia cada setmana segons la fase (Base → Build → Peak). L'LLM rep els exercicis amb `id_biblioteca` i només en decideix la dosi; si en falta algun, reintent.

**Què decideix el resultat**: 100 crol = nedar 63%, viratges ~20%, sortida ~12% ([Sci Rep 2025](https://www.nature.com/articles/s41598-025-02814-1)); 100 estils = viratges i canvis d'estil 45-50% ([JSSM 2022](https://www.jssm.org/jssm-21-233.xml%3EFulltext)); la transferència dels exercicis depèn del nedador ([VU 2021](https://vuir.vu.edu.au/42163/)); 7 setmanes d'ondulació subaquàtica → -8% en 10 m ([Ruiz-Navarro 2021](https://blogs.ugr.es/aquaticslab/en/the-effects-of-training-in-underwater-undulatory-swimming/)); cames sense taula +9,5-14% de força ([NMU](https://commons.nmu.edu/cgi/viewcontent.cgi?article=1026&context=facwork_conferencepapers)); en màsters la variabilitat del ritme es dispara als 52 anys ([JFMK 2026](https://www.mdpi.com/2411-5142/11/1/78)).

### Doble pic (dues A a <= 4 setmanes)

Un sol període competitiu: taper principal (Peak de 2 setmanes) abans de la primera, **sense Transició** entre elles, setmanes entremig = Build2 (amb plantilla post-competició i mínim de 12.000 m), **Peak d'1 setmana** abans de la segona, Transició després. Es detecta per dates encara que la primera ja hagi passat. Avís `doble_pic` (substitueix «tractar la segona com a B»).

Hivern 2026-27: Peak 53-1 · Cursa Catalunya (2) · Build2 (3) · Peak (4) · Cursa Espanya (5) · Transició (6).

**Evidència**: TrainingPeaks/Friel planifiquen per a proves de resistència llargues (TSS > 150; doble pic a 8-12 setmanes); en natació de 100-200 m un dia de competició és ~40-50 TSS ([TrainingPeaks](https://www.trainingpeaks.com/learn/articles/calculating-swimming-tss-score/)). En natació: 2-3 macrocicles per temporada i taper de 8-21 dies ([Hermosilla et al. 2021](https://www.mdpi.com/1660-4601/18/12/6474)); tapers de 7-21 dies als entrenadors nacionals ([Cano-Cuartero et al. 2025](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1642020/full)); la forma es manté entre competicions properes amb intensitat i poc volum ([Swimming Science Bulletin](https://coachsci.sdsu.edu/swim/bullets/taper6.htm)).

### Zones de ritme (problema detectat)

Les zones de `Ritmes_Jep.xlsx` (A2 1'22", A3 1'18") són més ràpides que el ritme de la millor marca de 200 m (1'31,5"/100); el Jep manté ~1'40"/100 entrenant. **Test CSS dissabte 03/10/2026** (400 + 200 m, repartint l'esforç: cada 100 com a molt 2" més ràpid que la mitjana); CSS/100 = (T400 − T200) / 2; zones = CSS + offsets (A2 = CSS, A3 = CSS − 4", A1 = CSS + 6", Recuperació = CSS + 12").

### Dades del Jep (`nedador_jep.json`)

`dies_disponibles`: dilluns-divendres · `rutina_espatlla_dia`: "dissabte" · `proves_objectiu`: 100m lliure, 100m estils, 200m lliure, 50m papallona · `prioritats_tecniques`: "Ritme de cursa", "Viratges", "Coordinació de braça". Amb E+I s'hi afegirà `setmana_tipus` (franges i gimnàs).