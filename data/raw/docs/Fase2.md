# BlondSwim — Fase 2: Mòduls amb LLM (judici)

> **Nota d'actualització (2026-10-02).** Aquest document és històric (Fase 2 tancada). Parts superades per la Fase 3 (detall a `fase3.md`):
> - **Esquelet de sessions**: el repartiment igual del volum i els dies Dl-Dj + dia opcional s'han substituït per la **plantilla setmanal de 5 dies** (Fases H i H2): rols per dia, pesos de volum, parts pròpies de cada rol amb el seu **bloc** (escalfament, tècnica, bloc principal, tornada a la calma), sèrie de control i pressupost d'intensitat. Per a nedadors sense la plantilla es manté l'esquelet antic. `dia_opcional` per defecte és `None`.
> - **Contingut**: `PartSessio.contingut` (text) s'ha substituït per `PartSessio.exercicis` (`Exercici` estructurat; el volum el calcula el codi) i es fa **una crida LLM per sessió** (no una per setmana), amb validació i un reintent.
> - **Historial**: `SessioRealitzada` té ara franja, modalitat, RPE (CR-10), assoliment i càrrega sRPE (Fase E+I); el full de registre setmanal és la nova font de dades reals.
> - **Classificació d'Espanya**: ara és classe A (doble pic, Fase H2).
> - **Flux de treball**: els canvis grans es lliuren com a patches `git am`; aider només per a canvis petits d'un sol fitxer.

Prerequisit complert: Fase 1 tancada (4 mòduls deterministes, 62 tests). Aquesta fase afegeix els punts on l'LLM (Claude API) intervé: seleccionar el model d'entrenament (parcialment — vegeu Mòdul 5) i generar el contingut concret d'un microcicle (Mòdul 6). Tota la resta (zones, taper, validació, esquelet de sessions) segueix sent determinista i s'aplica **abans i després** de la generació LLM, mai substituïda per ella.

**Abast confirmat (2026-09-27)**: categories **absolut i màster**. Junior queda fora d'abast per ara. Cobertura de proves: **totes les de piscina, 50-1500m, tots els estils + IM, i aigües obertes (AAOO)**.

---

## Principi de disseny

- **Separació estricta determinista/LLM**: cap càlcul numèric (volums, %, dates, zones, esquelet de sessions) passa per l'LLM. L'LLM només s'usa on realment aporta — contingut qualitatiu generatiu (Mòdul 6) o enriquiment textual opcional en casos de baixa evidència (Mòdul 5).
- **Few-shot amb dades reals**: `historial_jep.json` (des del 15 d'agost) i `Planificacio_Mesocicles_Jep.xlsx`.
- **Prompts versionats com a fitxers del repo** (`src/blondswim/prompts/*.md`).
- **Validació automàtica post-generació**: tota sortida de l'Agent de Microcicle passa per `validacio.validar_pla_complet` abans de mostrar-se.
- **Log de decisions amb força d'evidència**.
- **Crides LLM mai bloquejants sobre una decisió ja validada**: fallback silenciós si l'enriquiment del Mòdul 5 falla; Mòdul 6 sí que necessita la crida (és generatiu, sense fallback determinista equivalent — un error de l'API es propaga com `GeneracioMicrocicleError`).
- **El pla és dinàmic, no fix** (confirmat 2026-09-28): volum, classe de competició i tipus de setmana són el millor pla *inicial*, no una veritat immutable — han de poder-se reajustar durant la temporada segons evolució real del nedador (vegeu "`actualitzar_microcicle()`" més avall).
- **Decisions de canvi sempre humanes, mai automàtiques**: el sistema valida i avisa (ACWR, espaiat de pics A), però mai decideix per si sol quant baixar un volum, quantes setmanes de represa calen, o si cal canviar la prioritat d'una competició. Es prefereix components petits i composables (canviar volum, canviar classe, eliminar una competició) que el coach combina segons el cas, en lloc d'una funció monolítica que intenti automatitzar tot un escenari (p.ex. "gestionar malaltia").

---

## Ingestió de `PretemporadaSep26-27.xlsx` (fet)

