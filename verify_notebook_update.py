"""
Script để verify notebook đã được update
"""

import json

# Đọc notebook
with open("notebooks/Markovchain_With_Diagnostic_Clean.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

print(f"✅ Total cells: {len(nb['cells'])}")

# Kiểm tra cell 27
cell_27 = nb["cells"][27]
print(f"\n📝 Cell 27:")
print(f"   Type: {cell_27['cell_type']}")
if cell_27["cell_type"] == "markdown":
    content = "".join(cell_27["source"])
    print(f"   Content preview: {content[:100]}...")
    if "SO SÁNH P_23" in content or "SO SÁNH P_MOB" in content:
        print(f"   ✅ Cell 27 là markdown về so sánh P_23!")
    else:
        print(f"   ❌ Cell 27 không phải về so sánh P_23")

# Kiểm tra cell 28
cell_28 = nb["cells"][28]
print(f"\n📝 Cell 28:")
print(f"   Type: {cell_28['cell_type']}")
if cell_28["cell_type"] == "code":
    content = "".join(cell_28["source"])
    print(f"   Content preview: {content[:100]}...")
    if "compare_p24_vs_forecast" in content and "target_mob=23" in content:
        print(f"   ✅ Cell 28 là code chạy so sánh với MOB 23!")
    else:
        print(f"   ❌ Cell 28 không phải code so sánh MOB 23")

print("\n" + "="*80)
print("✅ VERIFICATION COMPLETE!")
print("="*80)
