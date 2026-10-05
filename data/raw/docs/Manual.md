# BlondSwim — Manual d'ús

*Versió 2026-10-05 · 456 tests · Per al coach (ús setmanal). Detall tècnic: `Architecture.md`; decisions i evidència: `Fase3.md` i `Disseny_proves_objectius.md`.*

## 1. Què fa

BlondSwim planifica l'entrenament de natació de cada nedador per a tota la temporada i en genera el contingut setmana a setmana:

- **Temporada**: periodització enrere des de cada competició A (Base → Build → Peak → Cursa → Transició), volums i descàrregues.
- **Setmana**: rols per dia (aeròbic, qualitat, tècnica, llarga…), pressupost d'intensitat i exercicis de tècnica; l'LLM només redacta els exercicis dins d'aquests límits.
- **Seguiment**: càrrega real (RPE), benestar (SRSS), sèrie de control i **progressió cap a l'objectiu A** amb els resultats de les competicions B/C i les simulacions.

El sistema **avisa i recomana; les decisions són sempre del coach**.

## 2. Instal·lació (un cop)

```bash
make setup
cp .env.example .env        # posa-hi ANTHROPIC_API_KEY
pytest -q && ruff check .
```

Executa sempre els scripts **des de l'arrel del repo**, amb el `.venv` actiu.

> zsh: si enganxes comandes amb comentaris (`# ...`), activa `setopt interactivecomments` (o posa-ho al `~/.zshrc`); si no, zsh intenta executar els comentaris.

## 3. On són les dades

Les dades **no són a git** (`.gitignore`): un `git push` no les puja. Fes-ne còpia de seguretat a part.

```
data/
├── competicions.json          catàleg comú de competicions (tots els nedadors)
└── nedadors/<id>/             una carpeta per nedador (jep, lou, cris, pere)
    ├── nedador.json           fitxa: proves objectiu, ritmes, setmana tipus
    ├── calendari.json         competicions on va el nedador, amb classe i proves
    ├── resultats.json         temps de competicions i simulacions (es crea en registrar-ne un)
    ├── historial.json         sessions reals (exemples per a l'LLM)
    ├── setmanes/              setmana_<id>_<YYYY>-W<ww>.xlsx  (full per a la piscina)
    ├── registres/             registre_<id>_<YYYY>-W<ww>.xlsx (RPE, SRSS, sèrie de control)
    └── log_decisions/         decisions de cada generació
```

Noms de fitxer sempre en **minúscules** i exactament com aquí.

## 4. Configurar un nedador

### 4.1 Fitxa (`nedador.json`)

Camps principals (la resta, vegeu la fitxa del Jep com a model):

```json
{
  "id": "jep",
  "nom": "Jep",
  "categoria": "master",
  "mode_ritme": "temps",
  "proves_objectiu": [
    {
      "prova": "100m Lliure",
      "prioritat": "P",
      "piscina": "25m",
      "nivell_actual": {"millor_marca": "1:17.08", "estimacio_pessimista": "1:20.00"},
      "objectius": [
        {"competicio_id": "2027-01-16_campionat-catalunya-hivern",
         "realista": "1:15.00", "ambicios": "1:12.00"}
      ]
    },
    {"prova": "200m Lliure", "prioritat": "S", "piscina": "50m"}
  ],
  "setmana_tipus": { "...": "..." }
}
```

- **`id`** = nom de la carpeta (minúscules, sense espais ni accents).
- **`prioritat`**: `P` (principal, pes 2) o `S` (secundària, pes 1).
- **`nivell_actual`**: un **rang**, perquè el nivell d'avui és incert: la millor marca (extrem optimista) i el temps que faria ara (extrem pessimista). Si els dos són iguals, la banda de progressió comença tancada (sense marge).
- **`objectius`**: per a cada competició A, un rang: **realista** (≥) i **ambiciós**. En un doble pic (Catalunya + Espanya) n'hi ha prou amb el de la primera A.
- Temps: `"1:17.08"`, `"1'17\"08"`, `"77.08"` o `"38\"86"`.
- Noms de prova: es reconeixen distància i estil; `"100m Lliure"` = `"100 lliures"` = `"100 crol"`, `"100m IM"` = `"100 estils"`.

### 4.2 Catàleg (`data/competicions.json`)

Totes les competicions de qualsevol nedador (circuit, campionats, trofeus…):

```json
{"id": "2026-11-14_etapa-3", "nom": "ETAPA 3 - V Memorial Màster José Cuesta UE Horta",
 "data_inici": "2026-11-14", "data_fi": "2026-11-14", "piscina": "25m"}
```

- `piscina`: `"25m"`, `"50m"` o `"aaoo"` (aigües obertes).
- Si la data no és definitiva, posa un `id` **sense el dia** (`"2027-03_etapa-13"`) i una data provisional: quan es confirmi, només canvies les dates.

