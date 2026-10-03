# BlondSwim — Guia d'ús d'aider per als models i el conversor

> **Nota d'actualització (2026-10-02).** Guia històrica de la Fase 0 (feta). Canvis posteriors:
> - **Calendari**: ara té **3 competicions de classe A** (Catalunya Hivern, Espanya Hivern 06-07/02/2027 i Catalunya Estiu); Espanya va passar de B a A a la Fase H2 (doble pic). El Pas 7 deia «2 de classe A».
> - **Columna `id`**: la còpia de `Provisional26-27.xlsx` d'aquest projecte no té la columna `id` (capçaleres: `class, data, competicio, piscina, modalitat`). La font de la ingestió és el fitxer de `data/raw/` del repo; si s'hi copia el del projecte, cal comprovar que `convertir_calendari()` continua generant els `id`.
> - **Pestanya `Ritmes`**: les adreces de cel·la del Pas 5 són les de `Planificacio_Mesocicles_Jep.xlsx`; `Ritmes_Jep.xlsx` del projecte és una versió antiga de 3 zones (vegeu `metodologia_ritmes.md`).
> - **Sessió**: l'estructura fixa de 5 parts del Pas 4 s'ha substituït per la plantilla setmanal de 5 dies amb parts per rol (Fases H/H2, `Fase3.md`).
> - **Flux de treball**: aider només per a canvis petits d'un sol fitxer; els canvis grans es lliuren com a patches `git am`.

Objectiu d'aquesta sessió amb aider: (1) actualitzar `nedador.py` amb el disseny final de `Ritmes`, (2) generar `macrocicle.py` i `sessio.py`, i (3) generar el conversor complet `xlsx_to_json.py` — tot a partir de les dades reals dels teus fitxers.

**Nota de rutes**: el projecte fa servir el layout `src/blondswim/...` (no `src/...`), confirma-ho abans de començar:
```bash
ls src/blondswim/models/ src/blondswim/ingestion/
```

---

## Pas 1 — Arrencar aider

Ja el tens instal·lat via `pipx`. Des de l'arrel de `ws_blondswim`:
```bash
make aider
```

---

## Pas 2 — Afegir els fitxers de context

```
/add src/blondswim/models/nedador.py
/add src/blondswim/models/calendari.py
/add src/blondswim/models/macrocicle.py
/add src/blondswim/models/sessio.py
/add src/blondswim/ingestion/xlsx_to_json.py
```

---

## Pas 3 — Prompt per actualitzar `nedador.py` (disseny final de Ritmes)

El `nedador.py` actual només té l'esquelet mínim (`RitmesCSS` amb `a1/a2/a3`). Cal ampliar-lo amb el disseny final que ja tens construït i validat a la pestanya `Ritmes`:

