# Allocation Logic - Quick Reference

## 🎯 TL;DR

**Phân bổ theo TỈ LỆ EAD_CURRENT, CÓ xét risk qua STATE_CURRENT + Transition Matrix**

---

## 📐 Công thức

```python
# BƯỚC 1: Assign STATE
STATE_FORECAST = sample(transition_probs[STATE_CURRENT])

# BƯỚC 2: Phân bổ EAD
ratio = EAD_lifecycle_state / Total_EAD_CURRENT_state
EAD_FORECAST = EAD_CURRENT × ratio
```

---

## 📊 Ví dụ nhanh

```
Input:
  LOAN_001: EAD_CURRENT = 300, STATE_CURRENT = DPD0
  LOAN_002: EAD_CURRENT = 400, STATE_CURRENT = DPD0
  Lifecycle @ DPD0 = 1000

Process:
  1. Assign STATE_FORECAST = DPD0 (cả 2 loans)
  2. Total EAD_CURRENT = 700
  3. Ratio = 1000 / 700 = 1.43
  
Output:
  LOAN_001: EAD_FORECAST = 300 × 1.43 = 429
  LOAN_002: EAD_FORECAST = 400 × 1.43 = 572
  Total: 1001 ≈ 1000 ✅
```

---

## ✅ Có xét risk?

**CÓ**, qua:
1. STATE_CURRENT (DPD0 vs DPD30+)
2. Transition Matrix (Score A vs Score D)

**KHÔNG** qua:
- Risk weight riêng cho từng loan
- Adjustment factor

---

## 📁 Files

- Chi tiết: `ALLOCATION_LOGIC_EXPLAINED.md`
- Tóm tắt: `ALLOCATION_SUMMARY.md`
- Demo: `demo_allocation_logic.py`
- Code: `src/rollrate/allocation_v2_fast.py`

---

## 🧪 Test nhanh

```bash
python demo_allocation_logic.py
```
