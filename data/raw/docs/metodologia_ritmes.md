# Metodologia de la pestanya "Ritmes" — raonament i aplicació a altres nedadors

> **Nota d'actualització (2026-10-02).** Un test CSS nou es registra amb `scripts/registrar_test_css.py --t400 ... --t200 ...` (`zones_css.ritmes_des_de_test_css()`), que aplica els offsets d'aquest document i desa les zones a `nedador_jep.json`. Detectat (Fase H2): les zones estimades actuals del Jep són més ràpides que el seu ritme real d'entrenament; cal el test CSS del 03/10/2026.
>
> **Quin fitxer descriu aquest document.** Les adreces de cel·la (B4-B22, B44, B48:B52, files 76-79) són les de la pestanya `Ritmes` de `Planificacio_Mesocicles_Jep.xlsx` (a `data/raw/` del repo), la que llegeix `xlsx_to_json.py`. **`Ritmes_Jep.xlsx`, el fitxer d'aquest projecte, és la versió antiga**: només 3 zones (A1-A3), sense Font 1 (CSS), sense Recuperació ni Velocitat, i amb adreces diferents. Es manté com a referència històrica.
>
> **Dues taules del Jep no coincideixen.** `Ritmes_Jep.xlsx` dona per 100 m A1 1'27", A2 1'22", A3 1'18"; la pestanya `Ritmes` de `Provisional26-27.xlsx` dona A1 1'27"-1'30", A2 1'24"-1'25", A3 1'20"-1'21". Totes dues són estimacions per millor marca (Font 2) i **queden substituïdes pel test CSS** (Font 1). La pestanya `Ritmes` del `Provisional` també conté la taula de Lou i les proves objectiu A de cada nedador.

Aquest document explica **per què** la pestanya `Ritmes` està dissenyada com està, quines fonts fonamenten cada xifra, i **què cal canviar** (i què no) per aplicar-la a Lou, Cris i Pere.

---

## 1. Problema de partida

El full original tenia un únic mètode: estimar zones d'entrenament (A1/A2/A3) com a percentatge sobre la millor marca de 100m lliures. Dos problemes:

1. **Font única i estàtica**: una marca de competició pot ser de fa mesos i no reflecteix la forma actual.
2. **Escala incompleta**: només 3 zones (A1-A3), sense zona de recuperació ni de velocitat/sprint — aquesta última és imprescindible per a l'Agent de Sèries USRPT (proves de 50m com 50 Papallona).

## 2. Font primària vs. font de fallback — per què dues fonts

**Font 1 (Test CSS 400+200)** és el mètode validat en la literatura de natació competitiva: deriva d'una mesura directa de l'estat de forma actual, es recalcula cada 6-8 setmanes, i la pràctica estàndard el situa entre les zones de llindar i VO2max.

**Font 2 (% sobre millor marca)** és una estimació raonable **quan no hi ha test recent** (per exemple, si un nedador encara no ha fet el CSS aquesta temporada), però no reflecteix la forma del moment amb la mateixa precisió.

**Regla de conciliació**: la Font 1 té sempre prioritat quan hi ha dades (`B9` i `B10` omplerts). Si no, la Font 2 actua com a fallback. Això es resol automàticament amb una fórmula `IF` a cada zona — no cal triar manualment quina font fer servir.

## 3. D'on surt cada zona — fonts i validesa

| Zona | Font 1 (CSS) | Font 2 (marca) | Font/justificació |
|---|---|---|---|
| Recuperació | CSS + 12s | marca × (1+0,20) | Maglischo (2003), *Swimming Fastest* — marc de 5 zones sobre ritme de llindar |
| A1 (aeròbic extensiu) | CSS + 6s | marca × (1+0,13) | Íd. |
| A2 (llindar) | CSS + 0s (= CSS) | marca × (1+0,065) | El CSS **és** per definició el ritme de llindar |
| A3 (VO2max) | CSS − 4s | marca × (1+0,015) | Íd. |
| Velocitat (sprint) | CSS × 0,85 | **marca real de 50m** × factor d'escala | Vegeu punt 4 — correcció important |

