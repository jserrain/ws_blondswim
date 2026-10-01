BlondSwim — Fase 1: Mòduls deterministes ✅ TANCADA

Estat: 4/4 mòduls implementats i testats — 62 tests, tots passant, make lint net. Fase 1 tancada (2026-09-27). Continua a fase2.md.

Mòdul 1 — zones_css.py ✅ Fet

Funcions: calcular_zones_des_de_marca, calcular_zones_des_de_css, calcular_css_pace, determinar_zones_nedador.

12 tests, inclosos test_zones_jep_validacio_manual, test_velocitat_no_supera_marca_100 (guarda contra el bug físic on Velocitat sortia més ràpida que el PB de 100m), test_prioritat_css_test, test_fallback_marques.

Commits: 8b1c00f, 6c3d842.

Mòdul 2 — context_competicio.py ✅ Fet
Per què es va revisar

El document TrainingPeaks/Joe Friel confirma retrospectivament una decisió ja presa: Espanya (4-7 feb), a ~3 setmanes de Catalunya Hivern, és classe B i no A — exactament el "conflict management" que descriu el document (dues A massa properes → la segona es tracta de facto com a B). No calia canviar-ho, però ara tenim la justificació metodològica explícita, i una validació que ho comprova explícitament al codi.

Regles
Màxim 1-3 competicions classe A per temporada.
Mínim 8-12 setmanes de separació entre A consecutives (12-16 per esports de resistència llarga).
Si dues A cauen més a prop del mínim, la segona es tracta de facto com a B (flag, no reclassificació automàtica — decisió de l'entrenador).
Funcions implementades

setmanes_entre(comp_a, comp_b) -> float, validar_espaiat_pics_a(competicions, min_setmanes=8, max_setmanes=12) -> list[dict] (avisos "separacio_insuficient" i "massa_pics_a"), detectar_candidats_retaper(competicions, pics_prioritzats, finestra_setmanes=4) -> list[dict], classificar_pics(competicions) -> dict.

Tests (8, tots passant)

test_setmanes_entre_catalunya_hivern_estiu, test_setmanes_entre_catalunya_hivern_espanya, test_validar_espaiat_pics_a_calendari_real (0 avisos amb les 2 A reals, ben separades), test_validar_espaiat_pics_a_separacio_insuficient, test_validar_espaiat_pics_a_massa_pics_a, test_detectar_candidats_retaper_amb_prioritat, test_detectar_candidats_retaper_sense_prioritat, test_classificar_pics_calendari_real.

Commit: 6154a41.

Mòdul 3 — taper.py ✅ Fet
Regles de taper i recuperació (definitives, implementades)
Classe	Taper pre-competició	Recuperació post-competició
A	Progressiu, 14 dies per defecte (rang 7-21, parametritzable)	14 dies per defecte (rang 1-3 setmanes)
B	Lleuger, 3 dies per defecte (rang 2-4) — s'aplica a totes les B, prioritzades o no	3 dies per defecte (rang 2-5), activa
C	Cap ajust	1 dia, estàndard

Re-taper: si una B marcada pic_prioritzat cau ≤4 setmanes després d'una A, s'activa sempre un re-taper dedicat; la càrrega de la setmana de re-càrrega es determina per checkpoint subjectiu 4-5 dies post-pic A.

Funcions implementades

calcular_taper(competicio, dies_taper_a=14, dies_recuperacio_a=14, dies_taper_b=3, dies_recuperacio_b=3) -> dict, detectar_retaper(competicio_a, competicio_b, pics_prioritzats, finestra_setmanes=4) -> bool, generar_pla_taper_temporada(competicions, pics_prioritzats) -> list[dict].

Tests (11, tots passant)

test_calcular_taper_classe_a, test_calcular_taper_classe_b, test_calcular_taper_classe_c, test_calcular_taper_parametres_personalitzats, test_detectar_retaper_amb_prioritat, test_detectar_retaper_sense_prioritat, test_detectar_retaper_competicio_anterior_no_classe_a, test_detectar_retaper_fora_de_finestra, test_generar_pla_taper_temporada_calendari_complet, test_generar_pla_taper_temporada_sense_retaper, test_generar_pla_taper_temporada_ordre_cronologic.

Commit: 83ad2e8.

Mòdul 4 — validacio.py ✅ Fet

Últim mòdul determinista de la Fase 1. Valida la coherència d'un pla generat (macrocicle+mesocicles+microcicles), combinant regles fixes amb els avisos ja generats pels Mòduls 2 i 3.

Enfocament (confirmat)
ACWR (Acute:Chronic Workload Ratio) en lloc de comparació punt a punt: ratio = volum_setmana_actual / mitjana(volum_ultimes_4_setmanes). Zona òptima 0.8–1.3, avís sever si ratio > 1.5.
Ràtio càrrega:descàrrega per categoria (confirmada pel Jep): junior 2:1, master/absolut 3:1 setmanes de càrrega màximes abans d'exigir descàrrega.
Funcions implementades

validar_descarrega_periodica(microcicles, categoria) -> list[dict], validar_progressio_volum(microcicles, finestra_setmanes=4, ratio_min=0.8, ratio_max=1.3, ratio_risc=1.5) -> list[dict], validar_coherencia_taper(microcicles, pla_taper) -> list[dict], validar_pla_complet(macrocicle, categoria, pla_taper, avisos_pics_a) -> list[dict].

Tests (9, tots passant)

test_validar_descarrega_periodica_master_sense_avis, test_validar_descarrega_periodica_master_amb_avis, test_validar_descarrega_periodica_junior_amb_avis, test_validar_progressio_volum_estable, test_validar_progressio_volum_salt_risc, test_validar_progressio_volum_represa_normal (verifica que l'ACWR no dona fals positiu en una represa normal post-descàrrega), test_validar_coherencia_taper_amb_avis, test_validar_pla_complet_integracio, test_validar_pla_complet_amb_avisos_pics_a.

Commits: e1cef67, 3521399.

Resum Fase 1
Mòdul	Fitxer	Tests	Estat
1	zones_css.py	12	✅
2	context_competicio.py	8	✅
3	taper.py	11	✅
4	validacio.py	9	✅
Total mòduls Fase 1		40	
Total suite (amb Fase 0)		62	✅ make lint net

Fase 1 tancada. Continua a fase2.md (Agent de Selecció de Model + Agent de Microcicle, LLM).