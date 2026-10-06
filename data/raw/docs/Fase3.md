# BlondSwim — Fase 3: Orquestració i sortida

Prerequisit complert: Fase 2 tancada (144 tests, `actualitzar_microcicle()` fet com a composició de 4 primitives — vegeu `fase2.md`). Aquesta fase connecta els mòduls existents en entry points d'ús real: generar contingut per blocs de temporada, i exportar el resultat a un format que el coach pugui llegir fora del codi.

---

## Estat actual (actualitzat 2026-10-05)

**456 tests (inclosos els d'`ingestion`), lint net.** Jerarquia de 3 nivells completa. Fetes: Fase A, Fase B+C+D, Etapa 4 (primera setmana real generada), F1, F2, G1, G2, G5, G6, **Fase H** (organització setmanal, pressupost d'intensitat i control de la recuperació), **Fase H2** (5 dies, biblioteca de tècnica, doble pic), **Fase E+I** (càrrega real sRPE, SRSS, sèrie de control i sessions múltiples al dia), **estructura de la sessió** (bloc de cada part a l'Excel), **script del test CSS**, **multi-nedador** (dades per carpeta) i **objectius i progressió** (proves P/S, pics, bandes, simulacions; vegeu la secció al final i `Disseny_proves_objectius.md`). Manual d'ús: `Manual.md`. Llista completa del que falta: secció «Pendent» al final.

**Organització setmanal vigent: la de la Fase H2 (5 dies, dilluns a divendres).** La plantilla de 4 dies de la Fase H es conserva més avall només com a historial.

**Historial de lliuraments (2026-10-03/05):** `blondswim_multinedador.zip` (5 patches, 369), patch de documentació de rutes, `blondswim_objectius.zip` (3 patches, 447), correcció de les competicions de control del pic 2 (448) i simulacions + `registrar_resultat.py` (456), aplicats al repo del Jep (`main` = `dcb20c0` + aquesta documentació).

**Historial de lliuraments (2026-10-01):** el repo del Jep no tenia aplicades la H ni la H2 (179 tests). `blondswim_faseEI.zip` (8 patches: H, H2, estil i E+I, 328 tests), `blondswim_test_css.patch` (329) i `blondswim_estructura_sessio.patch` (340), aplicats i verificats al repo del Jep. La `setmana_tipus` del Jep ja és a `nedador_jep.json`.

**Canvi de flux de treball (2026-09-30):** aider ha fallat repetidament en canvis multi-fitxer (commits només amb tests, blocs SEARCH/REPLACE no aplicats, fitxers corromputs). Per als canvis grans, Claude escriu el codi en un entorn propi amb els tests i lliura **patches `git am`** (un commit per pas); el Jep els aplica i executa `pytest -q && ruff check .`. Aider queda per a canvis petits d'un sol fitxer.

## Pla en curs

- **Fase A** — Classificació A/B a `generar_mesocicle()`. ✅
- **Fase B+C+D** — Model `Exercici`, generació estructurada, exportador. ✅ Etapa 4 feta (vegeu "Etapa 4" més avall).
- **Fase F** — Volum setmanal amb evidència. ✅ F1, F2. Pendents F3-F7.
- **Fase G** — Contingut setmana a setmana. ✅ G1, G2, G5, G6. Pendents G3, G4.
- **Fase H** — Organització setmanal, pressupost d'intensitat i control de la recuperació. ✅ (plantilla de 4 dies substituïda per la H2; el pressupost d'intensitat i la validació continuen vigents)
- **Fase H2** — 5 dies, biblioteca de tècnica (64 exercicis, 18 famílies), doble pic d'hivern. ✅ Implementada; pendent test CSS i regenerar la setmana 41 real.
- **Fase E+I** — Càrrega real (sRPE CR-10), benestar (SRSS), sèrie de control, sessions múltiples per dia (natació + gimnàs informatiu) i regla de decisió. ✅ Implementada (5 commits); pendent calibrar llindars amb 3-4 setmanes de dades. Substitueix l'antiga "Fase E".
- **Estructura de la sessió** — cada part porta el seu bloc (escalfament, tècnica, bloc principal 1..n, tornada a la calma) i l'Excel l'indica. ✅ (2026-10-01)
- **Script del test CSS** — `scripts/registrar_test_css.py`. ✅ (2026-10-01)
- **Multi-nedador** — una carpeta per nedador, catàleg comú i calendari per nedador. ✅ (2026-10-03)
- **Objectius i progressió** — proves P/S, pics del calendari, perfil per durada, bandes, zones, projecció, simulacions i registre de resultats. ✅ (2026-10-04/05). Pendents: planificador setmanal LLM i prompt per focus de prova (patches 4-5).

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

