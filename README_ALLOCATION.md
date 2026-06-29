# Allocation Logic - Complete Guide

## 📋 Tổng quan

Repository này chứa implementation và documentation đầy đủ về **Allocation Logic** - logic phân bổ forecast xuống loan-level.

## ❓ Câu hỏi chính

### **Logic allocate hiện tại như thế nào?**

**Trả lời:**
- **Phân bổ theo TỈ LỆ EAD_CURRENT** (Proportional)
- **CÓ xét risk** qua STATE_CURRENT và Transition Matrix
- **KHÔNG phân bổ đều** (Equal distribution)

---

## 🚀 Quick Start

### 1. Đọc tài liệu

```bash
# Quick reference (2 phút)
cat ALLOCATION_QUICK_REF.md

# Summary với FAQ (5 phút)
cat ALLOCATION_SUMMARY.md

# Chi tiết đầy đủ (15 phút)
cat ALLOCATION_LOGIC_EXPLAINED.md
```

### 2. Chạy demo

```bash
# Demo allocation logic
python demo_allocation_logic.py

# Test implementation mới
python test_optimized_allocation.py
```

### 3. Sử dụng trong code

```python
from src.rollrate.allocation_v2_optimized import allocate_multi_mob_optimized

# Allocation với actual data
df_result = allocate_multi_mob_optimized(
    df_raw=df_raw,  # ← Thêm df_raw để lấy actual
    df_loans_latest=df_loans_latest,
    df_lifecycle_final=df_lifecycle_final,
    matrices_by_mob=matrices_by_mob,
    target_mobs=[12, 24],
    parent_fallback=parent_fallback,
    seed=42
)

# Check kết quả
print(f"Actual loans: {df_result['IS_ACTUAL_MOB24'].sum()}")
print(f"Forecast loans: {(df_result['IS_ACTUAL_MOB24']==0).sum()}")
```

---

## 📚 Documentation Structure

```
ALLOCATION_DOCS_INDEX.md          ← Start here (navigation guide)
│
├─ ALLOCATION_QUICK_REF.md        ← Quick reference (2 min)
├─ ALLOCATION_SUMMARY.md          ← Summary + FAQ (5 min)
└─ ALLOCATION_LOGIC_EXPLAINED.md  ← Detailed explanation (15 min)

IMPLEMENTATION_OPTIMIZED_ALLOCATION.md  ← Implementation guide

demo_allocation_logic.py          ← Demo script
test_optimized_allocation.py      ← Test script
```

---

## 🎯 Key Features

### ✅ **Optimized Allocation**

**TRƯỚC:**
```python
# Allocate TẤT CẢ loans (kể cả có actual)
for all_loans:
    allocate_from_forecast()
```

**SAU:**
```python
# Lấy actual trước, chỉ allocate khi cần
for each_cohort:
    if has_actual:
        get_from_df_raw()  # ← Nhanh + chính xác
    else:
        allocate_forecast()
```

**Lợi ích:**
- ⚡ Nhanh hơn 60% (nếu 60% cohorts có actual)
- ✅ Chính xác hơn (dùng actual thay vì forecast)

### ✅ **Proportional Allocation**

```python
EAD_FORECAST = EAD_CURRENT × (EAD_lifecycle / Total_EAD_CURRENT)
```

**Ưu điểm:**
- Giữ nguyên tỉ lệ size giữa các loans
- Loan lớn → EAD_FORECAST lớn
- Loan nhỏ → EAD_FORECAST nhỏ

### ✅ **Risk-Aware**

**Risk được xét qua:**
1. STATE_CURRENT (DPD0 vs DPD30+)
2. Transition Matrix (Score A vs Score D)

**Không cần:**
- Risk weight riêng cho từng loan
- Adjustment factor

---

## 📊 Workflow

```
┌──────────────────────────────────────────────────────────┐
│                  ALLOCATION WORKFLOW                      │
└──────────────────────────────────────────────────────────┘

For each target_mob:
  │
  ├─ 1️⃣ CHECK ACTUAL
  │   ├─ Cohort có actual @ target_mob trong df_raw?
  │   └─ → YES: Lấy trực tiếp từ df_raw
  │
  ├─ 2️⃣ ALLOCATE FORECAST (cho cohorts cần)
  │   ├─ Assign STATE_FORECAST
  │   │   └─ Dựa trên STATE_CURRENT + Transition Matrix
  │   │
  │   └─ Phân bổ EAD
  │       └─ Proportional theo EAD_CURRENT
  │
  └─ 3️⃣ COMBINE
      └─ Actual + Forecast → Final result
```

---

## 🧪 Testing

### Demo Script

```bash
python demo_allocation_logic.py
```

