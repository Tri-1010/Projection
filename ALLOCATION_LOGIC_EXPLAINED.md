# Allocation Logic - Giải thích chi tiết

## 📋 Tổng quan

Logic allocation hiện tại trong `allocation_v2_fast.py` sử dụng **2 bước phân bổ**:

1. **Assign STATE** dựa trên **transition matrix** (xét STATE_CURRENT và risk)
2. **Phân bổ EAD** theo **tỉ lệ EAD_CURRENT** của từng loan trong cùng state

## 🔍 Chi tiết từng bước

### BƯỚC 1: Tính State Probabilities (Transition Matrix)

```python
# Với mỗi loan:
# 1. Lấy STATE_CURRENT (ví dụ: DPD0)
# 2. Lấy MOB_CURRENT (ví dụ: 20)
# 3. Apply transition matrix từ MOB_CURRENT → TARGET_MOB

init_vec = [1.0 if state == STATE_CURRENT else 0.0]  # Vector ban đầu
final_probs = init_vec @ combined_matrix  # Nhân ma trận

# Kết quả: Xác suất ở mỗi state @ TARGET_MOB
# Ví dụ: [0.85, 0.10, 0.03, 0.02, ...]
#        DPD0  DPD1+ DPD30+ DPD60+ ...
```

**✅ Logic này XÉT RISK theo STATE_CURRENT:**
- Loan ở DPD0 → Xác suất cao ở DPD0 @ target_mob
- Loan ở DPD30+ → Xác suất cao ở DPD30+ hoặc xấu hơn @ target_mob

### BƯỚC 2: Sample STATE_FORECAST

```python
# Random sampling theo xác suất từ BƯỚC 1
STATE_FORECAST = np.random.choice(
    states=['DPD0', 'DPD1+', 'DPD30+', ...],
    p=[0.85, 0.10, 0.03, ...]  # Xác suất từ transition matrix
)
```

**✅ Mỗi loan được assign state khác nhau dựa trên:**
- STATE_CURRENT của loan
- Transition matrix (risk profile)
- Random sampling

### BƯỚC 3: Phân bổ EAD theo State

Đây là phần **QUAN TRỌNG NHẤT**:

```python
# Với mỗi cohort (product, score, vintage):
for each_cohort:
    # Lấy EAD target từ lifecycle
    ead_lifecycle_DPD0 = 1000  # EAD forecast @ DPD0
    ead_lifecycle_DPD30 = 200   # EAD forecast @ DPD30+
    
    # Lấy tổng EAD_CURRENT của loans trong cohort theo state
    loans_in_DPD0 = [LOAN_001, LOAN_002, LOAN_003]
    ead_current_DPD0 = 800  # Tổng EAD hiện tại của 3 loans
    
    # Tính ratio
    ratio = ead_lifecycle_DPD0 / ead_current_DPD0  # = 1000 / 800 = 1.25
    
    # Phân bổ cho TỪNG LOAN theo tỉ lệ EAD_CURRENT
    for loan in loans_in_DPD0:
        EAD_FORECAST[loan] = EAD_CURRENT[loan] * ratio
```

**📊 Ví dụ cụ thể:**

```
Cohort: Product X, Score A, Vintage 2024-01

Lifecycle forecast @ MOB 24:
- DPD0: 1000 (EAD target)
- DPD30+: 200 (EAD target)

Loans hiện tại (MOB 20):
┌──────────┬──────────────┬─────────────┬────────────────┬──────────────┐
│ LOAN_ID  │ STATE_CURRENT│ EAD_CURRENT │ STATE_FORECAST │ EAD_FORECAST │
├──────────┼──────────────┼─────────────┼────────────────┼──────────────┤
│ LOAN_001 │ DPD0         │ 300         │ DPD0 (sampled) │ 300 × 1.25   │
│ LOAN_002 │ DPD0         │ 400         │ DPD0 (sampled) │ 400 × 1.25   │
│ LOAN_003 │ DPD0         │ 100         │ DPD30+ (sampled)│ 100 × 2.0    │
│ LOAN_004 │ DPD30+       │ 50          │ DPD30+ (sampled)│ 50 × 2.0     │
│ LOAN_005 │ DPD30+       │ 50          │ DPD30+ (sampled)│ 50 × 2.0     │
└──────────┴──────────────┴─────────────┴────────────────┴──────────────┘

Tính toán:
1. Loans được assign state DPD0: LOAN_001, LOAN_002
   - Tổng EAD_CURRENT = 300 + 400 = 700
   - Ratio = 1000 / 700 = 1.43
   - EAD_FORECAST:
     * LOAN_001: 300 × 1.43 = 429
     * LOAN_002: 400 × 1.43 = 572
   - Tổng: 429 + 572 = 1001 ≈ 1000 ✅

2. Loans được assign state DPD30+: LOAN_003, LOAN_004, LOAN_005
   - Tổng EAD_CURRENT = 100 + 50 + 50 = 200
   - Ratio = 200 / 200 = 1.0
   - EAD_FORECAST:
     * LOAN_003: 100 × 1.0 = 100
     * LOAN_004: 50 × 1.0 = 50
     * LOAN_005: 50 × 1.0 = 50
   - Tổng: 100 + 50 + 50 = 200 ✅
```