**Classificació de la setmana (Fase H)** — `Microcicle.dia_competicio` ("dissabte"/"diumenge") i `Microcicle.post_competicio` via `pla_setmanal.classificar_setmana()` (només competicions A i B). **Atenció**: una competició només fa setmana de competició si la seva `data_inici` cau en dissabte o diumenge. Un rang que comenci entre setmana (p.ex. 04-07/02) no activa l'activació ni el `dia_competicio`; per això el calendari ha de portar els dies en què el nedador competeix realment (Espanya: 06-07/02/2027).

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
- Capçalera de setmana: `"<Mes(os)> <Any> — Setmana <ISO> (<dates>) — <mesocicle>, Fase <tipus>"`. Capçalera de dia: `"Dilluns 5 — <franja> — <rol>"` (franja només si el nedador té `setmana_tipus`; rol només amb la plantilla setmanal). Sessions de gimnàs: una línia `"Dilluns 5 — tarda — Gimnàs (60 min, informatiu)"`.
- Columnes: `Part, Treball, Execució, Descans, Material, Intensitat, Objectiu, Temps (min), Volum (m)`. La columna **Part** (abans `Dia`, sempre buida) porta l'etiqueta del bloc a la primera fila de cada part (vegeu «Estructura de la sessió»). Una fila per `Exercici`; fila `Total`; `Temps (min)` = durada estimada (nedar + descansos, `agents/cicles.py`) per exercici i total del dia.
- **Rutina d'espatlla**: si `Nedador.rutina_espatlla_dia` és un dia de descans de la setmana, bloc "Descans a l'aigua. Rutina d'espatlla (opcional, 15 min)" en ordre cronològic. Jep: dissabte (H2).

## Script `scripts/generar_temporada.py --nedador <id>`

*(Fins al 2026-10-03, `generar_temporada_jep.py`.)* Per defecte: estructura de la temporada + contingut **només de la setmana del proper dilluns** → `data/nedadors/<id>/setmanes/setmana_<id>_<YYYY>-W<ww>.xlsx`. Opcions: `--dilluns YYYY-MM-DD` (accepta setmanes passades), `--mesocicle-sencer` (comportament antic), `--data-referencia`. Avisa si el nedador no fa servir la plantilla setmanal. Des de la E+I, a més: avaluació de la recuperació de la setmana anterior i full de registre en blanc (vegeu Fase E+I).

**Dades del Jep (`data/nedadors/jep/nedador.json`, gitignored)**: vegeu «Dades del Jep» al final (Fase H2 + E+I).

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