**Output:**
```
BƯỚC 2: PHÂN BỔ EAD (Proportional by EAD_CURRENT)
================================================================================

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

### Test Script

```bash
python test_optimized_allocation.py
```

**Expected:**
```
📊 Results @ MOB 24:
   Total loans: 100,000
   Actual loans: 60,000 (60.0%)
   Forecast loans: 40,000 (40.0%)

✅ SUCCESS: Actual data được lấy từ df_raw!
```

---

## 💻 Source Code

### Main Files

1. **allocation_v2_optimized.py** (NEW - Recommended)
   - Lấy actual từ df_raw trước
   - Chỉ allocate khi cần
   - Nhanh + chính xác

2. **allocation_v2_fast.py** (CURRENT)
   - Allocate tất cả loans
   - Vectorized operations
   - Đã test và stable

3. **allocation_v2_ultra_fast.py**
   - Ultra fast với batch processing
   - Cho dataset rất lớn

### Helper Functions

```python
# Lấy actual từ df_raw
_get_actual_loans_at_mob(df_raw, product, score, vintage, target_mob)

# Extract tất cả actual loans
_extract_actual_loans_for_mob(df_raw, df_lifecycle_final, target_mob)

# Lọc loans cần allocate
_get_cohorts_needing_allocation(df_loans_latest, df_actual_loans)
```

---

## 📝 Usage Examples

### Example 1: Basic Usage

```python
from src.rollrate.allocation_v2_optimized import allocate_multi_mob_optimized

df_result = allocate_multi_mob_optimized(
    df_raw=df_raw,
    df_loans_latest=df_loans_latest,
    df_lifecycle_final=df_lifecycle_final,
    matrices_by_mob=matrices_by_mob,
    target_mobs=[24],
    parent_fallback=parent_fallback,
)
```

### Example 2: Multiple MOBs

```python
df_result = allocate_multi_mob_optimized(
    df_raw=df_raw,
    df_loans_latest=df_loans_latest,
    df_lifecycle_final=df_lifecycle_final,
    matrices_by_mob=matrices_by_mob,
    target_mobs=[12, 24, 36],  # Multiple MOBs
    parent_fallback=parent_fallback,
)
```

### Example 3: Check Results

```python
# Check actual vs forecast
for mob in [12, 24]:
    is_actual_col = f'IS_ACTUAL_MOB{mob}'
    n_actual = df_result[is_actual_col].sum()
    n_forecast = (df_result[is_actual_col] == 0).sum()
    
    print(f"MOB {mob}:")
    print(f"  Actual: {n_actual:,}")
    print(f"  Forecast: {n_forecast:,}")
```

---

## ❓ FAQ

### 1. Có phân bổ đều không?

**KHÔNG.** Phân bổ theo tỉ lệ EAD_CURRENT (proportional).

### 2. Có xét risk không?

**CÓ**, qua STATE_CURRENT và Transition Matrix.

### 3. Tại sao không dùng risk weight?

**Không cần** vì transition matrix đã encode risk.

### 4. Có cần thay đổi logic không?

**KHÔNG**, trừ khi có business logic đặc biệt.

### 5. Làm sao biết loan nào là actual?

Check cột `IS_ACTUAL_MOB{X}`:
- `1` = Actual từ df_raw
- `0` = Forecast từ allocation

---

## 🔧 Troubleshooting

### Issue 1: Không có actual loans

**Nguyên nhân:** Cohort không có data @ target_mob trong df_raw

**Giải pháp:** Kiểm tra:
```python
# Check lifecycle
df_lc_24 = df_lifecycle_final[df_lifecycle_final['MOB'] == 24]
n_actual = (df_lc_24['IS_FORECAST'] == 0).sum()
print(f"Cohorts with actual: {n_actual}")

# Check df_raw
df_raw_24 = df_raw[df_raw['MOB'] == 24]
print(f"Loans @ MOB 24: {len(df_raw_24)}")
```

### Issue 2: Allocation chậm

**Nguyên nhân:** Quá nhiều loans cần allocate

**Giải pháp:** 
- Dùng `allocation_v2_ultra_fast` cho dataset lớn
- Hoặc sample data để test

### Issue 3: EAD không match lifecycle

**Nguyên nhân:** Rounding errors hoặc missing cohorts

**Giải pháp:** Check log output:
```
📊 Cohorts processed: 100, missing in lifecycle: 5
```

---

## 📞 Support

Nếu cần hỗ trợ:

1. Đọc FAQ trong `ALLOCATION_SUMMARY.md`
2. Chạy demo script
3. Check troubleshooting guide
4. Liên hệ developer

---

## 📅 Version History

- **v1.0** (2026-02-09): Initial implementation
  - Optimized allocation với actual data
  - Complete documentation
  - Demo và test scripts

---

**Author**: Kiro AI  
**Last Updated**: 2026-02-09  
**License**: Internal Use Only