```
Actualitza src/blondswim/models/nedador.py per reflectir el disseny final de la 
pestanya "Ritmes" (fitxer Planificacio_Mesocicles_Jep.xlsx), mantenint el que 
ja hi ha (Nedador, camps existents) i ampliant-ho així:

1. Amplia RitmesCSS amb 5 zones, no 3:
   - recuperacio, a1, a2, a3, velocitat (tots float | None)
   - data_test: str | None
   - font: Literal["css_test", "estimat_marca"] = "estimat_marca"

2. Afegeix un model nou MarquesReferencia:
   - marca_100_lliure_seg: float
   - marca_50_lliure_seg: float   # ara numèrica, s'usa per calcular la zona Velocitat
   - marca_50_papallona: str | None = None
   - marca_200_lliure: str | None = None
   - marca_100_im: str | None = None

3. Afegeix un model nou ParametresRitme (paràmetres del model, compartits per 
   defecte entre nedadors, no específics de cada un):
   - increment_a3: float = 0.015
   - increment_a2: float = 0.065
   - increment_a1: float = 0.13
   - increment_recuperacio: float = 0.20
   - factor_velocitat: float = 0.85
   - factor_escala_50_100: float = 2.02
   - factor_escala_100_200: float = 2.04
   - ajust_esquena_min: float = 0.10
   - ajust_esquena_max: float = 0.11
   - ajust_braca_min: float = 0.15
   - ajust_braca_max: float = 0.20
   - offset_recuperacio_css: float = 12
   - offset_a1_css: float = 6
   - offset_a2_css: float = 0
   - offset_a3_css: float = -4

4. Afegeix un model nou RitmeCursaObjectiu (independent de les zones 
   fisiològiques, per a les sèries USRPT):
   - prova: str
   - distancia_m: int
   - temps_objectiu_seg: float | None = None

5. Al model Nedador, afegeix els camps:
   - marques_referencia: MarquesReferencia | None = None
   - ritmes_css: RitmesCSS | None = None   (ja existia, revisa que faci servir el RitmesCSS ampliat)
   - parametres_ritme: ParametresRitme = ParametresRitme()   (per defecte, sobreescrivible)
   - ritmes_cursa_objectiu: list[RitmeCursaObjectiu] = []

IMPORTANT — regla de conciliació de fonts (documenta-ho com a docstring al 
model RitmesCSS, no com a lògica executable aquí): la font "css_test" té 
sempre prioritat quan a1/a2/a3 provenen d'un test CSS recent; si no n'hi ha, 
s'utilitza "estimat_marca". Aquesta regla es resol al conversor, no aquí — 
aquests models només representen l'estructura de dades.

No implementis els càlculs de les zones (offsets, factors d'escala) com a 
mètodes aquí — això és responsabilitat d'un mòdul de càlcul separat que 
farem a la Fase 1. Aquí només l'estructura de dades amb pydantic.
```

---

## Pas 4 — Prompt per als models `Macrocicle` i `Sessio`

```
Defineix els models pydantic Macrocicle i Sessio a src/blondswim/models/macrocicle.py 
i src/blondswim/models/sessio.py, seguint l'estil de nedador.py i calendari.py.

DADES REALS D'ORIGEN (full "Macrocicle", una fila per mesocicle):
Columnes: Mesocicle | Setmanes | Dates | Fase/Objectiu | Metodologia dominant | 
Volum setmanal (rang) | Volum mitjà previst (m) | Tancament (control/objectiu)

Exemple real:
M1 - Base | 1-4 | 21/09-18/10/2026 | "Base aeròbica general i tècnica..." | 
"Escola Australiana (volum, base aeròbica alta...)" | "15.500-17.000 m" | 15500 | 
"Control B: Etapa Barceloneta (17/10)"

Cada mesocicle també té, en una taula relacionada, tècnica_focus i 
especific_metodologia (contingut de tècnica i de la part específica/qualitat 
per aquell mesocicle).

DADES REALS D'ORIGEN (full "Microcicles", una fila per setmana, dins d'un mesocicle):
Columnes: Setmana | Dates | Meso | Tipus de setmana | Volum objectiu (m) | 
Dies qualitat (Dc+Ds) | Test CSS | Competició/Test oficial | Test avaluació | 
Focus específic

Exemple real:
19 | 25-31/01/2027 | M5 | "Ajust específic + mini-taper" | 13000 | No | "-" | 
"-" | "-" | "Mini-taper: ajust final de ritmes."

IMPORTANT — el camp "Tipus de setmana" a les dades reals NO és una categoria 
neta: valors com "Càrrega + Test CSS", "Nadal - Descàrrega activa", 
"Cap d'Any - Represa progressiva", "Taper + Competició A (Pic 1)" barregen 
tipus base amb notes puntuals. Proposa'm un disseny que separi:
  - tipus_base: Literal["carrega", "qualitat", "descarrega", "taper", "transicio"]
  - notes: str | None (per als casos especials com Nadal, Cap d'Any, Pic 1/2)
i demana'm confirmació abans d'assumir-ho com a definitiu.

DADES REALS D'ORIGEN (full "Estructura de sessió" — fix, no varia per nedador 
en aquesta fase):
5 parts amb % segons tipus de setmana (Càrrega / Qualitat / Descàrrega-Test):
Escalfament (10%/10%/15%), Tècnica+Subaquàtic (20%/15%/15%), 
Aeròbic/Llindar (50%/30%/20%), Específic/Qualitat (10%/35%/40%), 
Tornada a la calma (10%/10%/10%).

El model Sessio ha de representar aquesta estructura de 5 parts amb els 
percentatges per tipus de setmana, i un camp de contingut/descripció per part.

No incloguis lògica de negoci (regles de taper, validacions) en aquests 
models — només l'estructura de dades. Si algun camp et sembla ambigu, 
pregunta abans d'assumir.
```

