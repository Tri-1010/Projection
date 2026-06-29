# 🔍 Hướng Dẫn Tìm Segment Tăng Đột Biến

## Vấn Đề: Aggregation Effect

Bạn đã chỉ ra đúng:
- P_24 ổn định ✅
- States đã cẩn thận ✅
- Nhưng **một nhóm nhỏ segment tăng đột biến** → Kéo tổng tăng!

## 🎯 Ví Dụ

```
Product C tổng hợp:
  Segment A (40% weight): Flatten 0% ✅
  Segment B (35% weight): Flatten 0% ✅
  Segment C (20% weight): Flatten 0% ✅
  Segment D (5% weight):  Tăng 10%! ❌

Tổng = 40%*0% + 35%*0% + 20%*0% + 5%*10% = 0.5% tăng
```

Segment D chỉ 5% nhưng tăng 10% → Kéo tổng tăng 0.5%!

---

## 🔬 Cách Tìm Segment Tăng

### Cách 1: Chạy Script (Đơn Giản Nhất) ⭐

Trong notebook, thêm cell:

```python
from find_problematic_segments import find_problematic_segments

df_results = find_problematic_segments(
    forecast_results=forecast_results,
    disb_total_by_vintage=disb_total_by_vintage,
    buckets_30p=BUCKETS_30P,
    threshold_slope=0.002  # 0.2% per month = tăng đột biến
)
```

### Kết Quả Sẽ Cho Biết:

```
================================================================================
TÌM SEGMENTS TĂNG ĐỘT BIẾN SAU MOB 24
================================================================================

📊 TỔNG HỢP:
   Tổng cohorts: 50
   - Tăng (slope > 0.0020): 5 (10.0%)
   - Flatten: 40 (80.0%)
   - Giảm: 5 (10.0%)

================================================================================
TOP 10 COHORTS TĂNG MẠNH NHẤT:
================================================================================

Product    Score                     Vintage      Slope      Increase   Weight    
--------------------------------------------------------------------------------
C          550-649_10M-_POS          2023-12-01    0.5000%    3.00%      2.50%
C          <550_10M-_POS             2024-01-01    0.4500%    2.70%      1.80%
C          650+_10M+_POS             2023-11-01    0.3000%    1.80%      3.20%

================================================================================
PHÂN TÍCH THEO PRODUCT:
================================================================================

C:
   Tổng cohorts: 30
   Cohorts tăng: 3 (10.0%)
   Avg slope: 0.0500% per month
   Top cohorts tăng:
      - 550-649_10M-_POS/2023-12-01: 0.5000% per month
      - <550_10M-_POS/2024-01-01: 0.4500% per month

================================================================================
PHÂN TÍCH THEO SCORE:
================================================================================

Score                     Avg Slope    N Cohorts    Weight    
--------------------------------------------------------------------------------
550-649_10M-_POS            0.3500%          10       15.50%
<550_10M-_POS               0.3000%           8       12.30%
650+_10M+_POS               0.0500%          12       25.20%

================================================================================
KẾT LUẬN:
================================================================================

⚠️ MỘT SỐ COHORTS TĂNG (5/50)
   → Có thể là aggregation effect
   → Kiểm tra xem cohorts tăng có weight cao không
   → Tổng weight cohorts tăng: 7.5%
   → ✅ Weight thấp, ảnh hưởng nhỏ
```

---

## 🎯 Diễn Giải Kết Quả

### Nếu Thấy: "✅ Weight thấp, ảnh hưởng nhỏ"

```
Cohorts tăng chỉ chiếm 5-10% weight
→ Đây là aggregation effect nhỏ
→ Có thể chấp nhận
→ Hoặc loại bỏ segments này khỏi forecast
```

### Nếu Thấy: "❌ Weight cao! Đây là vấn đề lớn"

```
Cohorts tăng chiếm > 20% weight
→ Không phải aggregation effect nhỏ
→ Vấn đề nghiêm trọng hơn
→ Cần kiểm tra lại P_24 của segments này
```

