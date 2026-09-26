# BlondSwim — Arquitectura del sistema

Resum de l'arquitectura d'agents tal com ha quedat decidida després de la Fase 0. Aquest document és la referència viva del disseny — s'actualitza quan el disseny canvia, no s'arxiva.

## Decisió d'arquitectura

Pipeline de funcions Python, **no** un framework multi-agent complet (LangGraph, CrewAI, etc.). Un LLM (Claude, via API) només s'invoca als punts que requereixen judici; la resta són funcions deterministes. Justificació: amb 4 nedadors i objectiu de prospecció, la complexitat d'un framework d'agents no aporta valor proporcional al cost de construcció i manteniment.

Dos punts d'entrada:
- `generar_macrocicle(nedador_id)` — pipeline complet, un cop per macrocicle.
- `actualitzar_microcicle(nedador_id, setmana, feedback)` — recàlcul puntual (test CSS, checkpoint post-competició).

## Capes i agents

| Capa | Agent | Tipus | Estat |
|---|---|---|---|
| 1. Percepció | Perfil de Nedador | Determinista (dades) | ✓ Model `Nedador` (Fase 0) |
| 1. Percepció | Avaluació de Rendiment (CSS) | Determinista (càlcul) | ✓ Fórmula CSS implementada a `Ritmes`; falta portar-la a codi (Fase 1) |
| 1. Percepció | Context de Competició | Determinista | ✓ Model `Competicio` (Fase 0); falta la lògica de classificació/distància entre pics (Fase 1) |
| 2. Estratègia | Macrocicle | Determinista (estructura) | ✓ Model `Macrocicle`/`Mesocicle` (Fase 0) |
| 2. Estratègia | Mesocicle | Determinista | ✓ Niat dins `Macrocicle` |
| 2. Estratègia | Selecció de Model d'entrenament | **LLM** | Pendent (Fase 2) |
| 3. Operativa | Microcicle | **LLM** | Pendent (Fase 2) — model `Sessio`/`Microcicle` ja definit (Fase 0) |
| 3. Operativa | Sèries USRPT | **LLM** | Pendent (Fase 2) |
| 3. Operativa | Taper | Determinista | Regles ja dissenyades (vegeu més avall); falta portar-les a codi (Fase 1) |
| 4. Validació | Validació Fisiològica/Temporal | Determinista | Pendent (Fase 1) |
| 4. Validació | Ajust Individual | Determinista (regles) + interpretació lleugera | Pendent (Fase 1/2) |
| 5. Sortida | Coordinador / Sortida | Determinista | Pendent (Fase 3) |

## Regles de taper — ja tancades

```
1. Si pic_actual = A i no hi ha pic previ recent (>6 setmanes)
   → Taper complet: 10-15 dies, -40/-60% volum

2. Si distància(pic_actual, pic_anterior) <= 4 setmanes
   I pic_anterior va tenir taper complet
   I (pic_actual.classe = A O nedador.pics_prioritzats inclou pic_actual)
   → Re-taper: 5-7 dies, -20/-30% volum, manteniment intensitat

3. Si pic_actual = B/C i no prioritzat
   → Sense taper dedicat; control normal dins la fase de manteniment
```

Checkpoint post-pic A (dia 4-5): marcadors subjectius (son, DOMS, motivació, RPE) determinen si la setmana de re-càrrega és normal o reduïda — mai si hi ha re-taper o no (això ja ve fixat per la regla 2).

## Model de dades (Fase 0, tancat)

```
Nedador       → id, nom, edat, categoria, proves_objectiu, pics_prioritzats,
                mode_ritme, marques_referencia, ritmes_css, parametres_ritme,
                ritmes_cursa_objectiu
Competicio    → id, nom, data_inici, data_fi, classe (A/B/C), piscina (25m/50m/aaoo)
Macrocicle    → nom, temporada, mesocicles: list[Mesocicle]
Mesocicle     → id, nom, setmanes, dates, fase_objectiu, metodologia_dominant,
                volum_min, volum_max, volum_mitja_previst, tancament,
                tecnica_focus, especific_metodologia, microcicles: list[Microcicle]
Microcicle    → tipus_base (carrega/qualitat/descarrega/taper/transicio), notes,
                volum_objectiu, dies_qualitat, test_css, competicio_id, focus_especific
Sessio        → parts: list[PartSessio] (5 parts amb % per tipus de setmana)
```

## Font de ritmes — regla de conciliació

```
SI existeix ritmes_css amb font="css_test" (i és el més recent)
    → font primària per a totes les zones (recuperació→VO2max)
ALTRAMENT
    → font = "estimat_marca" (model de percentatge sobre millor marca), provisional

Ritme de cursa objectiu (USRPT) sempre és independent de les zones fisiològiques
    → es calcula del temps objectiu a la prova, no d'A1-A3
```

Zones: Recuperació (CSS+12s / marca×1,20), A1 (CSS+6s / marca×1,13), A2=llindar (CSS+0 / marca×1,065), A3=VO2max (CSS-4s / marca×1,015), Velocitat (CSS×0,85 / **marca real de 50m**, mai extrapolada del 100m — vegeu `docs/metodologia_ritmes.md` per al raonament complet).

## Pipeline d'ingesta (Fase 0, funcional)

```
Provisional26-27.xlsx (Calendari)              → calendari.json
Planificacio_Mesocicles_<nom>.xlsx (Macrocicle) → macrocicle_<nom>.json
Planificacio_Mesocicles_<nom>.xlsx (Ritmes)     → nedador_<nom>.json
```

Lectura sempre per nom de capçalera (mai per posició fixa) al full `Calendari` i `Macrocicle`, ja que l'estructura de columnes ha canviat més d'un cop durant el projecte. La pestanya `Ritmes` és una plantilla amb adreces de cel·la fixes per disseny (no una taula amb capçaleres variables).

## Pendent — properes fases

- Fase 1: portar les regles de taper i les fórmules de zones a codi (avui són a l'Excel i en aquest document, no en funcions Python).
- Fase 1: ampliar el conversor perquè llegeixi `Microcicles` (avui `mesocicles[].microcicles` sempre surt buit).
- Fase 4: usar el macrocicle de Jep com a "golden reference" per validar que el sistema reprodueix un pla acceptable.
