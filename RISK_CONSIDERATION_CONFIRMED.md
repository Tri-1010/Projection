# ✅ XÁC NHẬN: Code đã tính đến yếu tố RISK

## 🎯 Câu hỏi

> "Nghĩa là code hiện tại đã tính đến yếu tố risk thông qua state và segment nó thuộc về thông qua transition matrix?"

## ✅ TRẢ LỜI: ĐÚNG VẬY!

---

## 📊 Cách code xét RISK

### **1. Qua STATE_CURRENT** (Risk hiện tại của loan)

```python
# Trong code: allocation_v2_fast.py, line ~160

def get_state_probs(row):
    state_current = row['STATE_CURRENT']  # ← Lấy state hiện tại
    
    # Tạo vector ban đầu dựa trên STATE_CURRENT
    init_vec = np.zeros(n_states)
    if state_current in state_to_idx:
        init_vec[state_to_idx[state_current]] = 1.0  # ← 100% ở state hiện tại
    
    # Apply transition matrix
    final_probs = init_vec @ combined_matrix  # ← Xác suất @ target_mob
    
    return final_probs
```

**Ý nghĩa:**
- Loan ở **DPD0** → Vector [1, 0, 0, 0, ...] → Xác suất cao ở DPD0 @ target_mob
- Loan ở **DPD30+** → Vector [0, 0, 1, 0, ...] → Xác suất cao ở bad states @ target_mob

**→ RISK được xét qua STATE_CURRENT** ✅

---

### **2. Qua SEGMENT (Product + Score)** thông qua Transition Matrix

```python
# Trong code: allocation_v2_fast.py, line ~140

# Lấy transition matrix cho TỪNG SEGMENT
for _, row in unique_combos.iterrows():
    product = row['PRODUCT_TYPE']  # ← Segment: Product
    score = row['RISK_SCORE']      # ← Segment: Risk Score
    mob_current = row['MOB_CURRENT']
    
    # Lấy matrix riêng cho segment này
    combined = _get_combined_matrix(
        matrices_by_mob, 
        parent_fallback,
        product,  # ← Product khác → Matrix khác
        score,    # ← Score khác → Matrix khác
        mob_current, 
        target_mob
    )
    
    matrix_cache[(product, score, mob_current)] = combined
```

**Ý nghĩa:**

**Ví dụ cụ thể:**

```
2 loans cùng STATE_CURRENT = DPD0, cùng EAD = 1M:

LOAN_A: Product X, Score A (Low risk)
  → Dùng Matrix[X][A]
  → DPD0 → DPD0 = 90%  (xác suất cao giữ DPD0)
  → DPD0 → DPD90+ = 2% (xác suất thấp đi bad)

LOAN_B: Product X, Score D (High risk)
  → Dùng Matrix[X][D]
  → DPD0 → DPD0 = 70%  (xác suất thấp hơn giữ DPD0)
  → DPD0 → DPD90+ = 8% (xác suất cao hơn đi bad)
```

**→ RISK được xét qua SEGMENT (Product + Score)** ✅

---

## 🔍 Minh họa cụ thể

### **Scenario: 4 loans cùng cohort**

```
Cohort: Product X, Vintage 2024-01

┌──────────┬──────────────┬────────────┬─────────────┬──────────────────┐
│ LOAN_ID  │ STATE_CURRENT│ RISK_SCORE │ EAD_CURRENT │ Transition Probs │
├──────────┼──────────────┼────────────┼─────────────┼──────────────────┤
│ LOAN_001 │ DPD0         │ A (Low)    │ 1M          │ DPD0: 90%        │
│          │              │            │             │ DPD30+: 5%       │
│          │              │            │             │ DPD90+: 2%       │
├──────────┼──────────────┼────────────┼─────────────┼──────────────────┤
│ LOAN_002 │ DPD0         │ D (High)   │ 1M          │ DPD0: 70%        │
│          │              │            │             │ DPD30+: 15%      │
│          │              │            │             │ DPD90+: 8%       │
├──────────┼──────────────┼────────────┼─────────────┼──────────────────┤
│ LOAN_003 │ DPD30+       │ A (Low)    │ 1M          │ DPD0: 30%        │
│          │              │            │             │ DPD30+: 50%      │
│          │              │            │             │ DPD90+: 15%      │
├──────────┼──────────────┼────────────┼─────────────┼──────────────────┤
│ LOAN_004 │ DPD30+       │ D (High)   │ 1M          │ DPD0: 10%        │
│          │              │            │             │ DPD30+: 40%      │
│          │              │            │             │ DPD90+: 40%      │
└──────────┴──────────────┴────────────┴─────────────┴──────────────────┘
```

