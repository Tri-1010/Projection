# Chẩn đoán: DEL Rate Tăng Liên tục thay vì Flatten
# Diagnosis: DEL Rate Continuously Increasing Instead of Flattening

## Vấn đề / Problem

**Tiếng Việt:**
DEL rate (DEL30+, DEL60+, DEL90+) tiếp tục tăng ở MOB cao (25-36) thay vì đi ngang (flatten), điều này không hợp lý về mặt nghiệp vụ.

**English:**
DEL rate (DEL30+, DEL60+, DEL90+) continues to increase at high MOB (25-36) instead of flattening, which is unreasonable from a business perspective.

---

## Nguyên nhân có thể / Possible Causes

### 1. ⚠️ Absorbing States không được thiết lập đúng

**Tiếng Việt:**

Kiểm tra xem các absorbing states có được enforce đúng không:

```python
# Trong transition.py
ABSORBING_BASE = ["PREPAY", "WRITEOFF", "SOLDOUT"]

# Kiểm tra trong ma trận P:
# WRITEOFF → WRITEOFF phải = 1.0
# WRITEOFF → các state khác phải = 0.0
```

**Vấn đề:** Nếu WRITEOFF không phải absorbing state, loans có thể "thoát" khỏi WRITEOFF và quay lại DPD states, gây tăng DEL rate không hợp lý.

**Cách kiểm tra:**

```python
# Kiểm tra ma trận P_24
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]

# Kiểm tra WRITEOFF row
print("WRITEOFF row:")
print(P_24.loc["WRITEOFF"])

# Kết quả mong đợi:
# WRITEOFF    1.0
# DPD0        0.0
# DPD30+      0.0
# ...
```

**English:**

Check if absorbing states are properly enforced:

```python
# In transition.py
ABSORBING_BASE = ["PREPAY", "WRITEOFF", "SOLDOUT"]

# Check in matrix P:
# WRITEOFF → WRITEOFF must = 1.0
# WRITEOFF → other states must = 0.0
```

**Issue:** If WRITEOFF is not an absorbing state, loans can "escape" from WRITEOFF and return to DPD states, causing unreasonable DEL rate increase.

---

### 2. ⚠️ DPD90+ không phải Absorbing State

**Tiếng Việt:**

**QUAN TRỌNG:** Kiểm tra config của bạn:

```python
# Trong src/config.py
ABSORBING_BASE = ["PREPAY", "WRITEOFF", "SOLDOUT"]
# hoặc
ABSORBING_BASE = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]
```

**Vấn đề:** Nếu `DPD90+` KHÔNG phải absorbing state, loans có thể:
- DPD90+ → DPD120+ → DPD180+ → WRITEOFF (tiếp tục di chuyển)
- Gây DEL90+ tăng liên tục

**Giải pháp:**
- Nếu muốn DEL90+ flatten: Thêm `DPD90+` vào `ABSORBING_BASE`
- Hoặc: Chỉ để WRITEOFF là absorbing, nhưng kiểm tra transition rates

**English:**

**IMPORTANT:** Check your config:

```python
# In src/config.py
ABSORBING_BASE = ["PREPAY", "WRITEOFF", "SOLDOUT"]
# or
ABSORBING_BASE = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]
```

**Issue:** If `DPD90+` is NOT an absorbing state, loans can:
- DPD90+ → DPD120+ → DPD180+ → WRITEOFF (continue moving)
- Causing DEL90+ to continuously increase

**Solution:**
- If you want DEL90+ to flatten: Add `DPD90+` to `ABSORBING_BASE`
- Or: Keep only WRITEOFF as absorbing, but check transition rates

---

### 3. ⚠️ K values quá cao ở MOB cao

**Tiếng Việt:**

Kiểm tra K values ở MOB 24-36:

```python
# K values
print("K values at high MOB:")
for mob in range(20, 37):
    k = k_final_by_mob.get(mob, 1.0)
    print(f"MOB {mob}: k = {k:.3f}")
```

**Vấn đề:** Nếu K ≈ 1.0 ở MOB cao:
- Model tin hoàn toàn vào Markov forecast
- Nếu P_24 có transition rates cao (DPD0 → DPD30+), sẽ gây tăng liên tục

**Giải pháp:**
- Kiểm tra alpha: Nếu alpha > 1, model đang scale up K
- Xem xét giảm alpha hoặc cap K ở MOB cao

**English:**

Check K values at MOB 24-36:

```python
# K values
print("K values at high MOB:")
for mob in range(20, 37):
    k = k_final_by_mob.get(mob, 1.0)
    print(f"MOB {mob}: k = {k:.3f}")
```

**Issue:** If K ≈ 1.0 at high MOB:
- Model fully trusts Markov forecast
- If P_24 has high transition rates (DPD0 → DPD30+), will cause continuous increase