Registre diari real d'entrenament (18 ago - 25 set 2026), granularitat de sèrie (`SerieRealitzada`/`SessioRealitzada`, a `src/blondswim/models/historial.py`), ingerit via `convertir_pretemporada()` a `historial_jep.json`. Zones addicionals trobades: MPLA, TOLA, AeM (text lliure, no forçades a les 5 zones). Ús: bootstrap ACWR (Mòdul 4) i corpus few-shot (Mòdul 6).

**Estat: ✅ Fet.** 6 tests.

---

## Mòdul 5 — Agent de Selecció de Model (`seleccio_model.py`)

Taula de decisió per distància (50m-1500m, IM, AAOO) basada en revisió d'evidència real: USRPT feble per a sprint 50-100m (millor per a 400m+/AAOO), polaritzat amb evidència moderada-forta per 200-400m (estudi amb júniors d'elit, no extrapolable directament a màster), Bowman/escola australiana i AAOO com a pràctica documentada sense assaigs controlats. Fonts completes citades al codi/commit history.

**Disseny final**: taula determinista (cost zero, reproduïble) + enriquiment opcional via API de Claude només per a `forca_evidencia` `"sense_evidencia"`/`"practica_documentada"` (AAOO, IM), i només sobre `justificacio` — mai canvia `metodologia_principal`, `forca_evidencia` ni `avisos`. Fallback silenciós si la crida LLM falla.

```python
def seleccionar_metodologia(
    nedador: Nedador,
    prova_objectiu: str,
    categoria: Literal["absolut", "master"],
    enriquir_amb_llm: bool = True,
) -> DecisioMetodologia:
    ...
```

`DecisioMetodologia` (`src/blondswim/models/decisio.py`): `prova`, `categoria`, `metodologia_principal`, `metodologies_complementaries`, `forca_evidencia`, `justificacio`, `avisos`.

Client LLM: `src/blondswim/llm/client.py` — `get_llm_client()` (clau via `.env`/`ANTHROPIC_API_KEY`), `DEFAULT_MODEL` via `LLM_MODEL` (per defecte `"claude-sonnet-5"`). Reutilitzat pel Mòdul 6.

**Estat: ✅ Fet.** 32 tests, API mockejada. Validat també amb crida real (vegeu més avall).

---

## Mòdul 4 (extensió) — ACWR amb historial real

`validar_progressio_volum` accepta `historial_previ: list[int] | None` (volums reals pre-macrocicle). `calcular_volums_setmanals_historial()` agrupa `historial_jep.json` per setmana ISO. Comportament per defecte idèntic a l'anterior.

**Estat: ✅ Fet.** 5 tests nous.

---

## Esquelet de sessions (determinista, prerequisit del Mòdul 6, fet)

*(Superat per la plantilla setmanal de les Fases H/H2; vegeu la nota inicial.)*

Abans de generar contingut cal construir QUINES sessions té una setmana. Descobert durant el disseny: ni `Nedador` ni `Microcicle` tenien informació de dies d'entrenament disponibles — calia afegir-la.

**Nous camps a `Nedador`** (`src/blondswim/models/nedador.py`):
```python
dies_disponibles: list[str] = ["dilluns", "dimarts", "dimecres", "dijous"]
dia_opcional: str | None = "dissabte"
```
(Cas del Jep: Dl/Dt/Dc/Dj fixos + 1 dia opcional Dv o Ds.)

**`es_dia_opcional` a `Sessio`** (fet, 2026-09-28): el dia opcional queda marcat explícitament (`es_dia_opcional: bool = False` a `src/blondswim/models/sessio.py`, assignat a `generar_esquelet_sessions()` com `es_dia_opcional=(dia == nedador.dia_opcional)`), perquè el pla generat no doni la impressió que és un cinquè dia fix. Testat.

**Nova funció** `generar_esquelet_sessions(nedador, microcicle) -> list[Sessio]` (`src/blondswim/agents/esquelet_sessions.py`):

Regla d'assignació de `tipus_sessio` per dia:
- `tipus_base == "qualitat"`: totes les sessions són `"qualitat"`.
- `tipus_base == "carrega"` i `dies_qualitat == True`: dimecres + dia opcional són `"qualitat"`, resta `"carrega"`.
- `tipus_base == "carrega"` i `dies_qualitat == False`: totes `"carrega"`.
- `tipus_base` a `{"descarrega", "taper", "transicio"}`: totes hereten el mateix tipus.

