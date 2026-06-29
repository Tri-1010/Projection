# 📋 HƯỚNG DẪN: Kiểm tra K Values

## Mục đích

Trả lời câu hỏi: **"Tại sao K là vấn đề nếu transitions đã ổn định?"**

---

## Các bước thực hiện

### 1. Mở notebook

```
notebooks/Markovchain_With_Diagnostic_Clean.ipynb
```

### 2. Chạy các cells từ đầu đến cell 5

- Cell 1: Setup & Import
- Cell 2: Load Data
- Cell 3: Build Transition Matrices
- Cell 4: Calibration (K values)
- Cell 5: Forecast

**Lưu ý:** Đảm bảo cell 4 (Calibration) chạy thành công để có `k_raw_by_mob`, `k_smooth_by_mob`, `k_final_by_mob`.

### 3. Chạy cell mới: "1️⃣3️⃣ PHÂN TÍCH K VALUES CHI TIẾT"

Cell này sẽ hiển thị:

#### 📊 K VALUES THEO MOB
```
   MOB  |  K_raw  |  K_smooth  |  K_final  |  Change  |  Status
   -----|---------|------------|-----------|----------|----------
      1 | 0.450   | 0.480      |     0.480 | N/A      | ✅ Start
      2 | 0.520   | 0.530      |     0.530 | +0.050   | ✅ OK
    ...
     23 | 0.680   | 0.700      |     0.700 | +0.020   | ✅ OK
     24 | 0.920   | 0.950      |     0.950 | +0.250   | ⚠️ JUMP!
     25 | 0.980   | 1.000      |     1.000 | +0.050   | ❌ Rất cao
    ...
```

#### 📊 THỐNG KÊ K VALUES
```
   K trung bình TRƯỚC MOB 24 (MOB 12-23): 0.650
   K trung bình SAU MOB 24 (MOB 24-29):   0.950
   Chênh lệch:                             +0.300 (+46.2%)

   ❌ K SAU MOB 24 CAO HƠN TRƯỚC MOB 24 NHIỀU!
   → Đây là lý do slope SAU mature cao hơn slope TRƯỚC mature
   → Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng
```

#### ❌ PHÁT HIỆN K JUMPS
```
   ❌ PHÁT HIỆN 1 K JUMPS (>0.2):
      - MOB 24: 0.700 → 0.950 (change: +0.250)
```

#### 💡 GIẢI THÍCH
```
   Công thức forecast:
   v_{m+1} = v_m + k_m * (v_hat - v_m)
   where v_hat = v_m @ P_m

   Nếu P_m có movement (ví dụ: DPD0 → DEL30+ = 0.0004%):

   TRƯỚC MOB 24 (K = 0.650):
      Forecast movement = 0.650 * 0.0004% = 0.000260%

   SAU MOB 24 (K = 0.950):
      Forecast movement = 0.950 * 0.0004% = 0.000380%

   Chênh lệch: 0.000120% (+46.2%)

   ❌ FORECAST MOVEMENT SAU MOB 24 CAO HƠN TRƯỚC MOB 24!
   → Đây là lý do slope tăng
   → Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng
```

---

## Kết quả mong đợi

### Scenario 1: K tăng sau MOB 24

**Nếu thấy:**
```
K trung bình TRƯỚC MOB 24: 0.650
K trung bình SAU MOB 24:   0.950
Chênh lệch:                +0.300 (+46.2%)
```

**Kết luận:**
- ✅ Đây là nguyên nhân chính!
- K tăng → Forecast movement tăng → Slope tăng
- Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng

**Giải pháp:**
```python
# Giữ K sau MOB 24 bằng K trước MOB 24
k_avg_before = 0.65

for mob in range(24, 37):
    k_final_by_mob[mob] = k_avg_before
```

### Scenario 2: K không thay đổi nhiều

**Nếu thấy:**
```
K trung bình TRƯỚC MOB 24: 0.850
K trung bình SAU MOB 24:   0.880
Chênh lệch:                +0.030 (+3.5%)
```

**Kết luận:**
- K không phải nguyên nhân chính
- Cần kiểm tra các giả thuyết khác:
  - Transitions không thực sự ổn định?
  - Parent fallback được dùng nhiều hơn?

---

## Giải thích chi tiết

### "Ổn định" có 2 nghĩa

1. **P_m không thay đổi theo MOB**
   - P_23 ≈ P_24 ≈ P_25 (matrices giống nhau)

2. **P_m không gây movement**
   - v_hat ≈ v_m (state vector không thay đổi)

**P_m có thể "ổn định" theo nghĩa 1 nhưng vẫn có movement!**

### Tại sao K quan trọng?

**Công thức:**
```
forecast_movement = k_m * (P_m movement)
```

**Ví dụ:**
- P_m movement = 0.0004% (ổn định, không thay đổi)
- K = 0.7 → Forecast movement = 0.00028%
- K = 1.0 → Forecast movement = 0.0004%
- **Chênh lệch: +43%!**

**→ K tăng → Forecast movement tăng → Slope tăng**

---

## Câu hỏi thường gặp

### Q1: Tại sao K lại tăng sau MOB 24?

**A:** K được fit từ actual data. Nếu K_24 = 1.0, có nghĩa là:
- Actual data cho thấy P_24 accurate (forecast với K=1.0 match actual)
- Nhưng điều này có thể do:
  - P_24 thực sự accurate
  - Hoặc có bias trong data (ví dụ: cohorts mature hơn có K cao hơn)

### Q2: Nếu K=1.0 accurate, tại sao lại là vấn đề?

**A:** K=1.0 có thể accurate cho **one-step forecast** (MOB 24 → 25), nhưng:
- Khi forecast nhiều steps (MOB 24 → 30), errors accumulate
- Slope tăng liên tục thay vì flatten
- Điều này không hợp lý cho portfolio đã mature

### Q3: Giải pháp nào tốt nhất?

**A:** Tùy vào kết quả:

**Nếu K tăng sau MOB 24:**
```python
# Option 1: Giữ K sau MOB 24 bằng K trước MOB 24
k_avg_before = np.mean([k_final_by_mob.get(m, 1.0) for m in range(12, 24)])
for mob in range(24, 37):
    k_final_by_mob[mob] = k_avg_before

# Option 2: Cap K ở mức 0.7
for mob in range(24, 37):
    k_final_by_mob[mob] = min(k_final_by_mob[mob], 0.7)
```

**Nếu K không thay đổi nhiều:**
- Kiểm tra transitions có thực sự ổn định không
- Kiểm tra parent fallback usage

---

## Tóm tắt

1. ✅ Chạy cell "1️⃣3️⃣ PHÂN TÍCH K VALUES CHI TIẾT"
2. ✅ Xem K trung bình trước và sau MOB 24
3. ✅ Nếu K tăng > 20% → Đây là nguyên nhân chính
4. ✅ Áp dụng giải pháp: Giảm K sau MOB 24

**Câu trả lời cho câu hỏi:**
- "Ổn định" không có nghĩa là "không có movement"
- P_m có thể ổn định nhưng vẫn có movement
- K quyết định bao nhiêu % movement được áp dụng
- **K tăng → Slope tăng (ngay cả khi P_m không thay đổi)**