Els valors "increment X% sobre marca" (0,13 / 0,065 / 0,015) ja existien al teu full original — no els he inventat, els he mantingut com a Font 2. Els offsets de CSS (+12/+6/0/-4 segons) i el factor 0,85 de Velocitat són l'aportació nova, extrets del marc de 5 zones de Maglischo, el llibre de referència en periodització de natació.

## 4. Correcció important — per què la Velocitat NO surt del 100m

**Primer intent (incorrecte)**: vaig calcular Velocitat com el 85% del temps de la marca de 100m, igual que fèiem amb el CSS. **Resultat erroni**: donava un ritme *més ràpid que el propi rècord personal de 100m*, cosa físicament absurda.

**Per què passava**: el 85% de Maglischo està calibrat sobre el **CSS** (un ritme de llindar, sostenible, per definició més lent que un rècord). Aplicar el mateix 85% sobre la **marca** (que ja és un esforç gairebé màxim) multiplica un temps ja ràpid per un factor pensat per a un temps més lent — es "sobre-accelera" artificialment.

**Solució aplicada**: quan la font és la marca (no el CSS), la zona de Velocitat s'ancora directament a la **marca real de 50m lliures** del nedador (una dada que ja existia al full, abans només de referència) i s'escala a 100m amb el mateix factor d'escala 50↔100m que ja fas servir per a la resta de zones. Això manté la coherència física: la Velocitat mai supera el que el nedador ha demostrat que és capaç de fer.

**Lliçó per a la resta de nedadors**: aquesta correcció és estructural, no específica de Jep — s'aplica igual per a Lou, Cris i Pere. Sempre que la font sigui "marca", la Velocitat surt del 50m real, mai d'un percentatge del 100m.

## 5. Què cal canviar per a cada nedador (i què no)

**Cel·les a editar** (marcades en groc al full):

| Secció | Cel·les | Nota |
|---|---|---|
| Dades del nedador | `B4` (nom), `B5` (edat) | |
| Font 1 — CSS | `B8`-`B10` | Buides fins que facin el test. Un cop fet, s'omplen i la Font 1 pren prioritat automàticament. |
| Font 2 — Marca | `B15` (100m lliures), `B19`-`B22` (altres marques) | `B20` (50m lliures) és ara numèric i s'usa activament al càlcul (Velocitat) |
| Ritme de cursa objectiu | Files 76-79 | Substituir per les proves preferents de cada nedador (ja diferents: Lou/Cris/Pere no tenen les mateixes que Jep) |

**Cel·les a NO tocar** (fórmules i paràmetres compartits):

- Tots els percentatges/offsets (files 25-41) — són el model, no dades del nedador. Es mantenen idèntics per a tota la squad tret que hi hagi un motiu fisiològic específic per personalitzar-los (per exemple, un nedador amb una tècnica d'esquena molt diferent podria justificar un ajust individual — no és el cas ara).
- Totes les fórmules de les zones calculades i les taules (files 44-79) — es recalculen soles a partir de les dades de dalt.

**Cas particular Cris i Pere**: com que encara no tenen CSS ni marca de referència fiable (mode RPE), per a ells `B15` i `B20` es poden deixar en blanc temporalment — la Font 2 donarà `#VALUE!` o buit fins que hi hagi almenys una marca real introduïda. Recomanació: fer-los introduir la seva millor marca de 100m i de 50m encara que sigui d'entrenament (no oficial), etiquetant-ho clarament com a estimació provisional, fins al primer test CSS.

## 6. Relació amb el conversor `xlsx_to_json.py`

Aquesta estructura (una pestanya `Ritmes` idèntica per nedador, amb les mateixes adreces de cel·la) és el que permet que el conversor llegeixi totes les fitxes amb el mateix codi, sense casos especials per nedador — només canvia el fitxer d'origen. Quan tinguis els 4 fulls (Jep + Lou + Cris + Pere), el pas següent és ampliar `xlsx_to_json.py` perquè llegeixi `B44` (font activa) i esculli quins camps del `RitmesCSS`/`MarquesReferencia` omplir a cada `nedador.json`, seguint exactament la mateixa regla de conciliació documentada al punt 2.