Percentatges de cada `PartSessio` segons `tipus_sessio` de la sessió (`percentatge_carrega`/`qualitat`/`descarrega`); **assumpció MVP**: `taper` i `transicio` reutilitzen `percentatge_descarrega` (no tenen columna pròpia — a revisar si cal diferenciar-los més endavant).

`volum_total` de cada sessió: `volum_objectiu` repartit a parts iguals entre sessions actives (**assumpció MVP** — repartiment igual, sense pesar per tipus de dia; a refinar si cal donar menys volum als dies de qualitat). L'últim dia absorbeix el residu d'arrodoniment perquè la suma quadri exactament.

Sortida: `Sessio` amb `estructura.parts[].contingut = None` — el Mòdul 6 l'omple.

**Estat: ✅ Fet.** 10 tests (`tests/agents/test_esquelet_sessions.py`).

---

## Mòdul 6 — Agent de Microcicle (`generar_microcicle.py`)

*(El format de sortida i la crida per sessió han canviat a la Fase 3; vegeu la nota inicial.)*

### Objectiu

Omplir `contingut` de cada `PartSessio` de les `Sessio` ja generades per `generar_esquelet_sessions()`, sense tocar-ne mai els percentatges.

### Prompt versionat

`src/blondswim/prompts/generar_microcicle.md` — inclou context del nedador (proves, categoria, zones CSS+offsets), context del microcicle, metodologia del Mòdul 5, estructura fixa de sessions (amb el `sessio_id` real de cada sessió llistat explícitament, per evitar que l'LLM n'inventi), few-shot de `historial_jep.json`, i instruccions explícites (no tocar percentatges, no assumir patró fix de dies, sortida només amb `contingut` per part, retornar el `sessio_id` verbatim).

### Implementació (fet)

```python
def generar_microcicle(
    nedador: Nedador,
    sessions: list[Sessio],  # ja creades per generar_esquelet_sessions()
    metodologia: DecisioMetodologia,
    historial: list[SessioRealitzada] | None = None,
) -> list[Sessio]:
    """
    Crida l'API de Claude (get_llm_client()) amb tool-use FORÇAT
    (schema {"sessions": [{"sessio_id", "parts": [{"nom", "contingut"}]}]})
    per omplir NOMÉS el camp `contingut` de cada PartSessio de cada
    Sessio. Mai toca percentatges, volum_total, tipus_sessio, dia,
    ni id. Few-shot extret amb _extreure_few_shot() (prioritza
    rellevància amb metodologia.metodologia_principal, fallback
    cronològic). Si l'API falla, propaga GeneracioMicrocicleError
    (no hi ha fallback determinista possible aquí). Part sense
    resposta de l'LLM es queda amb contingut=None + log.warning.
    """
```

**`generar_i_validar_microcicle()`** (fet, 2026-09-28): orquestra tot el flux — cerca el `Microcicle` amb la `setmana` demanada entre TOTS els mesocicles del macrocicle via `_trobar_microcicle()` (numeració de setmana global, no reinicia per mesocicle), `raise ValueError` si no la troba; crida `generar_esquelet_sessions()` → `generar_microcicle()` → `validacio.validar_pla_complet()` sobre el macrocicle complet; guarda el log de decisió (`guardar_log_decisio()`, no bloquejant si falla escriure a disc — `except OSError`); retorna `(sessions, avisos)`.

**Estat: ✅ Fet.** 8 tests, API mockejada (cap crida real). Validat també amb crida real (vegeu més avall).

### Log de decisions (fet, 2026-09-28)

`guardar_log_decisio(nedador_id, setmana, metodologia, microcicle_generat=None) -> Path` a `generar_microcicle.py`. Guarda a `data/processed/log_decisions/<nedador_id>_<setmana>.json` (un registre per generació, sobreescriu):
```json
{
  "nedador_id": "...",
  "setmana": 0,
  "timestamp": "...",
  "metodologia": { /* DecisioMetodologia serialitzat */ },
  "microcicle_generat": null
}
```
Crida automàtica des de `generar_i_validar_microcicle()` en cada generació; error d'escriptura (`OSError`) no bloqueja el flux, només `log.warning`.

