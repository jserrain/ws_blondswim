# BlondSwim — Full de ruta (sprints)

*Creat 2026-10-02, revisat el mateix dia (coherència amb el calendari i els fitxers). Base: `Fase3.md` (340 tests, `ruff` net).*

> **Actualització 2026-10-05 (llegir primer).**
> - **Fet fora de sprint:** objectius i progressió (proves P/S, pics, bandes, zones, projecció), simulacions i `registrar_resultat.py` (456 tests). Vegeu `Disseny_proves_objectius.md` i `Manual.md`.
> - **Calendari nou** (PDF del Circuit Català): Horta passa al 14/11, Girona al 19/12 (50 m), Cornellà al 17/04. La **Barceloneta (17/10) és una simulació**: la W42 **no** és setmana de competició ni la W43 post-competició (corregeix els punts 2.8 i 3.4). Única B abans del pic 1: **CNSF 12/12** → W50 setmana de competició, W51 post-competició.
> - **Sprint 0:** test CSS ajornat a dilluns 05/10 (piscina tancada); 0.6 fet (calendari refet a mà, no des de l'Excel).
> - **Nou sprint prioritari («Objectius-2»):** planificador setmanal LLM (patch 4) i prompt per focus de prova (patch 5). Recomanat abans del Build (desembre), després de l'Sprint 2.

> **Actualització 2026-10-03.** Dades per nedador a `data/nedadors/<id>/` i catàleg comú `data/competicions.json` (369 tests). Abans de l'Sprint 0, migrar les dades: `python scripts/migrar_a_carpetes.py`. Els scripts reben `--nedador <id>`.

## Criteris d'ordre

1. **Calendari real**: la W41 comença dilluns 05/10, i el Peak d'hivern comença la W53 (28/12).
2. **Dependències**: Etapa 3b → F7; el registre setmanal → G3 i el calibratge; l'historial de plans i de tests CSS → base de càrrega i segon dia de qualitat.
3. **Cost**: els canvis d'un sol fitxer es fan amb aider. Els multi-fitxer es lliuren com a patches `git am` (un commit per pas).

**Ruta crítica:** test CSS → Sprint 1 → Etapa 3b + cicles → G3 → F4 abans de desembre.

**Setmanes amb competició B (afecten la plantilla):** ~~W42 (Barceloneta) i W43 post~~ (ara simulació) · ~~W45-W46 (UE Horta)~~ (ara C, 14/11) · **W50 (CNSF, ds 12/12) i W51 post**. Les C i les simulacions no canvien la plantilla.

---

## Sprint 0 — Cap de setmana 03-04/10 (coach, sense codi)

- [ ] **0.1** Dissabte: fer el test CSS (400 + 200 m, esforç repartit).
- [ ] **0.2** Simular el registre:
  ```bash
  python scripts/registrar_test_css.py --t400 <T400> --t200 <T200> --data 2026-10-03 --simular
  ```
- [ ] **0.3** Comprovar que la Velocitat (CSS × 0,85) és **més lenta** que el ritme del 100 de cursa. Si no ho és, ajustar l'offset abans de desar.
- [ ] **0.4** Registrar-lo de debò (sense `--simular`). Es crea una còpia `.bak` del JSON.
- [ ] **0.5** Confirmar l'ordre de l'aeròbica llarga (velocitat alàctica al principi o al final). Si cal canviar-lo, s'ha de fer a `PARTS_ROL` abans del pas 0.6.
- [ ] **0.6** Calendari: copiar el `Provisional26-27.xlsx` corregit a `data/raw/`, executar `make run-ingestion` i comprovar a `data/nedadors/jep/calendari.json` que Espanya d'Hivern és **classe A**, i a `data/competicions.json` que té les dates **06-07/02/2027** i que les dues proves de Budapest (aigües obertes i piscina) hi són.
- [ ] **0.7** Regenerar la W41:
  ```bash
  python scripts/generar_temporada.py --nedador jep --dilluns 2026-10-05
  ```
- [ ] **0.8** Revisar la W41 contra la taula de l'Etapa 4 (distribució per zones, papallona, volums per sessió, cicles). Anotar els problemes per a l'Sprint 2.
- [ ] **0.9** Decidir quin pla es neda la W41: el generat o el manual de la pestanya `Oct` del `Provisional` (setmana 10).

**Fet quan:** les zones del test estan desades, `calendari.json` és correcte i la W41 està revisada i llesta per a la piscina.

---

## Sprint 1 — Abans de dilluns 05/10 (canvis petits)

Objectiu: que la W41 surti sense soroll i que les dades comencin a acumular-se des del primer dia.

- [ ] **1.1 Avís de gimnàs** (`validacio.py`, aider). Avisar només si el gimnàs va **abans** de la tècnica o de l'activació el mateix dia. Test: el dimecres del Jep (natació al matí, gimnàs a la tarda) no ha d'avisar.
- [ ] **1.2 `--nomes-registre`** (`generar_temporada.py`, aider). Crea el full de registre de la setmana sense fer cap crida a l'API.
- [ ] **1.3 Historial de plans** (patch). En cada generació, desar el pla a `data/nedadors/<id>/plans/plan_<id>_<YYYY>-W<ww>.json` (afegir la ruta a `RutesNedador`): `volum_objectiu`, `tipus_base`, rol i volum de cada sessió. Mai sobreescriure sense un `.bak`. Prerequisit del punt 5.3.
- [ ] **1.4 Historial de tests CSS** (patch). Fer que `registrar_test_css.py` afegeixi una entrada (data, T400, T200, CSS) a `historial_tests_css`, a més de desar `ritmes_css`. Migrar el test del pas 0.4 a l'historial. Prerequisit del segon dia de qualitat.
- [ ] **1.5** Executar `pytest -q && ruff check .`.

**Fet quan:** la W41 no té el fals positiu de dimecres i existeixen els fitxers de pla i d'historial de CSS.

---

## Sprint 2 — Setmana del 05/10, abans de generar la W42 (prioritat màxima de codi)

Etapa 3b i validació de cicles, en un sol bloc de patches perquè comparteixen el parser.

- [x] **2.1 Parser de descans** (`utils/descans.py` o similar):
  - `c/1'40"` és un cicle (temps total de la repetició).
  - `d/15"` és un descans després de nedar.
  - Accepta formats com `1'40"`, `1:40`, `40"` i `15 s`.
  - Si no el sap llegir, retorna `None` i un avís (mai falla).
- [x] **2.2 Temps de nedar per repetició**: ritme de la zona (`ritmes_css`) × distància / 100. Per a zones sense ritme (MPLA, TOLA, cames, tècnica), usar un factor configurable sobre A1 o la Recuperació.
- [x] **2.3 Temps per exercici**:
  - Amb cicle: `series × cicle`.
  - Amb descans: `series × (nedar + descans)`.
  - El temps de la sessió és la suma de tots els exercicis.
- [x] **2.4 Validació de cicles** a `_problemes_sessio()`:
  - Si el cicle és més curt que el temps de nedar més un marge mínim, és un problema (p.ex. `4x100 A2 c/15"`).
  - Si el cicle és massa llarg per a la zona (A3 o velocitat sense recuperació completa), és un avís.
  - Els problemes entren al reintent únic.
- [x] **2.5 Excel**: omplir la columna `Temps (min)` per exercici i el total de la sessió.
- [x] **2.6 Prompt**: afegir la regla «`c/` = cicle total, `d/` = descans», amb un exemple per zona.
- [x] **2.7 Tests**:
  - Parser: tots els formats i els casos invàlids.
  - Càlcul de temps.
  - Cicle impossible, que provoca el reintent.
  - Excel amb la columna `Temps` plena.
- [ ] **2.8 Prova real contra l'API**: generar la W42 i revisar els cicles i els temps. **La W42 és setmana de competició** (Barceloneta, B, dissabte 17/10): s'espera activació el divendres (sense aeròbica llarga), qualitat el dimarts i volum × 0,8 (taper B). Comprovar també que no surt rutina d'espatlla el dissabte.
- [ ] **2.9 F7 — cota per temps**: substituir el límit `minuts_max_sessio × 40 m/min` pel temps calculat. Si la sessió supera `minuts_max_sessio`, és un problema i entra al reintent.

**Fet (codi, 06/10):** `agents/cicles.py` (parser `c/`/`d/`, temps per exercici i sessió amb factor d'estil, correcció automàtica dels `c/` impossibles a `d/`, descans mínim per zona, durada màxima), taula de cicles al prompt, `Temps (min)` a l'Excel, farciment ampliat («placeholder_removed», «Nota: …») i fins a 2 reintents dirigits quedant-se la millor versió. Decisions: un `c/` impossible no fa reintentar, es converteix; un descans insuficient sí. Pendent: 2.8 (prova real) i, de la 2.9, treure la cota aproximada de 40 m/min de l'esquelet (la durada ja es valida amb el temps calculat).

**Sprint 2b (06/10, després de la primera W41 amb l'Sprint 2):** notació `c/m:ss` i `d/m:ss` a tot arreu (les cometes trencaven el JSON dels reintents); descans validat només per a l'estil complet (cames, aletes, paracaigudes i tècnica, temps aproximat) amb factors de temps a la fitxa; distàncies i volums segons la piscina (25 per defecte, `PISCINA=50`) i distàncies no vàlides tornades a l'LLM en lloc d'arrodonir-les; biblioteca amb les dosis en múltiples de 25 (els «4x(12,5 + 12,5)» i «4x15 m» feien sortir 12 i 24 m); papallona tècnica només a la sessió de tècnica, amb el detall per exercici al reintent; marge de volum per sessió del 10% al 5% i avís si la setmana es desvia més d'un 5%.

**Sprint 2c (06/10, segona W41 amb el 2b: 16.425 m, +21%):** l'LLM no quadra els metres ni amb reintents → el volum l'ajusta el codi (`ajustar_volum`: sèries del bloc principal, sense tocar la biblioteca ni les parts fixes); comptador de papallona sense falsos positius (estils amb la papallona de cames de dofí, «braços estirats», «sense braçada»); pressupost d'A3 arrodonit a 100 amunt (4x50 = 200); «skip» com a farciment. Causes del sobrevolum (anàlisi): el prompt deia «no cal quadrar exactament», el rang no aclaria si incloïa la sèrie de control, les dosis obligatòries de la biblioteca no hi cabien, arrodoniment a l'alça per part i cap suma acumulada al format de resposta. Correccions: conveni de l'entrenador (sessió i parts a múltiples de 100, l'última part fa la resta; mètode del residu més gran), metres exactes per part al prompt, camp `metres_part` obligatori, dosi de la biblioteca dins dels metres de la part i ajust per part.

**Sprint 2d (06/10, tercera W41: 13.800 m, +1,5%):** papallona amb l'opció intermèdia de l'entrenador (≤150 m/sessió, 300 m el dia de tècnica, 600-900 m/setmana, repeticions de 25-50 m, mai a la calma); repartiment orientatiu per estils al prompt (esquena i braça 15%, 20% a tècnica) i resum per estils a la consola; estils sense papallona no compten; l'ajust de volum no baixa de 2 sèries ni de la meitat i no toca les rotacions d'estils; els exercicis obligatoris de la biblioteca que falten els afegeix el codi.

**Sprint 2e (06/10, quarta W41: 13.600 m exactes):** el codi retalla les intensitats per sobre del pressupost (velocitat 400/300 al dimarts) i corregeix els descansos curts d'A1/Rec sense reintent; avís quan un reintent no retorna parts; estils i papallona com a franges al prompt; avisos d'estils de la setmana a la consola.

**Sprint 3 (06/10): sèries de ritme objectiu.** Decisió de l'entrenador: una sèrie per prova P (100 L dimarts, 100 IM dijous) que va de l'estimació pessimista a l'objectiu realista del pic (sense taper), amb la forma per fase (ritme, densitat, volum) i la progressió condicionada als temps registrats (dins → +1, molt per sota → +2, per sobre → es manté; 2 per sobre → −1). Part fixa a la sessió, pestanya nova al registre (també s'afegeix als fulls ja creats), resum a la consola. Mòdul `agents/ritme_objectiu.py`.

**Estructura de la sessió (06/10, decisions de l'entrenador):** sèrie de control després de la tècnica (opció A); sèrie objectiu abans de la qualitat i seguida de 200 m de recuperació activa (ordre i recuperació activa amb base: Sports 2023 sobre l'ordre de sèries; Toubekis 2008 i Kostoulas 2018 sobre recuperació activa); cames dins de l'escalfament (~150 m) i sense part pròpia; tornada a la calma = nedar suau, la resta dels metres.

**Fet quan:** la W42 té `Temps (min)` ple, cap cicle impossible, cap sessió supera els 105 min i l'estructura correspon a una setmana de competició B.

---

## Sprint 3 — Setmana del 12/10 (amb el registre de la W41 omplert)

G3, continuïtat al prompt.

- [ ] **3.1** Afegir al context del prompt:
  - La posició dins el mesocicle: «setmana X de Y, fase Z, la propera setmana és de descàrrega».
  - El resum de la setmana anterior: volum planificat vs realitzat, rols i exercicis de tècnica fets.
  - Les dades reals: RPE mitjà per rol, assoliment, SRSS (recuperació i estrès) i la sèrie de control.
  - Les alertes actives i la recomanació de `avaluar_setmana`, si n'hi ha.
- [ ] **3.2** Instrucció al prompt: si l'RPE de la setmana anterior va ser més alt que el planificat o hi ha alertes, prioritzar la qualitat d'execució abans que la densitat, **sense** sortir del pressupost d'intensitat.
- [ ] **3.3** Si no hi ha dades reals, el prompt queda igual (sense trencar res).
- [ ] **3.4** Tests (prompt amb dades i sense dades) i una prova real generant la W43. **La W43 és post-competició**: dilluns de recuperació activa, qualitat el dijous i objectiu = mínim setmanal (12.000 m). Incloure al context el resultat de la prova B del 17/10.

**Fet quan:** el prompt de la W43 inclou dades reals de la W41/W42.

---

## Sprint 4 — Octubre (paquet de validació, un patch)

- [ ] **4.1 F5** — Avís de salt agut de volum a `validacio.py`: un salt setmanal per sobre d'un llindar respecte a la setmana anterior, excloent les represes després d'una descàrrega.
- [ ] **4.2** Fer que `cap_competicio_a_restant` digui a partir de quina setmana s'aplica.
- [ ] **4.3** Cablejar `guardar_log_ajust()` dins de les tres primitives d'ajust.
- [ ] **4.4** Revertir el `tipus_base` obsolet després d'`eliminar_competicio()`: enllaçar el taper amb la competició que l'origina.
- [ ] **4.5** Budapest a la setmana 26: **no és un duplicat**. Són dues proves (aigües obertes 29-30/06 i piscina 03-09/07). No eliminar-ne cap; tractar-les com un sol bloc competitiu (un sol taper, abans de la primera) i evitar avisos repetits. Depèn de la decisió de classe (7.1).
- [ ] **4.6** Executar `pytest -q && ruff check .`.

---

## Sprint 5 — Principis de novembre (~W44-45, amb 3-4 setmanes de dades)

- [ ] **5.1 Calibrar llindars**: revisar les alertes reals (falsos positius i negatius) de càrrega +15%, de l'SRSS (±1 DE, 2 dies) i de la sèrie de control. Ajustar els paràmetres i documentar-ho.
- [ ] **5.2 F3 — base de volum mòbil**: EWMA de 4-6 setmanes del volum realitzat, reutilitzant `carrega.py` i excloent descàrrega, taper i transició. Font: el registre real (`data/nedadors/<id>/historial.json` + fulls de registre), no les pestanyes de novembre-febrer del `Provisional` (són de la 25-26 i `Gen` és una còpia de `Desc`).
- [ ] **5.3 Base de càrrega**: amb l'historial de plans (pas 1.3), excloure les setmanes de descàrrega, taper i transició i aplicar el `ratio_planificat` a l'alerta del +15%.

---

## Sprint 6 — Abans de mitjans de desembre (data límit: el Peak de la W53)

- [ ] **6.1 F4 — taper exponencial**: calcular-lo sobre el volum mitjà del Build2 (Bosquet: −41-60%), amb el doble pic inclòs (Peak d'1 setmana abans d'Espanya).
- [ ] **6.2** Generar en sec les setmanes W53 a W6 i revisar-les.
- [ ] **6.3 F6** (si hi ha temps) — Control agregat d'intensitat per mesocicle.
- [ ] **6.4 Coach**: revisar la biblioteca de tècnica (`Biblioteca_tecnica_v1_families.xlsx`).

---

## Després de l'hivern (febrer 2027)

- [ ] **7.1 Coach**: decidir la classe del Mundial de Budapest (les dues proves), com a molt a la Transició de la W6.
- [ ] **7.2** Regla del segon dia de qualitat (2 blocs sense alertes i CSS millorant), amb l'historial de tests CSS.
- [ ] **7.3 Fase 4**: validació amb un criteri de referència. Les dues A d'hivern són el primer punt de comparació.
- [ ] **7.4 Fase 5**: Lou (amb CSS real), Cris i Pere (per RPE fins al primer test), cadascun amb la seva `setmana_tipus`.

## Només si cal (sense data)

- G4 — previsualització de la setmana N+1 com a esborrany.
- Dues sessions de natació el mateix dia o franja «vespre».
- Model «judge» configurable (`BLONDSWIM_LLM_PROVIDER`). Vegeu «Jutge LLM» a sota.

## Jutge LLM (verificació semàntica, en curs)

El codi valida les regles dures (volum, pressupost, papallona, cicles i descansos); el jutge només fa el judici semàntic: natació real, segur, part correcta, intensitat coherent, terminologia real, sense farciment. Rep els fets ja calculats pel codi («descans real 7 s») i els temps sense cometes («1:45», «15 s»), que trencaven el JSON.

Proves manuals amb Qwen3-30B-A3B local (06/10): sense context falla; amb rúbrica encerta «surar» i el descans, però s'inventa que l'IM no pot ser A1 i el veredicte canvia amb petits canvis de prompt. Conclusió: mesurar sobre un joc de casos i ensenyar el criteri amb exemples.

- [x] **J.1** `agents/jutge.py` (prompt amb rúbrica i few-shot, esquema amb un veredicte i una categoria per exercici, crida a una API compatible amb OpenAI) i `scripts/avaluar_jutge.py`.
- [x] **J.2** Joc de prova `data/raw/jutge/casos.jsonl`: 39 exercicis en 7 parts, 13 errors plantats.
Primera avaluació (06/10, Qwen3-30B-A3B, 38 exercicis):

| Configuració | Encert | Detecció | Falsos positius | s/crida |
|---|---|---|---|---|
| sense raonar, amb exemples | 58% | 85% | 56% | 5,5 |
| raonant, amb exemples | 74% | 92% | 36% | 17,5 |
| sense raonar, sense exemples | 66% | 77% | 40% | 5,4 |

Detecta bé, però rebutja massa: jutjava els descansos tot i dir-li que no, no coneixia termes reals (TOLA, ritme de cursa, paracaigudes, pull, negatiu, doble braç) i marcava com a error que faltés informació. Canvis (v2): el jutge ja no veu descansos ni ritmes, format estructurat, glossari, presumpció de validesa; les normes de l'entrenador comprovables pel text (polze arrossegant, «Ei») passen al codi (`pla_setmanal.problemes_normes`), i al joc de prova se substitueixen per un insegur (llast al canell) i un terme inventat.

- [ ] **J.3 Coach**: revisar els veredictes esperats del joc (sobretot els marcats `dubtos`).
- [ ] **J.4** Avaluar Qwen3 sense raonar, Qwen3 raonant i Gemma 3 27B; també sense exemples (`--sense-exemples`) per mesurar què aporten.
- [ ] **J.5** Decisió: detecció ≥ 85% i falsos positius ≤ 10% → primer filtre local amb el núvol de reserva; si no, mode ombra (registra, no rebutja).
- Contingut de gimnàs generat.

---

## Calendari resum

| Quan | Sprint | Clau |
|---|---|---|
| 03-04/10 | 0 | ~~Test CSS~~ (→ 05/10), calendari refet ✅, generar la W41 |
| 04-05/10 | — | Objectius, progressió i simulacions ✅ |
| fins al 05/10 | 1 | Avís de gimnàs, `--nomes-registre`, historials |
| setmana del 05/10 | 2 | Etapa 3b, cicles, F7 → W42 (competició B) |
| setmana del 12/10 | 3 | G3 → W43 (post-competició) |
| octubre | 4 | F5 i pendents menors (Budapest com a bloc) |
| oct-nov | Objectius-2 | Planificador setmanal LLM i prompt per focus de prova |
| ~W44-45 | 5 | Calibratge, F3, base de càrrega |
| abans del 15/12 | 6 | F4 taper (Peak de la W53) |
| febrer 2027 | 7 | Mundial, segon dia de qualitat, Fases 4-5 |
