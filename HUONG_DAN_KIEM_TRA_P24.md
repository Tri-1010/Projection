# 🔍 Hướng Dẫn Kiểm Tra P_24 Có Ổn Định Không

## Cách 1: Chạy Script (Đơn Giản Nhất)

### Bước 1: Mở notebook của bạn
Mở file notebook đang chạy model (ví dụ: `Markovchain.ipynb` hoặc `Final_Workflow.ipynb`)

### Bước 2: Chạy đến hết Calibration
Đảm bảo đã chạy xong các cells:
- Load data
- Build transition matrices
- Calibration

### Bước 3: Thêm cell mới và chạy

```python
# Import script
from check_p24_stability import check_p24_stability

# Chạy kiểm tra
check_p24_stability(matrices_by_mob, parent_fallback)
```

### Kết quả sẽ cho biết:

```
================================================================================
KIỂM TRA: P_24 CÓ THỰC SỰ ỔN ĐỊNH KHÔNG?
================================================================================

💡 Logic:
   - Nếu P_24 ổn định (< 1% movement) → K = 1.0 là ĐÚNG ✅
   - Nếu P_24 có movement (> 2%) → K = 1.0 gây DEL tăng ❌

📊 Đã phân tích 10 cohorts có P_24 thật:

   Product/Score        | Movement | Status
   ---------------------|----------|--------
   C/650+_10M-_POS      | 0.0250   | ⚠️ Hơi cao
   C/550-649_10M-_POS   | 0.0180   | ✅ Ổn định
   ...

📈 TỔNG HỢP:
   - Rất ổn định (< 1%):   3 cohorts (30.0%)
   - Ổn định (1-2%):       4 cohorts (40.0%)
   - Hơi cao (2-3%):       2 cohorts (20.0%)
   - Cao (> 3%):           1 cohorts (10.0%)

================================================================================
KẾT LUẬN:
================================================================================

✅ ĐA SỐ COHORTS CÓ P_24 ỔN ĐỊNH (< 2% movement)

💡 Giải thích:
   - P_24 đã ổn định tốt
   - K = 1.0 là HỢP LÝ
   - Nếu DEL vẫn tăng → Vấn đề KHÔNG phải do K cao

🔍 Cần kiểm tra:
   1. % cohorts dùng parent fallback (Cell 7)
   2. Aggregation effect (Cell 9)
   3. Có thể vấn đề là fallback, không phải K
```

---

## Cách 2: Kiểm Tra Thủ Công (Nếu Script Không Chạy)

### Cell 1: Kiểm tra 1 cohort cụ thể

```python
# Chọn 1 product và score để test
prod_str = "C"  # Thay bằng product của bạn
score_str = "650+_10M-_POS"  # Thay bằng score của bạn

print(f"Kiểm tra cohort: {prod_str}/{score_str}")
print("="*80)

# Lấy P_24
if 24 in matrices_by_mob[prod_str]:
    if score_str in matrices_by_mob[prod_str][24]:
        P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
        
        print("\n📊 Transition matrix P_24:")
        print(P_24)
        
        # Tính movement từ DPD0
        if "DPD0" in P_24.index:
            print("\n🔍 Transition rates từ DPD0:")
            print(P_24.loc["DPD0"])
            
            # Tính tổng movement → DEL30+
            del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
            movement = sum(P_24.loc["DPD0", s] for s in del30_states if s in P_24.columns)
            
            print(f"\n💡 Tổng movement DPD0 → DEL30+: {movement:.4f} ({movement*100:.2f}%)")
            
            print("\n" + "="*80)
            print("KẾT LUẬN:")
            print("="*80)
            
            if movement < 0.01:
                print("\n✅ P_24 RẤT ỔN ĐỊNH (< 1%)")
                print("   → K = 1.0 là HOÀN TOÀN ĐÚNG")
                print("   → Nếu DEL vẫn tăng, vấn đề KHÔNG phải do K")
                print("   → Kiểm tra % cohorts dùng fallback")
            elif movement < 0.02:
                print("\n✅ P_24 ỔN ĐỊNH (1-2%)")
                print("   → K = 1.0 là HỢP LÝ")
                print("   → DEL có thể tăng nhẹ (0.5-1% sau 6 tháng)")
            elif movement < 0.03:
                print("\n⚠️ P_24 HƠI CAO (2-3%)")
                print("   → K = 1.0 có thể gây DEL tăng")
                print("   → Xem xét giảm K xuống 0.5-0.7")
            else:
                print("\n❌ P_24 KHÔNG ỔN ĐỊNH (> 3%)")
                print("   → K = 1.0 GÂY DEL TĂNG")
                print("   → Cần giảm K xuống 0.3-0.5")
                print("   → HOẶC chấp nhận DEL tăng (nếu đây là reality)")
    else:
        print(f"⚠️ Không tìm thấy score {score_str} ở MOB 24")
else:
    print(f"⚠️ Không tìm thấy MOB 24 cho product {prod_str}")
```