`guardar_log_ajust(nedador_id, setmana, tipus_ajust, valor_anterior, valor_nou, motiu) -> Path` (fet, 2026-09-28): registra els ajustos fets amb les primitives d'`actualitzar_microcicle()` (volum, classe de competició, eliminació). A diferència de `guardar_log_decisio()`, **afegeix** a una llista en lloc de sobreescriure — hi pot haver diversos ajustos sobre la mateixa setmana al llarg de la temporada. Guarda/actualitza `data/processed/log_decisions/<nedador_id>_<setmana>_ajustos.json`:
```json
[
  {
    "timestamp": "...",
    "tipus_ajust": "volum",
    "valor_anterior": "...",
    "valor_nou": "...",
    "motiu": "..."
  }
]
```
**Nota**: encara no es crida automàticament des de `actualitzar_volum_microcicle()`/`actualitzar_classe_competicio()`/`eliminar_competicio()` — el coach l'invoca explícitament després de cridar la primitiva corresponent. Wiring automàtic queda com a millora futura si cal.

**Estat: ✅ Fet.** 4 tests (`test_guardar_log_decisio`, `test_guardar_log_decisio_sense_microcicle`, `test_guardar_log_ajust_crea_fitxer_amb_una_entrada`, `test_guardar_log_ajust_afegeix_a_fitxer_existent`).

---

## Prova real end-to-end amb l'API de Claude (fet, 2026-09-27)

Script manual (no forma part de la suite automàtica): `scripts/prova_generacio_microcicle.py`. Carrega dades reals del Jep (`nedador_jep.json`, `macrocicle_jep.json`, `historial_jep.json`, 31 sessions) i encadena `seleccionar_metodologia(enriquir_amb_llm=True)` → `generar_esquelet_sessions()` → `generar_microcicle()` contra l'API real (no mockejada). Objectiu: validar qualitativament el contingut generat, cosa que els tests mockejats no poden fer.

La prova va trobar i permetre corregir **dos bugs reals** que la suite mockejada no detectava:

**Bug 1 — Mòdul 6: `sessio_id` no coincidia.** El prompt no indicava explícitament quin `sessio_id` havia de retornar l'LLM per cada sessió; l'LLM en va inventar de nous a partir del nom del dia (`"Dilluns"`) en lloc dels ids reals (`"m1---base_s1_dilluns"`). Resultat: 0% de coincidència, totes les parts es quedaven `contingut=None`, tot i que la crida a l'API "funcionava" (resposta vàlida, simplement amb ids equivocats). **Fix**: el prompt ara llista explícitament el `sessio_id` real de cada sessió i instrueix retornar-lo verbatim. Confirmat amb una segona execució real: les 5 sessions / 25 parts es van omplir correctament amb contingut d'alta qualitat i coherent amb el vocabulari i les zones de ritme reals del Jep.

**Bug 2 — Mòdul 5: `max_tokens=1024` insuficient.** La crida d'enriquiment feia servir tool-use forçat però `max_tokens=1024` no bastava perquè Claude Sonnet 5 completés la crida forçada; la resposta arribava amb `tool_use.input={}` (buit), provocant `KeyError: 'justificacio'`, capturat pel fallback silenciós dissenyat (el pipeline no es trencava, però l'enriquiment no s'aplicava). Diagnosticat afegint `logging.DEBUG` i un log de `stop_reason`, que mostrava que la crida no arribava a `stop_reason: tool_use`. **Fix**: `max_tokens` pujat a `4096`. Confirmat: `stop_reason: tool_use` i justificació ampliada d'alta qualitat, personalitzada per edat, categoria i prova objectiu del Jep, incloent l'honestedat sobre el nivell d'evidència.

Aquests dos bugs reforcen el valor de fer proves reals (no només mockejades) abans de confiar en una funcionalitat generativa: cap dels dos era detectable amb mocks perquè depenien del comportament real del model davant un prompt/límit concrets.

---

## Ingestió de la pestanya "Microcicles" (fet, 2026-09-28)

Objectiu complert: elimina la construcció manual de `Microcicle` que feia servir `scripts/prova_generacio_microcicle.py`, ingerint la pestanya real de l'Excel a `Mesocicle.microcicles`.

