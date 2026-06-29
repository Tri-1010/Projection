# 🚀 QUICK START: Kiểm tra K Values

## Mục đích

Trả lời: **"Tại sao K là vấn đề nếu transitions đã ổn định?"**

---

## Các bước (3 phút)

### 1. Mở notebook
```
notebooks/Markovchain_With_Diagnostic_Clean.ipynb
```

### 2. Chạy cells 1-5
- Cell 1-3: Load data & build matrices
- Cell 4: Calibration (K values) ← **Quan trọng!**
- Cell 5: Forecast

### 3. Chạy cell mới: "1️⃣3️⃣ PHÂN TÍCH K VALUES CHI TIẾT"

### 4. Xem kết quả

**Tìm dòng này:**
```
K trung bình TRƯỚC MOB 24 (MOB 12-23): ???
K trung bình SAU MOB 24 (MOB 24-29):   ???
Chênh lệch:                             ???
```

---

## Kết quả

### ✅ Nếu K tăng > 20%

**Ví dụ:**
```
K trung bình TRƯỚC MOB 24: 0.650
K trung bình SAU MOB 24:   0.950
Chênh lệch:                +0.300 (+46.2%)

❌ K SAU MOB 24 CAO HƠN TRƯỚC MOB 24 NHIỀU!
```

**→ Đây là nguyên nhân chính!**

**Giải pháp:**
```python
# Chạy cell "Giải pháp 1" hoặc:
k_avg_before = 0.65
for mob in range(24, 37):
    k_final_by_mob[mob] = k_avg_before
```

### ⚠️ Nếu K không thay đổi nhiều

**Ví dụ:**
```
K trung bình TRƯỚC MOB 24: 0.850
K trung bình SAU MOB 24:   0.880
Chênh lệch:                +0.030 (+3.5%)

✅ K không thay đổi nhiều
```

**→ K không phải nguyên nhân chính**

**Cần kiểm tra:**
- Transitions có thực sự ổn định không?
- Parent fallback usage có tăng không?

---

## Giải thích ngắn gọn

**"Ổn định" ≠ "Không có movement"**

- P_m có thể ổn định (P_23 ≈ P_24 ≈ P_25)
- Nhưng P_m vẫn có movement (DPD0 → DEL30+ = 0.0004%)
- **K quyết định bao nhiêu % movement được áp dụng**

**Ví dụ:**
```
P_m movement = 0.0004%

K = 0.7 → Forecast movement = 0.00028%
K = 1.0 → Forecast movement = 0.0004%

Chênh lệch: +43%!
```

**→ K tăng → Slope tăng (ngay cả khi P_m không thay đổi)**

---

## Tóm tắt

1. Chạy cell "1️⃣3️⃣ PHÂN TÍCH K VALUES CHI TIẾT"
2. Xem K trước vs sau MOB 24
3. Nếu K tăng > 20% → Giảm K sau MOB 24
4. Nếu K không thay đổi → Kiểm tra giả thuyết khác

**Chi tiết:** Xem `HUONG_DAN_KIEM_TRA_K_VALUES.md`
