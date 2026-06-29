# Implementation: Optimized Allocation

## 📋 Tổng quan

File `allocation_v2_optimized.py` đã được implement đầy đủ logic **lấy actual data trước khi allocate**.

## ✅ Điểm khác biệt

### ❌ **TRƯỚC ĐÂY** (allocation_v2_fast)
```python
# Allocate TẤT CẢ loans (kể cả cohort đã có actual)
for all_loans:
    allocate_from_forecast()
```

**Vấn đề:**
- Mất thời gian allocate cho cohort đã có actual
- Kết quả kém chính xác (dùng forecast thay vì actual)

### ✅ **SAU KHI IMPLEMENT** (allocation_v2_optimized)
```python
# Lấy actual trước, chỉ allocate khi cần
for each_cohort:
    if cohort_has_actual_at_target_mob:
        get_actual_from_df_raw()  # ← Lấy trực tiếp từ df_raw
    else:
        allocate_from_forecast()   # ← Chỉ allocate khi cần
```

**Lợi ích:**
- ⚡ Nhanh hơn (không allocate cohort đã có actual)
- ✅ Chính xác hơn (dùng actual thay vì forecast)

## 🔧 Implementation Details

### 1. Helper Function: `_get_actual_loans_at_mob()`

Lấy actual loan-level data từ `df_raw` tại MOB cụ thể.

```python
def _get_actual_loans_at_mob(
    df_raw: pd.DataFrame,
    product: str,
    score: str,
    vintage_date: pd.Timestamp,
    target_mob: int,
) -> Optional[pd.DataFrame]:
    """
    Filter df_raw theo:
    - PRODUCT_TYPE = product
    - RISK_SCORE = score
    - VINTAGE_DATE = vintage_date
    - MOB = target_mob
    
    Returns:
        DataFrame với columns:
        - AGREEMENT_ID
        - STATE_ACTUAL
        - EAD_ACTUAL
        - DISBURSAL_AMOUNT
    """
```

### 2. Helper Function: `_extract_actual_loans_for_mob()`

Lấy tất cả actual loans cho các cohorts có actual @ target_mob.

```python
def _extract_actual_loans_for_mob(
    df_raw: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    target_mob: int,
) -> pd.DataFrame:
    """
    Workflow:
    1. Lọc lifecycle tại target_mob với IS_FORECAST = 0
    2. Lấy danh sách cohorts có actual
    3. Với mỗi cohort, gọi _get_actual_loans_at_mob()
    4. Combine tất cả actual loans
    
    Returns:
        DataFrame với IS_ACTUAL = 1
    """
```

### 3. Helper Function: `_get_cohorts_needing_allocation()`

Lọc ra các loans cần allocate (không có trong actual).

```python
def _get_cohorts_needing_allocation(
    df_loans_latest: pd.DataFrame,
    df_actual_loans: pd.DataFrame,
) -> pd.DataFrame:
    """
    Workflow:
    1. Lấy danh sách loan IDs đã có actual
    2. Filter loans không có trong danh sách đó
    
    Returns:
        DataFrame loans cần allocate
    """
```

### 4. Main Function: `allocate_multi_mob_optimized()`

Workflow chính:

```python
for each target_mob:
    # BƯỚC 1: Lấy actual từ df_raw
    df_actual = _extract_actual_loans_for_mob(...)
    
    # BƯỚC 2: Xác định loans cần allocate
    df_need_allocation = _get_cohorts_needing_allocation(...)
    
    # BƯỚC 3: Allocate cho loans cần forecast
    if len(df_need_allocation) > 0:
        df_allocated = allocate_fast(...)
    
    # BƯỚC 4: Combine actual + allocated
    df_combined = concat([df_actual, df_allocated])
    
    # BƯỚC 5: Tính DEL flags
    df_combined['DEL30_FLAG'] = ...
    df_combined['DEL90_FLAG'] = ...
    
    # BƯỚC 6: Merge vào loan_info
    loan_info = loan_info.merge(df_combined, ...)
```

## 📊 Output Format

Kết quả có thêm cột `IS_ACTUAL_MOB{X}`:

```
AGREEMENT_ID | STATE_FORECAST_MOB24 | EAD_FORECAST_MOB24 | IS_ACTUAL_MOB24
-------------|----------------------|--------------------|-----------------
LOAN_001     | DPD0                 | 100.5              | 1  ← Actual
LOAN_002     | DPD30+               | 50.2               | 0  ← Forecast
LOAN_003     | DPD0                 | 200.0              | 1  ← Actual
```

## 🧪 Testing

Chạy test script:

```bash
python test_optimized_allocation.py
```

Expected output:

```
📊 Results @ MOB 24:
   Total loans: 100,000
   Actual loans: 60,000 (60.0%)
   Forecast loans: 40,000 (40.0%)

✅ SUCCESS: Actual data được lấy từ df_raw!
```

## 📝 Usage trong Notebook

Update cell trong `Final_Workflow.ipynb`:

```python
# BEFORE (old)
from src.rollrate.allocation_v2_fast import allocate_multi_mob_fast

df_loan_forecast = allocate_multi_mob_fast(
    df_loans_latest=df_loans_latest,
    df_lifecycle_final=df_lifecycle_final,
    matrices_by_mob=matrices_by_mob,
    target_mobs=TARGET_MOBS,
    parent_fallback=parent_fallback,
    seed=42
)

# AFTER (new - optimized)
from src.rollrate.allocation_v2_optimized import allocate_multi_mob_optimized

df_loan_forecast = allocate_multi_mob_optimized(
    df_raw=df_raw,  # ← Thêm df_raw
    df_loans_latest=df_loans_latest,
    df_lifecycle_final=df_lifecycle_final,
    matrices_by_mob=matrices_by_mob,
    target_mobs=TARGET_MOBS,
    parent_fallback=parent_fallback,
    seed=42
)
```

## ⚠️ Important Notes

1. **df_raw phải có đủ data**: Nếu cohort không có data @ target_mob trong df_raw, sẽ fallback sang allocation

2. **VINTAGE_DATE**: Đảm bảo df_raw có cột VINTAGE_DATE hoặc có thể parse từ DISBURSAL_DATE

3. **Performance**: 
   - Nếu 60% cohorts có actual → Giảm 60% thời gian allocation
   - Nếu 100% cohorts cần forecast → Tốc độ tương đương allocation_v2_fast

4. **Accuracy**:
   - Actual data: 100% chính xác (lấy từ df_raw)
   - Forecast data: Phụ thuộc vào calibration

## 🎯 Next Steps

1. ✅ Test với data thực
2. ✅ Update notebook Final_Workflow.ipynb
3. ✅ Verify kết quả với user
4. 📝 Document trong README.md

## 📞 Support

Nếu có vấn đề, kiểm tra:

1. `IS_ACTUAL_MOB{X}` column có tồn tại không?
2. Có bao nhiêu % loans là actual vs forecast?
3. Log output có báo "Extracted X actual loans" không?

---

**Author**: Kiro AI  
**Date**: 2026-02-09  
**Version**: 1.0