### Cell 2: So sánh P_24 vs Parent Fallback

```python
# So sánh P_24 với parent fallback
prod_str = "C"
score_str = "650+_10M-_POS"

print(f"So sánh P_24 vs Parent Fallback: {prod_str}/{score_str}")
print("="*80)

if 24 in matrices_by_mob[prod_str] and score_str in matrices_by_mob[prod_str][24]:
    P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
    key_parent = (prod_str, score_str)
    
    if key_parent in parent_fallback:
        P_parent = parent_fallback[key_parent]
        
        if "DPD0" in P_24.index and "DPD0" in P_parent.index:
            del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
            
            p24_mov = sum(P_24.loc["DPD0", s] for s in del30_states if s in P_24.columns)
            parent_mov = sum(P_parent.loc["DPD0", s] for s in del30_states if s in P_parent.columns)
            
            print(f"\n📊 Movement comparison:")
            print(f"   P_24:    {p24_mov:.4f} ({p24_mov*100:.2f}%)")
            print(f"   Parent:  {parent_mov:.4f} ({parent_mov*100:.2f}%)")
            print(f"   Diff:    {parent_mov - p24_mov:+.4f} ({(parent_mov - p24_mov)*100:+.2f}%)")
            
            print("\n" + "="*80)
            print("KẾT LUẬN:")
            print("="*80)
            
            if parent_mov > p24_mov * 2:
                print("\n✅ XÁC NHẬN: Parent fallback cao hơn P_24 RẤT NHIỀU")
                print(f"   - P_24: {p24_mov*100:.2f}% (ổn định)")
                print(f"   - Parent: {parent_mov*100:.2f}% (cao gấp {parent_mov/p24_mov:.1f}x)")
                print("\n💡 Giải thích:")
                print("   - Nếu nhiều cohorts dùng parent fallback")
                print("   - → K = 1.0 + Parent fallback = DEL tăng")
                print("   - → Vấn đề là FALLBACK, không phải K")
            elif parent_mov > p24_mov * 1.5:
                print("\n✅ Parent fallback cao hơn P_24 đáng kể")
                print(f"   - P_24: {p24_mov*100:.2f}%")
                print(f"   - Parent: {parent_mov*100:.2f}% (cao gấp {parent_mov/p24_mov:.1f}x)")
            elif parent_mov > p24_mov:
                print("\n✅ Parent fallback hơi cao hơn P_24")
            else:
                print("\n⚠️ P_24 cao hơn hoặc bằng parent fallback")
                print("   → Không bình thường, cần kiểm tra lại")
```

### Cell 3: Kiểm tra tất cả cohorts