### 4.3 Calendari del nedador (`calendari.json`)

**Només les competicions on va el nedador.** Estar-hi = hi va.

```json
{"competicio_id": "2026-11-14_etapa-3", "classe": "C", "proves": ["100m Lliure", "100m IM"]}
```

| Classe | Significat | Efecte a la planificació |
|---|---|---|
| **A** | Objectiu de temporada | Defineix els pics: periodització, Peak i taper de 2 setmanes. Dues A a ≤ 4 setmanes = **doble pic** |
| **B** | Control amb mini-taper | Setmana de competició (taper de 3 dies, volum × 0,8, activació el dia abans) i setmana post-competició |
| **C** | Control sense taper | No canvia la setmana |

- **`proves`**: les que hi nedes. Les proves de les competicions A defineixen el **focus del pic** i el seu pes.
- Una competició del calendari sense proves = encara no decidit (l'informe avisa).

### 4.4 Simulacions (contrarellotge en un entrenament)

```json
{"competicio_id": "2026-10-17_etapa-1", "classe": "B", "tipus": "simulacio",
 "proves": ["100m Lliure", "100m IM"]}
```

o, sense competició del catàleg:

```json
{"competicio_id": "tt-2026-10-21", "classe": "C", "tipus": "simulacio",
 "data": "2026-10-21", "piscina": "25m", "nom": "Contrarellotge 100 IM",
 "proves": ["100m IM"]}
```

- Compta com a **punt de control** de la progressió (calibratge, zona, projecció), marcada `[S]`.
- **No altera la planificació**: cap mini-taper ni setmana post-competició, sigui quina sigui la classe.
- No fa saltar «sense millora» ni «nova millor marca» (no és una cursa oficial).
- Una simulació no pot ser de classe A.

## 5. Cicle setmanal

| Quan | Què | Comanda |
|---|---|---|
| Diumenge / dilluns | Generar la setmana | `make setmana NEDADOR=jep [DILLUNS=2026-10-12]` |
| Durant la setmana | Omplir el full de registre (minuts i RPE de cada sessió, SRSS cada dia, sèrie de control del dimecres) | Excel `registres/registre_jep_<YYYY>-W<ww>.xlsx` |
| Després de cada competició o simulació | Registrar el resultat | `python scripts/registrar_resultat.py ...` (secció 6) |
| Quan vulguis | Veure la progressió | `python scripts/informe_progressio.py --nedador jep` |

`make setmana` equival a `python scripts/generar_temporada.py --nedador jep --dilluns <data>`. Fa, per ordre:

1. Carrega la fitxa, el calendari (resolt amb el catàleg) i l'historial.
2. Avalua la **recuperació** de la setmana anterior (càrrega, SRSS, sèrie de control) a partir dels fulls de registre.
3. Mostra l'**informe de progressió** del pic actiu.
4. Periodifica la temporada i mostra la taula de setmanes (fase, bloc, descàrrega, competicions B/C).
5. Genera el contingut de la setmana amb l'LLM (una crida per sessió de natació) i l'exporta a Excel.
6. Crea el full de registre en blanc (mai en sobreescriu un d'existent).

Revisa sempre els avisos ⚠ de la consola abans d'anar a la piscina.

## 6. Resultats de competició

```bash
python scripts/registrar_resultat.py --nedador jep --competicio 2026-11-14_etapa-3 \
    --prova "100m Lliure" --temps 1:17.60 \
    --parcials 18.1,19.6,20.0,19.9 --bracades 15,16,17,18 --font video
```

- La competició ha de ser al calendari del nedador; si la prova no hi és inscrita, avisa.
- Parcials (cada 25 m) i braçades per llargada són opcionals (vídeo). La suma dels parcials ha de coincidir amb el temps (±0,5").
- Si ja hi ha un resultat d'aquella competició i prova: `--substituir`. Per provar sense desar: `--simular`.
- Abans de modificar `resultats.json`, en desa una còpia `.bak`.
- **Registra només resultats reals**: un temps inventat falseja el calibratge i la projecció.

## 7. Informe de progressió

```bash
python scripts/informe_progressio.py --nedador jep [--data 2026-11-15]
```

Per a cada prova del **pic actiu**:

```
100m Lliure (P, mixt) · objectiu 1'15"0 (realista) – 1'12"0 (ambiciós)
  Competició                 Data   Banda prevista    Resultat  Zona
  [S] Simulació — ETAPA 1    17/10  1'17"1 – 1'20"0   1'18"4    verda
  ETAPA 3 - UE Horta         14/11  1'16"0 – 1'18"9   —
  Calibratge: el realista demana +2.4% i l'ambiciós +6.3% abans del taper
  Projecció a la A: 1'15"8 (1'14"9 – 1'16"7, ±1σ, 2 curses) → camí del realista
  Ritme de cursa de referència: 1'15"0
```

- **Perfil** (mixt, mig_fons…): segons la **durada** de la prova per al nedador, no la distància (< 45 s velocitat, 45-120 s mixt, 120-240 s mig fons).
- **Banda prevista**: on hauria de ser el temps aquell dia. Va del nivell actual (millor marca ↔ estimació pessimista) al temps *sense taper* de la A (objectiu × 1,02).
- **Zona**:

| Zona | Significat | Què fer |
|---|---|---|
| Blava | Més ràpid que la banda | Valorar pujar l'objectiu |
| Verda | Dins la banda | Continuar |
| Groga | Fins a un 1% més lent | Dins del soroll: mirar la tendència i la sèrie de control |
| Vermella | Més d'un 1% més lent | Avís; dues seguides (competicions) → revisar l'entrenament |

- **Mai comparis una competició amb l'anterior**: el progrés entre dues curses (dècimes) és més petit que la variabilitat normal (~0,8%). Compta la zona i la tendència.
- **Calibratge** (primer resultat): quanta millora falta abans del taper. Si el realista demana més d'un 4%, avís per revisar l'objectiu.
- **Projecció** (≥ 2 resultats): tendència fins a la data de la A, menys el taper, amb un interval. Amb poques curses l'interval és ample: és orientativa.
- **Ritme de cursa de referència**: el temps que han de buscar les sèries de ritme de cursa; el realista, o la projecció quan n'hi ha (com a molt l'ambiciós).
- Només compten les competicions de control **de la mateixa piscina que la A** i **posteriors al pic anterior**.

## 8. Test CSS

```bash
python scripts/registrar_test_css.py --nedador jep --t400 6:52.3 --t200 3:18.1 --simular
python scripts/registrar_test_css.py --nedador jep --t400 6:52.3 --t200 3:18.1
```

Protocol: escalfament 15-20 min; 400 m al màxim amb ritme regular (cap 100 més de 2" més ràpid que la mitjana); 5-10 min suau; 200 m al màxim. Comprova que la zona de velocitat surti més lenta que el ritme del 100 de cursa abans de desar. Desa una còpia `.bak` de la fitxa. Les zones canvien tots els ritmes: registra el test **abans** de generar la setmana.

## 9. Avisos més habituals

| Avís | Què vol dir | Solució |
|---|---|---|
| `La competició '…' no és al catàleg` | Un `competicio_id` del calendari no existeix a `competicions.json` | Corregir l'id o afegir la competició al catàleg |
| `falta el nivell actual` / `falta l'objectiu` | Prova del pic sense dades a la fitxa | Omplir `nivell_actual` i `objectius` |
| `la prova no és a la fitxa` | Prova de la A que no és a `proves_objectiu` | Afegir-la a la fitxa (o treure-la de la A) |
| `competicions B/C … (mínim 2)` | Menys de 2 punts de control a la mateixa piscina abans del pic | Afegir competicions o simulacions |
| `l'objectiu realista demana un X%` | Objectiu exigent respecte al nivell | Revisar l'objectiu o confirmar-lo |
| `falta el resultat de …` | Competició B/C passada sense resultat | `registrar_resultat.py` |
| `el 100 IM no es neda en piscina de 50 m` | Prova impossible al calendari | Corregir les proves |
| `nova millor marca` | Resultat de competició més ràpid que la millor marca | Actualitzar `millor_marca` a la fitxa |

## 10. Problemes freqüents (git i terminal)

- **`git am` aturat** («You are in the middle of an am session»): normalment per canvis locals no desats al mateix fitxer. `git stash push <fitxer>`, `git am --abort`, tornar a aplicar el patch i `git stash pop`. No facis `git am --abort` sense mirar abans `git status`.
- **El terminal es queda amb `:`** després d'un `git diff` o `git log`: és el visor; prem `q`. Per evitar-lo: `git --no-pager diff`.
- **`can't open file scripts/...`**: el patch que crea l'script encara no està aplicat (`git log --oneline -5`).
- **Aplicar un patch**: deixa'l a l'arrel del repo, `git am <fitxer>.patch`, `pytest -q && ruff check .`, `git push origin main` i esborra el `.patch`.

## 11. Paràmetres ajustables (fitxa, `parametres_progressio`)

| Paràmetre | Per defecte | Què controla |
|---|---|---|
| `guany_taper` | 0,02 | Millora esperada pel taper de la A |
| `marge` | 0,01 | Soroll entre competicions (zona groga i interval) |
| `exigencia_max` | 0,04 | Millora màxima raonable abans del taper (avís) |
| `min_competicions_control` | 2 | Competicions de control mínimes per prova |

Són punts de partida raonats (dades d'elit i de màsters joves); es calibren amb els resultats de cada nedador.