**Solution:**
- Check alpha: If alpha > 1, model is scaling up K
- Consider reducing alpha or capping K at high MOB

---

### 4. ⚠️ P_24 có transition rates không hợp lý

**Tiếng Việt:**

Kiểm tra ma trận P_24:

```python
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]

# Kiểm tra transition từ DPD0 → DPD30+
print("Transition from DPD0:")
print(P_24.loc["DPD0"])

# Kiểm tra transition từ DPD30+ → DPD60+
print("\nTransition from DPD30+:")
print(P_24.loc["DPD30+"])
```

**Vấn đề:** Nếu P_24 có:
- DPD0 → DPD30+ = 0.05 (5% mỗi tháng)
- Sau 12 tháng (MOB 24→36), DEL30+ sẽ tăng đáng kể

**Nguyên nhân P_24 không hợp lý:**
- Data ở MOB 24 có seasonality (tháng cuối năm, Tết)
- Sample size nhỏ ở MOB 24
- Outliers trong data

**Giải pháp:**
- Dùng parent_fallback thay vì P_24 cho MOB 25+
- Smooth P_24 với parent_fallback
- Kiểm tra data quality ở MOB 24

**English:**

Check matrix P_24:

```python
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]

# Check transition from DPD0 → DPD30+
print("Transition from DPD0:")
print(P_24.loc["DPD0"])

# Check transition from DPD30+ → DPD60+
print("\nTransition from DPD30+:")
print(P_24.loc["DPD30+"])
```

**Issue:** If P_24 has:
- DPD0 → DPD30+ = 0.05 (5% per month)
- After 12 months (MOB 24→36), DEL30+ will increase significantly

**Why P_24 might be unreasonable:**
- Data at MOB 24 has seasonality (year-end, holidays)
- Small sample size at MOB 24
- Outliers in data

**Solution:**
- Use parent_fallback instead of P_24 for MOB 25+
- Smooth P_24 with parent_fallback
- Check data quality at MOB 24

---

### 5. ⚠️ Không có Prepayment trong Model

**Tiếng Việt:**

Kiểm tra xem PREPAY có trong state space không:

```python
print("States:", BUCKETS_CANON)
# Phải có: ["DPD0", ..., "PREPAY", "WRITEOFF", ...]
```

**Vấn đề:** Nếu không có PREPAY:
- Good loans (DPD0) không thể thoát khỏi portfolio
- Chỉ có bad loans (DPD30+) tích lũy
- DEL rate tăng liên tục

**Giải pháp:**
- Thêm PREPAY vào BUCKETS_CANON
- Đảm bảo PREPAY là absorbing state

**English:**

Check if PREPAY is in state space:

```python
print("States:", BUCKETS_CANON)
# Must have: ["DPD0", ..., "PREPAY", "WRITEOFF", ...]
```

**Issue:** If no PREPAY:
- Good loans (DPD0) cannot exit portfolio
- Only bad loans (DPD30+) accumulate
- DEL rate continuously increases

**Solution:**
- Add PREPAY to BUCKETS_CANON
- Ensure PREPAY is an absorbing state

---

## Cách Chẩn đoán / Diagnostic Steps

### Bước 1: Kiểm tra Absorbing States

```python
from src.config import ABSORBING_BASE, BUCKETS_CANON

print("Absorbing states:", ABSORBING_BASE)
print("All states:", BUCKETS_CANON)

# Kiểm tra ma trận P_24
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]

for state in ABSORBING_BASE:
    if state in P_24.index:
        print(f"\n{state} row:")
        print(P_24.loc[state])
        # Phải có: P[state, state] = 1.0, còn lại = 0.0
```

### Bước 2: Kiểm tra K values

```python
print("\nK values:")
for mob in range(20, 37):
    k = k_final_by_mob.get(mob, 1.0)
    print(f"MOB {mob}: k = {k:.3f}")

# Nếu k ≈ 1.0 ở MOB cao → Model tin hoàn toàn Markov
# Nếu k < 0.5 ở MOB cao → Model không tin Markov
```

### Bước 3: Kiểm tra Transition Rates ở MOB 24

```python
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]

print("\nTransition from DPD0:")
print(P_24.loc["DPD0"])

print("\nTransition from DPD30+:")
print(P_24.loc["DPD30+"])

# Kiểm tra:
# - DPD0 → DPD30+ phải < 0.02 (2%)
# - DPD30+ → WRITEOFF phải > 0.05 (5%)
```

### Bước 4: So sánh P_24 vs Parent Fallback

