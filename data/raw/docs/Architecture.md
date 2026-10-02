# BlondSwim — Arquitectura

*Actualitzat 2026-10-02 — 340 tests, `ruff` net.*

## Decisió d'arquitectura

Pipeline de funcions Python deterministes, amb crides a l'LLM (Claude, via API) només als punts de judici que ho requereixen realment. Es descarta un framework multi-agent complet (LangGraph/CrewAI): la majoria de la lògica (zones, classificació de competicions, periodització, taper, volums, organització setmanal, pressupost d'intensitat, selecció d'exercicis de tècnica, validacions, càrrega i recuperació) és determinista, i passar-la per un LLM només afegiria cost, latència i risc d'al·lucinació en xifres. **L'LLM només redacta els exercicis de cada sessió de natació dins dels límits que fixa el codi.**

**Principis confirmats:**
- **El pla és dinàmic** (2026-09-28): l'estructura de la temporada és el millor punt de partida; es genera el contingut setmana a setmana i es reajusta amb dades reals.
- **Decisions de canvi sempre humanes** (2026-09-28): el sistema valida i avisa (ACWR, espaiat de pics A, franges, alertes de recuperació, recomanació de setmana suau), però mai aplica un canvi sol.
- **Evidència abans que intuïció**: cada regla de planificació està contrastada amb fonts (TrainingPeaks/Friel, revisions científiques) i documentada a `fase3.md`, amb les limitacions explícites quan s'extrapola a màsters.

## Flux d'ús setmanal (Fase 3)

```
nedador_jep.json + calendari.json + historial_jep.json + registres/*.xlsx
        │
scripts/generar_temporada_jep.py [--dilluns YYYY-MM-DD]
        │
        ├─ Recuperació: llegeix els fulls de registre omplerts → càrrega sRPE,
        │  SRSS, sèrie de control → alertes de la setmana anterior
        ├─ generar_macrocicle()          temporada sencera (convenció TrainingPeaks)
        ├─ periodificar_temporada()      ATP enrere des de cada competició A
        ├─ generar_mesocicle()           bloc que conté la setmana, volums i microcicles
        ├─ generar_contingut_setmana()   esquelet determinista → LLM per sessió de natació
        │                                → validació + 1 reintent → avisos
        └─ Sortides: setmana_jep_<YYYY>-W<ww>.xlsx  (full de la piscina)
                     registres/registre_jep_<YYYY>-W<ww>.xlsx  (en blanc, per omplir)

scripts/registrar_test_css.py --t400 --t200   → actualitza ritmes_css del nedador
```

## Capes i mòduls

| Capa | Mòdul | Tipus | Fase | Tests |
|---|---|---|---|---|
| Dades | Models pydantic (`models/`: nedador, calendari, macrocicle, sessio, historial, decisio, **franja**, **registre**) | — | 0-E+I | 24 |
| Dades | Conversor Excel→JSON (`ingestion/xlsx_to_json.py`): calendari, macrocicle, microcicles, ritmes, pretemporada | Determinista | 0-2 | 36 |
| Dades | Ingestió del full de registre setmanal (`ingestion/registre_setmana.py`) | Determinista | E+I | 11 |
| Operativa | Zones CSS (`zones_css.py`) + `ritmes_des_de_test_css()` | Determinista | 1 | 13 |
| Operativa | Context de competició (`context_competicio.py`) | Determinista | 1 | 9 |
| Operativa | Taper (`taper.py`) | Determinista | 1 | 11 |
| Operativa | Periodització ATP (`periodificacio.py`): blocs, descàrregues, doble pic | Determinista | 3 | 14 |
| Operativa | Organització setmanal (`pla_setmanal.py`): rols per dia, pesos de volum, parts i **bloc de cada part**, sèrie de control, pressupost d'intensitat, papallona | Determinista | H/H2 | 35 |
| Operativa | Biblioteca i selector de tècnica (`tecnica.py`, `tecnica/biblioteca_tecnica.json`, 64 exercicis/18 famílies) | Determinista | H2 | 13 |
| Operativa | Esquelet de sessions (`esquelet_sessions.py`): plantilla de 5 dies o esquelet antic, franges i gimnàs | Determinista | 2-E+I | 14 + 11 |
| Validació | `validacio.py`: descàrrega periòdica, ACWR amb historial, taper, **franges natació/gimnàs** | Determinista | 1-E+I | 13 |
| Seguiment | Càrrega real sRPE (`carrega.py`): diària, setmanal, aguda/crònica, alerta +15% | Determinista | E+I | 21 (amb recuperació) |
| Seguiment | Indicadors de recuperació i regla de decisió (`recuperacio.py`): SRSS, sèrie de control | Determinista | E+I | (inclosos) |
| Estratègia | Selecció de metodologia (`seleccio_model.py`) | Determinista + enriquiment LLM opcional | 2 | 32 |
| Estratègia | Macrocicle i mesocicle (`generar_macrocicle.py`) | Determinista + enriquiment LLM opcional | 3 | 24 |
| Estratègia | Contingut de sessions (`generar_microcicle.py`): 1 crida LLM per sessió de natació, tool-use forçat, validació i reintent; primitives d'ajust; logs | LLM (judici) + determinista | 2-3 | 41 |
| Sortida | Full de la piscina (`export/mesocicle_excel.py`) | Determinista | 3 | 9 |
| Sortida | Full de registre setmanal (`export/registre_excel.py`) | Determinista | E+I | (amb la ingestió) |
| Utilitats | Dates (`utils/dates.py`): dilluns, setmanes que creuen d'any | Determinista | G2 | 9 |

