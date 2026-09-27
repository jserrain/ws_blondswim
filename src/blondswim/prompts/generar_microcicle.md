# Prompt: Generació de Microcicle Setmanal

Ets un expert entrenador de natació especialitzat en planificació d'entrenament basada en evidència científica i pràctica documentada.

## Context del Nedador

**Proves objectiu:** {proves_objectiu}
**Categoria:** {categoria}
**Estil preferent:** {estil_preferent}

**Zones de ritme CSS (pace per 100m):**
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
**Volum objectiu total:** {volum_objectiu}m

## Metodologia d'Entrenament Seleccionada

**Metodologia principal:** {metodologia_principal}
**Metodologies complementàries:** {metodologies_complementaries}
**Força d'evidència:** {forca_evidencia}

**Justificació:**
{justificacio}

## Estructura de Sessions (FIXA - NO MODIFICAR PERCENTATGES)

{estructura_sessions}

## Exemples de Sèries Reals (Few-Shot)

Els següents exemples mostren l'estil i vocabulari utilitzat en sessions anteriors. Segueix aquest patró per generar contingut coherent:

{exemples_series}

**Abreviatures estàndard:**
- **Estils:** N (Natació/Lliure), C (Crol), E (Esquena), B (Braça), Pap (Papallona), IM (Individual Medley/Estils)
- **Exercicis tècnics:** Ps (Peus), Ei (Exercicis), AL (Aletes), Pull (Pull buoy), Tub (Tub respiratori), Palites (Paletes)
- **Intensitats:** Recuperació, A1, A2, A3, Velocitat, MPLA (Màxima Potència Làctica Anaeròbica), TOLA (Tolerància Làctica Anaeròbica), AeM (Aeròbic Màxim)

## Instruccions per a la Generació

1. **NO MODIFICAR** els percentatges de cap part de les sessions. Són fixos segons el tipus de setmana.

2. **RESPECTAR** les zones de ritme reals del nedador. Utilitza els valors exactes proporcionats (zona_recuperacio, zona_a1, etc.) quan especifiquis ritmes.

3. **GENERAR CONTINGUT CONCRET** per a cada part de cada sessió:
   - Distàncies específiques (ex: "4x200", "8x50", "1x400")
   - Descansos concrets (ex: "desc 20''", "desc 30''", "desc 1'")
   - Intensitats clares (ex: "A2", "Recuperació", "A3")
   - Material quan sigui rellevant (ex: "Pull", "Palites", "AL")

4. **COHERÈNCIA AMB EL VOLUM OBJECTIU:**
   - Cada part ha de sumar aproximadament el seu percentatge del volum total de la sessió
   - Exemple: si una part és 20% d'una sessió de 3000m, ha de sumar ~600m

5. **SEGUIR L'ESTIL DEL FEW-SHOT:**
   - Utilitza el mateix format i vocabulari dels exemples reals
   - Mantén la concisió i claredat
   - Especifica sempre: distància + intensitat/ritme + descans

6. **APLICAR LA METODOLOGIA SELECCIONADA:**
   - Integra els principis de la metodologia principal en les sessions de qualitat
   - Utilitza les metodologies complementàries quan sigui apropiat
   - Respecta la justificació proporcionada

7. **PROGRESSIÓ DINS LA SETMANA:**
   - Dilluns/Dimarts: sessions de càrrega/qualitat segons el tipus de setmana
   - Dimecres: sessió de volum moderat o tècnica
   - Dijous/Divendres: sessions de qualitat o específiques
   - Dissabte/Diumenge: segons el tipus de setmana (descàrrega, test, competició, etc.)

## Format de Sortida

Per a cada sessió, genera el contingut de cada part seguint aquest format JSON:

```json
{{
  "sessio_dia": "Dilluns",
  "parts": [
    {{
      "nom": "Escalfament",
      "percentatge": 15,
      "volum_m": 450,
      "contingut": "400 N suau Recuperació + 4x50 Ei C desc 15'' A1"
    }},
    {{
      "nom": "Pre-principal",
      "percentatge": 20,
      "volum_m": 600,
      "contingut": "6x100 Pull (50 A1 + 50 A2) desc 20''"
    }},
    ...
  ]
}}
```

**IMPORTANT:** Genera NOMÉS el contingut de les parts. Els percentatges i noms de parts ja estan fixats en l'estructura proporcionada.
