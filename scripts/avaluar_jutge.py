#!/usr/bin/env python3
"""Avalua el jutge LLM contra un joc de casos etiquetats per l'entrenador.

Ús:
    python scripts/avaluar_jutge.py --etiqueta qwen3-no-raona
    python scripts/avaluar_jutge.py --etiqueta qwen3-raona --raonar si
    python scripts/avaluar_jutge.py --etiqueta gemma3 --raonar cap
        [--url http://localhost:8080] [--casos data/raw/jutge/casos.jsonl]
        [--nedador jep] [--sense-exemples] [--incloure-dubtosos]

Cada línia de `casos.jsonl` és una part de sessió (context + exercicis) i cada
exercici porta `esperat` (una categoria de `jutge.CATEGORIES`; «correcte» =
vàlid). Els exercicis amb `dubtos: true` no compten (revisa'ls i treu la marca).

Mètriques (per exercici):
- detecció: errors plantats que el jutge marca com a invàlids (recall);
- falsos positius: exercicis correctes que el jutge rebutja;
- categoria: entre els errors detectats, quants amb la categoria esperada.

Criteri: detecció >= 85% i falsos positius <= 10% -> apte com a primer filtre.
Si no, només mode ombra (avalua i registra, no rebutja).

Desa el detall a data/processed/jutge/<etiqueta>_<data-hora>.jsonl.
"""

import argparse
import json
import sys
import urllib.error
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.agents import cicles, jutge
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.sessio import EstructuraSessio, Exercici, PartSessio, Sessio
from blondswim.rutes import RutesNedador, carregar_nedador

ARREL = Path(__file__).parent.parent
MIN_DETECCIO = 0.85
MAX_FALSOS_POSITIUS = 0.10

# Zones d'exemple (CSS 1:38) si no s'indica cap nedador.
ZONES_EXEMPLE = RitmesCSS(recuperacio=110, a1=104, a2=98, a3=94, velocitat=83.3)


def _nedador(id_nedador: str | None) -> Nedador:
    if id_nedador:
        return carregar_nedador(RutesNedador(id_nedador, ARREL / "data"))
    return Nedador(
        id="exemple", nom="Exemple", categoria="master", proves_objectiu=["100m Lliure"],
        mode_ritme="temps", ritmes_css=ZONES_EXEMPLE,
    )


def _exercici(dades: dict) -> Exercici:
    camps = ("series", "distancia_m", "execucio", "intensitat", "descans", "material")
    return Exercici(**{k: dades[k] for k in camps if k in dades})


def _avisos_cicles(cas: dict, exercicis: list[Exercici], nedador: Nedador) -> list[str]:
    """Problemes de descans del cas: són feina del codi, no del jutge."""
    part = PartSessio(nom=cas["part"], percentatge_carrega=100, percentatge_qualitat=100,
                      percentatge_descarrega=100, exercicis=exercicis)
    sessio = Sessio(id=cas["id"], microcicle_setmana=1, dia="dilluns", tipus_sessio="carrega",
                    volum_total=0, estructura=EstructuraSessio(parts=[part]))
    return cicles.problemes_cicles(sessio, nedador)