**Fases tancades:** Fase 1 (2026-09-27, 62 tests) · Fase 2 (2026-09-28, 144 tests). **Fase 3 en curs** (vegeu `fase3.md`): fets A, B+C+D, F1-F2, G1-G2-G5-G6, H, H2, E+I, estructura de la sessió i script del test CSS.

## Client LLM

`src/blondswim/llm/client.py`: `get_llm_client()` (clau via `.env`/`ANTHROPIC_API_KEY`, `load_dotenv(override=True)`); `DEFAULT_MODEL` via `LLM_MODEL` (per defecte `"claude-sonnet-5"`). Usos: enriquiment opcional de la metodologia (Mòdul 5) i de `fase_objectiu` del mesocicle (fallback silenciós), i generació obligatòria del contingut de cada sessió de natació (`GeneracioMicrocicleError` si falla).

## Generació del contingut d'una sessió

1. **Esquelet determinista** (`esquelet_sessions.py` + `pla_setmanal.py`): rol del dia segons el tipus de setmana (normal, competició dissabte/diumenge, post-competició), volum per pes de rol (± 5%, limitat per `minuts_max_sessio × 40 m/min`), parts del rol en l'ordre de l'estructura recomanada (escalfament → tècnica → bloc o blocs principals → tornada a la calma), sèrie de control fixa el dimecres, exercicis de tècnica obligatoris de la biblioteca, franja de la sessió i sessions de gimnàs informatives.
2. **Prompt** (`prompts/generar_microcicle.md`): context del nedador i zones, rol i descripció, pressupost d'intensitat i de papallona, estructura de parts amb el seu bloc, exercicis de tècnica obligatoris, context de la setmana (competició, altres sessions del dia), resum de les sessions ja generades i few-shot de l'historial real.
3. **LLM**: retorna exercicis estructurats (`series`, `distancia_m` múltiple de 25, `execucio`, `descans`, `material`, `intensitat`, `objectiu`, `id_biblioteca`). El volum el calcula el codi.
4. **Validació** (`_problemes_sessio`): volum fora de rang, pressupost d'intensitat, papallona, regles de natació (estils 100/200, A3 ≥ 50 m), exercicis de tècnica obligatoris. Un sol reintent amb la llista de problemes; si persisteixen, avís al log.

## Regles implementades (resum; detall i fonts a `fase1.md`-`fase3.md`)

- **Competicions**: classes A/B/C; màxim 1-3 A per temporada; separació mínima 8-12 setmanes entre A, excepte **doble pic** (dues A a ≤ 4 setmanes: un sol període competitiu, Peak curt abans de la segona).
- **Periodització (ATP enrere des de cada A)**: Cursa, Peak de 2 setmanes, Build2, Build1, Base, en blocs de fins a 4 setmanes amb descàrrega a l'última; Transició després de la A.
- **Volum**: taula per fase (Base 13.600-15.000, Build 12.000-13.600), terra `volum_setmanal_min` (12.000), taper de Bosquet, setmana amb prova B × 0,8, post-competició = mínim. ACWR com a avís, mai com a regla.
- **Setmana tipus (5 dies)**: Dl aeròbic + cames, Dt qualitat, Dc tècnica en estat fresc + sèrie de control, Dj aeròbic + tècnica, Dv aeròbica llarga + velocitat alàctica; activació 24 h abans de competir; rutina d'espatlla el dissabte.
- **Pressupost d'intensitat per rol i fase** (sense làctic a Base) i **papallona 300-600 m/setmana**.
- **Taper i recuperació** (Mòdul 3): A 14 dies; B 3 dies; C cap.
- **Càrrega i recuperació (E+I)**: sRPE = RPE (CR-10) × minuts; aguda/crònica (7/28 dies); alertes de càrrega (+15%), SRSS (línia base individual ± 1 DE, 2 dies seguits) i sèrie de control (mateix temps amb més esforç o braçades); ≥ 2 alertes → recomanació de setmana suau (decisió del coach).
- **Natació i gimnàs**: màxim 3 sessions al dia (matí/migdia/tarda), com a molt una de natació; avís si el gimnàs és en una franja contigua a la qualitat o el dia de tècnica, activació o recuperació.

