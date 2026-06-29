# Allocation Logic - Tóm tắt

## ❓ Câu hỏi: Logic allocate hiện tại như thế nào?

### ✅ **Trả lời ngắn gọn:**

**Phân bổ theo TỈ LỆ EAD_CURRENT (Proportional), CÓ xét risk qua STATE_CURRENT và Transition Matrix.**

---

## 📊 Chi tiết 2 bước

### BƯỚC 1: Assign STATE_FORECAST

**Dựa trên:**
- STATE_CURRENT của loan (DPD0, DPD30+, ...)
- Transition Matrix (khác nhau cho mỗi product, score, mob)
- Random sampling theo xác suất

**Ví dụ:**
```
LOAN_001:
  STATE_CURRENT = DPD0
  Transition probs @ MOB 24:
    - DPD0: 85%
    - DPD1+: 10%
    - DPD30+: 3%
    - DPD60+: 1%
    - DPD90+: 1%
  
  → Sample: STATE_FORECAST = DPD0 (85% chance)
```

**✅ Risk được xét ở đây:**
- Loan ở DPD0 → Xác suất cao ở DPD0
- Loan ở DPD30+ → Xác suất cao ở bad states

### BƯỚC 2: Phân bổ EAD

**Công thức:**
```python
EAD_FORECAST[loan] = EAD_CURRENT[loan] × (EAD_lifecycle / Total_EAD_CURRENT)
```

**Ví dụ:**
```
Cohort có 3 loans được assign vào DPD0:
  LOAN_001: EAD_CURRENT = 300
  LOAN_002: EAD_CURRENT = 400
  LOAN_003: EAD_CURRENT = 100
  Total: 800

Lifecycle forecast @ DPD0 = 1000

Ratio = 1000 / 800 = 1.25

EAD_FORECAST:
  LOAN_001: 300 × 1.25 = 375
  LOAN_002: 400 × 1.25 = 500
  LOAN_003: 100 × 1.25 = 125
  Total: 1000 ✅
```

**✅ Tỉ lệ được giữ nguyên:**
- 300:400:100 = 375:500:125
- Loan lớn → EAD_FORECAST lớn
- Loan nhỏ → EAD_FORECAST nhỏ

---

## 🎯 So sánh các phương pháp

| Phương pháp | Công thức | Ưu điểm | Nhược điểm | Đang dùng? |
|-------------|-----------|---------|------------|------------|
| **Equal** | EAD / N_loans | Đơn giản | Không phản ánh size | ❌ |
| **Proportional** | EAD × (Current / Total) | Giữ tỉ lệ size | - | ✅ |
| **Risk-weighted** | EAD × weight × (Current / Total) | Adjust theo risk | Phức tạp, không cần | ❌ |

---

## ❓ FAQ

### 1. Có phân bổ đều không?

**KHÔNG.** Phân bổ theo tỉ lệ EAD_CURRENT.

### 2. Có xét risk không?

**CÓ**, qua 2 cách:
- STATE_CURRENT (loan ở DPD30+ có risk cao hơn)
- Transition Matrix (matrix khác nhau cho mỗi score)

### 3. Tại sao không dùng risk weight riêng?

**Không cần thiết** vì:
- Transition matrix đã encode risk
- STATE_FORECAST đã phản ánh risk
- Phân bổ EAD chỉ cần proportional

### 4. Có cần thay đổi không?

**KHÔNG**, trừ khi có business logic đặc biệt:
- Adjust theo collateral
- Penalize high-risk loans
- Ưu tiên certain types of loans

---

## 📁 Files liên quan

- **Logic chi tiết**: `ALLOCATION_LOGIC_EXPLAINED.md`
- **Demo script**: `demo_allocation_logic.py`
- **Source code**: `src/rollrate/allocation_v2_fast.py`

---

## 🧪 Test

Chạy demo:
```bash
python demo_allocation_logic.py
```

Expected output:
```
BƯỚC 2: PHÂN BỔ EAD (Proportional by EAD_CURRENT)
================================================================================

📊 Phân bổ EAD cho từng state:
--------------------------------------------------------------------------------

🔹 State: DPD0
   EAD target (lifecycle): 1,000
   Total EAD_CURRENT: 700
   Ratio: 1.4286

   Loans trong DPD0:
   LOAN_ID      EAD_CURRENT   ×    Ratio   =  EAD_FORECAST
   ------------ ------------ --- -------- --- ------------
   LOAN_001              300   ×   1.4286   =       428.57
   LOAN_002              400   ×   1.4286   =       571.43
   ------------ ------------ --- -------- --- ------------
   TOTAL                 700                     1,000.00
   ✅ Match với lifecycle! (diff = 0.00)
```

---

**Author**: Kiro AI  
**Date**: 2026-02-09