def _zones(nedador: Nedador) -> dict[str, float]:
    r = nedador.ritmes_css
    if r is None:
        return {}
    return {"A1": r.a1, "A2": r.a2, "A3": r.a3}


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}% ({a}/{b})" if b else "—"


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalua el jutge LLM local.")
    parser.add_argument("--etiqueta", required=True, help="Nom de la configuració provada")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--model", help="Camp model (llama-server l'ignora)")
    parser.add_argument("--raonar", choices=["si", "no", "cap"], default="no",
                        help="enable_thinking true/false, o cap (no s'envia; Gemma)")
    parser.add_argument("--casos", default=str(ARREL / "data/raw/jutge/casos.jsonl"))
    parser.add_argument("--nedador", help="Agafa les zones de la fitxa d'aquest nedador")
    parser.add_argument("--sense-exemples", action="store_true",
                        help="Sense few-shot (per mesurar què aporten)")
    parser.add_argument("--incloure-dubtosos", action="store_true")
    args = parser.parse_args()

    raonar = {"si": True, "no": False, "cap": None}[args.raonar]
    nedador = _nedador(args.nedador)
    casos = [json.loads(linia) for linia in Path(args.casos).read_text().splitlines() if linia]

    resultats: list[dict] = []
    temps: list[float] = []
    errors_resposta = 0
    for cas in casos:
        exercicis = [_exercici(e) for e in cas["exercicis"]]
        for avis in _avisos_cicles(cas, exercicis, nedador):
            print(f"⚠ {cas['id']}: {avis} (el codi ho rebutjaria abans del jutge)")
        textos = [jutge.text_exercici(ex, nedador) for ex in exercicis]
        context = jutge.ContextJutge(
            rol=cas["rol"], fase=cas["fase"], part=cas["part"],
            objectiu_part=cas["objectiu_part"], zones=_zones(nedador),
        )
        try:
            resposta = jutge.jutjar(
                args.url, context, textos, model=args.model, raonar=raonar,
                exemples=[] if args.sense_exemples else None,
            )
        except urllib.error.URLError as e:
            print(f"✗ No es pot connectar a {args.url}: {e.reason}. És en marxa llama-server?")
            return 2
        except (ValueError, KeyError) as e:
            errors_resposta += 1
            print(f"✗ {cas['id']}: resposta no vàlida ({e})")
            continue
        temps.append(resposta.segons)
        print(f"· {cas['id']}: {len(textos)} exercicis en {resposta.segons:.1f} s")
        for dades, text, v in zip(cas["exercicis"], textos, resposta.veredictes, strict=True):
            resultats.append({
                "cas": cas["id"], "exercici": text, "esperat": dades["esperat"],
                "dubtos": bool(dades.get("dubtos")), "valid": v.valid,
                "categoria": v.categoria, "motiu": v.motiu,
            })

    comptats = [r for r in resultats if args.incloure_dubtosos or not r["dubtos"]]
    errors = [r for r in comptats if r["esperat"] != "correcte"]
    correctes = [r for r in comptats if r["esperat"] == "correcte"]
    detectats = [r for r in errors if not r["valid"]]
    falsos_positius = [r for r in correctes if not r["valid"]]
    categoria_ok = [r for r in detectats if r["categoria"] == r["esperat"]]
    encerts = len(detectats) + len(correctes) - len(falsos_positius)

    print(f"\n=== {args.etiqueta} (raonar: {args.raonar}, "
          f"exemples: {'no' if args.sense_exemples else 'sí'}) ===")
    print(f"Encert global:     {_pct(encerts, len(comptats))}")
    print(f"Detecció d'errors: {_pct(len(detectats), len(errors))}")
    print(f"Falsos positius:   {_pct(len(falsos_positius), len(correctes))}")
    print(f"Categoria encertada (dels detectats): {_pct(len(categoria_ok), len(detectats))}")
    if temps:
        print(f"Temps per crida:   mitjana {sum(temps) / len(temps):.1f} s, "
              f"màxim {max(temps):.1f} s")
    if errors_resposta:
        print(f"Respostes no vàlides: {errors_resposta} de {len(casos)} crides")

    for categoria in jutge.CATEGORIES[1:]:
        de_cat = [r for r in errors if r["esperat"] == categoria]
        if de_cat:
            print(f"  {categoria:16} {_pct(sum(not r['valid'] for r in de_cat), len(de_cat))}")

    fallades = [r for r in comptats if r["valid"] != (r["esperat"] == "correcte")]
    if fallades:
        print("\nFallades:")
        for r in fallades:
            print(f"- [{r['cas']}] {r['exercici']}\n    esperat {r['esperat']}, "
                  f"jutge {'vàlid' if r['valid'] else r['categoria']}: {r['motiu']}")
    dubtosos = [r for r in resultats if r["dubtos"]]
    if dubtosos:
        print("\nDubtosos (no compten; revisa'ls al fitxer de casos):")
        for r in dubtosos:
            print(f"- {r['exercici']}: jutge {'vàlid' if r['valid'] else r['categoria']}"
                  f" ({r['motiu']})")

    if errors and correctes:
        apte = (len(detectats) / len(errors) >= MIN_DETECCIO
                and len(falsos_positius) / len(correctes) <= MAX_FALSOS_POSITIUS)
        print("\nCriteri: " + ("✓ apte com a primer filtre" if apte
                               else "✗ només mode ombra (no rebutja sessions)"))

    sortida = ARREL / "data/processed/jutge"
    sortida.mkdir(parents=True, exist_ok=True)
    fitxer = sortida / f"{args.etiqueta}_{datetime.now().astimezone():%Y%m%d-%H%M}.jsonl"
    fitxer.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in resultats))
    print(f"\nDetall desat a {fitxer.relative_to(ARREL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
