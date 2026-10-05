# BlondSwim — Disseny: proves objectiu, planificador setmanal i avaluació de la progressió

*2026-10-05 (rev. 4) · Estat: **patches 1-3, correcció del pic 2 i simulacions aplicats** (456 tests); pendents 4-5 (planificador LLM). Abast: **pic 1** (campionats d'hivern); el pic 2 queda modelat però no s'implementa.*

## 0. Decisions preses

| # | Decisió | Data |
|---|---|---|
| 1 | Cada prova té prioritat **P** (principal) o **S** (secundària) a la fitxa del nedador; pesos **P = 2, S = 1** | 2026-10-04 |
| 2 | Els **pics es calculen del calendari** (competicions A); un doble pic (Catalunya + Espanya) és un sol pic | 2026-10-04 |
| 3 | Les proves de cada competició (A, B, C) van al calendari del nedador | 2026-10-04 |
| 4 | El perfil de la prova es classifica per **durada** (temps del nedador), no per distància | 2026-10-04 |
| 5 | La metodologia depèn de la **fase** de la temporada, no d'una sola prova | 2026-10-04 |
| 6 | El repartiment setmanal entre proves el decideix un **LLM planificador**, dins de límits fixats pel codi; el coach **aprova el pla** abans de redactar les sessions | 2026-10-04 |
| 7 | El pes de cada prova surt de l'**objectiu A**: les proves nedades a la competició A són el focus | 2026-10-04 |
| 8 | Objectiu A com a **rang**: extrem realista i extrem ambiciós; Espanya hereta l'objectiu de Catalunya | 2026-10-04 |
| 9 | Les B i C tenen **objectius progressius** cap a l'A i serveixen per avaluar i modificar l'entrenament | 2026-10-04 |
| 10 | Rangs, objectius i proves de cada competició: **per nedador**, els omple el coach a la fitxa i al calendari | 2026-10-04 |
| 11 | Les curses es **graven en vídeo** per extreure'n parcials i braçades | 2026-10-04 |
| 12 | El **nivell actual és incert**: es dona com a rang (millor marca ↔ estimació pessimista), no com la millor marca | 2026-10-04 |
| 13 | **50 papallona fora** de les proves objectiu (distorsiona l'entrenament) | 2026-10-04 |
| 14 | Paràmetres inicials `guany_taper` 2% i `marge` 1%, calibrables amb dades | 2026-10-04 |
| 15 | El **calendari del nedador només conté les competicions on va** (estar-hi = hi va); el catàleg les té totes | 2026-10-04 |
| 16 | Catàleg nou a partir del PDF del Circuit Català 2026-27; una competició sense data definitiva porta un `id` sense el dia | 2026-10-04 |
| 17 | **Simulacions** (contrarellotge en entrenament): punts de control de la progressió que no alteren la planificació | 2026-10-05 |
| 18 | Les competicions de control d'un pic són les posteriors al pic anterior | 2026-10-04 |

**Jep (calendari 2026-10-05):** pic 1 = 100 lliure (P) i 100 IM (P), 50% cadascun; el 200 lliure (S) no es neda a les A d'hivern i passa a ser només del pic 2 (100 lliure + 200 lliure). Control del pic 1 (25 m): simulació Barceloneta 17/10, Horta 14/11 (C), Granollers 28/11 (C), CNSF 12/12 (B).

## 1. Problema actual

- La metodologia es tria per `proves_objectiu[0]` (50 papallona) i s'aplica a totes les sessions de la temporada; l'`estil_preferent` del prompt també és aquesta prova.
- La regla «≤ 100 m → Sprint/Tècnica» fa servir distàncies d'elit: per al Jep, el 100 lliure (1'17") i el 100 IM (1'38") són proves mixtes, no esprints.
- No hi ha cap mesura de **rendiment**: el sistema controla càrrega i recuperació, però no si el nedador millora cap a l'objectiu.

## 2. Model de dades

### 2.1 Fitxa del nedador (`data/nedadors/<id>/nedador.json`)

`proves_objectiu` passa de llista de textos a llista d'objectes. El **nivell actual** és un rang: la millor marca (extrem optimista) i el temps que el coach estima que faria ara (extrem pessimista). Els objectius van lligats a la competició A.

```json
"proves_objectiu": [
  {"prova": "100m Lliure", "prioritat": "P", "piscina": "25m",
   "nivell_actual": {"millor_marca": "1:17.08", "estimacio_pessimista": "1:20.00"},
   "objectius": [{"competicio_id": "2027-01-16_campionat-catalunya-hivern",
                  "realista": "1:15.00", "ambicios": "1:12.00"}]},
  {"prova": "100m IM",     "prioritat": "P", "piscina": "25m", "nivell_actual": {...}, "objectius": [...]},
  {"prova": "200m Lliure", "prioritat": "S", "piscina": "25m", "nivell_actual": {...}, "objectius": [...]}
]
```

- Compatibilitat: una llista de textos antiga es llegeix com a proves P sense objectius.
- En un doble pic, l'objectiu de la primera A val per a la segona si no se n'especifica cap.
- `marques_referencia` es manté (zones per marca); el 50 papallona hi pot continuar com a referència, però ja no és prova objectiu.
- `ritmes_cursa_objectiu` (ja existent, buit) es deriva d'aquí.

### 2.2 Calendari del nedador (`data/nedadors/<id>/calendari.json`)

Ja té `proves` per competició (patch multi-nedador). S'hi informen les proves de cada A, B i C:

```json
{"competicio_id": "2026-11-07_...horta", "classe": "B", "proves": ["100m Lliure", "100m IM"]}
```

### 2.3 Resultats (`data/nedadors/<id>/resultats.json`, nou)

Separat del calendari (pla ≠ realitzat), com els fulls de registre.

```json
{"competicio_id": "...", "prova": "100m Lliure", "temps": "1:18.40",
 "parcials_25": ["18.3", "19.9", "20.1", "20.1"],
 "bracades_llargada": [15, 16, 17, 18],
 "font": "video", "notes": "setmana de càrrega"}
```

Parcials i braçades són opcionals (vídeo). En el 100 IM en piscina de 25 m, cada parcial de 25 és un estil.

### 2.4 Dades derivades (codi)

- **Pic actiu** d'una setmana: la propera competició A (o grup de doble pic) i les proves que s'hi neden.
- **Pes** de cada prova al pic: P = 2, S = 1 (Jep: 100 lliure 40%, 100 IM 40%, 200 lliure 20%).
- **Perfil** de cada prova (secció 3).

## 3. Perfil per durada

Font: corba aeròbic/anaeròbic per durada d'esforç màxim (encreuament a 78,6 s).

| Durada (temps del nedador) | Perfil | Jep |
|---|---|---|
| < 45 s | Velocitat | — |
| 45-120 s | Mixt | 100 lliure (1'17"-1'20"), 100 IM (1'38") |
| 120-240 s | Mig fons | 200 lliure (3'03") |
| > 240 s | Fons | — |

Substitueix la regla per distància de `seleccio_model.py`. Es calcula amb l'extrem pessimista del nivell actual.

## 4. Metodologia per fase (pic 1)

| Fase | Enfocament | Proves |
|---|---|---|
| Base | Polaritzat; tècnica dels 4 estils; velocitat alàctica setmanal (sortides, viratges, 15 m); sense làctic | Totes, de manera general |
| Build1/Build2 | Ritme de cursa de les proves P del pic; secundàries amb manteniment | 100 lliure i 100 IM: específic; 200 lliure: aeròbic i A3 en repeticions llargues (Build2) |
| Peak | Ritme de cursa, poc volum (taper actual) | Proves del pic |

El pressupost d'intensitat per rol i fase **no canvia**. **Papallona:** sense el 50 papallona, la papallona només serveix al 100 IM (25 m de cursa, tècnica i transició papallona→esquena). El límit de 300-600 m/setmana passa a **150-400 m/setmana** (proposta, a calibrar). El dofí de cames continua sense comptar-hi.

## 5. Planificador setmanal (LLM)

**Tipus:** una **crida estructurada** per setmana (no un agent amb eines). El codi recull el context; les funcions de recollida es fan independents perquè es puguin convertir en eines d'un agent quan arribi la G3.

**Entrada (la prepara el codi):** fase i setmana dins del bloc; rols i volums de cada sessió; proves del pic amb prioritat, pes i perfil; competicions properes; focus de les 3 setmanes anteriors; estat de progressió de cada prova (secció 7); càrrega, SRSS, sèrie de control i RPE de la setmana anterior; prioritats tècniques.

**Sortida (tool-use forçat):**

```json
{"sessions": [
  {"sessio_id": "...", "prova_principal": "100m Lliure", "prova_secundaria": "100m IM",
   "focus": "Ritme de cursa del 100 lliure; transicions d'estils a ritme"}],
 "justificacio": "..."}
```

**Límits que valida el codi** (un reintent amb els problemes si no es compleixen):

- Només proves del pic actiu.
- Focus compatible amb el rol i la fase (p. ex. cap ritme de cursa a Base ni el dia de tècnica).
- En una finestra de 3-4 setmanes, el repartiment de focus s'acosta als pesos (±10 punts).
- Cap prova P sense focus més de 2 setmanes seguides.

**Aprovació del coach:** l'script mostra el pla i s'atura (`--aprovar`); un cop aprovat (o editat), es redacten les sessions. La decisió es desa a `log_decisions/`.

## 6. Redactor de sessions (canvis al prompt)

- Substituir «Metodologia seleccionada» i `estil_preferent` per: **focus de la sessió** (prova principal, secundària, què treballar) i el **ritme de cursa** de la prova principal.
- Mantenir la resta: rol, pressupost, tècnica obligatòria, regles de natació, validació i reintent.

## 7. Avaluació de la progressió

### 7.1 Principi: el nivell actual és incert

La millor marca (1'17") és un extrem, no el nivell d'avui. Cada resultat té soroll (~0,8% entre competicions en elit; més en màsters), i la primera B es neda en plena càrrega. Per això el sistema treballa amb **bandes**, no amb punts, i amb **tendències**, no amb comparacions entre dues curses.

### 7.2 Banda prevista

Dues línies entre el nivell actual i el temps **sense taper** a la data de la A (objectiu × 1,02):

- **Línia lenta:** de l'estimació pessimista a l'objectiu realista.
- **Línia ràpida:** de la millor marca a l'objectiu ambiciós.

Exemple, 100 lliure (nivell actual 1'17"-1'20"; objectiu 1'12"-1'15"):

| Competició | Data | Línia ràpida | Línia lenta |
|---|---|---|---|
| Barceloneta (B) | 17/10 | 1'17"0 | 1'20"0 |
| UE Horta (B) | 07/11 | 1'16"2 | 1'19"2 |
| Sabadell (C) | 21/11 | 1'15"6 | 1'18"7 |
| CNSF Marrugat (B) | 12/12 | 1'14"8 | 1'17"8 |
| *Sense taper a la A* | 16/01 | 1'13"4 | 1'16"5 |
| **Catalunya (A)** | 16/01 | **1'12"0** | **1'15"0** |

**Observació important:** si el nivell real d'avui és 1'20", l'objectiu «realista» d'1'15" demana un −6,3% en tres mesos (−4,4% d'entrenament + −2% de taper). En màsters s'ha documentat un −4% en una temporada sencera. Per tant, el realisme de l'objectiu **depèn del nivell real**, i la primera B serveix sobretot per **calibrar-lo** (7.4).

### 7.3 Lectura d'un resultat (zones)

| Zona | Resultat | Acció |
|---|---|---|
| Blava | Més ràpid que la línia ràpida | Proposar estrènyer el rang (pujar l'objectiu) |
| Verda | Dins de la banda | Continuar |
| Groga | Fins a `marge` (1%) més lent que la línia lenta | Dins del soroll: mirar tendència i sèrie de control |
| Vermella | Més d'un `marge` més lent que la línia lenta | Avís; si es repeteix o no hi ha fatiga que l'expliqui → recomanar revisar l'entrenament |

### 7.4 Calibratge i projecció

1. **Primer resultat (Barceloneta):** fixa el nivell real dins (o fora) del rang inicial. El sistema recalcula la millora necessària per a cada extrem de l'objectiu i avisa si l'objectiu realista exigeix més d'un ~4% abans del taper.
2. **A partir de dos resultats** de la mateixa prova i piscina: tendència (regressió lineal) projectada a la data de la A, menys el taper, amb un **interval** (de la variabilitat dels resultats i del `marge`). Resultat: «projecció 1'14"8-1'16"6 → camí del realista».
3. Amb només 3-4 curses la projecció és orientativa: l'interval s'informa sempre i es combina amb la sèrie de control i el test CSS.

### 7.5 Altres indicadors

- **Sèrie de control i test CSS:** condicions controlades, menys soroll → detecten abans si l'entrenament funciona. Les curses confirmen.
- **Vídeo:** parcials (on es guanya o es perd temps; al 100 IM, cada estil) i braçades per llargada (en màsters la millora és sobretot tècnica).
- **Variabilitat:** que es redueixi a mesura que s'acosta la A és senyal de bona preparació.

### 7.6 Ritme de cursa adaptatiu

Temps de referència de les sèries de ritme de cursa:

- Menys de 2 resultats: l'**objectiu realista** (1'15" → 37"5/50).
- Amb projecció: el **temps projectat**, com a molt l'ambiciós. Si la projecció no arriba al realista, es fa servir la projecció (entrenar a un ritme inassolible no és ritme de cursa).
- Un sol resultat **no** mou el ritme: a l'inici, l'amplada de la banda és la incertesa del nivell, no progrés (revisió de la implementació, 2026-10-04).

## 8. Validacions

- Cada competició A té almenys una prova P.
- Cap prova d'IM de 100 m en una competició de 50 m.
- Cada prova de la A té nivell actual (millor marca ≤ estimació pessimista) i objectiu (ambiciós ≤ realista).
- Cada prova de la A apareix en almenys **dues** B/C de la mateixa piscina abans de la A.
- Avís si l'objectiu realista exigeix més d'un ~4% abans del taper respecte a l'estimació pessimista.
- Avís si una competició B/C ja disputada no té resultat.

## 9. Pla d'implementació (patches `git am`)

| # | Patch | Estat |
|---|---|---|
| 1 | Models: `ProvaObjectiu` (prioritat, nivell actual, objectius), compatibilitat amb la llista antiga; `resultats.json`; utilitats de temps i de noms de prova | ✅ 2026-10-04 |
| 2 | Pic actiu i pesos a partir del calendari; perfil per durada; validacions | ✅ 2026-10-04 |
| 3 | Bandes, zones, calibratge, projecció i ritme de cursa; `informe_progressio.py`; informe dins `generar_temporada.py` | ✅ 2026-10-04 |
| 3b | Correcció: competicions de control posteriors al pic anterior | ✅ 2026-10-04 |
| 3c | Simulacions (`tipus: simulacio`) i `registrar_resultat.py` | ✅ 2026-10-05 |
| 4 | Planificador setmanal LLM + validació del pla + aprovació del coach + log | Pendent |
| 5 | Prompt del redactor: focus de sessió i ritme de cursa adaptatiu; retirar `estil_preferent` i la metodologia per prova; nou límit de papallona | Pendent |
| 6 | Documentació | ✅ 2026-10-05 (`Manual.md`, `Architecture.md`, `Fase3.md`, `FulldeRuta_1002.md`) |

## 10. Dades que ha d'omplir el coach (Jep)

- ✅ Fitxa en format nou, sense el 50 papallona; 100 lliure amb nivell 1'17"08-1'20" i objectiu 1'15"-1'12"; 100 IM amb objectiu 1'38"-1'35".
- ✅ Calendari del pic 1 tancat (4 punts de control de 25 m per prova).
- Pendent: marge al nivell del 100 IM (ara millor marca = estimació pessimista = 1'38", banda tancada a l'inici); objectius del pic 2 (100 i 200 lliure, 50 m) abans del febrer; data definitiva de Sant Andreu (13 o 20/03).

## 11. Evidència

- Aportació energètica per durada; encreuament a 78,6 s. [Sports Medicine 2026](https://link.springer.com/article/10.1007/s40279-026-02414-7)
- Distribució d'intensitat per especialitat en nedadors d'elit. [González-Ravé et al. 2021, IJSPP](https://zenodo.org/records/14697490)
- Polaritzat > llindar en 100 m, menys fatiga. [Pla et al. 2019](https://pubmed.ncbi.nlm.nih.gov/30040002/)
- Velocistes de 50 vs 100 m. [Papadimitriou et al. 2025](https://link.springer.com/article/10.1007/s00421-025-06064-x)
- Efectes residuals i blocs. [Issurin 2010](https://www.hmmrmedia.com/wp-content/uploads/2015/08/new-horizons-periodization.pdf); [ExRx](https://exrx.net/Sports/ResidualTraining)
- Estratègia en nedadors d'estils. [González-Ravé et al. 2022, JHK](https://jhk.termedia.pl/Competition-and-Training-Strategies-for-Developing-World-Class-200-and-400-m-Individual,167381,0,2.html)
- Variabilitat entre competicions 0,8%; millora útil ~0,4%. [Pyne et al. 2004](https://www.researchgate.net/publication/8345203_Progression_and_variability_of_competitive_performance_of_Olympic_swimmers)
- Variabilitat dins la temporada, que es redueix cap al pic. [Clephas & Wilhelm 2019](https://link.springer.com/article/10.1007/s12662-018-0563-7)
- Taper: ~3% (0,5-6%); 2,2% a Sydney 2000. [Mujika & Padilla 2003](https://www.academia.edu/17566285/Scientific_Bases_for_Precompetition_Tapering_Strategies)
- Màsters: −2 a −4% en una temporada, sobretot tècnic. [Marinho et al. 2020](https://www.mdpi.com/2411-5142/5/2/37)
- Màsters: declivi 0,6-0,7%/any. [Tanaka & Seals](https://pmc.ncbi.nlm.nih.gov/articles/PMC3781853/)

**Limitacions:** les dades de variabilitat i de taper són d'elit o de nedadors joves; els paràmetres (taper 2%, marge 1%, pesos 2/1, llindars de durada, límit de papallona, llindar del 4%) són punts de partida raonats que cal calibrar amb els resultats de cada nedador. Amb 3-4 curses per pic, qualsevol projecció té un interval ample.
