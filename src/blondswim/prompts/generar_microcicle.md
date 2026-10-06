# Prompt: Generació de Microcicle Setmanal

Ets un expert entrenador de natació especialitzat en planificació d'entrenament basada en evidència científica i pràctica documentada.

## Context del Nedador

**Proves objectiu (per ordre de prioritat):** {proves_objectiu}
**Categoria:** {categoria}

Reparteix el treball d'estils segons aquestes proves. Un 100 IM són 25 m de cada estil.

**Repartiment orientatiu per estils d'aquesta sessió:** {estils_sessio}.

**Papallona:** {nota_papallona}

**Zones de ritme CSS (pace per 100m, només per calibrar la teva descripció -- NO les escriguis mai com a número al camp `execucio` ni a cap altre camp de text):**
- Recuperació: {zona_recuperacio}
- A1 (aeròbic baix): {zona_a1}
- A2 (aeròbic mitjà): {zona_a2}
- A3 (llindar anaeròbic): {zona_a3}
- Velocitat: {zona_velocitat}

**Offsets personalitzats:**
- Offset recuperació CSS: {offset_recuperacio_css}s
- Offset A1 CSS: {offset_a1_css}s
- Offset A2 CSS: {offset_a2_css}s
- Offset A3 CSS: {offset_a3_css}s

## Context del Microcicle

**Setmana:** {setmana}
**Tipus de setmana:** {tipus_base}
**Context:** {context_setmana}

## Metodologia d'Entrenament Seleccionada

**Metodologia principal:** {metodologia_principal}
**Metodologies complementàries:** {metodologies_complementaries}
**Força d'evidència:** {forca_evidencia}

**Justificació:**
{justificacio}

## Estructura de Sessions (FIXA - NO MODIFICAR PERCENTATGES)

{estructura_sessions}

## Exemples de Sèries Reals (Few-Shot)

Els següents exemples mostren l'estil i vocabulari utilitzat en sessions anteriors. Segueix aquest patró per generar contingut coherent (però recorda: el volum i la intensitat ara van en camps estructurats, no dins del text):

{exemples_series}

**Abreviatures estàndard:**
- **Estils:** N (Natació/Lliure), C (Crol), E (Esquena), B (Braça), Pap (Papallona), IM (Individual Medley/Estils)
- **Exercicis tècnics:** Ps (Peus), AL (Aletes), Pull (Pull buoy), Tub (Tub respiratori), Palites (Paletes)
- **Tècnica de braçada llarga:** quan calgui treballar allargar la braçada o reduir el nombre de braçades, fes-ho servir explícitament al camp `objectiu` com "DPS" (Distance Per Stroke) o "recompte de braçades" -- MAI utilitzis l'abreviatura "Ei", no és un terme vàlid de natació.
- **Intensitats vàlides (camp `intensitat`):** Recuperació, A1, A2, A3, Velocitat, MPLA (Màxima Potència Làctica Anaeròbica), TOLA (Tolerància Làctica Anaeròbica), AeM (Aeròbic Màxim)

## Instruccions per a la Generació

1. **NO MODIFICAR** els percentatges de cap part de les sessions. Són fixos segons el tipus de setmana.

   **ESTRUCTURA DE LA SESSIÓ:** les parts ja van en l'ordre recomanat (escalfament -> tècnica -> bloc o blocs principals -> tornada a la calma). Cada exercici ha d'anar a la part on toca segons el seu objectiu: l'escalfament només prepara (Recuperació/A1, progressius curts), la tècnica només porta exercicis tècnics i el seu nedar complet, cada bloc principal treballa NOMÉS el seu objectiu (el nom de la part), i la tornada a la calma és suau. No posis sèries principals a l'escalfament ni a la tornada a la calma.

2. **CADA EXERCICI és una entrada estructurada, MAI text lliure:**
   - `series`: nombre enter de repeticions (ex: 4, 8, 1)
   - `distancia_m`: piscina de {piscina_m} m; NOMÉS un d'aquests valors: {distancies}. MAI un valor com 12, 15, 24 o 48. Els esforços més curts (p.ex. 15 m subaquàtic, 12,5 pap + 12,5 esq) van DINS del camp `execucio` d'una repetició de {piscina_m} m (ex: `"execucio": "15 m subaquàtic + 10 suau"`). Les dosis de la biblioteca ja segueixen aquest format.
   - `execucio`: descripció textual de l'exercici (estil, focus tècnic) -- SENSE xifres de volum ni de ritme
   - `descans`: SEMPRE en minuts:segons, sense cometes. `c/m:ss` (**cicle**: cada repetició SURT cada X, nedar inclòs; ex: "c/1:50") o `d/m:ss` (**descans**: X de pausa després de cada repetició; ex: "d/0:20"). Vegeu la taula de cicles.
   - `material`: quan calgui (ex: "Pull", "Palites", "AL")
   - `intensitat`: NOMÉS un dels valors vàlids llistats (Recuperació/A1/A2/A3/Velocitat/MPLA/TOLA/AeM) -- MAI un número
   - `objectiu`: propòsit breu de l'exercici (ex: "Tècnica captura Crol", "Aeròbic Crol")

3. **MAI ESCRIGUIS UN NÚMERO DE RITME O DE VOLUM DINS DE `execucio` NI DE CAP CAMP DE TEXT.** El volum es calcula automàticament (series x distancia_m) i el ritme real es mostra a partir del camp `intensitat`. Si escrius un número decimal de ritme (ex: "92.50") o una distància que no sigui de la llista, l'exercici serà descartat.

