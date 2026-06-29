# Risk Flow - Cách Risk được xét trong Code

## 🔄 Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOAN INPUT                                    │
│  LOAN_001: STATE_CURRENT=DPD0, SCORE=A, EAD=1M                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              BƯỚC 1: Lấy Transition Matrix                       │
│                                                                  │
│  Key = (Product, Score, MOB_CURRENT)                            │
│  Matrix = matrices_by_mob[Product][MOB][Score]                  │
│                                                                  │
│  → Matrix[X][A] (Low risk matrix)                               │
│    DPD0 → DPD0:   90%  ← High probability stay good            │
│    DPD0 → DPD30+:  5%                                           │
│    DPD0 → DPD90+:  2%  ← Low probability go bad                │
│                                                                  │
│  ✅ RISK được xét qua SEGMENT (Product + Score)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         BƯỚC 2: Tạo Initial Vector từ STATE_CURRENT             │
│                                                                  │
│  init_vec = [1, 0, 0, 0, 0, ...]                               │
│              ↑                                                   │
│              └─ 100% ở DPD0 (STATE_CURRENT)                     │
│                                                                  │
│  ✅ RISK được xét qua STATE_CURRENT                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           BƯỚC 3: Apply Transition Matrix                        │
│                                                                  │
│  final_probs = init_vec @ Matrix[X][A]                          │
│              = [1, 0, 0, ...] @ Matrix                          │
│              = [0.90, 0.05, 0.02, ...]                          │
│                 DPD0  DPD30+ DPD90+                             │
│                                                                  │
│  ✅ Xác suất đã phản ánh RISK (State + Score)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              BƯỚC 4: Sample STATE_FORECAST                       │
│                                                                  │
│  STATE_FORECAST = random.choice(                                │
│      states = [DPD0, DPD30+, DPD90+, ...],                     │
│      probs  = [0.90, 0.05, 0.02, ...]                          │
│  )                                                               │
│                                                                  │
│  → Xác suất 90% được assign DPD0 (good)                        │
│  → Xác suất 2% được assign DPD90+ (bad)                        │
│                                                                  │
│  ✅ STATE_FORECAST phản ánh RISK                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              BƯỚC 5: Phân bổ EAD                                │
│                                                                  │
│  EAD_FORECAST = EAD_CURRENT × ratio                             │
│               = 1M × (EAD_lifecycle / Total_EAD_CURRENT)        │
│                                                                  │
│  ✅ Proportional (không cần thêm risk weight)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OUTPUT                                        │
│  LOAN_001: STATE_FORECAST=DPD0, EAD_FORECAST=0.99M             │
│            (High probability good outcome - Low risk)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 So sánh: Low Risk vs High Risk

### **LOAN_A: Low Risk (DPD0 + Score A)**

```
Input:
  STATE_CURRENT = DPD0
  SCORE = A
  EAD = 1M

Step 1: Matrix[X][A]
  DPD0 → DPD0:   90%  ← Low risk matrix
  DPD0 → DPD90+:  2%

Step 2: init_vec = [1, 0, 0, ...]  ← Start at DPD0

Step 3: final_probs = [0.90, ..., 0.02]

Step 4: Sample → DPD0 (90% chance)

Output:
  STATE_FORECAST = DPD0 (likely)
  Risk reflected: ✅ Low risk → Good outcome
```

### **LOAN_B: High Risk (DPD30+ + Score D)**

```
Input:
  STATE_CURRENT = DPD30+
  SCORE = D
  EAD = 1M

Step 1: Matrix[X][D]
  DPD30+ → DPD0:   10%  ← High risk matrix
  DPD30+ → DPD90+: 40%

Step 2: init_vec = [0, 0, 1, ...]  ← Start at DPD30+

Step 3: final_probs = [0.10, ..., 0.40]

Step 4: Sample → DPD90+ (40% chance)

Output:
  STATE_FORECAST = DPD90+ (likely)
  Risk reflected: ✅ High risk → Bad outcome
```