## Model de dades

- **`Nedador`**: identitat, categoria, proves objectiu, mode de ritme, marques i `ritmes_css` (+ paràmetres i offsets), `dies_disponibles`, `volum_setmanal_min`, `minuts_max_sessio`, `rutina_espatlla_dia`, `prioritats_tecniques`, **`setmana_tipus`** (`dict[dia, list[SlotSessio]]`; si hi és, `dies_disponibles` se'n deriva).
- **`SlotSessio`**: `franja` (mati/migdia/tarda), `modalitat` (natacio/gimnas/altres), `durada_min`, `opcional`.
- **`Competicio`**: id, nom, dates ISO, classe A/B/C, piscina. Calendari independent a `data/processed/calendari.json`.
- **`Macrocicle` → `Mesocicle` → `Microcicle`**: temporada → bloc (`tipus` Base/Build1/Build2/Peak/Cursa/Transicio) → setmana (`volum_objectiu`, `tipus_base`, `dia_competicio`, `post_competicio`, `sessions_des_de`).
- **`Sessio`**: dia, `franja`, `modalitat`, `durada_min`, `tipus_sessio`, `rol`, `volum_total`/`volum_min`/`volum_max`, `exercicis_tecnica`, `estructura.parts` → **`PartSessio`** (`nom`, **`bloc`**: Escalfament/Tècnica/Bloc principal/Tornada a la calma/Sèrie de control, `fixa`, `exercicis`) → **`Exercici`** (`series`, `distancia_m`, `execucio`, `descans`, `material`, `intensitat`, `objectiu`, `id_biblioteca`).
- **`SessioRealitzada`**: data, `franja`, `modalitat`, `temps_total_min`, `volum_total_m`, `series`, **`rpe_sessio`** (CR-10), **`assoliment`** (1-5), `carrega` (sRPE).
- **`RegistreSRSS`** (4 ítems de recuperació + 4 d'estrès, 0-6) i **`RegistreSerieControl`** (temps de cada 100, braçades/llargada, RPE).
- **`DecisioMetodologia`** (Mòdul 5).

## Regla de reconciliació de ritmes

1. **Test CSS** (400 + 200 m) — font preferent: CSS/100 = (T400 − T200) / 2; A2 = CSS, A3 = CSS − 4", A1 = CSS + 6", Recuperació = CSS + 12", Velocitat = CSS × 0,85. Es registra amb `scripts/registrar_test_css.py`.
2. **Estimació per millor marca** (100 + 50 m lliure) — fallback; la Velocitat s'ancora a la marca de 50 m escalada a 100 m.

## Flux de treball de desenvolupament

- **Canvis grans**: Claude escriu el codi i els tests en un entorn propi i lliura **patches `git am`** (un commit per pas), verificats sobre un clon net del repo; el Jep els aplica i executa `pytest -q && ruff check .`.
- **Aider**: només per a canvis petits d'un sol fitxer (falla en canvis multi-fitxer).
- **Consultes de lectura** (grep, signatures) directament al terminal, sense LLM.
- Proves reals contra l'API abans de confiar en una funcionalitat generativa (els mocks no detecten errors de comportament del model).

## Pendent (detall a `fase3.md`)

- Temps per exercici (Etapa 3b) i validació de cicles respecte al ritme de la zona.
- G3 (continuïtat i dades reals al prompt) i G4 (previsualització N+1).
- Calibrar els llindars de càrrega i recuperació amb dades reals; historial de plans i de tests CSS.
- F3-F7 (volum mòbil, taper exponencial, salt agut, intensitat agregada, cota per temps).
- Fase 4 (validació amb criteri de referència) i Fase 5 (Lou, Cris i Pere).
