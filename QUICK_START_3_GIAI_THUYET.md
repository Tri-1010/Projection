# 🚀 QUICK START: Kiểm tra 3 Giải thuyết

## Mục đích

Xác định nguyên nhân chính: **Tại sao DEL tăng sau MOB 24?**

---

## Các bước (5 phút)

### 1. Mở notebook
```
notebooks/Markovchain_With_Diagnostic_Clean.ipynb
```

### 2. Chạy cells 1-5
- Setup & Calibration

### 3. Chạy 4 cells mới
- 1️⃣3️⃣ K VALUES
- 1️⃣4️⃣ TRANSITION STABILITY
- 1️⃣5️⃣ FALLBACK USAGE
- 1️⃣6️⃣ TÓM TẮT ← **Xem cell này!**

### 4. Xem kết quả

**Tìm dòng này trong cell "TÓM TẮT":**
```
📊 TÓM TẮT: CẢ 3 GIẢI THUYẾT

   1️⃣ K values:            ???
   2️⃣ Transition stability: ???
   3️⃣ Fallback usage:       ???

❌ NGUYÊN NHÂN CHÍNH: ???
```

---

## Kết quả

### ✅ Scenario 1: K values tăng

```
   1️⃣ K values:            ❌ K TĂNG CAO (>20%)
   2️⃣ Transition stability: ✅ Transitions ổn định
   3️⃣ Fallback usage:       ✅ Fallback không tăng nhiều

❌ NGUYÊN NHÂN CHÍNH: K values tăng
```

**→ Giải pháp:** Giảm K sau MOB 24

```python
k_avg_before = 0.65
for mob in range(24, 37):
    k_final_by_mob[mob] = k_avg_before
```

---

### ✅ Scenario 2: Transitions không ổn định

```
   1️⃣ K values:            ✅ K không thay đổi nhiều
   2️⃣ Transition stability: ❌ TRANSITIONS KHÔNG ỔN ĐỊNH (>0.1%)
   3️⃣ Fallback usage:       ✅ Fallback không tăng nhiều

❌ NGUYÊN NHÂN CHÍNH: Transitions không ổn định
```

**→ Giải pháp:** Tăng MIN_OBS

```python
# Trong src/config.py
MIN_OBS = 200  # Từ 100
MIN_EAD = 5e2  # Từ 1e2
```

---

### ✅ Scenario 3: Fallback usage tăng

```
   1️⃣ K values:            ✅ K không thay đổi nhiều
   2️⃣ Transition stability: ✅ Transitions ổn định
   3️⃣ Fallback usage:       ❌ FALLBACK TĂNG CAO (>20%)

❌ NGUYÊN NHÂN CHÍNH: Fallback usage tăng
```

**→ Giải pháp:** Tăng MIN_OBS hoặc giảm K

```python
# Option 1: Tăng MIN_OBS
MIN_OBS = 200

# Option 2: Giảm K cho fallback cohorts
for mob in range(24, 37):
    k_final_by_mob[mob] = 0.5
```

---

### ✅ Scenario 4: Nhiều nguyên nhân

```
   1️⃣ K values:            ❌ K TĂNG CAO (>20%)
   2️⃣ Transition stability: ❌ TRANSITIONS KHÔNG ỔN ĐỊNH (>0.1%)
   3️⃣ Fallback usage:       ❌ FALLBACK TĂNG CAO (>20%)

❌ NGUYÊN NHÂN CHÍNH: K values tăng, Transitions không ổn định, Fallback usage tăng
```

**→ Giải pháp:** Áp dụng nhiều giải pháp

```python
# 1. Tăng MIN_OBS
MIN_OBS = 200
MIN_EAD = 5e2

# 2. Giảm K
k_avg_before = 0.65
for mob in range(24, 37):
    k_final_by_mob[mob] = k_avg_before
```

---

## Giải thích ngắn gọn

### Giải thuyết 1: K values tăng

**"Ổn định" ≠ "Không có movement"**

- P_m có thể ổn định (P_23 ≈ P_24)
- Nhưng P_m vẫn có movement (0.0004%)
- **K quyết định bao nhiêu % movement được áp dụng**
- K tăng → Forecast movement tăng → Slope tăng

### Giải thuyết 2: Transitions không ổn định

**P_m có movement cao**

- P_m movement > 0.1% per month
- P_m không thực sự "ổn định"
- Movement cao → Forecast tăng → Slope tăng

### Giải thuyết 3: Fallback usage tăng

**Nhiều cohorts chuyển sang dùng fallback**

- Parent fallback có movement cao hơn P_m
- % fallback tăng → Slope tăng
- Cần tăng MIN_OBS để giảm % fallback

---

## Tóm tắt

1. Chạy cells 1-5 + 4 cells mới
2. Xem cell "TÓM TẮT CẢ 3 GIẢI THUYẾT"
3. Xác định nguyên nhân chính
4. Áp dụng giải pháp tương ứng

**Chi tiết:** Xem `HUONG_DAN_KIEM_TRA_3_GIAI_THUYET.md`
