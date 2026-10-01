From e9f1cd1cd34351d5a2a596cfbbab43ad12f7113f Mon Sep 17 00:00:00 2001
From: "Josep M. Serrainat" <josepm.serrainat@gmail.com>
Date: Wed, 30 Sep 2026 17:27:15 +0200
Subject: [PATCH] feat(H): weekly organisation, intensity budget and recovery
 control

- pla_setmanal: 4 sessions Mon/Tue/Thu/Fri; one quality day (Tue, Thu in
  post-competition weeks); activation 24 h before an A/B competition
  (Fri, or Sat for Sunday races); post-competition Monday = active recovery
- week classification (dia_competicio, post_competicio) on Microcicle;
  post-competition week target = weekly minimum
- per-role parts, volume weights and session cap from minuts_max_sessio
- fixed Monday control set 4x100 A2 (cycle from A2 pace + 15s)
- intensity budget per role/phase (no lactic in Base, lactic from Build),
  butterfly cap per role (IM counts 25%), swimming rules (IM 100/200,
  no A3 under 50 m); one combined retry listing the problems
- prompt: role description, budget, week context, rules
- exporter: role label per day, optional shoulder routine on rest day
- Nedador.rutina_espatlla_dia

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LUvU62fvMmuhfwn9zwowKK
---
 scripts/generar_temporada_jep.py            |   9 +
 src/blondswim/agents/esquelet_sessions.py   |  77 ++++
 src/blondswim/agents/generar_macrocicle.py  |  19 +-
 src/blondswim/agents/generar_microcicle.py  | 102 ++++--
 src/blondswim/agents/pla_setmanal.py        | 387 ++++++++++++++++++++
 src/blondswim/export/mesocicle_excel.py     |  56 ++-
 src/blondswim/models/macrocicle.py          |   4 +
 src/blondswim/models/nedador.py             |   2 +
 src/blondswim/models/sessio.py              |   8 +-
 src/blondswim/prompts/generar_microcicle.md |  24 +-
 tests/agents/test_generar_macrocicle.py     |  24 ++
 tests/agents/test_generar_microcicle.py     | 112 ++++++
 tests/agents/test_pla_setmanal.py           | 271 ++++++++++++++
 tests/export/test_mesocicle_excel.py        |  29 ++
 14 files changed, 1087 insertions(+), 37 deletions(-)
 create mode 100644 src/blondswim/agents/pla_setmanal.py
 create mode 100644 tests/agents/test_pla_setmanal.py

diff --git a/scripts/generar_temporada_jep.py b/scripts/generar_temporada_jep.py
index dfe6ef5..b4c4ac8 100755
--- a/scripts/generar_temporada_jep.py
+++ b/scripts/generar_temporada_jep.py
@@ -28,6 +28,7 @@ from blondswim.agents.generar_microcicle import (
     generar_contingut_mesocicle,
     generar_contingut_setmana,
 )
+from blondswim.agents.pla_setmanal import DIES_PLANTILLA, usa_plantilla
 from blondswim.agents.periodificacio import _dilluns_de, avui, periodificar_temporada
 from blondswim.agents.taper import generar_pla_taper_temporada
 from blondswim.export.mesocicle_excel import exportar_mesocicle_excel, exportar_setmana_excel
@@ -113,6 +114,13 @@ def main() -> int:
         f"({sum(1 for c in competicions if c.classe == 'A')} classe A)"
     )
     print(f"   ✓ Historial: {len(historial)} sessions")
