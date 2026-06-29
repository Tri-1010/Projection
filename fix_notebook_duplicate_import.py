"""
Sửa lỗi duplicate import trong notebook
"""

import json

# Đọc notebook
with open("notebooks/Markovchain_With_Diagnostic_Clean.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

print(f"Total cells: {len(nb['cells'])}")

# Tìm cell 28 (code cell)
cell_28 = nb["cells"][28]

if cell_28["cell_type"] == "code":
    source = cell_28["source"]
    print(f"\n📝 Cell 28 source (before fix):")
    print("".join(source[:5]))
    
    # Sửa duplicate import
    fixed_source = []
    import_seen = False
    
    for line in source:
        if "from compare_p24_vs_forecast import compare_p24_vs_forecast" in line:
            if not import_seen:
                fixed_source.append(line)
                import_seen = True
            # Skip duplicate
        else:
            fixed_source.append(line)
    
    # Update cell
    nb["cells"][28]["source"] = fixed_source
    
    print(f"\n📝 Cell 28 source (after fix):")
    print("".join(fixed_source[:5]))
    
    # Ghi lại notebook
    with open("notebooks/Markovchain_With_Diagnostic_Clean.ipynb", "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    
    print("\n✅ Đã sửa lỗi duplicate import!")
else:
    print(f"\n❌ Cell 28 không phải code cell!")