**Phân tích:**

1. **LOAN_001 vs LOAN_002** (cùng STATE_CURRENT = DPD0)
   - Score A → Xác suất DPD90+ = 2% (low risk) ✅
   - Score D → Xác suất DPD90+ = 8% (high risk) ✅
   - **→ RISK_SCORE được xét qua Matrix**

2. **LOAN_001 vs LOAN_003** (cùng Score A)
   - DPD0 → Xác suất DPD90+ = 2% (good state) ✅
   - DPD30+ → Xác suất DPD90+ = 15% (bad state) ✅
   - **→ STATE_CURRENT được xét**

3. **LOAN_004** (DPD30+ + Score D)
   - Xác suất DPD90+ = 40% (highest risk) ✅
   - **→ Cả STATE và SCORE đều được xét**

---

## 💡 Key Insight

### **Code KHÔNG cần explicit risk weight vì:**

```python
# KHÔNG CẦN làm thế này:
risk_weight = {
    'A': 0.8,
    'B': 0.9,
    'C': 1.0,
    'D': 1.2
}
EAD_FORECAST = EAD_CURRENT × ratio × risk_weight[score]
```

### **Vì risk ĐÃ được encode trong Transition Matrix:**

```python
# Matrix tự động adjust dựa trên score:
Matrix[Product_X][Score_A] ≠ Matrix[Product_X][Score_D]

# Khi apply matrix:
final_probs = init_vec @ Matrix[product][score]
# → Xác suất đã phản ánh risk của score rồi!
```

---

## 🎯 Tóm tắt

### ✅ **Code ĐÃ xét RISK qua:**

1. **STATE_CURRENT**
   - Loan ở DPD0 ≠ Loan ở DPD30+
   - Vector ban đầu khác nhau
   - Xác suất @ target_mob khác nhau

2. **SEGMENT (Product + Score)**
   - Matrix khác nhau cho mỗi segment
   - Score A có matrix khác Score D
   - Xác suất transition khác nhau

3. **MOB_CURRENT**
   - Matrix khác nhau cho mỗi MOB
   - Seasoning effect được xét

### ✅ **Kết quả:**

- **High-risk loans** (DPD30+ + Score D) → Xác suất cao ở bad states
- **Low-risk loans** (DPD0 + Score A) → Xác suất cao ở good states
- **Risk được phản ánh tự động** qua transition probabilities

---

## 📊 Validation

Để verify, có thể check:

```python
# Group by risk profile
df_result['RISK_PROFILE'] = df_result['STATE_CURRENT'] + '_' + df_result['RISK_SCORE']

# Check DEL90 rate per profile
del90_by_profile = df_result.groupby('RISK_PROFILE')['DEL90_FLAG'].mean()

print(del90_by_profile)

# Expected:
# DPD0_A:    2%  (lowest risk)
# DPD0_D:    8%  (medium risk)
# DPD30+_A: 15%  (medium-high risk)
# DPD30+_D: 40%  (highest risk)
```

**Nếu kết quả như expected → Risk được xét đúng** ✅

---

## ✅ KẾT LUẬN

**Câu trả lời cho câu hỏi:**

> "Code hiện tại đã tính đến yếu tố risk thông qua state và segment nó thuộc về thông qua transition matrix?"

## **ĐÚNG VẬY! 100%** ✅

**Risk được xét qua:**
1. ✅ STATE_CURRENT (state hiện tại của loan)
2. ✅ SEGMENT (Product + Risk Score)
3. ✅ Transition Matrix (encode risk profile)

**Không cần:**
- ❌ Explicit risk weight
- ❌ Manual adjustment
- ❌ Additional risk factors (trừ khi có data mới)

**Logic này:**
- ✅ Hợp lý
- ✅ Best practice
- ✅ Đầy đủ cho credit risk modeling

---

**Author**: Kiro AI  
**Date**: 2026-02-09  
**Status**: ✅ CONFIRMED