+    if usa_plantilla(nedador):
+        print(f"   ✓ Plantilla setmanal: {', '.join(nedador.dies_disponibles)}")
+    else:
+        print(
+            f"   ⚠ dies_disponibles={nedador.dies_disponibles}: no és la plantilla "
+            f"{DIES_PLANTILLA}; es fa servir l'esquelet antic"
+        )
 
     print("\n2. Generant macrocicle...")
     macrocicle, avisos_macro = generar_macrocicle(
@@ -213,6 +221,7 @@ def main() -> int:
         volum = sum(
             ex.volum_m for s in sessions for p in s.estructura.parts for ex in p.exercicis
         )
+        print(f"   · {sessions[0].notes if sessions and sessions[0].notes else ''}")
         print(
             f"   ✓ Setmana {microcicle.setmana} ({microcicle.dates}): "
             f"{len(sessions)} sessions, {volum}m (objectiu {microcicle.volum_objectiu}m)"
diff --git a/src/blondswim/agents/esquelet_sessions.py b/src/blondswim/agents/esquelet_sessions.py
index 554f4ad..9672940 100644
--- a/src/blondswim/agents/esquelet_sessions.py
+++ b/src/blondswim/agents/esquelet_sessions.py
@@ -2,6 +2,7 @@
 
 from datetime import date, timedelta
 
+from blondswim.agents import pla_setmanal
 from blondswim.models.macrocicle import Microcicle
 from blondswim.models.nedador import Nedador
 from blondswim.models.sessio import EstructuraSessio, PartSessio, Sessio
@@ -142,6 +143,9 @@ def generar_esquelet_sessions(
     Returns:
         Llista de Sessio amb estructura de parts fixada però contingut=None
     """
+    if pla_setmanal.usa_plantilla(nedador):
+        return _esquelet_plantilla(nedador, microcicle)
+
     # Determinar dies actius de la setmana
     dies_actius = nedador.dies_disponibles.copy()
 
@@ -257,3 +261,76 @@ def _crear_parts_estandard(tipus_sessio: str, volum_total: int) -> list[PartSess
         parts.append(part)
 
     return parts
+
+
+def _esquelet_plantilla(nedador: Nedador, microcicle: Microcicle) -> list[Sessio]:
+    """
+    Esquelet amb la plantilla setmanal (pla_setmanal): rols segons el tipus de
+    setmana (normal, competició dissabte/diumenge, post-competició), volum
+    repartit per pesos de rol, parts pròpies de cada rol i sèrie de control
+    fixa cada dilluns.
+    """
+    rols = pla_setmanal.rols_setmana(microcicle.dia_competicio, microcicle.post_competicio)
+    dies = sorted(rols, key=lambda d: _DIES_ORDRE[d])
+
+    # Pes de la setmana completa (les setmanes parcials no concentren volum).
+    suma_pesos = sum(pla_setmanal.PES_ROL[rols[d]] for d in dies)
+    volum_max_temps = nedador.minuts_max_sessio * pla_setmanal.METRES_PER_MINUT
+    notes = pla_setmanal.context_setmana(
+        microcicle.dia_competicio, microcicle.post_competicio
+    )
+
+    if microcicle.sessions_des_de is not None:
+        dies = [
+            d for d in dies if _data_del_dia(microcicle, d) >= microcicle.sessions_des_de
+        ]
+
+    sessions: list[Sessio] = []
+    for dia in dies:
+        rol = rols[dia]
+        objectiu = microcicle.volum_objectiu * pla_setmanal.PES_ROL[rol] / suma_pesos
+        objectiu = min(objectiu, volum_max_temps)
+        volum_sessio = _arrodonir_25(objectiu)
+        volum_min = _arrodonir_25(objectiu * (1 - pla_setmanal.MARGE_RANG_SESSIO))
+        volum_max = _arrodonir_25(
+            min(objectiu * (1 + pla_setmanal.MARGE_RANG_SESSIO), volum_max_temps)
+        )
+
+        parts: list[PartSessio] = []
+        volum_fix = 0
+        if dia == "dilluns":
+            control = pla_setmanal.part_serie_control(nedador)
+            volum_fix = sum(ex.volum_m for ex in control.exercicis)
+        volum_variable = max(volum_sessio - volum_fix, 0)
+
+        for i, (nom, pct) in enumerate(pla_setmanal.PARTS_ROL[rol]):
+            pct_sessio = round(pct * volum_variable / volum_sessio, 1) if volum_sessio else 0
+            parts.append(
+                PartSessio(
+                    nom=nom,
+                    percentatge_carrega=pct_sessio,
+                    percentatge_qualitat=pct_sessio,
+                    percentatge_descarrega=pct_sessio,
+                    contingut=None,
+                )
+            )
+            if i == 0 and volum_fix:
+                parts.append(control)
+
+        sessions.append(
+            Sessio(
+                id=f"{microcicle.mesocicle_id}_s{microcicle.setmana}_{dia}",
+                microcicle_setmana=microcicle.setmana,
+                dia=dia,
+                tipus_sessio=microcicle.tipus_base,
+                volum_total=volum_sessio,
+                estructura=EstructuraSessio(parts=parts),
+                es_dia_opcional=False,
+                notes=notes,
+                rol=rol,
+                volum_min=volum_min,
+                volum_max=volum_max,
+            )
+        )
+
+    return sessions
diff --git a/src/blondswim/agents/generar_macrocicle.py b/src/blondswim/agents/generar_macrocicle.py
index bae6504..1982d02 100644
--- a/src/blondswim/agents/generar_macrocicle.py
+++ b/src/blondswim/agents/generar_macrocicle.py
@@ -3,7 +3,7 @@
 import logging
 from datetime import date
 
-from blondswim.agents import context_competicio, periodificacio
+from blondswim.agents import context_competicio, periodificacio, pla_setmanal
 from blondswim.llm.client import DEFAULT_MODEL, get_llm_client
 from blondswim.models.calendari import Competicio
 from blondswim.models.historial import SessioRealitzada
@@ -356,6 +356,7 @@ def generar_microcicles_mesocicle(
     plans_fase: list[periodificacio.SetmanaPlan] | None = None,
     volum_setmanal_min: int = 12000,
     avisos: list[dict] | None = None,
+    competicions: list[Competicio] | None = None,
 ) -> list[Microcicle]:
     """
     Genera la llista de Microcicle (una per setmana) d'un mesocicle a partir
@@ -374,6 +375,10 @@ def generar_microcicles_mesocicle(
             prova B (taper B curt).
         avisos: Llista on s'afegeix l'avís "descarrega_insuficient" quan el
             terra aixeca una setmana de descàrrega (es muta si no és None).
+        competicions: Calendari (A/B) per classificar cada setmana
+            (dia_competicio, post_competicio). La setmana posterior a una
+            competició té com a objectiu el mínim setmanal (prioritat:
+            recuperació). Si és None, totes les setmanes són normals.
 
     Returns:
         Llista de Microcicle ordenada per setmana ascendent
@@ -417,8 +422,17 @@ def generar_microcicles_mesocicle(
             volum_carrega_anterior,
         )
 
+        dia_competicio, post_competicio = pla_setmanal.classificar_setmana(
+            plan.dilluns, competicions or []
+        )
+
         # F2: terra de volum (no taper/transició ni setmanes amb prova B).
         te_prova_b = any(c.classe == "B" for c in plan.competicions_b_c)
+
+        # H: setmana posterior a una competició -> objectiu = mínim setmanal.
+        if post_competicio and tipus_base in TIPUS_AMB_TERRA and not te_prova_b:
+            volum = _arrodonir_a_25(volum_setmanal_min)
+
         if (
             tipus_base in TIPUS_AMB_TERRA
             and not te_prova_b
@@ -450,6 +464,8 @@ def generar_microcicles_mesocicle(
                 dies_qualitat=dies_qualitat,
                 test_css=test_css,
                 sessions_des_de=sessions_des_de if i == 0 else None,
+                dia_competicio=dia_competicio,
+                post_competicio=post_competicio,
             )
         )
 
@@ -642,6 +658,7 @@ def generar_mesocicle(
         plans_fase=plans_fase,
         volum_setmanal_min=nedador.volum_setmanal_min,
         avisos=avisos,
+        competicions=competicions,
     )
     for micro in mesocicle.microcicles:
         plan = next(p for p in plans_bloc if p.setmana_iso == micro.setmana)
diff --git a/src/blondswim/agents/generar_microcicle.py b/src/blondswim/agents/generar_microcicle.py
index a23cd0c..0e6ece4 100644
--- a/src/blondswim/agents/generar_microcicle.py
+++ b/src/blondswim/agents/generar_microcicle.py
@@ -8,7 +8,13 @@ from typing import Literal
 
 from pydantic import ValidationError
 
-from blondswim.agents import context_competicio, seleccio_model, taper, validacio
+from blondswim.agents import (
+    context_competicio,
+    pla_setmanal,
+    seleccio_model,
+    taper,
+    validacio,
+)
 from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
 from blondswim.llm.client import DEFAULT_MODEL, get_llm_client
 from blondswim.models.calendari import Competicio
@@ -837,6 +843,9 @@ def _aplicar_contingut_sessio(sessio: Sessio, sessio_data: dict, setmana: int) -
         exercicis_data = part_data.get("exercicis", [])
 
         part = next((p for p in sessio.estructura.parts if p.nom == nom_part), None)
+        if part is not None and part.fixa:
+            logger.info(f"Part fixa '{nom_part}' a sessió '{sessio.id}': no es modifica")
+            continue
         if not part:
             logger.warning(
                 f"Part '{nom_part}' no trobada a sessió '{sessio.id}', ignorant. "
@@ -873,6 +882,34 @@ def _aplicar_contingut_sessio(sessio: Sessio, sessio_data: dict, setmana: int) -
         )
 
 
+def _fmt_ritme(valor: float | None) -> str:
+    """Ritme per 100 m amb dos decimals, o "N/A" si no n'hi ha."""
+    return f"{valor:.2f}" if valor is not None else "N/A"
+
+
+def _problemes_sessio(sessio: Sessio) -> list[str]:
+    """
+    Problemes d'una sessió generada: volum fora del rang flexible (marge del
+    10%), pressupost d'intensitat/papallona del rol i regles de natació
+    (vegeu pla_setmanal.problemes_contingut).
+    """
+    problemes: list[str] = []
+    volum_sessio = sum(
+        ex.volum_m for part in sessio.estructura.parts for ex in part.exercicis
+    )
+    if sessio.volum_min is not None and sessio.volum_max is not None and (
+        volum_sessio < sessio.volum_min * 0.9 or volum_sessio > sessio.volum_max * 1.1
+    ):
+        problemes.append(
+            f"volum generat {volum_sessio}m fora del rang "
+            f"[{sessio.volum_min}, {sessio.volum_max}]m. "
+            f"El volum ha estat {volum_sessio} m; ha d'estar "
+            f"entre {sessio.volum_min} i {sessio.volum_max} m."
+        )
+    problemes.extend(pla_setmanal.problemes_contingut(sessio))
+    return problemes
+
+
 def generar_microcicle(
     nedador: Nedador,
     sessions: list[Sessio],
@@ -937,6 +974,13 @@ def generar_microcicle(
                 f"(tipus: {sessio.tipus_sessio}, volum: {sessio.volum_total}m)**\n"
             )
             for part in sessio.estructura.parts:
+                if part.fixa:
+                    volum_fix = sum(ex.volum_m for ex in part.exercicis)
+                    estructura_sessions_text += (
+                        f"  - {part.nom}: JA FIXADA pel sistema ({volum_fix}m) -- "
+                        f"no la generis ni la incloguis a la resposta\n"
+                    )
+                    continue
                 if sessio.tipus_sessio == "carrega":
                     perc = part.percentatge_carrega
                 elif sessio.tipus_sessio == "qualitat":
@@ -958,11 +1002,11 @@ def generar_microcicle(
                 proves_objectiu=", ".join(nedador.proves_objectiu),
                 categoria=nedador.categoria,
                 estil_preferent=nedador.proves_objectiu[0] if nedador.proves_objectiu else "Lliure",
-                zona_recuperacio=f"{nedador.ritmes_css.recuperacio:.2f}" if nedador.ritmes_css else "N/A",
-                zona_a1=f"{nedador.ritmes_css.a1:.2f}" if nedador.ritmes_css else "N/A",
-                zona_a2=f"{nedador.ritmes_css.a2:.2f}" if nedador.ritmes_css else "N/A",
-                zona_a3=f"{nedador.ritmes_css.a3:.2f}" if nedador.ritmes_css else "N/A",
-                zona_velocitat=f"{nedador.ritmes_css.velocitat:.2f}" if nedador.ritmes_css else "N/A",
+                zona_recuperacio=_fmt_ritme(nedador.ritmes_css.recuperacio if nedador.ritmes_css else None),
+                zona_a1=_fmt_ritme(nedador.ritmes_css.a1 if nedador.ritmes_css else None),
+                zona_a2=_fmt_ritme(nedador.ritmes_css.a2 if nedador.ritmes_css else None),
+                zona_a3=_fmt_ritme(nedador.ritmes_css.a3 if nedador.ritmes_css else None),
+                zona_velocitat=_fmt_ritme(nedador.ritmes_css.velocitat if nedador.ritmes_css else None),
                 offset_recuperacio_css=f"{nedador.parametres_ritme.offset_recuperacio_css:.1f}",
                 offset_a1_css=f"{nedador.parametres_ritme.offset_a1_css:.1f}",
                 offset_a2_css=f"{nedador.parametres_ritme.offset_a2_css:.1f}",
@@ -981,6 +1025,9 @@ def generar_microcicle(
                 rol=sessio.rol,
                 volum_min=sessio.volum_min,
                 volum_max=sessio.volum_max,
+                descripcio_rol=pla_setmanal.descripcio_rol(sessio),
+                pressupost_sessio=pla_setmanal.text_pressupost(sessio),
+                context_setmana=sessio.notes or "Setmana sense competició",
             )
 
             # Crida inicial
@@ -1042,30 +1089,31 @@ def generar_microcicle(
 
             _aplicar_contingut_sessio(sessio, sessio_data, setmana)
 
-            # Verificar volum dins el rang flexible (amb marge del 10%)
-            volum_sessio = sum(
-                ex.volum_m for part in sessio.estructura.parts for ex in part.exercicis
-            )
-            if sessio.volum_min is not None and sessio.volum_max is not None:
-                fora_rang = (
-                    volum_sessio < sessio.volum_min * 0.9
-                    or volum_sessio > sessio.volum_max * 1.1
+            # Validar volum, pressupost d'intensitat i regles; UN reintent amb
+            # la llista de problemes si cal.
+            problemes = _problemes_sessio(sessio)
+            if problemes:
+                logger.warning(
+                    f"Setmana {setmana}, sessió '{sessio.id}': "
+                    + "; ".join(problemes)
+                    + ". Reintentant."
                 )
-                if fora_rang:
+                prompt_correccio = (
+                    prompt
+                    + "\n\nLa proposta anterior tenia aquests problemes. "
+                    + "Corregeix-los:\n"
+                    + "\n".join(f"- {p}" for p in problemes)
+                )
+                response = _cridar_api_sessio(client, prompt_correccio, tools)
+                sessio_data = _extreure_tool_use_sessio(response)
+                if sessio_data and _extreure_parts(sessio_data):
+                    _aplicar_contingut_sessio(sessio, sessio_data, setmana)
+                problemes_finals = _problemes_sessio(sessio)
+                if problemes_finals:
                     logger.warning(
-                        f"Setmana {setmana}, sessió '{sessio.id}': volum generat "
-                        f"{volum_sessio}m fora del rang "
-                        f"[{sessio.volum_min}, {sessio.volum_max}]m. Reintentant."
-                    )
-                    prompt_volum = (
-                        prompt
-                        + f"\n\nEl volum ha estat {volum_sessio} m; ha d'estar "
-                        f"entre {sessio.volum_min} i {sessio.volum_max} m."
+                        f"Setmana {setmana}, sessió '{sessio.id}': encara amb "
+                        f"problemes després del reintent: " + "; ".join(problemes_finals)
                     )
-                    response = _cridar_api_sessio(client, prompt_volum, tools)
-                    sessio_data = _extreure_tool_use_sessio(response)
-                    if sessio_data and _extreure_parts(sessio_data):
-                        _aplicar_contingut_sessio(sessio, sessio_data, setmana)
 
         # Verificar que totes les parts tenen contingut (advertir si no)
         for sessio in sessions:
diff --git a/src/blondswim/agents/pla_setmanal.py b/src/blondswim/agents/pla_setmanal.py
new file mode 100644
index 0000000..78aae51
--- /dev/null
+++ b/src/blondswim/agents/pla_setmanal.py
@@ -0,0 +1,387 @@
+"""
+Organització setmanal (acordada 2026-09-30, vegeu fase3.md — Fase H).
+
+- 4 sessions: dilluns, dimarts, dijous, divendres (mai 3 dies seguits sense nedar).
+- 1 sol dia de qualitat per setmana (dimarts; dijous la setmana post-competició).
+- Dia abans de competir: activació (24 h abans). Dies de descans: sense nedar.
+- Setmana post-competició: dilluns de recuperació activa i objectiu = mínim setmanal.
+- Pressupost d'intensitat i de papallona per rol, validat després de cada sessió.
+- Sèrie de control fixa (4x100 A2) cada dilluns.
+
+Tot és determinista; l'LLM només omple els exercicis dins d'aquests límits.
+"""
+
+import math
+import re
+from datetime import date, timedelta
+
+from blondswim.models.calendari import Competicio
+from blondswim.models.nedador import Nedador
+from blondswim.models.sessio import Exercici, PartSessio, Sessio
+
+# Dies de la plantilla setmanal. Si el nedador té uns altres dies disponibles,
+# l'esquelet fa servir la lògica antiga (rols per dia fixos).
+DIES_PLANTILLA: list[str] = ["dilluns", "dimarts", "dijous", "divendres"]
+
+# Pes relatiu del volum de cada rol dins la setmana.
+PES_ROL: dict[str, float] = {
+    "aerobica": 1.0,
+    "mitjana": 1.0,
+    "llarga": 1.1,
+    "qualitat": 0.95,
+    "tecnica": 0.95,
+    "activacio": 0.5,
+    "recuperacio": 0.6,
+}
+
+# Marge del rang de volum d'una sessió al voltant del seu objectiu.
+MARGE_RANG_SESSIO: float = 0.05
+
+# Metres per minut (amb descansos) per limitar el volum per temps de sessió.
+METRES_PER_MINUT: int = 40
+
+# Parts de cada rol: (nom, % del volum no fixat).
+PARTS_ROL: dict[str, list[tuple[str, float]]] = {
+    "aerobica": [
+        ("Escalfament", 15), ("Tècnica", 15), ("Aeròbic", 60), ("Tornada a la calma", 10),
+    ],
+    "llarga": [
+        ("Escalfament", 10), ("Tècnica", 10), ("Aeròbic llarg", 65),
+        ("Velocitat alàctica", 5), ("Tornada a la calma", 10),
+    ],
+    "qualitat": [
+        ("Escalfament", 15), ("Tècnica+Subaquàtic", 15), ("Aeròbic", 30),
+        ("Qualitat", 25), ("Tornada a la calma", 15),
+    ],
+    "tecnica": [
+        ("Escalfament", 15), ("Tècnica i papallona", 45), ("Aeròbic suau", 30),
+        ("Tornada a la calma", 10),
+    ],
+    "activacio": [
+        ("Escalfament", 30), ("Tècnica i sortides", 25), ("Ritme de cursa", 10),
+        ("Nedar suau", 20), ("Tornada a la calma", 15),
+    ],
+    "recuperacio": [
+        ("Escalfament", 20), ("Tècnica suau", 30),
+        ("Aeròbic suau amb canvis de ritme", 40), ("Tornada a la calma", 10),
+    ],
+}
+
+ETIQUETA_ROL: dict[str, str] = {
+    "aerobica": "Aeròbic i tècnica",
+    "mitjana": "Aeròbic i tècnica",
+    "llarga": "Aeròbica llarga",
+    "qualitat": "Qualitat",
+    "tecnica": "Tècnica",
+    "activacio": "Activació pre-competició",
+    "recuperacio": "Recuperació activa",
+}
+
+NOM_SERIE_CONTROL = "Sèrie de control"
+
+# Grups d'intensitat per al pressupost.
+_GRUP_ZONA: dict[str, str] = {
+    "Recuperació": "baixa",
+    "A1": "baixa",
+    "A2": "a2",
+    "A3": "a3",
+    "AeM": "a3",
+    "Velocitat": "velocitat",
+    "MPLA": "lactic",
+    "TOLA": "lactic",
+}
+
+# Pressupost de la sessió de qualitat segons el tipus de setmana (tipus_sessio).
+# a3 en fracció del volum de la sessió; velocitat i lactic en metres.
+_PRESSUPOST_QUALITAT: dict[str, dict[str, float]] = {
+    "carrega": {"a3": 0.25, "velocitat": 300, "lactic": 0},     # Base: llindar + alàctic
+    "qualitat": {"a3": 0.20, "velocitat": 300, "lactic": 400},  # Build: làctic
+    "descarrega": {"a3": 0.10, "velocitat": 200, "lactic": 0},  # ritme de cursa curt
+    "taper": {"a3": 0.15, "velocitat": 300, "lactic": 200},     # ritme de cursa
+    "transicio": {"a3": 0.0, "velocitat": 100, "lactic": 0},    # sense qualitat
+}
+
+_PRESSUPOST_ROL: dict[str, dict[str, float]] = {
+    "aerobica": {"a3": 0.05, "velocitat": 0, "lactic": 0},
+    "mitjana": {"a3": 0.05, "velocitat": 0, "lactic": 0},
+    "llarga": {"a3": 0.05, "velocitat": 200, "lactic": 0},
+    "tecnica": {"a3": 0.0, "velocitat": 0, "lactic": 0},
+    "activacio": {"a3": 0.0, "velocitat": 150, "lactic": 0},
+    "recuperacio": {"a2": 0, "a3": 0.0, "velocitat": 0, "lactic": 0},
+}
+
+# Màxim de papallona per sessió (m). Setmana: 300-600 m, sobretot a la tècnica.
+PAPALLONA_MAX_ROL: dict[str, int] = {
+    "tecnica": 350,
+    "qualitat": 150,
+    "llarga": 50,
+    "aerobica": 50,
+    "mitjana": 50,
+    "activacio": 50,
+    "recuperacio": 0,
+}
+PAPALLONA_SETMANA: tuple[int, int] = (300, 600)
+
+_DESCRIPCIO_ROL: dict[str, str] = {
+    "aerobica": (
+        "Aeròbic i tècnica: base aeròbica A1/A2 amb treball tècnic. "
+        "Sense velocitat ni làctic."
+    ),
+    "llarga": (
+        "Aeròbica llarga: sèries llargues A1/A2. Al final, una dosi curta de "
+        "velocitat alàctica (4-6 x 15-25 m, recuperació completa, d/45\" o més)."
+    ),
+    "tecnica": (
+        "Només tècnica: exercicis tècnics i nedar en Recuperació/A1/A2. Inclou la "
+        "papallona tècnica de la setmana (200-350 m, combinant exercicis i nedar "
+        "papallona). Sense A3, velocitat ni làctic."
+    ),
+    "activacio": (
+        "Activació 24 h abans de competir: sessió curta. Escalfament, tècnica i "
+        "sortides, 4-6 x 25 a ritme de cursa amb recuperació completa (d/1' o més) "
+        "i nedar suau per acabar."
+    ),
+    "recuperacio": (
+        "Recuperació activa després de competir: volum baix en Recuperació/A1, amb "
+        "canvis de ritme suaus i tècnica. Sense A2 (excepte la sèrie de control), "
+        "A3, velocitat ni làctic."
+    ),
+}
+_DESCRIPCIO_QUALITAT: dict[str, str] = {
+    "carrega": (
+        "Qualitat de Base: bloc principal a A3/llindar (sèries de 50-200 m) i "
+        "velocitat alàctica curta. Sense làctic (MPLA/TOLA)."
+    ),
+    "qualitat": (
+        "Qualitat de Build: producció o tolerància làctica (MPLA/TOLA) i ritme de "
+        "cursa de 100 m, amb recuperacions àmplies."
+    ),
+    "descarrega": (
+        "Qualitat de descàrrega: velocitat alàctica i ritme de cursa curt. "
+        "Sense tolerància làctica."
+    ),
+    "taper": "Qualitat de taper: ritme de cursa amb poc volum i recuperacions completes.",
+    "transicio": "Transició: sense qualitat; aeròbic suau i tècnica.",
+}
+
+
+# --- Classificació de la setmana i rols ---
+
+
+def classificar_setmana(
+    dilluns: date, competicions: list[Competicio]
+) -> tuple[str | None, bool]:
+    """
+    Retorna (dia_competicio, post_competicio) per a la setmana de `dilluns`.
+
+    Només compten les competicions A i B (les C es tracten com un dia normal).
+    - dia_competicio: "dissabte" o "diumenge" si una competició comença aquest
+      cap de setmana (si dura els dos dies, "dissabte").
+    - post_competicio: True si una competició va acabar el cap de setmana anterior.
+    """
+    dissabte = dilluns + timedelta(days=5)
+    diumenge = dilluns + timedelta(days=6)
+    dia_competicio: str | None = None
+    post = False
+    for c in competicions:
+        if c.classe not in ("A", "B"):
+            continue
+        inici = date.fromisoformat(c.data_inici)
+        fi = date.fromisoformat(c.data_fi) if c.data_fi else inici
+        if dissabte <= inici <= diumenge:
+            dia = "dissabte" if inici == dissabte else "diumenge"
+            if dia_competicio is None or dia == "dissabte":
+                dia_competicio = dia
+        if dilluns - timedelta(days=2) <= fi <= dilluns - timedelta(days=1):
+            post = True
+    return dia_competicio, post
+
+
+def rols_setmana(dia_competicio: str | None, post_competicio: bool) -> dict[str, str]:
+    """Rol de cada dia (4 sessions) segons el tipus de setmana."""
+    dia_activacio = "dissabte" if dia_competicio == "diumenge" else "divendres"
+    if post_competicio and dia_competicio:
+        # Dues competicions seguides: les curses fan d'estímul intens.
+        return {
+            "dilluns": "recuperacio", "dimarts": "aerobica",
+            "dijous": "tecnica", dia_activacio: "activacio",
+        }
+    if post_competicio:
+        return {
+            "dilluns": "recuperacio", "dimarts": "aerobica",
+            "dijous": "qualitat", "divendres": "tecnica",
+        }
+    if dia_competicio:
+        return {
+            "dilluns": "aerobica", "dimarts": "qualitat",
+            "dijous": "tecnica", dia_activacio: "activacio",
+        }
+    return {
+        "dilluns": "aerobica", "dimarts": "qualitat",
+        "dijous": "tecnica", "divendres": "llarga",
+    }
+
+
+def usa_plantilla(nedador: Nedador) -> bool:
+    """True si el nedador entrena els dies de la plantilla setmanal."""
+    return sorted(nedador.dies_disponibles) == sorted(DIES_PLANTILLA)
+
+
+def context_setmana(dia_competicio: str | None, post_competicio: bool) -> str:
+    """Text breu del context de la setmana per al prompt i les notes."""
+    parts = []
+    if post_competicio:
+        parts.append("Setmana posterior a una competició (prioritat: recuperació)")
+    if dia_competicio:
+        parts.append(f"Competició el {dia_competicio}; activació 24 h abans")
+    return ". ".join(parts) if parts else "Setmana sense competició"
+
+
+# --- Sèrie de control ---
+
+
+def cicle_serie_control(nedador: Nedador) -> str:
+    """Cicle de la sèrie de control: ritme A2 per 100 + 15\", arrodonit a 5\" amunt."""
+    if nedador.ritmes_css is None or nedador.ritmes_css.a2 is None:
+        return "d/20\""
+    segons = int(math.ceil((nedador.ritmes_css.a2 + 15) / 5) * 5)
+    return f"c/{segons // 60}'{segons % 60:02d}\""
+
+
+def part_serie_control(nedador: Nedador) -> PartSessio:
+    """Part fixa amb la sèrie de control setmanal (4x100 crol A2)."""
+    return PartSessio(
+        nom=NOM_SERIE_CONTROL,
+        percentatge_carrega=0,
+        percentatge_qualitat=0,
+        percentatge_descarrega=0,
+        fixa=True,
+        exercicis=[
+            Exercici(
+                series=4,
+                distancia_m=100,
+                execucio=(
+                    "Crol. Anota el temps de cada 100, les braçades per llargada "
+                    "i l'esforç (0-10)"
+                ),
+                descans=cicle_serie_control(nedador),
+                intensitat="A2",
+                objectiu="Control setmanal de recuperació",
+            )
+        ],
+    )
+
+
+# --- Pressupost i validació ---
+
+
+def pressupost_sessio(sessio: Sessio) -> dict[str, int]:
+    """Màxim de metres per grup d'intensitat (a2 només si està limitat)."""
+    rol = sessio.rol or "aerobica"
+    if rol == "qualitat":
+        base = _PRESSUPOST_QUALITAT.get(sessio.tipus_sessio, _PRESSUPOST_QUALITAT["carrega"])
+    else:
+        base = _PRESSUPOST_ROL.get(rol, _PRESSUPOST_ROL["aerobica"])
+    resultat = {
+        "a3": int(round(base["a3"] * sessio.volum_total / 25) * 25),
+        "velocitat": int(base["velocitat"]),
+        "lactic": int(base["lactic"]),
+    }
+    if "a2" in base:
+        resultat["a2"] = int(base["a2"])
+    return resultat
+
+
+def descripcio_rol(sessio: Sessio) -> str:
+    """Descripció del rol per al prompt."""
+    rol = sessio.rol or "aerobica"
+    if rol == "qualitat":
+        return _DESCRIPCIO_QUALITAT.get(sessio.tipus_sessio, _DESCRIPCIO_QUALITAT["carrega"])
+    return _DESCRIPCIO_ROL.get(rol, _DESCRIPCIO_ROL["aerobica"])
+
+
+def text_pressupost(sessio: Sessio) -> str:
+    """Pressupost d'intensitat i papallona en text per al prompt."""
+    p = pressupost_sessio(sessio)
+    linies = [
+        f"- A3/AeM: màxim {p['a3']} m",
+        f"- Velocitat: màxim {p['velocitat']} m",
+        f"- MPLA/TOLA (làctic): màxim {p['lactic']} m",
+    ]
+    if "a2" in p:
+        linies.append(f"- A2: màxim {p['a2']} m")
+    linies.append(
+        f"- Papallona: màxim {PAPALLONA_MAX_ROL.get(sessio.rol or 'aerobica', 50)} m "
+        "(el 25% de cada exercici d'estils compta com a papallona)"
+    )
+    return "\n".join(linies)
+
+
+def _exercicis_variables(sessio: Sessio) -> list[Exercici]:
+    return [ex for part in sessio.estructura.parts if not part.fixa for ex in part.exercicis]
+
+
+def metres_per_grup(sessio: Sessio) -> dict[str, int]:
+    """Metres per grup d'intensitat, sense les parts fixes."""
+    total: dict[str, int] = {"baixa": 0, "a2": 0, "a3": 0, "velocitat": 0, "lactic": 0}
+    for ex in _exercicis_variables(sessio):
+        grup = _GRUP_ZONA.get(ex.intensitat or "A1", "baixa")
+        total[grup] += ex.volum_m
+    return total
+
+
+_RE_PAPALLONA = re.compile(r"\bpap(allona)?\b", re.IGNORECASE)
+_RE_ESTILS = re.compile(r"\bIM\b|\bestils\b", re.IGNORECASE)
+
+
+def metres_papallona(sessio: Sessio) -> int:
+    """Papallona: l'exercici sencer si l'esmenta; el 25% si és d'estils."""
+    total = 0
+    for ex in _exercicis_variables(sessio):
+        if _RE_PAPALLONA.search(ex.execucio):
+            total += ex.volum_m
+        elif _RE_ESTILS.search(ex.execucio):
+            total += ex.volum_m // 4
+    return total
+
+
+def problemes_contingut(sessio: Sessio) -> list[str]:
+    """
+    Problemes de pressupost i de regles de natació d'una sessió generada.
+
+    - Metres per grup d'intensitat per sobre del pressupost del rol.
+    - Papallona per sobre del màxim del rol.
+    - Estils complets (>= 100 m) que no són múltiple de 100.
+    - A3 en repeticions de menys de 50 m (no s'arriba al llindar).
+    """
+    problemes: list[str] = []
+    metres = metres_per_grup(sessio)
+    pressupost = pressupost_sessio(sessio)
+    noms = {"a2": "A2", "a3": "A3/AeM", "velocitat": "Velocitat", "lactic": "MPLA/TOLA"}
+    for grup, maxim in pressupost.items():
+        if metres[grup] > maxim:
+            problemes.append(
+                f"{noms[grup]}: {metres[grup]} m, per sobre del màxim de {maxim} m"
+            )
+
+    pap_max = PAPALLONA_MAX_ROL.get(sessio.rol or "aerobica", 50)
+    pap = metres_papallona(sessio)
+    if pap > pap_max:
+        problemes.append(f"Papallona: {pap} m, per sobre del màxim de {pap_max} m")
+
+    for ex in _exercicis_variables(sessio):
+        if (
+            _RE_ESTILS.search(ex.execucio)
+            and ex.distancia_m >= 100
+            and ex.distancia_m % 100 != 0
+        ):
+            problemes.append(
+                f"'{ex.execucio}': uns estils complets han de ser de 100 o 200 m, "
+                f"no de {ex.distancia_m} m"
+            )
+        if ex.intensitat == "A3" and ex.distancia_m < 50:
+            problemes.append(
+                f"'{ex.execucio}': A3 en repeticions de {ex.distancia_m} m no arriba "
+                "al llindar (mínim 50 m)"
+            )
+    return problemes
diff --git a/src/blondswim/export/mesocicle_excel.py b/src/blondswim/export/mesocicle_excel.py
index 9a1a6ba..06f78e4 100644
--- a/src/blondswim/export/mesocicle_excel.py
+++ b/src/blondswim/export/mesocicle_excel.py
@@ -7,6 +7,7 @@ from pathlib import Path
 import openpyxl
 from openpyxl.styles import Font
 
+from blondswim.agents.pla_setmanal import ETIQUETA_ROL
 from blondswim.models.macrocicle import Mesocicle, Microcicle
 from blondswim.models.nedador import Nedador
 from blondswim.models.sessio import Sessio
@@ -28,6 +29,16 @@ _MESOS_CA = {
     11: "Novembre", 12: "Desembre",
 }
 
+# Rutina d'espatlla fora de l'aigua (opcional, ~15 min): força-resistència de la
+# part posterior de l'espatlla i estabilitzadors de l'escàpula (factor de risc
+# amb evidència, vegeu fase3.md — Fase H).
+RUTINA_ESPATLLA: list[tuple[str, str]] = [
+    ("3x15", "Rotació externa amb goma elàstica, colze a 90° enganxat al cos (cada braç)"),
+    ("3x15", "Obertures amb goma elàstica (band pull-apart), braços estirats"),
+    ("3x10", "Y-T-W estirat de bocaterrosa, sense pes o 0,5-1 kg"),
+    ("3x12", "Flexions escapulars (serrat anterior), sense doblegar els colzes"),
+]
+
 _COLUMNES = [
     "Dia", "Treball", "Execució", "Descans", "Material",
     "Intensitat", "Objectiu", "Temps (min)", "Volum (m)",
@@ -48,6 +59,7 @@ def _escriure_setmana(
     microcicle: Microcicle | None,
     setmana: int,
     sessions: list[Sessio],
+    nedador: Nedador | None = None,
 ) -> int:
     """
     Escriu una setmana (capçalera + dies + exercicis + totals) a partir de
@@ -84,7 +96,21 @@ def _escriure_setmana(
 
     sessions_des_de = microcicle.sessions_des_de if microcicle else None
 
+    # Rutina d'espatlla en un dia de descans (si el nedador en té i cau dins la setmana).
+    dia_rutina = nedador.rutina_espatlla_dia if nedador else None
+    rutina_pendent = (
+        data_inici is not None
+        and dia_rutina in _DIES_ORDRE
+        and not any(s.dia == dia_rutina for s in sessions_setmana)
+    )
+    if rutina_pendent and sessions_des_de is not None:
+        rutina_pendent = data_inici + timedelta(days=_DIES_ORDRE[dia_rutina]) >= sessions_des_de
+
     for sessio in sessions_setmana:
+        if rutina_pendent and _DIES_ORDRE[sessio.dia] > _DIES_ORDRE[dia_rutina]:
+            row_idx = _escriure_rutina_espatlla(ws, row_idx, data_inici, dia_rutina)
+            rutina_pendent = False
+
         if data_inici:
             data_sessio = data_inici + timedelta(days=_DIES_ORDRE[sessio.dia])
             if sessions_des_de is not None and data_sessio < sessions_des_de:
@@ -92,6 +118,10 @@ def _escriure_setmana(
             capçalera_dia = f"{sessio.dia.capitalize()} {data_sessio.day}"
         else:
             capçalera_dia = sessio.dia.capitalize()
+        # Etiqueta del rol només per a les sessions de la plantilla setmanal
+        # (porten context a `notes`); la lògica antiga no canvia de format.
+        if sessio.rol in ETIQUETA_ROL and sessio.notes:
+            capçalera_dia += f" — {ETIQUETA_ROL[sessio.rol]}"
 
         cell = ws.cell(row=row_idx, column=1, value=capçalera_dia)
         cell.font = Font(bold=True)
@@ -124,9 +154,32 @@ def _escriure_setmana(
         ws.cell(row=row_idx, column=9, value=volum_total_dia).font = Font(bold=True)
         row_idx += 1
 
+    if rutina_pendent:
+        row_idx = _escriure_rutina_espatlla(ws, row_idx, data_inici, dia_rutina)
+
     return row_idx + 1  # línia en blanc entre setmanes
 
 
+def _escriure_rutina_espatlla(ws, row_idx: int, data_inici: date, dia: str) -> int:
+    """Escriu el bloc de la rutina d'espatlla (dia de descans). Retorna la fila següent."""
+    data = data_inici + timedelta(days=_DIES_ORDRE[dia])
+    cell = ws.cell(
+        row=row_idx,
+        column=1,
+        value=(
+            f"{dia.capitalize()} {data.day} — Descans a l'aigua. "
+            "Rutina d'espatlla (opcional, 15 min, fora de l'aigua)"
+        ),
+    )
+    cell.font = Font(bold=True)
+    row_idx += 1
+    for treball, execucio in RUTINA_ESPATLLA:
+        ws.cell(row=row_idx, column=2, value=treball)
+        ws.cell(row=row_idx, column=3, value=execucio)
+        row_idx += 1
+    return row_idx
+
+
 def _ajustar_amplades(ws) -> None:
     """Ajusta l'amplada de cada columna al contingut (màxim 50)."""
     for col in ws.columns:
@@ -184,6 +237,7 @@ def exportar_mesocicle_excel(
             microcicles_per_setmana.get(setmana),
             setmana,
             resultats[setmana],
+            nedador,
         )
 
     _ajustar_amplades(ws)
@@ -220,7 +274,7 @@ def exportar_setmana_excel(
     ws = wb.active
     ws.title = f"Setmana {microcicle.setmana}"
 
-    _escriure_setmana(ws, 1, mesocicle, microcicle, microcicle.setmana, sessions)
+    _escriure_setmana(ws, 1, mesocicle, microcicle, microcicle.setmana, sessions, nedador)
 
     _ajustar_amplades(ws)
     wb.save(output_path)
diff --git a/src/blondswim/models/macrocicle.py b/src/blondswim/models/macrocicle.py
index c4cdbb6..ba918ea 100644
--- a/src/blondswim/models/macrocicle.py
+++ b/src/blondswim/models/macrocicle.py
@@ -21,6 +21,10 @@ class Microcicle(BaseModel):
     competicio_test_oficial: str | None = None
     test_avaluacio: str | None = None
     focus_especific: str | None = None
+    # Organització setmanal (pla_setmanal.classificar_setmana): dia de la
+    # competició A/B del cap de setmana i si la setmana segueix una competició.
+    dia_competicio: Literal["dissabte", "diumenge"] | None = None
+    post_competicio: bool = False
 
 class Mesocicle(BaseModel):
     """
diff --git a/src/blondswim/models/nedador.py b/src/blondswim/models/nedador.py
index c126dff..2ae1299 100644
--- a/src/blondswim/models/nedador.py
+++ b/src/blondswim/models/nedador.py
@@ -77,3 +77,5 @@ class Nedador(BaseModel):
     volum_setmanal_min: int = 12000
     # Durada màxima d'una sessió (F7, encara no validat).
     minuts_max_sessio: int = 105
+    # Dia de descans amb rutina d'espatlla fora de l'aigua (opcional, 15 min).
+    rutina_espatlla_dia: str | None = None
diff --git a/src/blondswim/models/sessio.py b/src/blondswim/models/sessio.py
index abca4fb..830ba6b 100644
--- a/src/blondswim/models/sessio.py
+++ b/src/blondswim/models/sessio.py
@@ -42,6 +42,9 @@ class PartSessio(BaseModel):
     percentatge_descarrega: float
     contingut: str | None = None
     exercicis: list[Exercici] = []
+    # Part fixada pel codi (p.ex. la sèrie de control): l'LLM no la genera
+    # ni la modifica, i no compta per al pressupost d'intensitat.
+    fixa: bool = False
 
 class EstructuraSessio(BaseModel):
     """
@@ -69,6 +72,9 @@ class Sessio(BaseModel):
     estructura: EstructuraSessio
     es_dia_opcional: bool = False  # True si correspon al dia opcional del nedador
     notes: str | None = None
-    rol: Literal["llarga", "mitjana", "qualitat"] | None = None
+    rol: Literal[
+        "llarga", "mitjana", "qualitat",
+        "aerobica", "tecnica", "activacio", "recuperacio",
+    ] | None = None
     volum_min: int | None = None
     volum_max: int | None = None
diff --git a/src/blondswim/prompts/generar_microcicle.md b/src/blondswim/prompts/generar_microcicle.md
index 74c3f73..539e184 100644
--- a/src/blondswim/prompts/generar_microcicle.md
+++ b/src/blondswim/prompts/generar_microcicle.md
@@ -4,9 +4,10 @@ Ets un expert entrenador de natació especialitzat en planificació d'entrenamen
 
 ## Context del Nedador
 
-**Proves objectiu:** {proves_objectiu}
+**Proves objectiu (per ordre de prioritat):** {proves_objectiu}
 **Categoria:** {categoria}
-**Estil preferent:** {estil_preferent}
+
+Reparteix el treball d'estils segons aquestes proves. La papallona té un límit de metres per sessió (vegeu el pressupost) per protegir l'espatlla: prioritza la tècnica i la regularitat, no el volum.
 
 **Zones de ritme CSS (pace per 100m, només per calibrar la teva descripció -- NO les escriguis mai com a número al camp `execucio` ni a cap altre camp de text):**
 - Recuperació: {zona_recuperacio}
@@ -25,7 +26,7 @@ Ets un expert entrenador de natació especialitzat en planificació d'entrenamen
 
 **Setmana:** {setmana}
 **Tipus de setmana:** {tipus_base}
-**Volum objectiu total:** {volum_objectiu}m
+**Context:** {context_setmana}
 
 ## Metodologia d'Entrenament Seleccionada
 
@@ -82,10 +83,19 @@ Els següents exemples mostren l'estil i vocabulari utilitzat en sessions anteri
 
    **VOLUM FLEXIBLE:** la sessió ha de fer entre {volum_min} i {volum_max} m (piscina 25 m). La suma de `series × distancia_m` de tots els exercicis ha d'estar dins d'aquest rang. Si no hi arribes, ajusta el nombre de `series` o la `distancia_m` (sempre múltiple de 25) fins a quedar-hi dins.
 
-   **ROL DE LA SESSIÓ ({rol}):**
-   - `llarga`: aeròbic A1/A2 continu i sèries llargues.
-   - `mitjana`: mixta, tècnica + aeròbic.
-   - `qualitat`: A3/Velocitat/MPLA amb recuperacions àmplies, menys volum.
+   **ROL DE LA SESSIÓ ({rol}):** {descripcio_rol}
+
+   **PRESSUPOST D'INTENSITAT (OBLIGATORI).** Suma dels metres (`series × distancia_m`) per camp `intensitat`, sense comptar les parts fixades pel sistema:
+{pressupost_sessio}
+   La resta del volum ha de ser Recuperació, A1 o A2. El sistema ho comprova i rebutja la sessió si se supera.
+
+   **REGLES DE NATACIÓ (OBLIGATÒRIES):**
+   - Uns estils complets (IM) són de 100 o 200 m, mai 125 o 150 m. Els estils "per estils" en repeticions de 25 m són vàlids.
+   - A3 només en repeticions de 50 m o més: en 25 m no s'arriba al llindar.
+   - Velocitat i ritme de cursa amb recuperació completa (d/45" o més per cada 25 m).
+   - Els descansos han de ser coherents amb el ritme de la zona: el cicle ha de deixar com a mínim 10" de descans a A3 i 15" a A2.
+   - No afegeixis metres de farciment (p.ex. un 25 m solt) per quadrar el volum: ajusta les sèries principals.
+   - Fes servir només termes de natació reals. Si una expressió no és estàndard, descriu l'acció.
 
    **VARIETAT DINS LA SETMANA:** no repeteixis el mateix conjunt principal que les sessions ja generades aquesta setmana. Consulta el resum següent i varia el focus.
 
diff --git a/tests/agents/test_generar_macrocicle.py b/tests/agents/test_generar_macrocicle.py
index e02e471..77b6468 100644
--- a/tests/agents/test_generar_macrocicle.py
+++ b/tests/agents/test_generar_macrocicle.py
@@ -816,3 +816,27 @@ def test_setmana_amb_prova_b_sense_terra():
     vmin, _vmax = VOLUM_SETMANAL_CARREGA["Build1"]
     assert microcicles[0].volum_objectiu == round(vmin * FACTOR_PROVA_B / 25) * 25
     assert microcicles[0].volum_objectiu < 12000
+
+
+# --- Fase H: classificació de la setmana ---
+
+
+def test_setmana_post_competicio_objectiu_minim_i_classificacio():
+    """La setmana posterior a una prova B té com a objectiu el mínim setmanal."""
+    # Bloc Build1 des del 07/09/2026; prova B diumenge 13/09 (setmana 0).
+    prova_b = Competicio(
+        id="b1", nom="B", data_inici="2026-09-13", data_fi="2026-09-13",
+        classe="B", piscina="25m",
+    )
+    mesocicle = _crear_mesocicle("Build1", "1-4", 0, 0, 0)
+    plans = _plans_bloc("Build1", 4)
+
+    microcicles = generar_microcicles_mesocicle(
+        mesocicle, plans, volum_setmanal_min=12000, competicions=[prova_b]
+    )
+
+    assert microcicles[0].dia_competicio == "diumenge"
+    assert microcicles[0].post_competicio is False
+    assert microcicles[1].post_competicio is True
+    assert microcicles[1].volum_objectiu == 12000
+    assert all(m.dia_competicio is None for m in microcicles[1:])
diff --git a/tests/agents/test_generar_microcicle.py b/tests/agents/test_generar_microcicle.py
index c86c4d6..e927369 100644
--- a/tests/agents/test_generar_microcicle.py
+++ b/tests/agents/test_generar_microcicle.py
@@ -1763,3 +1763,115 @@ def test_generar_contingut_setmana_dilluns_fora_del_macrocicle(nedador_test, met
             avisos_pics_a=[],
             metodologia=metodologia_test,
         )
+
+
+# --- Fase H: pressupost d'intensitat i parts fixes ---
+
+
+def _nedador_plantilla() -> Nedador:
+    return Nedador(
+        id="jep",
+        nom="Jep",
+        categoria="master",
+        proves_objectiu=["100m lliure", "100m estils"],
+        mode_ritme="temps",
+        dies_disponibles=["dilluns", "dimarts", "dijous", "divendres"],
+        ritmes_css=RitmesCSS(font="css_test", a1=87.1, a2=82.09, a3=78.24, velocitat=67.55),
+    )
+
+
+def _resposta_parts(parts: list[dict]):
+    block = MagicMock()
+    block.type = "tool_use"
+    block.name = "retornar_contingut_sessio"
+    block.input = {"parts": parts}
+    response = MagicMock()
+    response.content = [block]
+    response.stop_reason = "tool_use"
+    response.usage = MagicMock(output_tokens=100)
+    return response
+
+
+def _parts_valides(sessio: Sessio, extra: dict | None = None) -> list[dict]:
+    """Una part principal amb el volum que falta (A1) i 2x25 A1 a la resta."""
+    variables = [p for p in sessio.estructura.parts if not p.fixa]
+    fix = sum(ex.volum_m for p in sessio.estructura.parts if p.fixa for ex in p.exercicis)
+    objectiu = sessio.volum_total - fix - 50 * (len(variables) - 1)
+    if extra:
+        objectiu -= extra["series"] * extra["distancia_m"]
+    parts = []
+    for i, p in enumerate(variables):
+        exercicis = (
+            [{"series": objectiu // 100, "distancia_m": 100, "execucio": "Crol",
+              "intensitat": "A1"}]
+            if i == 0
+            else [{"series": 2, "distancia_m": 25, "execucio": "Crol", "intensitat": "A1"}]
+        )
+        if extra and i == 0:
+            exercicis.append(extra)
+        parts.append({"nom": p.nom, "exercicis": exercicis})
+    return parts
+
+
+def test_pressupost_superat_reintenta_amb_els_problemes(metodologia_test):
+    """Làctic a la qualitat de Base -> reintent amb la llista de problemes."""
+    nedador = _nedador_plantilla()
+    microcicle = Microcicle(
+        setmana=41, dates="05-11/10/2026", mesocicle_id="meso_1", tipus_base="carrega",
+        volum_objectiu=13600, dies_qualitat=False, test_css=False,
+    )
+    sessio = next(
+        s for s in generar_esquelet_sessions(nedador, microcicle) if s.rol == "qualitat"
+    )
+    lactic = {"series": 4, "distancia_m": 50, "execucio": "Crol", "intensitat": "MPLA"}
+
+    mock_client = MagicMock()
+    mock_client.messages.create.side_effect = [
+        _resposta_parts(_parts_valides(sessio, extra=lactic)),
+        _resposta_parts(_parts_valides(sessio)),
+    ]
+    with patch(
+        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
+    ):
+        generar_microcicle(nedador, [sessio], metodologia_test)
+
+    assert mock_client.messages.create.call_count == 2
+    primer = mock_client.messages.create.call_args_list[0].kwargs["messages"][0]["content"]
+    segon = mock_client.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
+    assert "MPLA/TOLA (làctic): màxim 0 m" in primer
+    assert "Qualitat de Base" in primer
+    assert "MPLA/TOLA: 200 m, per sobre del màxim de 0 m" in segon
+    intensitats = {
+        ex.intensitat for p in sessio.estructura.parts for ex in p.exercicis
+    }
+    assert "MPLA" not in intensitats
+
+
+def test_part_fixa_no_es_demana_ni_es_sobreescriu(metodologia_test):
+    """La sèrie de control del dilluns no va al prompt com a part a generar."""
+    nedador = _nedador_plantilla()
+    microcicle = Microcicle(
+        setmana=41, dates="05-11/10/2026", mesocicle_id="meso_1", tipus_base="carrega",
+        volum_objectiu=13600, dies_qualitat=False, test_css=False,
+    )
+    dilluns = generar_esquelet_sessions(nedador, microcicle)[0]
+    parts = _parts_valides(dilluns)
+    parts.append({
+        "nom": "Sèrie de control",
+        "exercicis": [{"series": 8, "distancia_m": 50, "execucio": "x", "intensitat": "A3"}],
+    })
+
+    mock_client = MagicMock()
+    mock_client.messages.create.return_value = _resposta_parts(parts)
+    with patch(
+        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
+    ):
+        generar_microcicle(nedador, [dilluns], metodologia_test)
+
+    prompt = mock_client.messages.create.call_args_list[0].kwargs["messages"][0]["content"]
+    assert "Sèrie de control: JA FIXADA pel sistema (400m)" in prompt
+    control = next(p for p in dilluns.estructura.parts if p.fixa)
+    assert [(e.series, e.distancia_m, e.intensitat) for e in control.exercicis] == [
+        (4, 100, "A2")
+    ]
+    assert mock_client.messages.create.call_count == 1
diff --git a/tests/agents/test_pla_setmanal.py b/tests/agents/test_pla_setmanal.py
new file mode 100644
index 0000000..3321f56
--- /dev/null
+++ b/tests/agents/test_pla_setmanal.py
@@ -0,0 +1,271 @@
+"""Tests de l'organització setmanal (Fase H): rols, esquelet, pressupost i validació."""
+
+from datetime import date
+
+import pytest
+
+from blondswim.agents import pla_setmanal
+from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
+from blondswim.models.calendari import Competicio
+from blondswim.models.macrocicle import Microcicle
+from blondswim.models.nedador import Nedador, RitmesCSS
+from blondswim.models.sessio import EstructuraSessio, Exercici, PartSessio, Sessio
+
+DILLUNS = date(2026, 10, 5)  # setmana ISO 41
+
+
+def _comp(data_inici: str, data_fi: str | None = None, classe: str = "B") -> Competicio:
+    return Competicio(
+        id=f"c_{data_inici}",
+        nom="Competició",
+        data_inici=data_inici,
+        data_fi=data_fi or data_inici,
+        classe=classe,
+        piscina="25m",
+    )
+
+
+@pytest.fixture
+def nedador_plantilla() -> Nedador:
+    return Nedador(
+        id="jep",
+        nom="Jep",
+        categoria="master",
+        proves_objectiu=["100m lliure", "100m estils"],
+        mode_ritme="temps",
+        dies_disponibles=["dilluns", "dimarts", "dijous", "divendres"],
+        ritmes_css=RitmesCSS(font="css_test", a1=87.1, a2=82.09, a3=78.24, velocitat=67.55),
+    )
+
+
+def _microcicle(
+    tipus_base: str = "carrega",
+    volum: int = 13600,
+    dia_competicio: str | None = None,
+    post: bool = False,
+) -> Microcicle:
+    return Microcicle(
+        setmana=41,
+        dates="05-11/10/2026",
+        mesocicle_id="meso_1",
+        tipus_base=tipus_base,
+        volum_objectiu=volum,
+        dies_qualitat=False,
+        test_css=False,
+        dia_competicio=dia_competicio,
+        post_competicio=post,
+    )
+
+
+# --- Classificació de la setmana ---
+
+
+def test_classificar_setmana_normal():
+    assert pla_setmanal.classificar_setmana(DILLUNS, []) == (None, False)
+
+
+def test_classificar_competicio_dissabte_i_diumenge():
+    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-10")]) == ("dissabte", False)
+    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-11")]) == ("diumenge", False)
+
+
+def test_classificar_a_de_dos_dies_activa_divendres():
+    comp = _comp("2026-10-10", "2026-10-11", classe="A")
+    assert pla_setmanal.classificar_setmana(DILLUNS, [comp]) == ("dissabte", False)
+
+
+def test_classificar_post_competicio():
+    """Competició que acaba el cap de setmana anterior -> post_competicio."""
+    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-04")]) == (None, True)
+
+
+def test_classificar_ignora_competicions_c():
+    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-10", classe="C")]) == (
+        None,
+        False,
+    )
+
+
+# --- Rols ---
+
+
+def test_rols_setmana_normal_un_sol_dia_de_qualitat():
+    rols = pla_setmanal.rols_setmana(None, False)
+    assert rols == {
+        "dilluns": "aerobica", "dimarts": "qualitat",
+        "dijous": "tecnica", "divendres": "llarga",
+    }
+    assert list(rols.values()).count("qualitat") == 1
+
+
+def test_rols_competicio_dissabte_activacio_divendres():
+    rols = pla_setmanal.rols_setmana("dissabte", False)
+    assert rols["divendres"] == "activacio"
+    assert rols["dimarts"] == "qualitat"
+
+
+def test_rols_competicio_diumenge_activacio_dissabte():
+    rols = pla_setmanal.rols_setmana("diumenge", False)
+    assert rols["dissabte"] == "activacio"
+    assert "divendres" not in rols
+    assert len(rols) == 4
+
+
+def test_rols_post_competicio_recuperacio_i_qualitat_dijous():
+    rols = pla_setmanal.rols_setmana(None, True)
+    assert rols["dilluns"] == "recuperacio"
+    assert rols["dijous"] == "qualitat"
+
+
+def test_rols_post_i_competicio_sense_qualitat():
+    rols = pla_setmanal.rols_setmana("dissabte", True)
+    assert "qualitat" not in rols.values()
+    assert rols["dilluns"] == "recuperacio"
+    assert rols["divendres"] == "activacio"
+
+
+# --- Esquelet amb plantilla ---
+
+
+def test_esquelet_plantilla_setmana_normal(nedador_plantilla):
+    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle())
+
+    assert [s.dia for s in sessions] == ["dilluns", "dimarts", "dijous", "divendres"]
+    assert [s.rol for s in sessions] == ["aerobica", "qualitat", "tecnica", "llarga"]
+    assert all(s.tipus_sessio == "carrega" for s in sessions)
+    assert abs(sum(s.volum_total for s in sessions) - 13600) <= 50
+    for s in sessions:
+        assert s.volum_min <= s.volum_total <= s.volum_max
+        assert s.volum_total % 25 == 0
+
+
+def test_esquelet_serie_de_control_fixa_dilluns(nedador_plantilla):
+    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle())
+    dilluns = sessions[0]
+
+    fixes = [p for p in dilluns.estructura.parts if p.fixa]
+    assert len(fixes) == 1
+    control = fixes[0]
+    assert control.nom == pla_setmanal.NOM_SERIE_CONTROL
+    ex = control.exercicis[0]
+    assert (ex.series, ex.distancia_m, ex.intensitat) == (4, 100, "A2")
+    assert ex.descans == "c/1'40\""  # A2 82" + 15" -> 1'40" (múltiple de 5")
+    assert dilluns.estructura.parts[1].fixa  # just després de l'escalfament
+    assert all(not p.fixa for s in sessions[1:] for p in s.estructura.parts)
+
+
+def test_esquelet_competicio_diumenge_activacio_dissabte(nedador_plantilla):
+    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle(dia_competicio="diumenge"))
+
+    assert [s.dia for s in sessions] == ["dilluns", "dimarts", "dijous", "dissabte"]
+    activacio = sessions[-1]
+    assert activacio.rol == "activacio"
+    assert activacio.volum_total < min(s.volum_total for s in sessions[:-1])
+    assert "diumenge" in activacio.notes
+
+
+def test_esquelet_post_competicio_dilluns_de_recuperacio(nedador_plantilla):
+    sessions = generar_esquelet_sessions(
+        nedador_plantilla, _microcicle(volum=12000, post=True)
+    )
+
+    assert sessions[0].rol == "recuperacio"
+    assert sessions[0].volum_total < 0.7 * sessions[1].volum_total
+    assert abs(sum(s.volum_total for s in sessions) - 12000) <= 50
+
+
+def test_esquelet_sense_plantilla_manté_la_logica_antiga():
+    nedador = Nedador(
+        id="x", nom="X", categoria="master", proves_objectiu=[], mode_ritme="temps"
+    )  # dies per defecte: dilluns-dijous
+    sessions = generar_esquelet_sessions(nedador, _microcicle())
+    assert {s.rol for s in sessions} <= {"llarga", "mitjana", "qualitat"}
+    assert all(s.notes is None for s in sessions)
+
+
+def test_cicle_serie_control_sense_ritmes():
+    nedador = Nedador(
+        id="x", nom="X", categoria="master", proves_objectiu=[], mode_ritme="rpe"
+    )
+    assert pla_setmanal.cicle_serie_control(nedador) == "d/20\""
+
+
+# --- Pressupost i validació ---
+
+
+def _sessio(rol: str, tipus: str, exercicis: list[Exercici], fixes: list[Exercici] | None = None):
+    parts = [
+        PartSessio(
+            nom="Principal", percentatge_carrega=100, percentatge_qualitat=100,
+            percentatge_descarrega=100, exercicis=exercicis,
+        )
+    ]
+    if fixes:
+        parts.append(
+            PartSessio(
+                nom="Control", percentatge_carrega=0, percentatge_qualitat=0,
+                percentatge_descarrega=0, exercicis=fixes, fixa=True,
+            )
+        )
+    volum = sum(e.volum_m for e in exercicis + (fixes or []))
+    return Sessio(
+        id="s", microcicle_setmana=41, dia="dimarts", tipus_sessio=tipus,
+        volum_total=volum, estructura=EstructuraSessio(parts=parts), rol=rol,
+    )
+
+
+def _ex(series, dist, intensitat, execucio="Crol"):
+    return Exercici(series=series, distancia_m=dist, execucio=execucio, intensitat=intensitat)
+
+
+def test_qualitat_base_no_admet_lactic():
+    s = _sessio("qualitat", "carrega", [_ex(30, 100, "A1"), _ex(4, 25, "MPLA")])
+    assert any("MPLA/TOLA" in p for p in pla_setmanal.problemes_contingut(s))
+
+
+def test_qualitat_build_admet_lactic_dins_pressupost():
+    s = _sessio("qualitat", "qualitat", [_ex(28, 100, "A1"), _ex(6, 50, "MPLA")])
+    assert pla_setmanal.problemes_contingut(s) == []
+
+
+def test_tecnica_no_admet_a3():
+    s = _sessio("tecnica", "carrega", [_ex(28, 100, "A1"), _ex(4, 100, "A3")])
+    assert any("A3/AeM" in p for p in pla_setmanal.problemes_contingut(s))
+
+
+def test_papallona_per_sobre_del_maxim():
+    s = _sessio(
+        "tecnica", "carrega",
+        [_ex(25, 100, "A1"), _ex(8, 50, "A1", "Pap tècnica, un braç")],
+    )
+    assert any("Papallona" in p for p in pla_setmanal.problemes_contingut(s))
+
+
+def test_estils_compten_un_quart_de_papallona():
+    s = _sessio("aerobica", "carrega", [_ex(2, 100, "A1", "IM per estils")])
+    assert pla_setmanal.metres_papallona(s) == 50
+
+
+def test_estils_125_invalid_i_a3_en_25():
+    s = _sessio(
+        "qualitat", "carrega",
+        [_ex(28, 100, "A1"), _ex(1, 125, "A2", "IM complet"), _ex(4, 25, "A3")],
+    )
+    problemes = pla_setmanal.problemes_contingut(s)
+    assert any("125 m" in p for p in problemes)
+    assert any("llindar" in p for p in problemes)
+
+
+def test_parts_fixes_no_compten_al_pressupost():
+    """La sèrie de control (A2) no trenca el pressupost de la recuperació."""
+    s = _sessio(
+        "recuperacio", "carrega",
+        [_ex(16, 100, "A1")],
+        fixes=[_ex(4, 100, "A2")],
+    )
+    assert pla_setmanal.problemes_contingut(s) == []
+
+
+def test_recuperacio_no_admet_a2_variable():
+    s = _sessio("recuperacio", "carrega", [_ex(16, 100, "A1"), _ex(4, 100, "A2")])
+    assert any(p.startswith("A2") for p in pla_setmanal.problemes_contingut(s))
diff --git a/tests/export/test_mesocicle_excel.py b/tests/export/test_mesocicle_excel.py
index 604a7e8..8ac3a0c 100644
--- a/tests/export/test_mesocicle_excel.py
+++ b/tests/export/test_mesocicle_excel.py
@@ -348,3 +348,32 @@ def test_exportar_setmana_igual_que_dins_del_mesocicle(
     )
 
     assert _valors(path_setmana) == _valors(path_meso)
+
+
+# --- Fase H: rol a la capçalera i rutina d'espatlla ---
+
+
+def test_exportar_setmana_rol_i_rutina_espatlla(mesocicle_test, estructura_test, tmp_path):
+    """Sessions de plantilla: etiqueta del rol; rutina d'espatlla el dimecres (descans)."""
+    nedador = Nedador(
+        id="jep", nom="Jep", categoria="master", proves_objectiu=["100m lliure"],
+        mode_ritme="temps", dies_disponibles=["dilluns", "dimarts", "dijous", "divendres"],
+        rutina_espatlla_dia="dimecres",
+    )
+    microcicle = mesocicle_test.microcicles[1]  # 05-11/10/2026
+    sessions = []
+    for dia, rol in (("dilluns", "aerobica"), ("dimarts", "qualitat"), ("dijous", "tecnica")):
+        s = _sessio(2, dia, estructura_test)
+        s.rol = rol
+        s.notes = "Setmana sense competició"
+        sessions.append(s)
+
+    path = exportar_setmana_excel(
+        nedador, mesocicle_test, microcicle, sessions, tmp_path / "h.xlsx"
+    )
+    primeres = [f[0] for f in _valors(path) if f[0]]
+
+    assert "Dilluns 5 — Aeròbic i tècnica" in primeres
+    assert "Dimarts 6 — Qualitat" in primeres
+    rutina = next(i for i, v in enumerate(primeres) if v.startswith("Dimecres 7 — Descans"))
+    assert primeres.index("Dimarts 6 — Qualitat") < rutina < primeres.index("Dijous 8 — Tècnica")
-- 
2.43.0