```python
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]
P_parent = parent_fallback[("C", "650+_POS")]

print("\nP_24 vs P_parent - DPD0 row:")
print("P_24:")
print(P_24.loc["DPD0"])
print("\nP_parent:")
print(P_parent.loc["DPD0"])

# Nếu P_24 khác biệt lớn so với P_parent → có vấn đề
```

### Bước 5: Kiểm tra DEL Rate Curve

```python
# Lấy forecast cho 1 cohort
cohort_key = ("C", "650+_POS", "2023-12-01")
forecast = forecast_results[cohort_key]

# Tính DEL30+ theo MOB
del30_by_mob = {}
for mob, ead_vec in forecast.items():
    del30_amt = ead_vec[BUCKETS_30P].sum()
    disb_total = disb_total_by_vintage[cohort_key]
    del30_pct = del30_amt / disb_total
    del30_by_mob[mob] = del30_pct

# Plot
import matplotlib.pyplot as plt
mobs = sorted(del30_by_mob.keys())
del30_values = [del30_by_mob[m] for m in mobs]

plt.figure(figsize=(12, 6))
plt.plot(mobs, del30_values, marker='o')
plt.axvline(x=24, color='red', linestyle='--', label='Last historical MOB')
plt.xlabel('MOB')
plt.ylabel('DEL30+')
plt.title('DEL30+ Curve')
plt.legend()
plt.grid(True)
plt.show()

# Kiểm tra:
# - Sau MOB 24, curve phải flatten (slope ≈ 0)
# - Nếu vẫn tăng → có vấn đề
```

---

## Giải pháp / Solutions

### Giải pháp 1: Thêm DPD90+ vào Absorbing States

```python
# Trong src/config.py
ABSORBING_BASE = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]
```

**Ưu điểm:**
- DEL90+ sẽ flatten ngay lập tức
- Phù hợp nếu DPD90+ = NPL (Non-Performing Loan)

**Nhược điểm:**
- Không phản ánh recovery từ DPD90+

### Giải pháp 2: Giảm K ở MOB cao

```python
# Sau khi fit K, cap K ở MOB cao
for mob in range(25, 37):
    if mob in k_final_by_mob:
        k_final_by_mob[mob] = min(k_final_by_mob[mob], 0.3)
    else:
        k_final_by_mob[mob] = 0.3  # Chỉ tin 30% Markov
```

**Ưu điểm:**
- Giảm ảnh hưởng của P_24 không hợp lý
- Curve sẽ flatten hơn

**Nhược điểm:**
- Arbitrary threshold (0.3)

### Giải pháp 3: Dùng Parent Fallback cho MOB 25+

```python
# Modify _get_P_for_segment
def _get_P_for_segment(matrices_by_mob, parent_fallback, product, score, mob, states):
    prod_str = str(product)
    score_str = str(score)
    
    # Nếu MOB > 24, dùng parent fallback luôn
    if mob > 24:
        key_exact = (prod_str, score_str)
        if key_exact in parent_fallback:
            return parent_fallback[key_exact]
    
    # Logic cũ cho MOB <= 24
    ...
```

**Ưu điểm:**
- Parent fallback ổn định hơn (tổng hợp tất cả MOB)
- Giảm noise từ P_24

**Nhược điểm:**
- Mất thông tin MOB-specific

### Giải pháp 4: Smooth P_24 với Parent Fallback

```python
# Tạo P_24_smoothed
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]
P_parent = parent_fallback[("C", "650+_POS")]

# Weighted average
alpha = 0.7  # 70% P_24, 30% P_parent
P_24_smoothed = alpha * P_24 + (1 - alpha) * P_parent

# Dùng P_24_smoothed cho MOB 25+
```

**Ưu điểm:**
- Giữ được thông tin MOB-specific
- Giảm noise

**Nhược điểm:**
- Cần tune alpha

---

## Khuyến nghị / Recommendations

**Tiếng Việt:**

1. **Kiểm tra ngay:** Chạy các diagnostic steps ở trên
2. **Ưu tiên kiểm tra:**
   - Absorbing states (WRITEOFF, DPD90+)
   - K values ở MOB 24-36
   - Transition rates trong P_24
3. **Giải pháp nhanh:** Thêm DPD90+ vào ABSORBING_BASE nếu phù hợp nghiệp vụ
4. **Giải pháp dài hạn:** Smooth P_24 hoặc dùng parent fallback cho MOB 25+

**English:**

1. **Check immediately:** Run the diagnostic steps above
2. **Priority checks:**
   - Absorbing states (WRITEOFF, DPD90+)
   - K values at MOB 24-36
   - Transition rates in P_24
3. **Quick solution:** Add DPD90+ to ABSORBING_BASE if business-appropriate
4. **Long-term solution:** Smooth P_24 or use parent fallback for MOB 25+

---

*Document created: 2026-01-20*
