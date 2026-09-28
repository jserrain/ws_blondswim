"""Script per debugar les capçaleres de la pestanya Microcicles."""

from pathlib import Path
import openpyxl

def llegir_capçaleres(ws, header_row: int = 1) -> dict[str, int]:
    """Llegir capçaleres (còpia de la funció original)."""
    capçaleres = {}
    for cell in ws[header_row]:
        if cell.value:
            # Normalitzar: minúscules, sense espais interns
            nom_normalitzat = str(cell.value).strip().lower().replace(" ", "")
            capçaleres[nom_normalitzat] = cell.column
    return capçaleres

def main():
    base_dir = Path(__file__).parent.parent
    fitxer = base_dir / "data" / "raw" / "Planificacio_Mesocicles_Jep.xlsx"
    
    print(f"📂 Obrint: {fitxer}")
    wb = openpyxl.load_workbook(fitxer, data_only=True)
    
    if "Microcicles" not in wb.sheetnames:
        print(f"❌ Pestanya 'Microcicles' no trobada")
        print(f"Pestanyes disponibles: {wb.sheetnames}")
        return
    
    ws = wb["Microcicles"]
    print(f"\n✅ Pestanya 'Microcicles' trobada")
    
    # Llegir capçaleres
    capçaleres = llegir_capçaleres(ws, header_row=1)
    
    print(f"\n📋 Capçaleres normalitzades retornades per llegir_capçaleres():")
    print(f"   Total: {len(capçaleres)} capçaleres")
    for nom, idx in sorted(capçaleres.items()):
        print(f"   '{nom}' -> columna {idx}")
    
    print(f"\n🔍 Capçaleres originals (sense normalitzar) a la fila 1:")
    for cell in ws[1]:
        if cell.value:
            print(f"   Columna {cell.column}: '{cell.value}'")
    
    print(f"\n🔎 Verificació de capçaleres requerides:")
    required = ["mesocicle", "microcicle", "setmana", "dates", "tipus", "volumobjectiu(m)"]
    for req in required:
        if req in capçaleres:
            print(f"   ✓ '{req}' trobada")
        else:
            print(f"   ✗ '{req}' NO trobada")
            # Buscar similars
            similars = [k for k in capçaleres.keys() if req[:5] in k or k[:5] in req]
            if similars:
                print(f"      Similars: {similars}")

if __name__ == "__main__":
    main()
