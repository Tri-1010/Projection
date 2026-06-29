# 🎯 GIẢI THÍCH: Tại sao K là vấn đề nếu transitions đã ổn định?

## Câu hỏi cốt lõi

> "k trước mob 24 < 1, sau đó mặc định là 1, nhưng nếu nó đã ổn định thì tại sao k là vấn đề?"

**Đây là câu hỏi THEN CHỐT!** Bạn đã chỉ ra điểm cốt lõi của vấn đề.

---

## Phân tích chi tiết

### 1. Định nghĩa "ổn định"

Khi nói **"transitions đã ổn định"**, có 2 cách hiểu:

#### Cách hiểu A: P_m không thay đổi nhiều theo MOB
```
P_23 ≈ P_24 ≈ P_25 ≈ ... (matrices giống nhau)
```

#### Cách hiểu B: P_m gây ít movement
```
v_hat = v_m @ P_m
v_hat ≈ v_m (state vector không thay đổi nhiều)
```

**Đây là 2 khái niệm KHÁC NHAU!**

---

### 2. Ví dụ minh họa

Giả sử có transition matrix P_24:

```
         DPD0   DPD30+  DPD60+  WRITEOFF
DPD0     0.98   0.015   0.004   0.001
DPD30+   0.00   0.90    0.08    0.02
DPD60+   0.00   0.00    0.85    0.15
WRITEOFF 0.00   0.00    0.00    1.00
```

**P_24 "ổn định" theo cách hiểu A:**
- P_23 ≈ P_24 ≈ P_25 (matrices không thay đổi nhiều)

**Nhưng P_24 vẫn có movement:**
- DPD0 → DPD30+: 1.5%
- DPD0 → DPD60+: 0.4%
- DPD0 → WRITEOFF: 0.1%
- **Tổng movement: 2.0%**

---

### 3. Tại sao K quan trọng?

#### Scenario 1: K < 1 trước MOB 24

```python
# MOB 23 → 24
v_23 = [0.80, 0.15, 0.04, 0.01]  # 80% DPD0, 15% DPD30+, ...
v_hat = v_23 @ P_23  # Markov forecast
k_23 = 0.7

v_24 = v_23 + k_23 * (v_hat - v_23)
     = v_23 + 0.7 * (movement)
     = [0.79, 0.16, 0.04, 0.01]  # Chỉ move 70% của Markov
```

**DEL30+ tăng:** 15% → 16% = +1% (chỉ 70% của Markov movement)

#### Scenario 2: K = 1 sau MOB 24

```python
# MOB 24 → 25
v_24 = [0.79, 0.16, 0.04, 0.01]
v_hat = v_24 @ P_24  # Markov forecast (giống P_23)
k_24 = 1.0

v_25 = v_24 + k_24 * (v_hat - v_24)
     = v_24 + 1.0 * (movement)
     = [0.78, 0.17, 0.04, 0.01]  # Move 100% của Markov
```

**DEL30+ tăng:** 16% → 17% = +1% (100% của Markov movement)

---

### 4. Vấn đề thực sự

**Ngay cả khi P_m "ổn định" (không thay đổi theo MOB), P_m vẫn có movement!**

```
P_m "ổn định" ≠ P_m không có movement
```

**Ví dụ:**
- P_23 movement = 0.0004% (rất nhỏ, nhưng KHÔNG phải 0!)
- Nếu K jump từ 0.7 → 1.0:
  - Trước: Forecast movement = 0.7 * 0.0004% = 0.00028%
  - Sau: Forecast movement = 1.0 * 0.0004% = 0.0004%
  - **Tăng 43%!**

---

### 5. Tại sao slope SAU mature cao hơn slope TRƯỚC mature?

**Từ kết quả của bạn:**
- Slope TRƯỚC mature (MOB 12→24): 0.3314%/month
- Slope SAU mature (MOB 23→29): 0.5636%/month

**Giải thích:**

#### Trước MOB 24: K < 1
```
K_12 = 0.5, K_13 = 0.6, ..., K_23 = 0.7
→ Forecast chỉ tin Markov 50-70%
→ Slope thấp hơn
```

#### Sau MOB 24: K = 1
```
K_24 = 1.0, K_25 = 1.0, ..., K_29 = 1.0
→ Forecast tin Markov 100%
→ Slope cao hơn
```

**Ngay cả khi P_m không thay đổi, việc K tăng cũng làm slope tăng!**

---

## Kết luận

### Câu trả lời cho câu hỏi của bạn:

**"Tại sao K là vấn đề nếu transitions đã ổn định?"**

**Trả lời:**

1. **"Ổn định" không có nghĩa là "không có movement"**
   - P_m có thể ổn định (không thay đổi theo MOB)
   - Nhưng P_m vẫn có movement (DPD0 → DEL30+)

2. **K quyết định bao nhiêu % movement được áp dụng**
   - K = 0.7 → Chỉ áp dụng 70% movement
   - K = 1.0 → Áp dụng 100% movement
   - **K tăng → Slope tăng**

3. **K jump gây slope tăng đột ngột**
   - Nếu K jump từ 0.7 → 1.0 ở MOB 24
   - Slope sẽ tăng 43% ngay lập tức
   - **Đây là lý do slope SAU mature cao hơn slope TRƯỚC mature**

---

## Minh họa bằng số

### Giả sử P_m movement = 0.0004% (ổn định, không thay đổi)

#### Scenario A: K = 0.7 (trước MOB 24)
```
Forecast movement = 0.7 * 0.0004% = 0.00028%/month
Sau 12 tháng: 0.00028% * 12 = 0.00336%
```

#### Scenario B: K = 1.0 (sau MOB 24)
```
Forecast movement = 1.0 * 0.0004% = 0.0004%/month
Sau 6 tháng: 0.0004% * 6 = 0.0024%
```

**Slope:**
- Trước MOB 24: 0.00336% / 12 = 0.00028%/month
- Sau MOB 24: 0.0024% / 6 = 0.0004%/month
- **Sau MOB 24 cao hơn 43%!**

---

## Vậy giải pháp là gì?

### Option 1: Giữ K < 1 sau MOB 24
```python
for mob in range(25, 37):
    k_final_by_mob[mob] = 0.3  # Hoặc 0.5, 0.7
```

**Ưu điểm:**
- Giảm slope sau MOB 24
- Forecast conservative hơn

**Nhược điểm:**
- Nếu P_m thực sự accurate, forecast sẽ underestimate

### Option 2: Kiểm tra xem P_m có thực sự accurate không
```python
# Backtest: So sánh forecast vs actual
# Nếu forecast với K=1.0 accurate → Giữ K=1.0
# Nếu forecast với K=1.0 overestimate → Giảm K
```

**Đây là cách đúng nhất!**

---

## Câu hỏi tiếp theo

**Để trả lời chính xác, cần kiểm tra:**

1. **P_m có thực sự accurate không?**
   - Backtest: Forecast với K=1.0 vs Actual
   - Nếu accurate → K=1.0 đúng, slope tăng là đúng
   - Nếu overestimate → K=1.0 sai, cần giảm K

2. **K values trước MOB 24 là bao nhiêu?**
   - Nếu K_23 = 0.7, K_24 = 1.0 → K jump 43%
   - Nếu K_23 = 0.9, K_24 = 1.0 → K jump 11%

3. **Tại sao K được fit ra như vậy?**
   - K được fit từ actual data
   - Nếu K_24 = 1.0, có nghĩa là actual data cho thấy P_24 accurate
   - Nhưng tại sao slope SAU mature lại cao hơn slope TRƯỚC mature?

**Chạy script để kiểm tra!**
