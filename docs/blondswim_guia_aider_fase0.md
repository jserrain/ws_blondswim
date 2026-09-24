# BlondSwim — Guia d'ús d'aider per al conversor i els models restants

Objectiu d'aquesta sessió amb aider: generar `src/models/macrocicle.py`, `src/models/sessio.py` i el conversor complet `src/ingestion/xlsx_to_json.py`, a partir de les dades reals del teu full `Planificacio_Mesocicles_Jep.xlsx`.

---

## Pas 1 — Instal·lar i configurar aider

```bash
pip install aider-chat
```

Com que ja tens `ANTHROPIC_API_KEY` al `.env` (Fase 0, Pas 4), aider la pot fer servir directament si l'exportes a la sessió de terminal:

```bash
export $(cat .env | xargs)   # carrega ANTHROPIC_API_KEY a l'entorn de la terminal
aider --model sonnet         # aider fa servir Claude Sonnet
```

Executa aquesta comanda **des de l'arrel del projecte** (`blondswim/`), perquè aider indexi el repo sencer.

---

## Pas 2 — Afegir els fitxers de context

Dins d'aider, afegeix els fitxers que ja existeixen (encara buits o amb l'esquelet de la Fase 0) perquè els pugui editar:

```
/add src/models/macrocicle.py
/add src/models/sessio.py
/add src/models/nedador.py
/add src/models/calendari.py
/add src/ingestion/xlsx_to_json.py
```

Afegir `nedador.py` i `calendari.py` (ja fets) és important perquè aider mantingui **el mateix estil i convencions** (noms de camps, ús de `Literal`, etc.) en els models nous.

---

## Pas 3 — Prompt per als models `Macrocicle` i `Sessio`

Enganxa aquest prompt a aider (inclou dades reals del teu full perquè no hagi d'inventar l'estructura):

```
Defineix els models pydantic Macrocicle i Sessio a src/models/macrocicle.py i 
src/models/sessio.py, seguint l'estil de nedador.py i calendari.py.

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

## Pas 4 — Prompt per al conversor `xlsx_to_json.py`

Un cop revisats i acceptats els models (Pas 5), passa aquest prompt:

```
Escriu el conversor complet a src/ingestion/xlsx_to_json.py. Ha de:

1. Llegir data/raw/Provisional26-27.xlsx, pestanya "Calendari".
2. Per cada fila amb dades, extreure: nom competició, classe (A/B/C), piscina.
3. El camp de data ve com a text lliure — de vegades data única 
   (datetime), de vegades rang ("16-17 gen" o "2027-01-16 a 2027-01-17"). 
   Separa-ho sempre en data_inici i data_fi en format ISO (YYYY-MM-DD). 
   Si és data única, data_inici = data_fi.
4. Validar cada registre contra el model Competicio (pydantic) — si una fila 
   no compleix l'esquema, atura l'execució amb un missatge d'error clar 
   indicant número de fila i el problema, no generis un JSON parcial en silenci.
5. Escriure el resultat a data/processed/calendari.json.

Fes també una segona funció que llegeixi data/raw/Planificacio_Mesocicles_Jep.xlsx, 
pestanya "Macrocicle", i generi data/processed/macrocicle_jep.json validant 
contra el model Macrocicle — aquest és el cas de referència ("golden reference") 
que farem servir a la Fase 4 per validar el sistema, no una dada d'entrada regular.

Afegeix un __main__ que executi totes dues conversions i imprimeixi un resum 
(número de registres processats, errors trobats).

Escriu-ho amb funcions petites i testables per separat (una funció per parsejar 
dates, una per llegir cada full, una per validar/escriure), no una única funció 
monolítica — a tests/test_ingestion.py hi haurem d'escriure tests per a cadascuna.
```

---

## Pas 5 — Revisió (fes-ho abans de continuar)

Un cop aider generi el codi, revisa **abans d'executar-lo**:

- [ ] Els models `macrocicle.py` i `sessio.py` reflecteixen exactament els camps reals (compara amb les taules d'aquest document).
- [ ] La proposta de `tipus_base`/`notes` per al "Tipus de setmana" et sembla correcta, o prefereixes una altra categorització?
- [ ] El parser de dates gestiona els 3 formats reals que hi ha al teu Excel: data única (`datetime`), rang curt ("16-17 gen"), rang amb any ("2027-01-16 a 2027-01-17").
- [ ] El conversor falla clarament (no en silenci) si una fila no encaixa amb el model — comprova-ho forçant un error (per exemple, esborra temporalment una classe A/B/C d'una fila de prova).

## Pas 6 — Executar i validar

```bash
python -m src.ingestion.xlsx_to_json
```

Revisa manualment `data/processed/calendari.json` i `data/processed/macrocicle_jep.json` contra les dades reals (2 competicions classe A, dates ISO correctes, volums del macrocicle coincidint amb els que has vist en aquest document).

Quan ho tinguis fet, comparteix el resultat (o els fitxers generats) i ho revisem junts abans de tancar la Fase 0 definitivament.