**Estructura real (diferent de la primera inspecció, que era incorrecta)**: les capçaleres NO són a la fila 1 (que és un títol), sinó a la **fila 2**: `Setmana, Dates, Meso, Tipus de setmana, Volum objectiu (m), Dies qualitat (Dc+Ds), Test CSS (repetició 6-8 set.), Competició / Test oficial, Test avaluació d'assoliment, Focus específic — Jep`.

Disseny final:
- `convertir_microcicles(fitxer_entrada, mesocicles) -> dict[str, list[Microcicle]]` — rep la llista de `Mesocicle` ja creats per fer-hi el mapatge (no els torna a llegir).
- **`Meso`** conté un codi curt (p.ex. `"M1"`), no el nom complet del mesocicle. Es vincula amb `mesocicle_id` fent `nom.split(" - ", 1)[0].strip().lower()` sobre el `nom` de cada `Mesocicle` (p.ex. `"M1 - Base"` → `"m1"`), comparat amb el valor normalitzat de `Meso`. `Meso` no trobat → `log.warning` i s'ignora la fila (no bloqueja la ingestió).
- **`Tipus de setmana`** és text compost (p.ex. `"Càrrega específica + Test CSS"`), detectat per paraula clau (`descarrega` comprovada ABANS que `carrega`, ja que hi és com a substring). Paraula clau no reconeguda → `raise ValueError` amb el text literal i la fila (mai s'assumeix per defecte).
- **`Dies qualitat (Dc+Ds)`** (bool), **`Test CSS`** (bool, `True` si la cel·la té contingut real), **`Competició/Test oficial`**, **`Test avaluació`** (`str | None`) — dades reals de l'Excel, no calen les assumpcions MVP per defecte que fèiem servir a l'script de prova manual.
- **`notes`**: es guarda el text literal de "Tipus de setmana" (aporta matisos que `tipus_base` per si sol no capta, p.ex. "+ Test CSS").
- **Cas especial (setmana 15, mesocicle M4, "Cap d'Any - Represa progressiva")**: no conté cap paraula clau reconeguda. Mapejat explícitament (no per paraula clau genèrica) a `tipus_base="descarrega"`, basat únicament en el patró de volum d'aquesta temporada (continuació de la descàrrega de la setmana anterior: 12000m, per sota dels 12500m de la setmana 14; torna a càrrega+qualitat a la setmana 16) — no en com es va entrenar la temporada passada, que serveix només com a informació de fons, no com a pauta.

**Estat: ✅ Fet.** 20 microcicles vinculats correctament als 5 mesocicles. 9 tests nous (`tests/ingestion/test_microcicles.py`).

---

## `actualitzar_microcicle()` — pla dinàmic i reajustable (fet, 2026-09-28)

**Motivació**: el pla inicial (volum per setmana dins un rang `volum_min`/`volum_max`, classe de competició A/B/C, tipus de setmana) és el millor punt de partida, no una veritat fixa. Durant la temporada poden canviar: fatiga acumulada del nedador (baixar volum), canvi de classe d'una competició (p.ex. B→C), impossibilitat de competir per malaltia, etc.

**Disseny: components petits i composables, no una funció monolítica.** Es va valorar (2026-09-28) fer una funció única `gestionar_malaltia()` que baixés volum + reclassifiqués competicions automàticament, i es va descartar: trencaria el principi que les decisions de canvi són sempre humanes. En comptes d'això, el coach combina quatre primitives independents segons el cas real:

### Bloc 1 — Ajust de volum (fet)

```python
def _trobar_microcicle(macrocicle: Macrocicle, setmana: int) -> Microcicle:
    """Retorna el Microcicle amb aquesta setmana, cercant a tots els
    mesocicles (numeració global). Raise ValueError si no es troba."""

def actualitzar_volum_microcicle(
    macrocicle: Macrocicle,
    setmana: int,
    nou_volum_objectiu: int,
    motiu: str,
) -> tuple[Microcicle, list[dict]]:
    """Actualitza volum_objectiu del microcicle trobat, recalcula avisos
    amb validacio.validar_progressio_volum() (ACWR) sobre tots els
    microcicles del macrocicle. No regenera sessions ni contingut LLM."""
```

Ús típic per a represa post-malaltia: el coach crida aquesta funció per a cada setmana de represa, amb volum reduït i `motiu="represa post-malaltia"`, tantes vegades com calgui — mai una xifra ni un nombre de setmanes decidits automàticament pel sistema.

`generar_i_validar_microcicle()` reutilitza `_trobar_microcicle()` (extreta d'ell mateix).

**Estat: ✅ Fet.** 2 tests.

### Bloc 2 — Canvi de classe de competició (fet)

El calendari de competicions (`list[Competicio]`, model a `src/blondswim/models/calendari.py`) és un JSON independent (`data/processed/calendari.json`, generat per `convertir_calendari()`), no un camp de `Macrocicle`/`Nedador`. Els pics prioritzats es deriven directament de `classe == "A"` — una sola font de veritat al calendari mateix, sense camp nou a `Nedador`.

```python
def _recalcular_taper_i_pics(competicions: list[Competicio]) -> tuple[list[dict], list[dict]]:
    """Deriva pics_prioritzats (ids amb classe=="A") i retorna
    (pla_taper, avisos_pics_a)."""

def actualitzar_classe_competicio(
    competicions: list[Competicio],
    competicio_id: str,
    nova_classe: Literal["A", "B", "C"],
    motiu: str,
) -> tuple[list[Competicio], list[dict], list[dict]]:
    """Canvia classe d'una Competicio (qualsevol direcció A/B/C, no només
    baixar), recalcula pla_taper i avisos_pics_a amb
    _recalcular_taper_i_pics(). Raise ValueError si id no existeix."""
```

**Estat: ✅ Fet.** 3 tests.

### Bloc 3 — Eliminació completa d'una competició (fet)

Diferent d'un canvi de classe: "el nedador ja no hi competeix" (malaltia, lesió) treu la competició del tot, no la manté al calendari amb menys prioritat.

```python
def eliminar_competicio(
    competicions: list[Competicio],
    competicio_id: str,
    motiu: str,
) -> tuple[list[Competicio], list[dict], list[dict]]:
    """Treu la Competicio del calendari (raise ValueError si id no existeix),
    recalcula (pla_taper, avisos_pics_a) amb _recalcular_taper_i_pics()
    sobre la llista ja sense ella. No compta per res un cop eliminada."""
```

**Pendent explícit, no bloquejant**: revertir el `tipus_base` de microcicles que ja tenien taper assignat a causa d'una competició concreta ara eliminada requereix saber quins microcicles es van marcar taper *per aquella competició* — i ara mateix `tipus_base` ve directament de la ingestió de l'Excel, no d'un càlcul enllaçat al taper. No es resol en aquesta iteració.

**Estat: ✅ Fet.** 3 tests.

### Bloc 4 — Log de decisions ampliat (fet)

`guardar_log_ajust()` (vegeu secció Mòdul 6 més amunt) — registra els ajustos de volum/classe/eliminació en un fitxer append-only separat del log de metodologia.

**Estat: ✅ Fet.** 2 tests.

**Estat global d'`actualitzar_microcicle()`: ✅ Fet i tancat (com a composició de primitives).** 144 tests totals al projecte, lint net. Només queda el pendent explícit del revert de taper anotat al Bloc 3, i el wiring automàtic de `guardar_log_ajust()` dins les tres primitives (opcional, no bloquejant).

---

## Pendent

1. ~~Refinar assumpcions MVP de l'esquelet de sessions~~ — resolt amb la plantilla setmanal (Fases H/H2).
2. Revertir `tipus_base` de microcicles amb taper obsolet després d'`eliminar_competicio()` (pendent de disseny, no bloquejant). Seguiment a `fase3.md`.
3. (Opcional) Cridar `guardar_log_ajust()` automàticament des de les tres primitives d'ajust, en lloc que el coach ho faci explícitament. Seguiment a `fase3.md`.

---

## Pendent general

Seguiment a `fase3.md` (secció «Pendent»).

---

## Nota operativa: consum de tokens (2026-09-28)

A partir d'ara, les consultes purament de lectura (grep, mirar una signatura, inspeccionar l'estructura d'un fitxer) es fan **directament al terminal, fora d'aider**, sense cap crida a LLM. Aider només s'usa per escriure/modificar codi. Motiu: el crèdit de l'API d'Anthropic es va esgotar durant aquesta sessió per l'ús acumulat d'aider en consultes que no requerien cap raonament.
