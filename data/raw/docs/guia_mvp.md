# BlondSwim — Guia de construcció del MVP

> **Rutes (2026-10-03).** Les dades ja no són a `data/processed/`: hi ha una carpeta per nedador, `data/nedadors/<id>/` (`nedador.json`, `calendari.json`, `historial.json`, `setmanes/`, `registres/`, `log_decisions/`), i el catàleg comú `data/competicions.json`. Les referències a `data/processed/`, `nedador_jep.json`, `historial_jep.json` o `calendari.json` amb classe d'aquest document són històriques; vegeu «Dades per nedador» a `Architecture.md`.

> **Nota d'actualització (2026-10-02).** Guia inicial del MVP, històrica. Decisions superades: Espanya d'Hivern ara és **classe A** (doble pic); la sessió ja no és una plantilla fixa de 5 parts sinó una **plantilla setmanal de 5 dies amb parts per rol** (escalfament, tècnica, blocs principals, tornada a la calma); el contingut es genera setmana a setmana i el seguiment es fa amb el **full de registre** (sRPE, SRSS, sèrie de control). Estat actual: `Architecture.md` i `Fase3.md`.

Guia de referència per construir el sistema d'agents de planificació d'entrenament de natació. Ús propi + 3 nedadors coachejats, amb objectiu de prospecció com a entrenador personal (fase 2: clubs).

---

## 0. Decisions ja tancades (context)