## ❓ Trả lời câu hỏi: Phân bổ theo tỉ lệ nào?

### ✅ **Phân bổ theo TỈ LỆ EAD_CURRENT (Proportional)**

**KHÔNG phải** phân bổ đều (equal distribution).

**Logic:**
```python
EAD_FORECAST[loan] = EAD_CURRENT[loan] × (EAD_lifecycle_state / Total_EAD_CURRENT_state)
```

**Ý nghĩa:**
- Loan có EAD_CURRENT lớn → EAD_FORECAST lớn
- Loan có EAD_CURRENT nhỏ → EAD_FORECAST nhỏ
- Tỉ lệ giữa các loans được giữ nguyên

### ✅ **Có xét RISK không?**

**CÓ**, nhưng qua 2 cách:

1. **STATE_CURRENT** (gián tiếp):
   - Loan ở DPD0 có xác suất cao ở DPD0 @ target_mob
   - Loan ở DPD30+ có xác suất cao ở DPD30+ @ target_mob
   - → Transition matrix đã encode risk

2. **Transition Matrix** (trực tiếp):
   - Matrix khác nhau cho mỗi (product, score, mob)
   - Score A có transition matrix khác Score D
   - → Risk profile được phản ánh qua matrix

### ❌ **KHÔNG xét risk theo cách:**

- Không có weight riêng cho từng loan dựa trên risk score
- Không có adjustment factor cho high-risk loans
- Chỉ dựa vào STATE_CURRENT + Transition Matrix

## 📊 So sánh các phương pháp phân bổ

### 1. **Equal Distribution** (Không dùng)
```python
# Chia đều cho tất cả loans
EAD_FORECAST[loan] = EAD_lifecycle_state / N_loans_in_state
```

**Ví dụ:**
- 3 loans trong DPD0
- EAD target = 1000
- Mỗi loan: 1000 / 3 = 333.33

**Vấn đề:** Không phản ánh size của loan

### 2. **Proportional (EAD_CURRENT)** ✅ **ĐANG DÙNG**
```python
# Phân bổ theo tỉ lệ EAD hiện tại
EAD_FORECAST[loan] = EAD_CURRENT[loan] × ratio
```

**Ví dụ:**
- LOAN_001: EAD_CURRENT = 300 → EAD_FORECAST = 429
- LOAN_002: EAD_CURRENT = 400 → EAD_FORECAST = 572
- Tỉ lệ: 300:400 = 429:572 ✅

**Ưu điểm:** Giữ nguyên tỉ lệ size giữa các loans

### 3. **Risk-Weighted** (Không dùng)
```python
# Phân bổ theo risk weight
risk_weight[loan] = f(STATE_CURRENT, RISK_SCORE, ...)
EAD_FORECAST[loan] = EAD_CURRENT[loan] × ratio × risk_weight[loan]
```

**Ví dụ:**
- High-risk loan: weight = 1.2
- Low-risk loan: weight = 0.8

**Không cần thiết vì:** Transition matrix đã encode risk

## 🎯 Kết luận

### Logic hiện tại:

1. **Assign STATE**: Dựa trên STATE_CURRENT + Transition Matrix (có xét risk)
2. **Phân bổ EAD**: Theo tỉ lệ EAD_CURRENT (proportional, không xét thêm risk)

### Tại sao không cần risk-weighted allocation?

- **Transition matrix đã xét risk**: Loan ở DPD30+ có xác suất cao ở bad states
- **STATE_FORECAST đã phản ánh risk**: Loan được assign vào state nào phụ thuộc vào risk
- **Phân bổ EAD chỉ cần proportional**: Giữ nguyên tỉ lệ size giữa các loans

### Có cần thay đổi không?

**KHÔNG**, trừ khi:
- Muốn adjust EAD dựa trên thêm factors (ví dụ: collateral, payment history)
- Muốn penalize high-risk loans nhiều hơn
- Có business logic đặc biệt

## 📝 Code Reference

**File:** `src/rollrate/allocation_v2_fast.py`

**Key sections:**
- Line 100-200: Tính state probabilities (transition matrix)
- Line 260-280: Sample STATE_FORECAST
- Line 285-340: Phân bổ EAD theo proportional

---

**Author**: Kiro AI  
**Date**: 2026-02-09  
**Version**: 1.0
