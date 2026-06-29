# Hướng Dẫn Chạy Diagnostic - DEL Tăng Liên Tục

## Tình Huống

Bạn đã phát hiện đúng vấn đề:
- ✅ DEL curve tăng liên tục ở MOB cao (25-36) thay vì đi ngang
- ✅ P_24 nên có transition rates thấp (portfolio đã mature)
- ✅ Parent fallback có rates cao hơn (tổng hợp MOB 1-24)
- ✅ Curve bắt đầu flatten từ MOB 24 nhưng sau đó lại tăng

## Xác Nhận

✅ **Parent fallback KHÔNG được dùng** cho MOB 25-36 trong trường hợp bình thường
✅ **P_24 được dùng** cho MOB 25-36 (last available MOB)
✅ **Absorbing states đã đúng**: `["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]`

## Ba Nguyên Nhân Có Thể

### 1. K Values Quá Cao ở MOB 25+
Nếu K ≈ 1.0, model tin hoàn toàn Markov → gây movement → DEL tăng

### 2. Nhiều Cohorts Dùng Parent Fallback ở MOB 24
Nếu nhiều cohorts không đủ data ở MOB 24 (n_obs < 100 hoặc EAD < 100), chúng dùng parent fallback có rates cao hơn

### 3. Aggregation Effect
Khi tổng hợp cohorts lên product level, một số cohorts có weight cao đang kéo DEL tăng

---

## BƯỚC 1: Chạy Diagnostic Notebook

### Cách Đơn Giản Nhất (Khuyến Nghị)

1. **Chạy notebook chính** (Markovchain.ipynb hoặc Final_Workflow.ipynb) đến hết phần Calibration
2. **Mở notebook diagnostic**: `notebooks/Diagnostic_DEL_Increase.ipynb`
3. **Chạy từng cell** theo thứ tự trong notebook diagnostic
4. **Đọc kết quả** và áp dụng giải pháp

### Hoặc: Chạy Script Trong Notebook Chính

Nếu bạn muốn chạy diagnostic trực tiếp trong notebook chính:

```python
# Import script
from diagnose_why_increase_after_24 import diagnose_why_increase_after_24

# Chạy diagnostic
diagnose_why_increase_after_24(
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    k_final_by_mob=k_final_by_mob,
    forecast_results=forecast_results,
    disb_total_by_vintage=disb_total_by_vintage,
    df_del_product=df_del_product  # Optional
)
```

### Kiểm Tra Biến Cần Thiết

Đảm bảo các biến này tồn tại trong notebook:
```python
# Kiểm tra
print("matrices_by_mob:", type(matrices_by_mob))
print("parent_fallback:", type(parent_fallback))
print("k_final_by_mob:", type(k_final_by_mob))
print("forecast_results:", type(forecast_results))
print("disb_total_by_vintage:", type(disb_total_by_vintage))
```

---

## BƯỚC 2: Đọc Kết Quả Diagnostic

Script sẽ in ra:

### 1️⃣ KIỂM TRA K VALUES
```
MOB  |  K value  |  Status
-----|-----------|----------
24   |   0.850   | ✅ Trung bình
25   |   0.920   | ❌ Rất cao
26   |   0.950   | ❌ Rất cao
...
```

**Nếu thấy ❌**: K quá cao → Nguyên nhân #1

### 2️⃣ KIỂM TRA % COHORTS DÙNG FALLBACK Ở MOB 24
```
Tổng cohorts: 50
Cohorts dùng fallback ở MOB 24: 20 (40.0%)
❌ Quá nhiều cohorts dùng fallback!
```

**Nếu > 30%**: Nhiều cohorts dùng fallback → Nguyên nhân #2

### 3️⃣ SO SÁNH P_24 vs PARENT FALLBACK
```
DPD0 → DEL30+ comparison:
P_24:    0.0150 (1.50%)
Parent:  0.0350 (3.50%)
Diff:    +0.0200 (+2.00%)

✅ BẠN ĐÚNG! Parent fallback có movement cao hơn P_24
```

### 4️⃣ PHÂN TÍCH TỪNG COHORT
```
Top cohorts tăng mạnh:
- C/650+_10M-_POS/2023-12-01: slope = 0.002500 (0.2500%/month)
  → ❌ Cohort này dùng FALLBACK ở MOB 24!
```

---

## BƯỚC 3: Áp Dụng Giải Pháp

### Giải Pháp 1: Giảm K ở MOB 25+ (Nếu K quá cao)