```python
# Kiểm tra tất cả cohorts
print("Kiểm tra tất cả cohorts có P_24")
print("="*80)

p24_movements = []

for prod_str in matrices_by_mob.keys():
    if 24 not in matrices_by_mob[prod_str]:
        continue
        
    for score_str in matrices_by_mob[prod_str][24].keys():
        # Skip fallback
        is_fallback = matrices_by_mob[prod_str][24][score_str].get("is_fallback", False)
        if is_fallback:
            continue
        
        P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
        
        # Tính movement
        if "DPD0" in P_24.index:
            del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
            movement = sum(P_24.loc["DPD0", s] for s in del30_states if s in P_24.columns)
            
            p24_movements.append({
                "product": prod_str,
                "score": score_str,
                "movement": movement
            })

print(f"\n📊 Tìm thấy {len(p24_movements)} cohorts có P_24 thật")

# Phân loại
very_stable = [x for x in p24_movements if x["movement"] < 0.01]
stable = [x for x in p24_movements if 0.01 <= x["movement"] < 0.02]
moderate = [x for x in p24_movements if 0.02 <= x["movement"] < 0.03]
high = [x for x in p24_movements if x["movement"] >= 0.03]

print(f"\n📈 Phân loại:")
print(f"   - Rất ổn định (< 1%):  {len(very_stable):3d} cohorts ({len(very_stable)/len(p24_movements)*100:.1f}%)")
print(f"   - Ổn định (1-2%):      {len(stable):3d} cohorts ({len(stable)/len(p24_movements)*100:.1f}%)")
print(f"   - Hơi cao (2-3%):      {len(moderate):3d} cohorts ({len(moderate)/len(p24_movements)*100:.1f}%)")
print(f"   - Cao (> 3%):          {len(high):3d} cohorts ({len(high)/len(p24_movements)*100:.1f}%)")

print("\n" + "="*80)
print("KẾT LUẬN:")
print("="*80)

if len(high) > len(p24_movements) * 0.3:
    print("\n❌ NHIỀU COHORTS CÓ P_24 KHÔNG ỔN ĐỊNH")
    print("   → K = 1.0 GÂY DEL TĂNG")
    print("   → Cần giảm K xuống 0.3-0.5")
elif len(moderate) + len(high) > len(p24_movements) * 0.5:
    print("\n⚠️ MỘT SỐ COHORTS CÓ P_24 VẪN CÓ MOVEMENT")
    print("   → K = 1.0 có thể gây DEL tăng nhẹ")
    print("   → Xem xét giảm K xuống 0.5-0.7")
else:
    print("\n✅ ĐA SỐ COHORTS CÓ P_24 ỔN ĐỊNH")
    print("   → K = 1.0 là HỢP LÝ")
    print("   → Nếu DEL vẫn tăng, vấn đề KHÔNG phải do K")
    print("   → Kiểm tra % cohorts dùng fallback")
```

---

## Cách 3: Chạy Notebook Diagnostic Hoàn Chỉnh

Mở notebook: `notebooks/Markovchain_With_Diagnostic.ipynb`

Chạy các cells:
- **Cell 8**: So sánh P_24 vs Parent fallback
- **Cell 7**: Kiểm tra % cohorts dùng fallback
- **Cell 10**: Xem kết luận

---

## Diễn Giải Kết Quả

### Nếu thấy: "✅ P_24 ổn định (< 2%)"
→ **BẠN ĐÚNG!** K = 1.0 là hợp lý
→ Vấn đề có thể là fallback, không phải K

### Nếu thấy: "❌ P_24 không ổn định (> 3%)"
→ K = 1.0 gây DEL tăng
→ Cần giảm K hoặc chấp nhận DEL tăng

### Nếu thấy: "⚠️ P_24 hơi cao (2-3%)"
→ K = 1.0 có thể gây DEL tăng nhẹ
→ Tùy chọn: giảm K hoặc chấp nhận

---

## Bước Tiếp Theo

Sau khi kiểm tra P_24:

1. **Nếu P_24 ổn định** → Kiểm tra % fallback (Cell 7)
2. **Nếu P_24 không ổn định** → Quyết định:
   - Giảm K xuống 0.3-0.5
   - HOẶC chấp nhận DEL tăng (nếu đây là reality)

---

**Chọn cách nào bạn thấy dễ nhất và chạy thử!**
