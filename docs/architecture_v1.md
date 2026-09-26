BlondSwim — Arquitectura
Decisió d'arquitectura

Pipeline de funcions Python deterministes, amb crides a l'LLM (Claude, via API) només als punts de judici que ho requereixen realment. Es descarta un framework multi-agent complet (LangGraph/CrewAI) per a l'abast de l'MVP: la majoria de lògica (càlcul de zones, classificació de competicions, taper, validacions) és determinista i no aporta res passar-la per un LLM — només cost, latència i risc d'al·lucinació en xifres.

Dos entry points previstos (Fase 3): generar_macrocicle(nedador_id) i actualitzar_microcicle(nedador_id, setmana, feedback).

Capes i agents
Capa	Agent/Mòdul	Tipus	Fase	Estat
Dades	Models pydantic (Nedador, Competicio, Macrocicle/Mesocicle/Microcicle, Sessio)	—	0	✅ Fet
Dades	Conversor Excel→JSON (xlsx_to_json.py)	Determinista	0	✅ Fet
Operativa	Zones CSS (zones_css.py)	Determinista	1	✅ Fet
Operativa	Context de competició (context_competicio.py)	Determinista	1	🔲 Dissenyat, pendent implementar
Operativa	Taper (taper.py)	Determinista	1	🔲 Dissenyat, pendent implementar
Validació	Validació fisiològica/temporal (validacio.py)	Determinista	1	🔲 No dissenyat
Estratègia	Selecció de model d'entrenament	LLM (judici)	2	🔲 No iniciat
Estratègia	Generació de microcicle	LLM (judici)	2	🔲 No iniciat
Estratègia	Ajust per feedback subjectiu/test periòdic	LLM (judici)	2	🔲 No iniciat
Sortida	Exportador Excel + resum Markdown	Determinista	3	🔲 No iniciat
Regles de classificació i taper (revisades — TrainingPeaks/Joe Friel)

Font: document de periodització TrainingPeaks/Joe Friel compartit pel Jep (2026-09-26). Substitueix el disseny original de 3 regles simples.

Classificació de competicions (Mòdul 2)
Classes A/B/C ja existents al calendari (Provisional26-27.xlsx).
Nova validació: màxim 1-3 competicions classe A per temporada; mínim 8-12 setmanes de separació entre A consecutives (12-16 per esports de resistència llarga). Si dues A cauen massa properes, la segona es tracta de facto com a B — decisió de l'entrenador, mai automàtica i silenciosa.
Cas real ja coherent amb aquesta regla sense necessitat de canvis: Espanya (4-7 feb 2027) és classe B, no A, precisament perquè cau a ~3 setmanes de Catalunya Hivern (16-17 gen) — per sota del mínim de separació entre A's. El document confirma metodològicament una decisió ja presa.
Taper i recuperació (Mòdul 3)
Classe	Taper pre-competició	Recuperació post-competició
A	Progressiu, 7-21 dies	1-3 setmanes
B	Lleuger, 2-4 dies (aplica a totes les B, prioritzades o no)	2-5 dies, activa
C	Cap	1-2 dies, estàndard

Canvi respecte al disseny original: abans només les B marcades com a pic_prioritzat rebien algun ajust pre-competició; ara totes les B reben el micro-taper lleuger. També s'afegeix la recuperació post-competició obligatòria per a les 3 classes, que no existia al disseny original.

Re-taper (sense canvis)

Quan una competició B marcada com a pic_prioritzat cau dins de 4 setmanes després d'una A, s'activa sempre un re-taper dedicat. La càrrega de la setmana de re-càrrega (no el fet d'aplicar-lo) es determina per checkpoint subjectiu (son, DOMS, motivació, RPE) 4-5 dies post-pic A.

Detall complet de funcions i prompts d'implementació: veure fase1.md.

Resum del model de dades
Nedador: identitat, categoria, proves objectiu, pics prioritzats, mode de ritme (temps/RPE), marques de referència, zones CSS (font: test CSS o estimació per marca), paràmetres de càlcul de ritme.
Competicio: id, nom, dates ISO, classe A/B/C, piscina (25m/50m/aaoo).
Macrocicle → Mesocicle → Microcicle: estructura niada; cada mesocicle té volum (min/max/mitjà), fase/objectiu, metodologia dominant, tancament, focus tècnic i específic.
Sessio: 5 parts (Escalfament, Tècnica+Subaquàtic, Aeròbic/Llindar, Específic/Qualitat, Tornada a la calma) amb percentatges variables segons tipus de setmana.
Regla de reconciliació de ritmes (Ritmes tab)

Dues fonts possibles per a les zones de ritme d'un nedador:

Test CSS (400m+200m) — font preferent quan disponible.
Estimació per millor marca (100m lliure + 50m lliure) — fallback.

La zona Velocitat es calcula de manera diferent segons la font, per evitar el bug físic detectat durant el disseny (una Velocitat calculada per marca_100 × 0.85 podia sortir més ràpida que el propi rècord personal, cosa impossible): amb marca, s'ancora a marca_50_lliure × factor_escala_50_100, no a la marca de 100m. Amb CSS, s'usa css_pace_100m × factor_velocitat, que sí és vàlid fisiològicament perquè el CSS és un ritme submàxim.

Pendent
Implementar Mòduls 2 i 3 (context_competicio.py, taper.py) — dissenyats, prompts d'aider llestos a fase1.md.
Dissenyar i implementar Mòdul 4 (validacio.py).
Ingestió de la pestanya Microcicles (encara no coberta pel conversor).
Fase 2: Agent de Selecció de Model + Agent de Microcicle (LLM) — és el que permetrà demanar la planificació completa un cop hi hagi test CSS + calendari B/C confirmat.
Fase 4: validació golden-reference contra el pla manual del Jep.
Extensió a Lou (CSS real), Cris i Pere (RPE fins al primer test).