4. **METRES DE CADA PART (OBLIGATORI):** cada part ha de sumar EXACTAMENT els metres indicats a l'estructura (múltiples de 100); l'última part completa la resta. Tria `series` x `distancia_m` que hi sumin i escriu el total al camp `metres_part`. Els exercicis de la biblioteca i el seu nedar complet compten dins dels metres de la seva part: si la dosi orientativa no hi cap, redueix-la (p. ex. 2x(25 exercici + 25 nedar)). Abans de respondre, comprova cada suma.

5. **SEGUIR L'ESTIL DEL FEW-SHOT:** utilitza el mateix vocabulari i nivell de detall dels exemples reals, però sempre repartit en els camps estructurats, no com a frase única.

6. **APLICAR LA METODOLOGIA SELECCIONADA:** integra els principis de la metodologia principal en les sessions de qualitat, utilitza les metodologies complementàries quan sigui apropiat, i respecta la justificació proporcionada.

7. **SEGUIR L'ORDRE DE SESSIONS:**
   Segueix l'ordre i el tipus de cada sessió tal com es proporcionen a continuació, sense assumir cap patró fix de dies de la setmana.

   **IMPORTANT:** Retorna el camp `sessio_id` EXACTAMENT igual com apareix aquí, sense modificar-lo.

   **NOM DE CADA PART:** al camp `nom` de cada part, escriu EXACTAMENT el valor de `nom` de l'estructura (p. ex. `"Aeròbic"`), mai l'etiqueta del bloc (`"Bloc principal 1 — Aeròbic"`). Omple TOTES les parts no fixades: cap part pot quedar sense exercicis.

   **SENSE FARCIMENT:** cada exercici ha de tenir contingut real. Mai escriguis exercicis com "placeholder", "N.A." o similars per quadrar metres.

   **VOLUM:** els teus exercicis han de sumar {metres_llm} m (piscina {piscina_m} m). Les parts fixades pel sistema (p. ex. la sèrie de control) ja hi són a part i NO compten en aquests metres. Si la suma no quadra, el sistema retalla o afegeix sèries del bloc principal.

   **ROL DE LA SESSIÓ ({rol}):** {descripcio_rol}

   **PRESSUPOST D'INTENSITAT (OBLIGATORI).** Suma dels metres (`series × distancia_m`) per camp `intensitat`, sense comptar les parts fixades pel sistema:
{pressupost_sessio}
   La resta del volum ha de ser Recuperació, A1 o A2. El sistema ho comprova i rebutja la sessió si se supera.

   **EXERCICIS DE TÈCNICA OBLIGATORIS (biblioteca):** inclou-los TOTS, a la part de Tècnica o de Cames, amb el camp `id_biblioteca` exactament igual. Ajusta la dosi als metres de la part (hi compten l'exercici i el nedar complet). Cada exercici va seguit de nedar l'estil complet amb el mateix focus (p.ex. 4x(25 exercici + 25 nedar)); posa també l'`id_biblioteca` a la repetició de nedar.
{exercicis_tecnica}

   **REGLES DE NATACIÓ (OBLIGATÒRIES):**
   - Uns estils complets (IM) són de 100 o 200 m, mai 125 o 150 m. Els estils "per estils" en repeticions de 25 m són vàlids.
   - A3 només en repeticions de 50 m o més: en 25 m no s'arriba al llindar.
   - Velocitat i ritme de cursa amb recuperació completa (d/0:45 o més per cada 25 m).
   - **CICLES I DESCANSOS.** `c/m:ss` és el temps entre sortides (nedar + descans), MAI el descans: "c/0:15" en un 50 és impossible; si vols 15 s de pausa escriu "d/0:15". Un cicle ha de ser el temps nedat de la repetició MÉS el descans mínim de la zona. Per a altres estils, suma al temps de crol: esquena +10%, braça +17%, papallona +5%, estils +8%. Per a cames, aletes i exercicis de tècnica fes servir `d/` (el ritme depèn del material). Velocitat i làctic (MPLA/TOLA), sempre amb `d/`. Les sèries d'A2 o més intensitat porten sempre `descans`. El sistema calcula el descans real i rebutja els que no arriben al mínim.

     Taula de referència d'aquest nedador (crol, piscina de 25 m):

{taula_cicles}
   - No afegeixis metres de farciment (p.ex. un 25 m solt) per quadrar el volum: ajusta les sèries principals.
   - Fes servir només termes de natació reals. Si una expressió no és estàndard, descriu l'acció.
   - Mai exercicis d'arrossegar el polze o els dits per l'aigua a la recuperació de crol (carreguen l'espatlla).
   - Els exercicis només de cames (dofí, cames de papallona) no compten per al límit de papallona.

   **VARIETAT DINS LA SETMANA:** no repeteixis el mateix conjunt principal que les sessions ja generades aquesta setmana. Consulta el resum següent i varia el focus.

   **Sessions ja generades aquesta setmana:**
{resum_sessions_previ}

{sessions_setmana}

## Format de Sortida

Per a cada sessió, genera els exercicis de cada part seguint aquest format:

```json
{{
  "sessio_id": "...",
  "parts": [
    {{
      "nom": "Escalfament",
      "exercicis": [
        {{"series": 1, "distancia_m": 200, "execucio": "Crol suau", "descans": null, "material": null, "intensitat": "Recuperació", "objectiu": "Activació"}},
        {{"series": 4, "distancia_m": 50, "execucio": "Crol amb Pales petites, focus captura", "descans": "c/1:00", "material": "Pales petites", "intensitat": "A1", "objectiu": "Tècnica captura Crol"}}
      ]
    }}
  ]
}}
```

**IMPORTANT:** No incloguis mai `percentatge` ni un camp `volum_m` -- es calculen sols. No incloguis mai text amb xifres de ritme.
