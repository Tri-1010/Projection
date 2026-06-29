import json

# Read as binary first to check BOM
with open('notebooks/Markovchain_With_Diagnostic.ipynb', 'rb') as f:
    first_bytes = f.read(10)
    print(f"First bytes: {first_bytes}")
    
    # Check for BOM
    if first_bytes.startswith(b'\xef\xbb\xbf'):
        print("⚠️  Found UTF-8 BOM marker")
    else:
        print("✅ No BOM marker")

# Try to load and re-save without BOM
try:
    with open('notebooks/Markovchain_With_Diagnostic.ipynb', 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    
    # Save without BOM
    with open('notebooks/Markovchain_With_Diagnostic_Clean.ipynb', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    
    print("✅ Created clean version: Markovchain_With_Diagnostic_Clean.ipynb")
    
except Exception as e:
    print(f"❌ Error: {e}")
