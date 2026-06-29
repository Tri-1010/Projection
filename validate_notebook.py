import json

try:
    with open('notebooks/Markovchain_With_Diagnostic.ipynb', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("✅ JSON is valid!")
    print(f"   Cells: {len(data['cells'])}")
    print(f"   Has metadata: {'metadata' in data}")
    print(f"   Has kernelspec: {'kernelspec' in data.get('metadata', {})}")
    print(f"   Notebook format: {data.get('nbformat', 'unknown')}.{data.get('nbformat_minor', 'unknown')}")
    
    # Check each cell
    for i, cell in enumerate(data['cells']):
        cell_type = cell.get('cell_type', 'unknown')
        print(f"   Cell {i+1}: {cell_type}")
    
except json.JSONDecodeError as e:
    print(f"❌ JSON error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