---

## 📊 Risk Encoding trong Matrix

### **Cách Matrix encode risk:**

```
Matrix Structure:
  matrices_by_mob[Product][MOB][Score]

Example:
  matrices_by_mob['X'][20]['A']  ← Low risk matrix
  matrices_by_mob['X'][20]['D']  ← High risk matrix

Matrix Content (DPD0 row):
                    To:
  From:    DPD0   DPD1+  DPD30+  DPD60+  DPD90+
  ─────────────────────────────────────────────
  Score A:  90%    5%     3%      1%      1%    ← Low risk
  Score D:  70%   10%    10%      5%      5%    ← High risk
```

**Ý nghĩa:**
- Score A: 90% giữ DPD0 → Low risk ✅
- Score D: 70% giữ DPD0 → High risk ✅
- Matrix đã encode risk profile!

---

## 🎯 Tại sao không cần explicit risk weight?

### **Cách KHÔNG tốt (redundant):**

```python
# Redundant vì risk đã có trong matrix
risk_weight = {'A': 0.8, 'B': 0.9, 'C': 1.0, 'D': 1.2}

# Apply matrix (đã có risk)
probs = init_vec @ Matrix[score]  # ← Risk đã được xét

# Apply weight lần nữa (redundant!)
EAD_FORECAST = EAD_CURRENT × ratio × risk_weight[score]  # ❌
```

### **Cách TỐT (hiện tại):**

```python
# Apply matrix (đã có risk)
probs = init_vec @ Matrix[score]  # ← Risk được xét ở đây

# Sample state (phản ánh risk)
STATE_FORECAST = sample(probs)

# Phân bổ EAD (proportional)
EAD_FORECAST = EAD_CURRENT × ratio  # ✅ Đơn giản, đủ
```

**Tại sao đủ?**
- Matrix đã encode risk → probs đã phản ánh risk
- STATE_FORECAST đã phản ánh risk
- EAD chỉ cần proportional

---

## ✅ Validation

### **Test 1: Risk reflected in STATE assignment?**

```python
# Group by risk profile
df_low_risk = df[(df['STATE_CURRENT']=='DPD0') & (df['RISK_SCORE']=='A')]
df_high_risk = df[(df['STATE_CURRENT']=='DPD30+') & (df['RISK_SCORE']=='D')]

# Check DEL90 rate
del90_low = df_low_risk['DEL90_FLAG'].mean()   # Expected: ~2%
del90_high = df_high_risk['DEL90_FLAG'].mean() # Expected: ~40%

assert del90_low < del90_high  # ✅ Risk reflected
```

### **Test 2: Matrix different per score?**

```python
# Check matrix values
matrix_a = matrices_by_mob['X'][20]['A']
matrix_d = matrices_by_mob['X'][20]['D']

# DPD0 → DPD0 probability
prob_a = matrix_a.loc['DPD0', 'DPD0']  # Expected: ~90%
prob_d = matrix_d.loc['DPD0', 'DPD0']  # Expected: ~70%

assert prob_a > prob_d  # ✅ Score A better than D
```

---

## 🎓 Key Takeaway

### **Risk được xét HOÀN TOÀN qua:**

1. ✅ **STATE_CURRENT** → Initial vector
2. ✅ **SEGMENT (Score)** → Matrix selection
3. ✅ **Transition Matrix** → Probabilities

### **Không cần thêm:**

- ❌ Explicit risk weight
- ❌ Manual adjustment
- ❌ Additional factors (trừ khi có data mới)

### **Kết quả:**

- ✅ Low risk loans → Good outcomes
- ✅ High risk loans → Bad outcomes
- ✅ Risk được phản ánh tự động

---

**Kết luận:** Code hiện tại **ĐÃ XÉT RISK ĐẦY ĐỦ** qua STATE và SEGMENT thông qua Transition Matrix! ✅

---

**Author**: Kiro AI  
**Date**: 2026-02-09
