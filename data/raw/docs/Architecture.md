BlondSwim — Arquitectura
Decisió d'arquitectura

Pipeline de funcions Python deterministes, amb crides a l'LLM (Claude, via API) només als punts de judici que ho requereixen realment. Es descarta un framework multi-agent complet (LangGraph/CrewAI) per a l'abast de l'MVP: la majoria de lògica (càlcul de zones, classificació de competicions, taper, validacions, esquelet de sessions) és determinista i no aporta res passar-la per un LLM — només cost, latència i risc d'al·lucinació en xifres.

Dos entry points de Fase 3: generar_macrocicle(nedador_id) (🔲 pendent) i actualitzar_microcicle() (✅ fet, 2026-09-28 — vegeu fase2.md, implementat com a composició de 4 primitives: ajust de volum, canvi de classe de competició, eliminació de competició, log d'ajustos).

Principi confirmat (2026-09-28): el pla generat és dinàmic, no una veritat fixa. Volum, classe de competició i tipus de setmana són el millor punt de partida; han de poder reajustar-se durant la temporada (fatiga, malaltia, canvi de classe d'una competició) sense refer tot el macrocicle.

Principi confirmat (2026-09-28): decisions de canvi sempre humanes, mai automàtiques. El sistema valida i avisa, però no decideix per si sol quant baixar un volum o quantes setmanes de represa calen — per això actualitzar_microcicle() és composició de primitives petites, no una funció monolítica tipus "gestionar malaltia".

Capes i agents
Capa	Agent/Mòdul	Tipus	Fase	Estat
Dades	Models pydantic (Nedador, Competicio, Macrocicle/Mesocicle/Microcicle, Sessio)	—	0	✅ Fet
Dades	Conversor Excel→JSON (xlsx_to_json.py)	Determinista	0	✅ Fet
Dades	Ingestió historial real (convertir_pretemporada, historial_jep.json)	Determinista	2	✅ Fet (6 tests)
Dades	Ingestió Microcicles (convertir_microcicles, vincula Mesocicle.microcicles)	Determinista	2	✅ Fet (9 tests)
Operativa	Zones CSS (zones_css.py)	Determinista	1	✅ Fet (12 tests)
Operativa	Context de competició (context_competicio.py)	Determinista	1	✅ Fet (8 tests)
Operativa	Taper (taper.py)	Determinista	1	✅ Fet (11 tests)
Operativa	Esquelet de sessions (esquelet_sessions.py)	Determinista	2	✅ Fet (10 tests)
Validació	Validació fisiològica/temporal (validacio.py), amb ACWR + historial real	Determinista	1/2	✅ Fet (13 tests)
Estratègia	Selecció de model d'entrenament (seleccio_model.py)	Determinista + enriquiment LLM opcional	2	✅ Fet (32 tests) — validat amb crida real
Estratègia	Generació de contingut de microcicle (generar_microcicle.py) + orquestració (generar_i_validar_microcicle) + log de decisions	LLM (judici, ús obligatori)	2	✅ Fet (10 tests) — validat amb crida real
Estratègia	actualitzar_microcicle — 4 primitives (volum, classe competició, eliminació competició, log d'ajustos)	Determinista + judici del coach	2	✅ Fet (10 tests)
Estratègia	generar_macrocicle(nedador_id) — orquestració temporada sencera	LLM (crides repetides) + determinista	3	🔲 No iniciat
Estratègia	Ajust per feedback subjectiu/test periòdic	LLM (judici)	3	🔲 No iniciat
Sortida	Exportador Excel + resum Markdown	Determinista	3	🔲 No iniciat

Fase 1 tancada (2026-09-27): 62 tests, make lint net.

Fase 2 tancada (2026-09-28): 144 tests, make lint net. Ingestió d'historial real, Mòdul 5 (Selecció de Model), extensió d'ACWR amb historial real, esquelet de sessions (amb es_dia_opcional), Mòdul 6 (Agent de Microcicle + orquestració + log de decisions), ingestió de Microcicles, i actualitzar_microcicle() complet (4 primitives), fets. Mòduls 5/6 validats amb una prova real end-to-end contra l'API de Claude (vegeu més avall). Detall complet: fase2.md.

Client LLM (Fase 2)

src/blondswim/llm/client.py: get_llm_client() retorna un client Anthropic configurat (clau via .env/ANTHROPIC_API_KEY, carregat amb load_dotenv(override=True)); DEFAULT_MODEL configurable via variable d'entorn LLM_MODEL (per defecte "claude-sonnet-5"). Reutilitzat pel Mòdul 5 (enriquiment opcional) i pel Mòdul 6 (generació, ús obligatori, tool-use forçat per garantir sortida estructurada).

Regles de classificació i taper (TrainingPeaks/Joe Friel) — implementades
Classificació de competicions (Mòdul 2)
Classes A/B/C ja existents al calendari (Provisional26-27.xlsx).
Validació implementada (validar_espaiat_pics_a): màxim 1-3 competicions classe A per temporada; mínim 8-12 setmanes de separació entre A consecutives (12-16 per esports de resistència llarga).
Taper i recuperació (Mòdul 3)
Classe	Taper pre-competició	Recuperació post-competició
A	Progressiu, 14 dies per defecte (rang 7-21)	14 dies per defecte (rang 1-3 setmanes)
B	Lleuger, 3 dies per defecte (rang 2-4) — aplica a totes les B	3 dies per defecte (rang 2-5), activa
C	Cap	1 dia, estàndard

Re-taper (detectar_retaper): quan una B marcada pic_prioritzat cau dins de 4 setmanes després d'una A.

Validació de coherència del pla (Mòdul 4)
ACWR: ratio = volum_setmana / mitjana(volum_ultimes_4_setmanes), zona òptima 0.8–1.3, avís sever si >1.5.
Ràtio càrrega:descàrrega per categoria: junior 2:1, master/absolut 3:1.
Historial real per ACWR: validar_progressio_volum accepta historial_previ: list[int] | None. calcular_volums_setmanals_historial() agrupa historial_jep.json per setmana ISO.
Selecció de model d'entrenament (Mòdul 5)
Taula de decisió per distància (50m-1500m, IM, AAOO) basada en revisió d'evidència real — veure fase2.md per a les fonts.
Determinista per defecte; enriquiment opcional via API de Claude només per a forca_evidencia "sense_evidencia"/"practica_documentada", i només sobre justificacio. Fallback silenciós si la crida LLM falla.
Esquelet de sessions (prerequisit del Mòdul 6)

generar_esquelet_sessions(nedador, microcicle) -> list[Sessio] (src/blondswim/agents/esquelet_sessions.py), 100% determinista. Requereix Nedador.dies_disponibles: list[str] i dia_opcional: str | None. Decideix tipus_sessio per dia i percentatges de cada PartSessio segons tipus_base del microcicle i dies_qualitat. Marca explícitament Sessio.es_dia_opcional quan correspon al dia opcional del nedador. Repartiment de volum_total entre sessions: igual per a totes (assumpció MVP, a refinar). taper/transicio reutilitzen percentatges de descarrega (assumpció MVP, sense columna pròpia al model).

Generació de contingut de microcicle (Mòdul 6)

generar_microcicle(nedador, sessions, metodologia, historial=None) -> list[Sessio] (src/blondswim/agents/generar_microcicle.py). Omple només el camp contingut de cada PartSessio ja creada per l'esquelet; mai toca percentatges, volum, tipus_sessio, dia ni id. Crida l'API amb tool-use forçat. Prompt versionat a src/blondswim/prompts/generar_microcicle.md.

generar_i_validar_microcicle(nedador, macrocicle, setmana, metodologia, pla_taper, avisos_pics_a, historial=None) -> tuple[list[Sessio], list[dict]]: orquestra esquelet → generació → validacio.validar_pla_complet() → guardar_log_decisio() (no bloquejant). Cerca la setmana amb _trobar_microcicle() (numeració global entre mesocicles).

Prova real amb l'API (2026-09-27)

Script manual scripts/prova_generacio_microcicle.py (no forma part de la suite automàtica) va encadenar Mòdul 5 → esquelet → Mòdul 6 contra l'API real amb dades del Jep, i va trobar dos bugs no detectables amb tests mockejats:

Mòdul 6: el prompt no indicava el sessio_id exacte a retornar; l'LLM en va inventar. Fix: llistar explícitament els ids reals al prompt amb instrucció d'eco verbatim.
Mòdul 5: max_tokens=1024 insuficient per completar la crida de tool-use forçat. Fix: max_tokens=4096.

Detall complet a fase2.md.

Ingestió de "Microcicles" (2026-09-28)

convertir_microcicles(fitxer_entrada, mesocicles) -> dict[str, list[Microcicle]] (src/blondswim/ingestion/xlsx_to_json.py), vinculada a Mesocicle.microcicles dins convertir_macrocicle_jep. Capçaleres a la fila 2. Meso (codi curt) es vincula al mesocicle_id pel primer tros del nom del Mesocicle abans de " - ". Tipus de setmana és text compost, detectat per paraula clau. 20 microcicles reals vinculats als 5 mesocicles. Detall complet: fase2.md.

actualitzar_microcicle() — pla dinàmic i reajustable (fet, 2026-09-28)

Implementat com a composició de 4 primitives, totes a generar_microcicle.py, no una funció monolítica (decisió explícita per mantenir el principi "decisions humanes, mai automàtiques"):

actualitzar_volum_microcicle(macrocicle, setmana, nou_volum_objectiu, motiu) — ajust de volum, valida amb ACWR (Mòdul 4), mai bloqueja.
actualitzar_classe_competicio(competicions, competicio_id, nova_classe, motiu) — canvi A/B/C, recalcula taper i espaiat de pics A.
eliminar_competicio(competicions, competicio_id, motiu) — treu la competició del tot (malaltia/lesió), diferent d'una simple baixada de classe.
guardar_log_ajust(nedador_id, setmana, tipus_ajust, valor_anterior, valor_nou, motiu) — log append-only (data/processed/log_decisions/<nedador_id>_<setmana>_ajustos.json), separat del log de metodologia (guardar_log_decisio, que sobreescriu).

El calendari de competicions (list[Competicio]) és un JSON independent (data/processed/calendari.json), no un camp de Macrocicle/Nedador; els pics prioritzats es deriven de classe == "A".

Pendent explícit, no bloquejant: revertir tipus_base de microcicles amb taper obsolet després d'eliminar_competicio() — requereix saber quins microcicles es van marcar taper per aquella competició concreta, i tipus_base ve directament de la ingestió, no d'un càlcul enllaçat. Detall complet: fase2.md.

Resum del model de dades
Nedador: identitat, categoria, proves objectiu, pics prioritzats, mode de ritme (temps/RPE), marques de referència, zones CSS, paràmetres de càlcul de ritme, dies_disponibles/dia_opcional (Fase 2).
Competicio: id, nom, dates ISO, classe A/B/C, piscina (25m/50m/aaoo).
Macrocicle → Mesocicle → Microcicle: estructura niada; Microcicle és a nivell de setmana (volum objectiu, tipus_base, dies_qualitat, test_css, competicio_test_oficial, test_avaluacio, focus_especific), ingerit amb dades reals de la pestanya "Microcicles".
Sessio: referencia el seu microcicle_setmana; es_dia_opcional: bool; EstructuraSessio amb 5 PartSessio (Escalfament, Tècnica+Subaquàtic, Aeròbic/Llindar, Específic/Qualitat, Tornada a la calma), cada una amb 3 percentatges i contingut: str | None (omplert pel Mòdul 6).
SessioRealitzada/SerieRealitzada: registre diari d'entrenament executat, usat per ACWR i few-shot.
DecisioMetodologia (Mòdul 5): prova, categoria, metodologia principal/complementàries, força d'evidència, justificació, avisos.
Regla de reconciliació de ritmes (Ritmes tab)

Dues fonts possibles per a les zones de ritme d'un nedador:

Test CSS (400m+200m) — font preferent quan disponible.
Estimació per millor marca (100m lliure + 50m lliure) — fallback.

La zona Velocitat es calcula de manera diferent segons la font: amb marca, s'ancora a marca_50_lliure × factor_escala_50_100. Amb CSS, s'usa css_pace_100m × factor_velocitat.

Pendent
Refinar assumpcions MVP de l'esquelet de sessions: repartiment de volum per dia i percentatges de taper/transicio.
Revertir tipus_base obsolet després d'eliminar_competicio() (no bloquejant).
(Opcional) wiring automàtic de guardar_log_ajust() dins les tres primitives d'ajust.
Fase 3: generar_macrocicle(nedador_id) (orquestració temporada sencera) + exportador Excel — en curs.
Fase 4: validació golden-reference contra el pla manual del Jep; seguiment dels resultats de tests (CSS, controls B) al llarg de la temporada.
Extensió a Lou (CSS real), Cris i Pere (RPE fins al primer test).
Nota operativa: consum de tokens

Consultes purament de lectura (grep, signatures, estructura de fitxers) es fan directament al terminal, fora d'aider — sense cap crida a LLM. Aider només s'usa per escriure/modificar codi.