---

## Pas 5 — Prompt per al conversor `xlsx_to_json.py`

```
Escriu el conversor complet a src/blondswim/ingestion/xlsx_to_json.py. Ha de:

1. Llegir data/raw/Provisional26-27.xlsx, pestanya "Calendari".

   IMPORTANT — llegeix les columnes SEMPRE per nom de capçalera (fila 1), 
   mai per lletra/posició fixa. L'estructura d'aquesta pestanya ja ha 
   canviat una vegada durant aquest projecte; el conversor ha de sobreviure 
   a canvis futurs de l'ordre de columnes sense trencar-se. Capçaleres 
   actuals: id, class, data, competicio, piscina, modalitat.

2. Per cada fila amb dades, extreure: id (ja ve calculat al fitxer font, 
   no cal generar-lo), nom competició, classe (A/B/C), piscina.

3. El camp de data ve com a text lliure o com a datetime — de vegades data 
   única (datetime), de vegades rang en text ("2027-01-16 a 2027-01-17"). 
   Separa-ho sempre en data_inici i data_fi en format ISO (YYYY-MM-DD). 
   Si és data única, data_inici = data_fi. Si el format no encaixa amb cap 
   dels dos casos, atura l'execució amb un error clar indicant fila i valor 
   original — no l'ignoris en silenci.

4. Reconciliació piscina/modalitat: neteja piscina amb .strip() abans de 
   res més (pot venir amb espais en blanc en lloc de buida de veritat). Si 
   després de netejar queda buida, el valor real és "aaoo" (agafat de la 
   columna modalitat), no una piscina. Si modalitat="piscina" però piscina 
   queda buida després de netejar, és una inconsistència de dades: registra-ho 
   com a advertència (no aturis l'execució) i salta aquesta fila.

5. Validar cada registre contra el model Competicio (pydantic) — si una fila 
   no compleix l'esquema, atura l'execució amb un missatge d'error clar 
   indicant número de fila i el problema, no generis un JSON parcial en silenci.

6. Escriure el resultat a data/processed/calendari.json.

7. Sanity check final: si el resultat té zero competicions de classe "A", 
   avisa clarament (podria indicar un fitxer font corrupte o buit) encara 
   que tècnicament no sigui un error de validació.

Fes una segona funció que llegeixi data/raw/Planificacio_Mesocicles_Jep.xlsx, 
pestanya "Macrocicle", i generi data/processed/macrocicle_jep.json validant 
contra el model Macrocicle — cas de referència ("golden reference") per a la 
Fase 4, no dada d'entrada regular. Llegeix també per nom de capçalera, no 
per posició.

Fes una tercera funció que llegeixi la pestanya "Ritmes" del mateix fitxer i 
generi data/processed/nedador_<nom>.json validant contra el model Nedador 
(amb MarquesReferencia, RitmesCSS, RitmeCursaObjectiu). Aquesta pestanya SÍ 
té adreces de cel·la fixes per disseny (és una plantilla, no una taula amb 
capçaleres variables), així que pots fer servir les adreces directes:
  - B4: nom del nedador
  - B5: edat
  - B8: data del test CSS (buida si no n'hi ha hagut cap)
  - B9, B10: temps 400m i 200m del test CSS en segons (buits si no n'hi ha)
  - B15: millor marca 100m lliures (segons)
  - B20: millor marca 50m lliures (segons) — s'usa per calcular la zona Velocitat
  - B19, B21, B22: altres marques de referència (text, no calen parsejar-les, 
    guarda-les tal qual a MarquesReferencia)
  - B44: font activa, ja calculada per fórmula al full ("Test CSS (...)" o 
    "Estimat per millor marca (provisional)") — usa-la per omplir el camp 
    "font" de RitmesCSS ("css_test" si el text conté "Test CSS", altrament 
    "estimat_marca"). Si B9 i B10 estan buits, ignora B44 i assigna 
    font="estimat_marca" directament — no depenguis només del text de B44 
    per si canvia la redacció de la fórmula.
  - B48:B52: zones calculades (Recuperació, A1, A2, A3, Velocitat) en segons 
    per 100m — llegeix-les amb data_only=True (calen recalculades, no fórmules)
  - Files 76-79, columnes A-C: taula de Ritme de cursa objectiu (Prova | 
    Distància (m) | Temps objectiu (s)) — ignora les files on la columna A 
    estigui buida o sigui el placeholder "[Prova]"

Afegeix un __main__ que executi les tres conversions i imprimeixi un resum 
(número de registres processats, avisos/inconsistències trobades, font 
utilitzada per a cada nedador processat).

Escriu-ho amb funcions petites i testables per separat (una funció per 
parsejar dates, una per llegir capçaleres per nom, una per llegir cada full, 
una per validar/escriure), no una única funció monolítica — a 
tests/ingestion/test_xlsx_to_json.py hi haurem d'escriure tests per a 
cadascuna, incloent un test específic per al cas piscina/modalitat 
inconsistent i un per al format de data no reconegut.
```

