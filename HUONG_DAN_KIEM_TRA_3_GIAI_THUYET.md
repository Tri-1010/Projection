# 📋 HƯỚNG DẪN: Kiểm tra cả 3 Giải thuyết

## Mục đích

Xác định nguyên nhân chính khiến DEL tăng sau MOB 24 bằng cách kiểm tra cả 3 giải thuyết:

1. **Giải thuyết 1**: K values tăng sau MOB 24
2. **Giải thuyết 2**: Transitions không ổn định
3. **Giải thuyết 3**: Fallback usage tăng sau MOB 24

---

## Các bước thực hiện

### 1. Mở notebook

```
notebooks/Markovchain_With_Diagnostic_Clean.ipynb
```

### 2. Chạy cells 1-5 (Setup & Calibration)

- Cell 1: Setup & Import
- Cell 2: Load Data
- Cell 3: Build Transition Matrices
- Cell 4: Calibration (K values)
- Cell 5: Forecast

### 3. Chạy 4 cells mới (Kiểm tra 3 giải thuyết)

#### Cell 1️⃣3️⃣: PHÂN TÍCH K VALUES CHI TIẾT
- Hiển thị K values từ MOB 1-36
- So sánh K trước vs sau MOB 24
- Tìm K jumps lớn

#### Cell 1️⃣4️⃣: GIẢI THUYẾT 2 - TRANSITION STABILITY
- Kiểm tra P_m movement từ MOB 20-30
- So sánh movement trước vs sau MOB 24
- Xác định transitions có ổn định không

#### Cell 1️⃣5️⃣: GIẢI THUYẾT 3 - FALLBACK USAGE
- Kiểm tra % fallback từ MOB 20-30
- So sánh % fallback trước vs sau MOB 24
- Xác định fallback usage có tăng không

#### Cell 1️⃣6️⃣: TÓM TẮT CẢ 3 GIẢI THUYẾT
- Tổng hợp kết quả từ 3 giải thuyết
- Xác định nguyên nhân chính
- Đưa ra giải pháp phù hợp

---

## Kết quả mong đợi

### Scenario 1: Giải thuyết 1 đúng (K values tăng)

```
📊 TÓM TẮT: CẢ 3 GIẢI THUYẾT

   1️⃣ K values:            ❌ K TĂNG CAO (>20%)
   2️⃣ Transition stability: ✅ Transitions ổn định
   3️⃣ Fallback usage:       ✅ Fallback không tăng nhiều

❌ NGUYÊN NHÂN CHÍNH: K values tăng

💡 GIẢI PHÁP:
   1. Giảm K sau MOB 24 (xem cell 'Giải pháp 1')
```

**Giải thích:**
- K tăng từ 0.65 → 0.95 (+46%)
- Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng
- Forecast movement = K * P_m movement
- K tăng → Forecast movement tăng → Slope tăng

**Giải pháp:**
```python
# Giữ K sau MOB 24 bằng K trước MOB 24
k_avg_before = 0.65
for mob in range(24, 37):
    k_final_by_mob[mob] = k_avg_before
```

---

### Scenario 2: Giải thuyết 2 đúng (Transitions không ổn định)

```
📊 TÓM TẮT: CẢ 3 GIẢI THUYẾT

   1️⃣ K values:            ✅ K không thay đổi nhiều
   2️⃣ Transition stability: ❌ TRANSITIONS KHÔNG ỔN ĐỊNH (>0.1%)
   3️⃣ Fallback usage:       ✅ Fallback không tăng nhiều

❌ NGUYÊN NHÂN CHÍNH: Transitions không ổn định

💡 GIẢI PHÁP:
   2. Tăng MIN_OBS để lọc cohorts không ổn định
```

**Giải thích:**
- P_m có movement cao (>0.1% per month)
- P_m không thực sự "ổn định"
- Movement cao → Forecast tăng → Slope tăng

**Giải pháp:**
```python
# Tăng MIN_OBS trong src/config.py
MIN_OBS = 200  # Từ 100 lên 200
MIN_EAD = 5e2  # Từ 1e2 lên 5e2
```

---

### Scenario 3: Giải thuyết 3 đúng (Fallback usage tăng)

```
📊 TÓM TẮT: CẢ 3 GIẢI THUYẾT

   1️⃣ K values:            ✅ K không thay đổi nhiều
   2️⃣ Transition stability: ✅ Transitions ổn định
   3️⃣ Fallback usage:       ❌ FALLBACK TĂNG CAO (>20%)

❌ NGUYÊN NHÂN CHÍNH: Fallback usage tăng

💡 GIẢI PHÁP:
   3. Tăng MIN_OBS để giảm % fallback
```

**Giải thích:**
- % fallback tăng từ 40% → 60% (+50%)
- Parent fallback có movement cao hơn P_m
- Nhiều cohorts chuyển sang dùng fallback → Slope tăng