- **Arquitectura**: pipeline de funcions Python, no framework multi-agent complet. LLM (Claude, via API) només als punts de judici; la resta són funcions deterministes.
- **Dos entry points**: `generar_macrocicle(nedador_id)` i `actualitzar_microcicle(nedador_id, setmana, feedback)`.
- **Calendari real**: 2 pics A (Catalunya Hivern 16-17 gen, Catalunya Estiu 29-30 maig). Espanya (4-7 feb) és B, amb possibilitat de re-taper si el nedador la marca com a `pic_prioritzat`.
- **Regla de re-taper**: activada per checkpoint subjectiu (son, DOMS, motivació, RPE) 4-5 dies post-pic A; determina la càrrega de la setmana de re-càrrega, no si hi ha re-taper (que sempre s'aplica si hi ha un segon pic proper).
- **Plantilla base**: `Planificacio_Mesocicles_Jep.xlsx` (estructura de mesocicles + sessió en 5 parts amb % variable) és la plantilla mestra per a tots els nedadors.

---

## 1. Model de dades

Migrar de "Excel com a font de veritat" a **JSON/SQLite intern**, amb Excel com a capa d'entrada/sortida (import inicial + export final), no com a base de dades de treball.

```
nedador.json        → id, nom, categoria, proves_objectiu[], pics_prioritzats[], 
                       ritmes_css {A1,A2,A3, data_test}, mode_ritme (temps|RPE)
calendari.json       → competicions [{data_inici, data_fi, classe, piscina, nom}]
                       (conversió de Calendari.xlsx; separar data_inici/data_fi com a camps propis)
macrocicle_template.json → mesocicles [{nom, setmanes, fase, metodologia, volum_rang}]
                       (basat en el teu full, parametritzable per nedador)
sessio_template.json → 5 parts + % per tipus de setmana (Càrrega/Qualitat/Descàrrega/Test)
```

**Primer pas tècnic**: script conversor `xlsx_to_json.py` per al `Calendari.xlsx` actual, corregint alhora:
- separar el rang de dates ("16-17 gen") en `data_inici`/`data_fi`
- reparar la fórmula `#REF!` de la pestanya `Sept`

---

## 2. Passos de construcció (ordre recomanat)

### Fase 0 — Dades (1a prioritat, base de tot la resta)
1. Definir els esquemes JSON de dalt.
2. Conversor Excel → JSON (calendari + ritmes).
3. Migrar la teva fitxa (Jep) com a primer registre complet — és l'únic nedador amb dades 100% reals ara mateix.

### Fase 1 — Mòduls deterministes (sense LLM, es poden testar aïllats)
4. Càlcul de zones CSS (A1/A2/A3) a partir del test 400+200.
5. Agent de Context de Competició: classificació + càlcul de distància entre pics + flag de candidat a re-taper.
6. Agent de Taper: les 3 regles de decisió ja definides.
7. Agents de Validació (fisiològica + temporal): regles fixes (2-3 setmanes màx. sense descàrrega, coherència de dates).
8. **Test amb el teu propi macrocicle com a oracle**: els mòduls deterministes han de reproduir exactament els volums i dates del teu full manual.

### Fase 2 — Mòduls amb LLM (judici)
9. Agent de Selecció de Model: prompt amb la taula de decisió + few-shot amb el teu cas (50 Pap + 100 Lliure + 100 IM → Bowman+USRPT combinats).
10. Agent de Microcicle: esquelet fix (5 parts, % per tipus de setmana) + LLM omple el contingut específic de cada sessió.
11. Agent d'Ajust: interpreta el checkpoint subjectiu (son/DOMS/motivació/RPE) i el test CSS periòdic, actualitza ritmes i volum de la setmana següent.

### Fase 3 — Orquestració i sortida
12. `generar_macrocicle()` i `actualitzar_microcicle()` com a funcions d'entrada.
13. Exportador de sortida: Excel amb la mateixa estructura del teu full actual (compatibilitat immediata) + resum en Markdown.

### Fase 4 — Validació amb cas real ("golden test")
14. Generar el teu propi macrocicle + microcicle de setmana 1 amb el sistema.
15. Comparar amb `Planificacio_Mesocicles_Jep.xlsx` (el que ja vas fer a mà).
16. Iterar prompts/regles fins que la diferència sigui acceptable per a tu com a entrenador — **aquest és el criteri de qualitat del sistema, no una mètrica abstracta**.

### Fase 5 — Extensió als altres 3 nedadors
17. Fitxes de Lou (CSS real), Cris i Pere (mode RPE fins al test de dijous).
18. Generar plans, revisió manual per part teva.

### Fase 6 — Material de prospecció
19. Preparar comparativa abans/després (temps d'entrenador estalviat, consistència del pla).
20. Pitch amb els 4 casos reals com a prova social per a la fase clubs.

---

## 3. Millores d'optimització i eficiència

- **Few-shot amb el teu propi pla**: usa `Planificacio_Mesocicles_Jep.xlsx` com a exemple dins els prompts dels Agents de Selecció de Model i Microcicle. Redueix iteracions i alinea l'estil de sortida amb el que ja consideres correcte.
- **Separació estricta determinista/LLM**: cap càlcul (zones CSS, %, taper) no ha de passar per l'LLM — estalvia cost de tokens i elimina una font d'error/al·lucinació en xifres.
- **Prompts versionats com a fitxers del repo** (no editats manualment al chat cada vegada): un `.md` per agent LLM, sota control de versions amb aider. Facilita iterar i revertir canvis.
- **Validació automàtica post-generació**: un cop l'LLM genera un microcicle, passa'l pels Agents de Validació deterministes abans de mostrar-lo — no confiïs només en el judici de l'LLM per a coherència fisiològica/temporal.
- **Cache de contingut estable**: l'estructura de sessió (5 parts, %) no canvia sovint dins un mateix tipus de setmana — no cal regenerar-la amb LLM cada vegada, només el contingut específic (sèries, ritmes).
- **Log de decisions**: guarda per què s'ha triat un model d'entrenament o per què s'ha aplicat re-taper (input + regla activada). Aporta auditabilitat, útil tant per confiança teva com per a la prospecció amb clients.

---

## 4. Criteri d'èxit del MVP

El sistema es considera llest per a la prospecció quan:
- Genera el macrocicle complet + el detall de microcicle d'una setmana per als **4 nedadors**.
- Tu, com a entrenador, l'acceptes **sense haver de reescriure'l a mà** (petits ajustos són acceptables; una reescriptura completa no).
- El teu propi pla generat pel sistema s'assembla prou al que ja vas fer manualment com per confiar-hi en un cas real.

---

## 5. Decisions obertes — necessito la teva confirmació

| # | Decisió | Recomanació |
|---|---|---|
| 1 | **Model LLM a utilitzar** | Claude (API), coherent amb el teu ús d'aider i el teu know-how de NiuIA en RAG/agents amb Claude. |
| 2 | **Emmagatzematge de dades** | JSON/SQLite intern com a font de veritat; Excel només com a capa d'import inicial i exportació final (no com a base de treball del sistema). |
| 3 | **Format de sortida final** | Excel amb la mateixa estructura del teu full actual (compatibilitat immediata amb el que ja uses amb els nedadors), amb un resum opcional en Markdown per lectura ràpida. |
| 4 | **Prioritat d'implementació** | Començar per tu mateix (Jep) com a únic cas de validació (Fase 0-4) abans d'estendre als altres 3 nedadors — minimitza risc i et dona un "golden test" fiable. |

Si hi estàs d'acord amb les recomanacions, comencem per la **Fase 0** (esquemes de dades + conversor Excel→JSON). Si vols canviar algun punt, digue'm quin i ajusto la guia.