## Pas 6 — Revisió (fes-ho abans d'executar)

- [ ] `nedador.py` conté els 4 models nous (`MarquesReferencia`, `ParametresRitme`, `RitmeCursaObjectiu`, `RitmesCSS` ampliat) i el `Nedador` original segueix funcionant (el test del Pas 11 de la Fase 0 encara passa: `make test`).
- [ ] `macrocicle.py`/`sessio.py` reflecteixen exactament els camps reals (compara amb les taules d'aquest document).
- [ ] La proposta de `tipus_base`/`notes` per al "Tipus de setmana" et sembla correcta, o prefereixes una altra categorització?
- [ ] El conversor llegeix les columnes del `Calendari` **per nom de capçalera**, no per lletra fixa.
- [ ] El conversor **no** regenera l'`id` de cada competició — el llegeix directament de la columna `id` (ja ve calculat al fitxer font).
- [ ] El parser de dates del calendari gestiona els 2 formats reals actuals (data única `datetime`, rang ISO "2027-01-16 a 2027-01-17") i falla amb error clar davant qualsevol altre format.
- [ ] La reconciliació piscina/modalitat funciona: la fila de Budapest aigües obertes (`id` que comença per `2027-06-29_`) ha de donar `piscina=None`, `modalitat="aaoo"`.
- [ ] El conversor llegeix `B48:B52` amb `data_only=True` (valors calculats, no la fórmula en text).
- [ ] El conversor falla clarament (no en silenci) si una fila no encaixa amb cap model.

## Pas 7 — Executar i validar

```bash
make run-ingestion
```

Revisa manualment els 3 JSON generats: `calendari.json` (17 competicions, 2 de classe A en aquell moment — **ara 3**, vegeu la nota inicial —, tots amb `id` legible i estable com `"2027-01-16_campionat-catalunya-hivern"`), `macrocicle_jep.json` (volums coincidint amb el full), i `nedador_jep.json` (`font="estimat_marca"`, zones amb els valors que ja vam validar: A2≈82.09s, Velocitat≈67.55s).

Quan ho tinguis fet, comparteix el resultat i ho revisem junts.