---

## 🔧 Giải Pháp

### Giải Pháp 1: Loại Bỏ Segments Tăng (Nếu Weight Thấp)

```python
# Nếu chỉ 1-2 segments nhỏ tăng, có thể loại bỏ

# Ví dụ: Loại bỏ segment "550-649_10M-_POS"
segments_to_exclude = [("C", "550-649_10M-_POS")]

# Filter forecast results
forecast_results_filtered = {
    k: v for k, v in forecast_results.items()
    if (k[0], k[1]) not in segments_to_exclude
}

# Tính lại tổng hợp
# ...
```

### Giải Pháp 2: Kiểm Tra P_24 Của Segments Tăng

```python
# Kiểm tra P_24 của segment tăng mạnh
prod_str = "C"
score_str = "550-649_10M-_POS"

if 24 in matrices_by_mob[prod_str] and score_str in matrices_by_mob[prod_str][24]:
    P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
    
    # Xem P_24 có ổn định không
    if "DPD0" in P_24.index:
        del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
        movement = sum(P_24.loc["DPD0", s] for s in del30_states if s in P_24.columns)
        
        print(f"P_24 movement: {movement:.4f} ({movement*100:.2f}%)")
        
        if movement > 0.03:
            print("❌ P_24 của segment này KHÔNG ổn định!")
            print("   → Đây là vấn đề thật, không phải aggregation")
        else:
            print("✅ P_24 ổn định")
            print("   → Có thể do K cao hoặc fallback")
```

### Giải Pháp 3: Giảm K Cho Segments Tăng

```python
# Nếu P_24 ổn định nhưng vẫn tăng → K có thể cao

# Tạo k_by_mob riêng cho từng segment
k_by_mob_custom = {}

for cohort_key in forecast_results.keys():
    product, score, vintage = cohort_key
    
    # Nếu là segment tăng mạnh
    if (product, score) in [("C", "550-649_10M-_POS")]:
        # Giảm K cho MOB 25+
        k_custom = k_final_by_mob.copy()
        for mob in range(25, 37):
            k_custom[mob] = 0.3  # Giảm xuống 0.3
        k_by_mob_custom[cohort_key] = k_custom
    else:
        k_by_mob_custom[cohort_key] = k_final_by_mob

# Forecast lại với K custom
# ...
```

---

## 📊 Cách 2: Kiểm Tra Thủ Công

Nếu script không chạy, bạn có thể kiểm tra thủ công:

```python
# Tính slope cho từng cohort
for cohort_key in list(forecast_results.keys())[:20]:
    forecast = forecast_results[cohort_key]
    disb_total = disb_total_by_vintage.get(cohort_key, 1.0)
    
    product, score, vintage = cohort_key
    
    if 24 in forecast and 30 in forecast:
        del30_24 = forecast[24][BUCKETS_30P].sum() / disb_total
        del30_30 = forecast[30][BUCKETS_30P].sum() / disb_total
        slope = (del30_30 - del30_24) / 6
        
        if slope > 0.002:  # 0.2% per month
            print(f"❌ {product}/{score}/{vintage}: slope = {slope*100:.4f}% per month")
```

---

## 🎯 Kết Luận

### Bạn Đúng!

Vấn đề có thể là **một nhóm nhỏ segment tăng đột biến**.

### Cần Làm:

1. **Chạy script** `find_problematic_segments()` → Tìm segments nào tăng
2. **Kiểm tra weight** → Nếu weight thấp (< 10%) → Aggregation effect nhỏ
3. **Kiểm tra P_24** của segments tăng → Xem có ổn định không
4. **Quyết định**:
   - Nếu weight thấp → Chấp nhận hoặc loại bỏ
   - Nếu weight cao → Kiểm tra P_24 và K của segments đó

---

**Chạy script và cho tôi biết kết quả nhé!**
