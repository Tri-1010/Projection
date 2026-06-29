"""
Test tất cả các fixes
"""

import json
import sys

print("="*80)
print("KIỂM TRA TẤT CẢ CÁC FIXES")
print("="*80)

# 1. Kiểm tra script
print("\n1️⃣ Kiểm tra compare_p24_vs_forecast.py...")
try:
    from compare_p24_vs_forecast import compare_p24_vs_forecast
    print("   ✅ Import thành công!")
    
    # Kiểm tra function có đúng parameters không
    import inspect
    sig = inspect.signature(compare_p24_vs_forecast)
    params = list(sig.parameters.keys())
    
    required_params = ["matrices_by_mob", "forecast_results", "actual_results", "disb_total_by_vintage"]
    optional_params = ["buckets_30p", "target_mob", "forecast_mob_end"]
    
    for param in required_params:
        if param not in params:
            print(f"   ❌ Thiếu parameter: {param}")
            sys.exit(1)
    
    for param in optional_params:
        if param not in params:
            print(f"   ❌ Thiếu parameter: {param}")
            sys.exit(1)
    
    print("   ✅ Parameters đầy đủ!")
    
except Exception as e:
    print(f"   ❌ Lỗi: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. Kiểm tra notebook
print("\n2️⃣ Kiểm tra notebook...")
try:
    with open("notebooks/Markovchain_With_Diagnostic_Clean.ipynb", "r", encoding="utf-8") as f:
        nb = json.load(f)
    
    print(f"   ✅ Notebook có {len(nb['cells'])} cells")
    
    # Kiểm tra cell 27
    cell_27 = nb["cells"][27]
    if cell_27["cell_type"] != "markdown":
        print(f"   ❌ Cell 27 không phải markdown!")
        sys.exit(1)
    
    content_27 = "".join(cell_27["source"])
    if "SO SÁNH P_23" not in content_27 and "SO SÁNH P_MOB" not in content_27:
        print(f"   ❌ Cell 27 không có nội dung đúng!")
        sys.exit(1)
    
    print("   ✅ Cell 27 OK (markdown về so sánh)")
    
    # Kiểm tra cell 28
    cell_28 = nb["cells"][28]
    if cell_28["cell_type"] != "code":
        print(f"   ❌ Cell 28 không phải code!")
        sys.exit(1)
    
    content_28 = "".join(cell_28["source"])
    
    # Kiểm tra duplicate import
    import_count = content_28.count("from compare_p24_vs_forecast import compare_p24_vs_forecast")
    if import_count > 1:
        print(f"   ❌ Cell 28 có {import_count} duplicate imports!")
        sys.exit(1)
    
    if "target_mob=23" not in content_28:
        print(f"   ❌ Cell 28 không có target_mob=23!")
        sys.exit(1)
    
    if "forecast_mob_end=29" not in content_28:
        print(f"   ❌ Cell 28 không có forecast_mob_end=29!")
        sys.exit(1)
    
    print("   ✅ Cell 28 OK (code chạy so sánh với MOB 23)")
    
except Exception as e:
    print(f"   ❌ Lỗi: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Tổng kết
print("\n" + "="*80)
print("✅ TẤT CẢ KIỂM TRA PASS!")
print("="*80)
print("\n📝 Tóm tắt:")
print("   ✅ compare_p24_vs_forecast.py - OK")
print("   ✅ Notebook cell 27 (markdown) - OK")
print("   ✅ Notebook cell 28 (code) - OK")
print("   ✅ Không có duplicate import")
print("   ✅ target_mob=23 đã được set")
print("   ✅ forecast_mob_end=29 đã được set")

print("\n🚀 Sẵn sàng chạy notebook!")
print("\n💡 Bước tiếp theo:")
print("   1. Mở: notebooks/Markovchain_With_Diagnostic_Clean.ipynb")
print("   2. Kernel → Restart & Run All")
print("   3. Xem kết quả ở cell 28")