**Giải pháp:**
```python
# Tăng MIN_OBS để giảm % fallback
MIN_OBS = 200
MIN_EAD = 5e2

# Hoặc giảm K cho cohorts dùng fallback
for mob in range(24, 37):
    k_final_by_mob[mob] = 0.5  # Giảm K cho fallback cohorts
```

---

### Scenario 4: Nhiều giải thuyết đúng

```
📊 TÓM TẮT: CẢ 3 GIẢI THUYẾT

   1️⃣ K values:            ❌ K TĂNG CAO (>20%)
   2️⃣ Transition stability: ❌ TRANSITIONS KHÔNG ỔN ĐỊNH (>0.1%)
   3️⃣ Fallback usage:       ❌ FALLBACK TĂNG CAO (>20%)

❌ NGUYÊN NHÂN CHÍNH: K values tăng, Transitions không ổn định, Fallback usage tăng

💡 GIẢI PHÁP:
   1. Giảm K sau MOB 24 (xem cell 'Giải pháp 1')
   2. Tăng MIN_OBS để lọc cohorts không ổn định
   3. Tăng MIN_OBS để giảm % fallback
```

**Giải thích:**
- Nhiều nguyên nhân cùng tác động
- Cần áp dụng nhiều giải pháp

**Giải pháp:**
```python
# 1. Tăng MIN_OBS
MIN_OBS = 200
MIN_EAD = 5e2

# 2. Giảm K sau MOB 24
k_avg_before = 0.65
for mob in range(24, 37):
    k_final_by_mob[mob] = k_avg_before

# 3. Re-run calibration và forecast
```

---

## Chi tiết từng giải thuyết

### Giải thuyết 1: K values tăng

**Kiểm tra:**
```
K trung bình TRƯỚC MOB 24 (MOB 12-23): ???
K trung bình SAU MOB 24 (MOB 24-29):   ???
Chênh lệch:                             ???
```

**Kết luận:**
- Nếu chênh lệch > 20% → K tăng là nguyên nhân chính
- Nếu chênh lệch < 20% → K không phải nguyên nhân chính

**Giải thích:**
- Công thức: `forecast_movement = k_m * (P_m movement)`
- K tăng → Forecast movement tăng → Slope tăng
- Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng

---

### Giải thuyết 2: Transitions không ổn định

**Kiểm tra:**
```
Average movement (all): ??? (???%)
```

**Kết luận:**
- Nếu movement > 0.1% → Transitions không ổn định
- Nếu movement < 0.1% → Transitions ổn định

**Giải thích:**
- P_m "ổn định" có 2 nghĩa:
  1. P_m không thay đổi theo MOB (P_23 ≈ P_24)
  2. P_m không gây movement (v_hat ≈ v_m)
- P_m có thể ổn định theo nghĩa 1 nhưng vẫn có movement!
- Movement cao → Forecast tăng → Slope tăng

---

### Giải thuyết 3: Fallback usage tăng

**Kiểm tra:**
```
% fallback TRƯỚC MOB 24: ???%
% fallback SAU MOB 24:   ???%
Chênh lệch:              ???%
```

**Kết luận:**
- Nếu chênh lệch > 20% → Fallback usage tăng là nguyên nhân
- Nếu chênh lệch < 20% → Fallback usage không phải nguyên nhân

**Giải thích:**
- Parent fallback có movement cao hơn P_m
- Nhiều cohorts chuyển sang dùng fallback → Slope tăng
- Cần tăng MIN_OBS để giảm % fallback

---

## Câu hỏi thường gặp

### Q1: Tại sao cần kiểm tra cả 3 giải thuyết?

**A:** Vì có thể có nhiều nguyên nhân cùng tác động:
- K tăng + Transitions không ổn định
- K tăng + Fallback usage tăng
- Cả 3 cùng tác động

Kiểm tra cả 3 giúp xác định nguyên nhân chính và áp dụng giải pháp phù hợp.

### Q2: Giải thuyết nào quan trọng nhất?

**A:** Tùy vào kết quả:
- Nếu chỉ 1 giải thuyết đúng → Đó là nguyên nhân chính
- Nếu nhiều giải thuyết đúng → Cần áp dụng nhiều giải pháp
- Thường thì **Giải thuyết 1 (K values)** là nguyên nhân phổ biến nhất

### Q3: Nếu cả 3 giải thuyết đều sai thì sao?

**A:** Có thể là:
- Aggregation effect (weighting)
- Data quality issues
- Model specification issues
- Cần kiểm tra thêm chi tiết từng cohort

---

## Tóm tắt

1. ✅ Chạy cells 1-5 (Setup & Calibration)
2. ✅ Chạy 4 cells mới (Kiểm tra 3 giải thuyết)
3. ✅ Xem cell "TÓM TẮT CẢ 3 GIẢI THUYẾT"
4. ✅ Xác định nguyên nhân chính
5. ✅ Áp dụng giải pháp phù hợp

**Kết quả mong đợi:**
- Xác định được 1-3 nguyên nhân chính
- Áp dụng giải pháp tương ứng
- Re-run forecast và verify kết quả