```python
# Sau khi fit K, thêm đoạn này
print("K values trước khi cap:")
for mob in range(24, 37):
    print(f"MOB {mob}: {k_final_by_mob.get(mob, 1.0):.3f}")

# Cap K ở MOB 25+
for mob in range(25, 37):
    if mob in k_final_by_mob:
        k_final_by_mob[mob] = min(k_final_by_mob[mob], 0.3)
    else:
        k_final_by_mob[mob] = 0.3

print("\nK values sau khi cap:")
for mob in range(24, 37):
    print(f"MOB {mob}: {k_final_by_mob.get(mob, 1.0):.3f}")
```

### Giải Pháp 2: Tăng MIN_OBS/MIN_EAD (Nếu nhiều cohorts dùng fallback)

```python
# Trong src/config.py, sửa:
MIN_OBS = 200  # Thay vì 100
MIN_EAD = 500  # Thay vì 100

# Sau đó chạy lại từ đầu:
# 1. Load data
# 2. Compute transition matrices
# 3. Fit K
# 4. Forecast
```

### Giải Pháp 3: Force Dùng Parent Fallback cho MOB 25+

**Cách 1: Sửa code trong `src/rollrate/calibration_kmob.py`**

Tìm function `_get_P_for_segment()` và thêm đoạn này ở đầu:

```python
def _get_P_for_segment(matrices_by_mob, parent_fallback, product, score, mob, states):
    prod_str = str(product)
    score_str = str(score)

    # ⭐ THÊM: Force dùng parent fallback cho MOB > 24
    if mob > 24:
        if parent_fallback is not None:
            key_exact = (prod_str, score_str)
            if key_exact in parent_fallback:
                print(f"   Using parent fallback for MOB {mob} (product={prod_str}, score={score_str})")
                return parent_fallback[key_exact].reindex(index=states, columns=states, fill_value=0.0)
    
    # Logic cũ tiếp tục...
    mob_dict = matrices_by_mob.get(prod_str, {})
    # ...
```

**Cách 2: Thay P_24 bằng parent fallback trong matrices_by_mob**

```python
# Sau khi compute transition matrices, thay P_24 bằng parent fallback
for prod_str in matrices_by_mob.keys():
    if 24 in matrices_by_mob[prod_str]:
        for score_str in matrices_by_mob[prod_str][24].keys():
            key = (prod_str, score_str)
            if key in parent_fallback:
                print(f"Replacing P_24 with parent fallback for {prod_str}/{score_str}")
                matrices_by_mob[prod_str][24][score_str]["P"] = parent_fallback[key]
                matrices_by_mob[prod_str][24][score_str]["is_fallback"] = True
                matrices_by_mob[prod_str][24][score_str]["reason"] = "forced parent fallback for MOB 25+ stability"
```

---

## BƯỚC 4: Chạy Lại Forecast và Kiểm Tra

```python
# Chạy lại forecast với K đã điều chỉnh
forecast_results = forecast_all_vintages_partial_step(
    actual_results=actual_results,
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    max_mob=36,
    k_by_mob=k_final_by_mob,  # K đã được cap
    states=states,
)

# Kiểm tra lại DEL curve
from diagnose_del_curve import diagnose_del_curve

diagnose_del_curve(
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    k_final_by_mob=k_final_by_mob,
    forecast_results=forecast_results,
    disb_total_by_vintage=disb_total_by_vintage,
    product="C",
    score="650+_10M-_POS",
    vintage="2023-12-01"
)
```

---

## Scripts Bổ Sung

### Kiểm Tra Chất Lượng P_24

```python
from check_p24_quality import check_p24_quality

check_p24_quality(
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    product="C",
    score="650+_10M-_POS"
)
```

Sẽ cho bạn biết:
- P_24 có absorbing states đúng không?
- Transition rates từ DPD0 có hợp lý không?
- P_24 khác biệt bao nhiêu so với parent fallback?

---

## Tóm Tắt Quy Trình

1. ✅ **Chạy diagnostic script** → Xác định nguyên nhân
2. ✅ **Áp dụng giải pháp** phù hợp (1, 2, hoặc 3)
3. ✅ **Chạy lại forecast** với điều chỉnh
4. ✅ **Kiểm tra DEL curve** xem đã flatten chưa
5. ✅ **Lặp lại** nếu cần

---

## Kết Luận

Bạn đã phát hiện đúng vấn đề! Bây giờ chỉ cần:
1. Chạy diagnostic script để xác định nguyên nhân cụ thể
2. Áp dụng giải pháp phù hợp
3. Kiểm tra lại kết quả

Script sẽ cho bạn các chỉ báo rõ ràng (❌ hoặc ✅) để dễ dàng quyết định.

---

**Tạo ngày**: 2026-01-21
**Trạng thái**: Sẵn sàng chạy diagnostic