Observacions del calendari: avís `cap_competicio_a_restant` confús (es refereix a les setmanes 23-27 de 2027, després de l'última A); el Mundial de Budapest surt dues vegades a la setmana 26 (vegeu «Calendari 2026-27» més avall: **no és un duplicat**, són dues proves diferents); el Campionat d'Espanya d'Hivern (setmana 5) era B dins d'un bloc de Base. **Decisió pendent del Jep: classe del Mundial de Budapest.** (El Campionat d'Espanya es va resoldre a la Fase H2: classe A, doble pic.)

---

## Calendari 2026-27 — notes de coherència (2026-10-02)

Font: pestanya `Calendari` de `Provisional26-27.xlsx` (corregida el 2026-10-02) → `data/processed/calendari.json` via `convertir_calendari()`.

- **Campionat d'Espanya d'Hivern**: classe **A**, **06-07/02/2027** (decisió H2). El full tenia `B` i `2027-02-04 a 2027-02-07`; corregit. Cal regenerar `calendari.json` i comprovar-hi la classe i les dates (amb el rang 04-07 la setmana no es classificaria com a setmana de competició perquè comença en dijous).
- **Mundial de Budapest 2027**: dues proves, **aigües obertes 29-30/06** (`modalitat="aaoo"`) i **piscina 50 m 03-09/07**. Totes dues cauen a la setmana 26 i formen un sol bloc competitiu. No s'ha d'eliminar cap fila: cal decidir-ne la classe (pendent del coach) i, si escau, tractar-les juntes a la periodització.
- **Proves B de la tardor que afecten les setmanes generades**: Barceloneta **ds 17/10** (W42: setmana de competició → activació divendres, sense aeròbica llarga, volum × 0,8; W43: post-competició → dilluns de recuperació, qualitat dijous, objectiu = mínim), UE Horta **ds 07/11** (W45 / W46) i CNSF Marrugat **ds 12/12** (W50 / W51). Les C (Girona 24/10, Sabadell 21/11, etc.) no modifiquen la plantilla.
- Ordre de files: Sant Jordi (25/04, C) apareix abans de Cornellà (24/04, B). No afecta la ingestió.

---

## Fase H — Organització setmanal, pressupost d'intensitat i control de la recuperació (acordat i implementat 2026-09-30)

> **Historial.** La plantilla de 4 dies (Dl, Dt, Dj, Dv), la sèrie de control del dilluns, la rutina d'espatlla del dimecres i els pesos de volum d'aquesta secció **van ser substituïts per la Fase H2** (5 dies, sèrie de control el dimecres, rutina d'espatlla el dissabte). Continuen vigents: 1 dia de qualitat, activació 24 h abans, setmana post-competició, pressupost d'intensitat, límits de papallona, regles de natació i indicadors de recuperació. El patch original de la H (`Fase_Patch.md`) s'ha retirat del projecte.

### Decisions del coach (Jep)

1. **1 sol dia de qualitat per setmana**; s'avalua amb tests de seguiment abans d'afegir-ne un segon.
2. **Papallona 300-600 m/setmana**, equilibri entre tècnica i nedar papallona.
3. ~~4 sessions no consecutives: dilluns, dimarts, dijous, divendres~~ → **5 sessions (H2)**.
4. **Competicions**: dissabte o diumenge; els dos dies només en proves A (segons les proves).
5. **Prioritat recuperació**, però **complint sempre el mínim** setmanal; tests per avaluar la recuperació.
6. **Dia abans de competir: activació. Dies de descans: descans total a l'aigua.**
7. **Sèrie de control** 4x100 crol A2 cada setmana (dilluns a la H → **dimecres a la H2**); **rutina d'espatlla** opcional de 15 min (dimecres a la H → **dissabte a la H2**).

### Plantilla setmanal de la Fase H (historial, 4 dies)

| Dia | Normal | Competició dissabte | Competició diumenge | Post-competició |
|---|---|---|---|---|
| Dl | Aeròbic i tècnica + sèrie de control | Aeròbic i tècnica + control | Aeròbic i tècnica + control | **Recuperació activa** (~60% del volum) + control |
| Dt | **Qualitat** | **Qualitat** | **Qualitat** | Aeròbic i tècnica |
| Dc | Descans (rutina d'espatlla) | Descans | Descans | Descans |
| Dj | Tècnica (papallona tècnica) | Tècnica | Tècnica | **Qualitat** |
| Dv | Aeròbica llarga + velocitat alàctica | **Activació** | Descans | Tècnica |
| Ds | Descans | 🏁 | **Activació** | Descans |
| Dg | Descans | Descans | 🏁 | Descans |

Plantilla vigent: vegeu «Fase H2». Post-competició i competició el mateix cap de setmana: sense dia de qualitat (les curses fan d'estímul intens). Setmana de Cursa (A): mateixa lògica d'activació; la Transició posterior és setmana post-competició.

### Volum i parts per rol

*(Ordre de les parts revisat el 2026-10-01: vegeu «Estructura de la sessió». Pesos vigents: vegeu «Fase H2».)*

Pesos de volum de la H (historial): aeròbica 1,0 · llarga 1,1 · qualitat 0,95 · tècnica 0,95 · activació 0,5 · recuperació 0,6. Rang de cada sessió = objectiu ± 5%, limitat a `minuts_max_sessio × 40 m/min`. Parts pròpies per rol (`PARTS_ROL`); la sèrie de control (400 m) és una part fixa, amb cicle = ritme A2 + 15" arrodonit a 5" (Jep amb les zones estimades: c/1'40"; es recalcula amb el test CSS).

### Pressupost d'intensitat per sessió (validat en codi, vigent)

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

## Fase E+I — Càrrega real, benestar i sessions múltiples (acordat i implementat 2026-10-01)

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
    rpe_sessio: int | None = None   # 0-10, CR-10
    assoliment: int | None = None   # 1-5, independent de l'RPE
    @property
    def carrega(self) -> int | None: ...   # rpe_sessio × temps_total_min
    # series i volum_total_m tenen ara valor per defecte (sessions de gimnàs)

class RegistreSRSS(BaseModel):
    nedador_id: str
    data: date
    recuperacio: list[int]   # 4 ítems, 0-6
    estres: list[int]        # 4 ítems, 0-6

class RegistreSerieControl(BaseModel):
    nedador_id: str
    data: date
    temps_100: list[float]          # 4 valors, segons
    bracades_llargada: list[float] | None = None
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

### Implementació (fet, 2026-10-01)

Commits (patches `git am`, sobre H + H2 + `style: sort imports`):

1. **E+I-1 Models** — `models/franja.py` (`Franja`, `Modalitat`, `SlotSessio`, `franges_consecutives`), `models/registre.py` (`RegistreSRSS`, `RegistreSerieControl`, etiquetes CR-10, ítems SRSS), `Nedador.setmana_tipus` amb `slots_dia()` i `franja_natacio()`, camps nous a `Sessio` i `SessioRealitzada`. 23 tests.
2. **E+I-2+3 Esquelet, LLM, Excel i validació** — `esquelet_sessions._afegir_franges_i_altres_sessions()`: franja a la natació i sessions de gimnàs informatives (mai el dia de competició ni abans de `sessions_des_de`); `generar_microcicle` només crida l'LLM per a la natació i li diu si aquell dia hi ha gimnàs; capçalera `"Dilluns 5 — matí — <rol>"` i línia `"Gimnàs (60 min, informatiu)"` (franja només si el nedador té `setmana_tipus`); `validacio.validar_franges_setmana()` dins `generar_i_validar_microcicle`. 11 tests.
3. **E+I-4+5 Càrrega i recuperació** — `agents/carrega.py` (`carrega_diaria`, `carrega_setmanal`, `evolucio_carrega` amb aguda/crònica/balanç, `alerta_carrega_setmanal`) i `agents/recuperacio.py` (`alerta_srss`, `alerta_serie_control`, `avaluar_setmana` amb `recomanacio_setmana_seguent` i `dades_incompletes`). 21 tests.
4. **E+I-6 Full de registre** — `export/registre_excel.exportar_registre_setmana()` (pestanyes Sessions, Benestar (SRSS) i Sèrie de control, amb validació de dades i llegenda CR-10) i `ingestion/registre_setmana` (`convertir_registre_setmana`, `carregar_registres`; files a mitges = `ValueError` amb el número de fila; temps "1:40.5", "1'40", 100.5 o hora d'Excel). 11 tests.
5. **E+I-7 Script** — `generar_temporada_jep.py` llegeix `data/processed/registres/registre_*.xlsx`, mostra la càrrega i les alertes de la setmana anterior, els avisos de franges de la setmana generada, i crea el full de registre en blanc (mai en sobreescriu un d'existent).

**Diferències respecte al disseny:**
- Els minuts de la sessió són `SessioRealitzada.temps_total_min` (ja existia), no un camp `minuts` nou.
- **Com a molt una sessió de natació per dia** (validat a `Nedador`): la plantilla de rols és per dia. Dobles sessions d'aigua, pendent si cal.
- L'avaluació de la recuperació es fa a l'script, no dins `generar_mesocicle()`. Encara no exclou de la base de càrrega les setmanes de descàrrega/taper/transició passades (la periodificació només coneix les setmanes futures) ni aplica `ratio_planificat`: es passaran quan hi hagi historial de plans.
- La regla "2 blocs sense alertes i CSS millorant → segon dia de qualitat" no està implementada (cal historial de tests CSS).
- Regla "dies durs, durs": només s'avisa en els conflictes clars (gimnàs el dia de tècnica, activació o recuperació, o en franja contigua a la qualitat); `ROLS_SENSE_GIMNAS` és configurable.

**Flux setmanal**: executar l'script → full de la piscina + full de registre en blanc → omplir RPE/minuts (es pot fer al vespre), SRSS cada dia d'entrenament i la sèrie de control → la setmana següent l'script avalua la setmana anterior.

---

## Estructura de la sessió (acordat i implementat 2026-10-01)

**Petició del coach**: cada exercici ha de dir a quina part de la sessió pertany (escalfament, tècnica, bloc principal —numerat si n'hi ha més d'un— i tornada a la calma), seguint l'estructura recomanada.

**Implementació:**
- `PartSessio.bloc`: `Escalfament`, `Tècnica`, `Bloc principal`, `Tornada a la calma` o `Sèrie de control` (assignat a l'esquelet amb `pla_setmanal.BLOC_PART`; `None` en sessions antigues).
- `pla_setmanal.etiquetes_parts()`: `"Bloc principal 1 — Qualitat"`, `"Bloc principal 2 — Aeròbic"`; sense número si només n'hi ha un. Al dia de tècnica, la part de tècnica és el bloc principal.
- Excel: columna **Part** amb l'etiqueta a la primera fila de cada part.
- Prompt: cada part va amb el seu bloc i una regla explícita: cada exercici a la part que correspon al seu objectiu; l'escalfament només prepara, la tècnica només porta exercicis tècnics i el seu nedar complet, i no hi ha sèries principals a l'escalfament ni a la tornada a la calma.

**Ordre de les parts per rol** (el treball exigent, en fresc, just després de l'escalfament i la tècnica):

| Rol | Parts |
|---|---|
| Aeròbica | Escalfament · Tècnica · **Aeròbic** · Cames · Tornada a la calma |
| Llarga | Escalfament · Tècnica · **Velocitat alàctica** · Aeròbic llarg · Cames · Tornada a la calma |
| Qualitat | Escalfament · Tècnica+Subaquàtic · **Qualitat** · Aeròbic · Tornada a la calma |
| Tècnica | Escalfament · Sèrie de control · **Tècnica i papallona** · Cames · Nedar suau · Tornada a la calma |
| Activació | Escalfament · Tècnica i sortides · Ritme de cursa · Nedar suau · Tornada a la calma |
| Recuperació | Escalfament · Tècnica suau · Aeròbic suau amb canvis de ritme · Cames · Tornada a la calma |

**Canvi respecte a la Fase H2 (pendent de confirmar pel coach)**: a l'aeròbica llarga, la velocitat alàctica passa del final al principi del bloc principal (la qualitat alàctica cau amb la fatiga). A la qualitat, l'aeròbic passa darrere de la qualitat.

---

## Script `scripts/registrar_test_css.py` (fet 2026-10-01)

```bash
python scripts/registrar_test_css.py --nedador jep --t400 6:52.3 --t200 3:18.1 --data 2026-10-03 --simular
python scripts/registrar_test_css.py --nedador jep --t400 6:52.3 --t200 3:18.1 --data 2026-10-03
```

Temps com `6:52.3`, `6'52.3` o segons. Calcula CSS/100 = (T400 − T200) / 2 i les zones amb els offsets del nedador (`zones_css.ritmes_des_de_test_css()`), mostra les zones d'abans i les noves i les desa a `ritmes_css` (font `css_test`, `data_test`), amb còpia `.bak` del JSON. Velocitat = CSS × 0,85: comprovar que queda més lenta que el ritme del 100 de cursa.

---

## Volum setmanal — criteris amb evidència (acordat 2026-09-30, actualitzat amb la H2)

**Context del Jep**: A = 100 crol i 100 estils; B = alguna prova de 200 crol; **5 dies/setmana (H2; a la H eren 4)** sense dia opcional; sessió màxima 1:30-1:45 h; sense molèsties d'espatlla; **12.000 m/setmana = mínim normal** (no aplica a taper ni transició).

**Evidència (resum)**: no hi ha criteri científic de volum absolut; la distribució per zones pesa més que els metres ([Nugent et al. 2017](https://pubmed.ncbi.nlm.nih.gov/27465628/); [Kilen et al.](https://onlinelibrary.wiley.com/doi/10.1080/17461391.2015.1028466)); en màsters, bloc de volum → bloc d'intensitat ([IJSPP 2015](https://pubmed.ncbi.nlm.nih.gov/25710182/)); l'edat i el volum prediuen el rendiment màster ([Lapierre et al. 2018](https://pubmed.ncbi.nlm.nih.gov/30130814/); [Zamparo et al. 2012](https://link.springer.com/article/10.1007/s00421-012-2376-y)); lesió associada a càrrega aguda i ACWR alts, però ACWR qüestionat → avís, no regla ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9205558/); [Impellizzeri et al. 2020](https://www.researchgate.net/publication/341936245_AcuteChronic_Workload_Ratio_Conceptual_Issues_and_Fundamental_Pitfalls)); taper de 2 setmanes amb −41-60% de volum ([Bosquet et al. 2007](https://www.semanticscholar.org/paper/Effects-of-tapering-on-performance:-a-Bosquet-Montpetit/a41517ab5fa06b92568b861e2b1aa32b3003d214)).

**Dades de referència** (`Provisional26-27.xlsx`, sessions planificades a mà, 5 dies): 2.800 m/sessió de mitjana (p25-p75 2.700-2.900), ~62 min/sessió, ~45 m/min, 13.930 m/setmana. **El fitxer barreja dues temporades**: les pestanyes **Sept i Oct** tenen les dates del **2026** (setmanes 5-13; la setmana 5 té les etiquetes de dia desplaçades, «Dilluns 1» hauria de ser «Dilluns 31/08») i són la planificació manual d'aquesta temporada; les pestanyes **Nov, Desc, Gen i Feb** tenen les dates del **2025** (dilluns 3/11, 1/12, 16/02) i són la planificació de la 25-26; **Gen és una còpia exacta de Desc** (no hi ha dades reals de gener) i la numeració salta de la setmana 20 a la 27. El registre real d'entrenament és `historial_jep.json` (`PretemporadaSep26-27.xlsx`, 18/08-25/09/2026).

**Rangs per tipus de setmana**: càrrega 13.600-15.000 · qualitat 12.000-13.600 · descàrrega 12.000-12.400 · taper A setmana 1: 8.400-9.800 · taper A setmana 2: 5.600-8.200 · taper B: 10.400-12.000. Es van calcular amb 4 dies; amb la H2 el volum setmanal no canvia i es reparteix en 5 sessions. Provisionals: recalibrar amb F3.

### Millores (Fase F)

- **F1** ✅ `Nedador.volum_setmanal_min=12000`, `minuts_max_sessio=105`, `dia_opcional=None`; taula `VOLUM_SETMANAL_CARREGA` ajustada.
- **F2** ✅ Terra de volum i avís `descarrega_insuficient` (vegeu `generar_mesocicle()`).
- **F3** Base de volum mòbil (EWMA 4-6 setmanes realitzades, excloent descàrrega/taper/transició). Pendent (pot reutilitzar les mitjanes de E+I-4).
- **F4** Taper exponencial alineat amb Bosquet sobre el volum mitjà de Build2. Pendent.
- **F5** Avís de salt agut de volum a `validacio.py`. Pendent.
- **F6** Distribució d'intensitat: **avançada per la Fase H a nivell de sessió** (pressupost per rol). Pendent: control agregat per mesocicle.
- **F7** Cota de volum per temps de sessió: aproximada a la Fase H (40 m/min); amb l'Etapa 3b la durada calculada ja és un problema de validació (>110% de `minuts_max_sessio`); falta treure la cota de 40 m/min de l'esquelet.

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

## Pendent (actualitzat 2026-10-05)

**Objectius i progressió (prioritat)**
0. **Planificador setmanal LLM** (patch 4) i **prompt per focus de prova** (patch 5): vegeu `Disseny_proves_objectius.md`, seccions 5-6. Fins llavors, la metodologia es tria per la primera prova de la fitxa (ara el 100 lliure).

**Tasques del coach (sense codi)**
- ~~Test CSS dissabte 03/10~~ (piscina tancada) → **dilluns 05/10**; registrar-lo amb `registrar_test_css.py --nedador jep` abans de generar la W41.
- ~~Regenerar `calendari.json`~~ ✅ Catàleg nou a partir del PDF del Circuit Català i calendari del Jep refet (Espanya A, 06-07/02/2027).
- Generar i revisar la W41 amb les zones del test (re-verificació de l'Etapa 4).
- Marge al nivell del 100 IM (ara 1'38" = 1'38") i objectius del pic 2 (abans del febrer); data definitiva de Sant Andreu (13 o 20/03).
- Revisar la biblioteca de tècnica (`Biblioteca_tecnica_v1_families.xlsx`).
- Decidir la classe del Mundial de Budapest (les dues proves, aigües obertes i piscina).
- Confirmar l'ordre de l'aeròbica llarga (velocitat alàctica al principi).

**Qualitat dels fulls (prioritat)**
1. ✅ **Etapa 3b — temps per exercici** (Sprint 2): ritme per zona × factor d'estil + parseig de `descans`; omple `Temps (min)`.
2. ✅ **Validació de cicles** (Sprint 2): els `c/` impossibles passen a `d/`; descans per sota del mínim de la zona o sessió massa llarga → fins a 2 reintents dirigits.
3. **G3 — continuïtat al prompt**: setmana anterior, posició dins el mesocicle i dades reals (RPE, SRSS).

**Ajustos petits**
4. Avís `gimnas_dia_no_recomanat`: només si el gimnàs va *abans* de la tècnica o l'activació (ara és un fals positiu el dimecres del Jep).
5. Opció `--nomes-registre` a l'script (full de registre sense crides a l'API).

**Càrrega i recuperació (amb 3-4 setmanes de dades)**
6. Calibrar els llindars de sRPE, SRSS i sèrie de control.
7. Base de càrrega: excloure descàrrega/taper/transició i aplicar l'increment planificat (cal historial de plans).
8. Regla del segon dia de qualitat (cal historial de tests CSS).
9. Dues sessions de natació el mateix dia o franja «vespre», si cal.

**Volum (Fase F)**: F3 base de volum mòbil (reutilitzar `carrega.py`), F4 taper exponencial, F5 avís de salt agut, F6 intensitat agregada per mesocicle, F7 cota per temps de sessió.

**Contingut (Fase G)**: G4 previsualització N+1 com a esborrany.

**Pendents menors**: revertir `tipus_base` obsolet després d'`eliminar_competicio()`; cablejat de `guardar_log_ajust()`; missatge de `cap_competicio_a_restant` (a partir de quina setmana); tractar les dues proves de Budapest com un sol bloc competitiu (no eliminar-ne cap); model "judge" configurable (`BLONDSWIM_LLM_PROVIDER`); contingut de gimnàs generat; esquelet antic per a Lou, Cris i Pere fins que tinguin plantilla pròpia.

## Pendent general

- Fase 4: validació amb un criteri de referència (candidat: els indicadors de recuperació i rendiment de la Fase H, alimentats per E+I).
- Fase 5: extensió a Lou (CSS real), Cris i Pere (RPE fins al primer test), cadascun amb la seva `setmana_tipus`.

---

## Fase H2 — 5 dies, biblioteca de tècnica i doble pic (acordat i implementat 2026-10-01) — VIGENT

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

Les zones estimades per millor marca són més ràpides que el ritme de la millor marca de 200 m (1'31,5"/100); el Jep manté ~1'40"/100 entrenant. A més, **hi ha dues taules del Jep que no coincideixen**: `Ritmes_Jep.xlsx` (A1 1'27", A2 1'22", A3 1'18" per 100) i la pestanya `Ritmes` de `Provisional26-27.xlsx` (A1 1'27"-1'30", A2 1'24"-1'25", A3 1'20"-1'21"). Totes dues són estimacions per marca i **queden substituïdes pel test CSS**; `Ritmes_Jep.xlsx` és, a més, la versió antiga de 3 zones (vegeu `metodologia_ritmes.md`). **Test CSS dissabte 03/10/2026** (400 + 200 m, repartint l'esforç: cada 100 com a molt 2" més ràpid que la mitjana); CSS/100 = (T400 − T200) / 2; zones = CSS + offsets (A2 = CSS, A3 = CSS − 4", A1 = CSS + 6", Recuperació = CSS + 12").

### Dades del Jep (`data/nedadors/jep/nedador.json`, actualitzat 2026-10-01)

`dies_disponibles`: dilluns-divendres (derivat de `setmana_tipus`) · `rutina_espatlla_dia`: "dissabte" · `proves_objectiu`: 100m lliure, 100m estils, 200m lliure, 50m papallona · `prioritats_tecniques`: "Ritme de cursa", "Viratges", "Coordinació de braça".

**Horari real (`setmana_tipus`)**: natació al matí dilluns i dimecres (7:00-8:45), a la tarda dimarts, dijous i divendres (18:30-19:45/20:00); gimnàs dilluns i dimecres a la tarda (18:00-19:00, 60 min). Divendres només natació (el gimnàs se solaparia).

```json
"setmana_tipus": {
  "dilluns":   [{"franja": "mati", "modalitat": "natacio"},
                {"franja": "tarda", "modalitat": "gimnas", "durada_min": 60}],
  "dimarts":   [{"franja": "tarda", "modalitat": "natacio"}],
  "dimecres":  [{"franja": "mati", "modalitat": "natacio"},
                {"franja": "tarda", "modalitat": "gimnas", "durada_min": 60}],
  "dijous":    [{"franja": "tarda", "modalitat": "natacio"}],
  "divendres": [{"franja": "tarda", "modalitat": "natacio"}]
}
```

Notes: la qualitat de dimarts a la tarda queda a ~11 h de la tècnica de dimecres a les 7:00 (acceptable: volum baix i sense intensitat). El dimecres surt l'avís `gimnas_dia_no_recomanat`, que en aquest cas és un fals positiu (pendent, punt 4).

## Multi-nedador: dades per carpeta (2026-10-03)

Preparació de la Fase 5 (Lou, Cris i Pere). Decisions: (1) calendari en dues capes, catàleg comú `data/competicions.json` + calendari per nedador amb classe A/B/C i proves; (2) ritmes dins de la fitxa del nedador; (3) identificador = nom de la carpeta `data/nedadors/<id>/`. JSON com a font de veritat, Excel només com a sortida.

Commits (patches `git am`):

1. **calendari** — `CompeticioCataleg`, `InscripcioCompeticio`, `resoldre_calendari()`, `separar_calendari()`, `fusionar_cataleg()`; `Competicio.proves` opcional. Els agents continuen rebent `list[Competicio]`. 7 tests.
2. **rutes** — `blondswim/rutes.py`: `RutesNedador` deriva totes les rutes de l'id; `carregar_nedador` (comprova id = carpeta), `carregar_competicions`, `carregar_historial`, `llistar_nedadors`. Els logs de decisions van a `data/nedadors/<id>/log_decisions/`. 15 tests.
3. **scripts** — `generar_temporada.py --nedador <id>` (substitueix `generar_temporada_jep.py`), `registrar_test_css.py --nedador <id>`, `make setmana NEDADOR=<id>`.
4. **migració** — `scripts/migrar_a_carpetes.py [--simular]` copia `data/processed/` a la nova estructura (no esborra ni sobreescriu). `make run-ingestion` escriu la nova estructura i ja no trepitja `nedador.json` si existeix. 7 tests.

**Pendent:** fitxes i calendaris de Lou, Cris i Pere; dates de temporada per nedador (ara fixes a l'script).

## Objectius, progressió i simulacions (2026-10-04/05)

Disseny complet, decisions i evidència: **`Disseny_proves_objectius.md`**. Ús: **`Manual.md`**, seccions 4, 6 i 7.

**Problema de partida:** la metodologia es triava per `proves_objectiu[0]` (50 papallona) per a tota la temporada, amb una regla per distància pensada per a temps d'elit, i el sistema no mesurava el rendiment.

**Decisions del coach (Jep):** proves P/S a la fitxa (pesos 2/1); pics calculats de les competicions A del calendari; perfil per durada; metodologia per fase; objectiu A com a rang (realista/ambiciós) i nivell actual com a rang; B i C com a punts de control progressius; vídeo per a parcials i braçades; 50 papallona fora; el calendari del nedador només conté les competicions on va; simulacions (contrarellotge en entrenament).

Commits (patches `git am`):

1. **objectius** — `ProvaObjectiu`, `NivellActual`, `ObjectiuProva`, `ParametresProgressio`; `ResultatCompeticio` i `resultats.json`; `utils/temps.py`, `utils/proves.py`. La llista antiga de textos continua funcionant. 38 tests.
2. **proves** — `agents/proves.py`: pics (doble pic a ≤ 4 setmanes), pesos, perfil per durada, competicions de control, `validar_objectius()` (només el pic actiu per defecte). 22 tests.
3. **progressio** — `agents/progressio.py`: bandes (línia ràpida de la millor marca a l'ambiciós, línia lenta de l'estimació pessimista al realista, fins al temps sense taper de la A), zones, calibratge, projecció lineal amb interval ±1σ (soroll mínim = `marge`), ritme de cursa de referència; `informe_progressio.py` i informe dins `generar_temporada.py`. 18 tests.
4. **fix** — les competicions de control d'un pic comencen després del pic anterior. 1 test.
5. **simulacions** — `InscripcioCompeticio.tipus` (`competicio`/`simulacio`), simulacions sobre el catàleg o definides amb `data` i `piscina`; fora de la planificació (`competicions_planificacio()`); a l'informe `[S]`, sense «sense millora» ni «nova millor marca»; `scripts/registrar_resultat.py`. 8 tests.

**Revisió durant la implementació:** el ritme de cursa ja no es mou amb un sol resultat dins la banda (a l'inici, l'amplada és incertesa del nivell, no progrés): realista fins que hi ha projecció, i després la projecció, com a molt l'ambiciós.

**Calendari del Jep (pic 1, 25 m):** simulació Barceloneta 17/10, Horta 14/11 (C), Granollers 28/11 (C), CNSF 12/12 (B, assaig general; W50 setmana de competició, W51 post-competició), Girona 19/12 (C, 50 m, pic 2), Catalunya 16-17/01 i Espanya 06-07/02 (A, doble pic). Pesos del pic 1: 100 lliure 50%, 100 IM 50%. El 200 lliure passa al pic 2.

**Limitacions:** taper 2%, marge 1%, exigència 4% i pesos 2/1 són punts de partida raonats (dades d'elit i de màsters joves); amb 3-4 curses per pic la projecció és orientativa.
