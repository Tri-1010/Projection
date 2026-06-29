# 🚀 HƯỚNG DẪN TRIỂN KHAI CẢI THIỆN NHANH

## 📌 MỤC TIÊU
Triển khai 4 cải thiện có impact cao nhất trong 1-2 ngày:
1. ✅ Validation & Monitoring
2. ✅ Parent Fallback Hierarchy
3. ✅ Adaptive ROLL_WINDOW
4. ✅ DECAY_LAMBDA per Product

---

## 1️⃣ VALIDATION & MONITORING

### **File cần tạo:** `src/rollrate/validation.py`

```python
"""
validation.py - Validation & Monitoring cho allocation và forecast
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from src.config import CFG, BUCKETS_CANON, BUCKETS_30P, BUCKETS_60P, BUCKETS_90P


def validate_allocation(
    df_loan_forecast: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    target_mob: int,
    tolerance_ead: float = 5.0,
    tolerance_del: float = 10.0,
) -> Dict:
    """
    Kiểm tra allocation có khớp lifecycle không.
    
    Parameters
    ----------
    df_loan_forecast : DataFrame
        Loan-level forecast output
    df_lifecycle_final : DataFrame
        Lifecycle forecast (cohort-level)
    target_mob : int
        MOB cần validate
    tolerance_ead : float
        Ngưỡng chấp nhận cho EAD difference (%)
    tolerance_del : float
        Ngưỡng chấp nhận cho DEL rate difference (%)
    
    Returns
    -------
    dict
        {
            'ead_diff_pct': float,
            'del30_diff_pct': float,
            'del60_diff_pct': float,
            'del90_diff_pct': float,
            'state_distribution': DataFrame,
            'warnings': List[str],
            'passed': bool
        }
    """
    
    warnings = []
    
    # ===================================================
    # 1. Check total EAD
    # ===================================================
    ead_col = f'EAD_FORECAST_MOB{target_mob}'
    
    if ead_col not in df_loan_forecast.columns:
        warnings.append(f"Missing column: {ead_col}")
        return {'passed': False, 'warnings': warnings}
    
    total_ead_loan = df_loan_forecast[ead_col].sum()
    
    # Lifecycle EAD = sum of all state buckets
    df_lc_mob = df_lifecycle_final[df_lifecycle_final['MOB'] == target_mob]
    state_cols = [c for c in BUCKETS_CANON if c in df_lc_mob.columns]
    total_ead_lc = df_lc_mob[state_cols].sum().sum()
    
    if total_ead_lc == 0:
        warnings.append(f"Lifecycle EAD = 0 at MOB {target_mob}")
        ead_diff_pct = np.nan
    else:
        ead_diff_pct = abs(total_ead_loan - total_ead_lc) / total_ead_lc * 100
    
    if ead_diff_pct > tolerance_ead:
        warnings.append(f"EAD mismatch: {ead_diff_pct:.2f}% > {tolerance_ead}%")
    
    # ===================================================
    # 2. Check DEL rates
    # ===================================================
    total_disb = df_loan_forecast['DISBURSAL_AMOUNT'].sum()
    
    del_metrics = {}
    
    for del_type in ['DEL30', 'DEL60', 'DEL90']:
        ead_del_col = f'EAD_{del_type}_MOB{target_mob}'
        pct_col = f'{del_type}_PCT'
        
        if ead_del_col in df_loan_forecast.columns and total_disb > 0:
            del_loan = df_loan_forecast[ead_del_col].sum() / total_disb
        else:
            del_loan = np.nan
        
        if pct_col in df_lc_mob.columns:
            del_lc = df_lc_mob[pct_col].mean()
        else:
            del_lc = np.nan
        
        if not np.isnan(del_loan) and not np.isnan(del_lc) and del_lc > 0:
            diff_pct = abs(del_loan - del_lc) / del_lc * 100
        else:
            diff_pct = np.nan
        
        del_metrics[f'{del_type.lower()}_diff_pct'] = diff_pct
        
        if not np.isnan(diff_pct) and diff_pct > tolerance_del:
            warnings.append(f"{del_type} mismatch: {diff_pct:.2f}% > {tolerance_del}%")
    
    # ===================================================
    # 3. Check state distribution
    # ===================================================
    state_col = f'STATE_FORECAST_MOB{target_mob}'
    
    if state_col in df_loan_forecast.columns:
        # Loan-level distribution
        loan_dist = (
            df_loan_forecast.groupby(state_col)[ead_col]
            .sum()
            .reindex(BUCKETS_CANON, fill_value=0)
        )
        loan_dist_pct = loan_dist / loan_dist.sum() * 100
        
        # Lifecycle distribution
        lc_dist = df_lc_mob[state_cols].sum()
        lc_dist_pct = lc_dist / lc_dist.sum() * 100
        
        # Compare
        state_comparison = pd.DataFrame({
            'Loan_EAD': loan_dist,
            'Loan_PCT': loan_dist_pct,
            'Lifecycle_EAD': lc_dist,
            'Lifecycle_PCT': lc_dist_pct,
        })
        state_comparison['Diff_PCT'] = (
            state_comparison['Loan_PCT'] - state_comparison['Lifecycle_PCT']
        )
    else:
        state_comparison = pd.DataFrame()
        warnings.append(f"Missing column: {state_col}")
    
    # ===================================================
    # 4. Summary
    # ===================================================
    passed = len(warnings) == 0
    
    result = {
        'ead_diff_pct': ead_diff_pct,
        **del_metrics,
        'state_distribution': state_comparison,
        'warnings': warnings,
        'passed': passed,
    }
    
    return result


def print_validation_report(validation_result: Dict, target_mob: int):
    """
    In báo cáo validation đẹp mắt.
    """
    
    print("\n" + "="*60)
    print(f"📊 VALIDATION REPORT @ MOB {target_mob}")
    print("="*60)
    
    # EAD
    ead_diff = validation_result.get('ead_diff_pct', np.nan)
    if not np.isnan(ead_diff):
        status = "✅" if ead_diff < 5 else "⚠️"
        print(f"\n{status} EAD Difference: {ead_diff:.2f}%")
    
    # DEL rates
    for del_type in ['del30', 'del60', 'del90']:
        key = f'{del_type}_diff_pct'
        diff = validation_result.get(key, np.nan)
        if not np.isnan(diff):
            status = "✅" if diff < 10 else "⚠️"
            print(f"{status} {del_type.upper()} Difference: {diff:.2f}%")
    
    # State distribution
    if 'state_distribution' in validation_result:
        df_dist = validation_result['state_distribution']
        if not df_dist.empty:
            print("\n📋 State Distribution Comparison:")
            print(df_dist.to_string())
    
    # Warnings
    warnings = validation_result.get('warnings', [])
    if warnings:
        print("\n⚠️ WARNINGS:")
        for w in warnings:
            print(f"   - {w}")
    
    # Overall
    passed = validation_result.get('passed', False)
    if passed:
        print("\n✅ VALIDATION PASSED")
    else:
        print("\n❌ VALIDATION FAILED")
    
    print("="*60 + "\n")


def validate_transition_matrices(matrices_by_mob: Dict, atol: float = 1e-6) -> List[str]:
    """
    Kiểm tra transition matrices có hợp lệ không:
    - Row sum = 1 (stochastic)
    - State order khớp BUCKETS_CANON
    - Absorbing states có prob = 1 ở lại
    """
    
    issues = []
    
    for product, mob_dict in matrices_by_mob.items():
        for mob, score_dict in mob_dict.items():
            for score, entry in score_dict.items():
                P = entry["P"]
                
                # Check state order
                if list(P.index) != BUCKETS_CANON or list(P.columns) != BUCKETS_CANON:
                    issues.append(
                        f"({product}, MOB={mob}, {score}): State order mismatch"
                    )
                    continue
                
                # Check row sum
                row_sums = P.sum(axis=1)
                if not np.allclose(row_sums, 1.0, atol=atol):
                    bad_rows = P.index[~np.isclose(row_sums, 1.0, atol=atol)].tolist()
                    issues.append(
                        f"({product}, MOB={mob}, {score}): "
                        f"Row sum != 1 for states: {bad_rows}"
                    )
                
                # Check absorbing states
                absorbing = ['WRITEOFF', 'PREPAY', 'SOLDOUT']
                for st in absorbing:
                    if st in P.index and st in P.columns:
                        if not np.isclose(P.loc[st, st], 1.0, atol=atol):
                            issues.append(
                                f"({product}, MOB={mob}, {score}): "
                                f"Absorbing state {st} has P[{st},{st}] = {P.loc[st, st]:.4f} != 1"
                            )
    
    return issues


def monitor_forecast_quality(
    df_actual: pd.DataFrame,
    df_forecast: pd.DataFrame,
    metric: str = 'DEL90_PCT',
) -> pd.DataFrame:
    """
    Monitor forecast quality theo thời gian:
    - MAPE (Mean Absolute Percentage Error)
    - Bias (forecast - actual)
    - Coverage (% cohorts có forecast)
    """
    
    # Merge actual vs forecast
    merged = df_actual.merge(
        df_forecast,
        on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'MOB'],
        how='inner',
        suffixes=('_ACT', '_FC')
    )
    
    if merged.empty:
        print("⚠️ No matching cohorts between actual and forecast")
        return pd.DataFrame()
    
    # Calculate metrics
    merged['APE'] = abs(
        merged[f'{metric}_FC'] - merged[f'{metric}_ACT']
    ) / merged[f'{metric}_ACT'].replace(0, np.nan) * 100
    
    merged['BIAS'] = merged[f'{metric}_FC'] - merged[f'{metric}_ACT']
    
    # Aggregate by product and MOB
    summary = merged.groupby(['PRODUCT_TYPE', 'MOB']).agg({
        'APE': 'mean',
        'BIAS': 'mean',
        f'{metric}_ACT': 'count',
    }).rename(columns={
        'APE': 'MAPE',
        'BIAS': 'AVG_BIAS',
        f'{metric}_ACT': 'N_COHORTS',
    })
    
    return summary
```

### **Cách sử dụng:**

```python
# Trong notebook Final_Workflow.ipynb

from src.rollrate.validation import (
    validate_allocation,
    print_validation_report,
    validate_transition_matrices,
    monitor_forecast_quality,
)

# 1. Validate transition matrices
print("🔍 Validating transition matrices...")
matrix_issues = validate_transition_matrices(matrices_by_mob)
if matrix_issues:
    print("⚠️ Found issues in transition matrices:")
    for issue in matrix_issues[:10]:  # Show first 10
        print(f"   - {issue}")
else:
    print("✅ All transition matrices are valid")

# 2. Validate allocation
for target_mob in [12, 24]:
    result = validate_allocation(
        df_loan_forecast=df_loan_forecast,
        df_lifecycle_final=df_lifecycle_final,
        target_mob=target_mob,
        tolerance_ead=5.0,
        tolerance_del=10.0,
    )
    print_validation_report(result, target_mob)

# 3. Monitor forecast quality
print("\n📈 Monitoring forecast quality...")
quality_summary = monitor_forecast_quality(
    df_actual=df_lifecycle_final[df_lifecycle_final['IS_FORECAST'] == 0],
    df_forecast=df_full_history_forecast,
    metric='DEL90_PCT',
)
print(quality_summary)
```

---

## 2️⃣ PARENT FALLBACK HIERARCHY

### **File cần sửa:** `src/rollrate/transition.py`

Thêm function mới:

```python
def build_fallback_hierarchy(
    matrices_by_mob: Dict,
    pairs: pd.DataFrame,
) -> Dict:
    """
    Xây dựng fallback hierarchy:
    1. Score-level: (product, score) - all MOBs
    2. Product-level: (product) - all scores, all MOBs
    3. Portfolio-level: all products, all scores, all MOBs
    """
    
    fallback = {
        'score_level': {},      # (product, score) -> P
        'product_level': {},    # product -> P
        'portfolio_level': None # P
    }
    
    # 1. Score-level (đã có sẵn trong parent_fallback)
    for (prod, score), grp in pairs.groupby(['product_t', 'score_t']):
        P = compute_transition_from_pairs(
            grp,
            value_col='ead_t',
            parent_P=None,
            zero_row_policy='uniform',
        )
        fallback['score_level'][(str(prod), str(score))] = P
    
    # 2. Product-level (aggregate all scores)
    for prod, grp in pairs.groupby('product_t'):
        P = compute_transition_from_pairs(
            grp,
            value_col='ead_t',
            parent_P=None,
            zero_row_policy='uniform',
        )
        fallback['product_level'][str(prod)] = P
    
    # 3. Portfolio-level (aggregate all)
    P_portfolio = compute_transition_from_pairs(
        pairs,
        value_col='ead_t',
        parent_P=None,
        zero_row_policy='uniform',
    )
    fallback['portfolio_level'] = P_portfolio
    
    return fallback


def get_fallback_matrix_smart(
    product: str,
    score: str,
    mob: int,
    matrices_by_mob: Dict,
    fallback_hierarchy: Dict,
) -> pd.DataFrame:
    """
    Lấy matrix với fallback hierarchy thông minh:
    1. Try exact (product, score, mob)
    2. Try adjacent MOB (±1, ±2)
    3. Try score-level (product, score)
    4. Try product-level (product)
    5. Try portfolio-level
    """
    
    # 1. Try exact
    if (
        product in matrices_by_mob
        and mob in matrices_by_mob[product]
        and score in matrices_by_mob[product][mob]
    ):
        return matrices_by_mob[product][mob][score]["P"]
    
    # 2. Try adjacent MOB
    if product in matrices_by_mob:
        for delta in [1, -1, 2, -2, 3, -3]:
            adj_mob = mob + delta
            if (
                adj_mob in matrices_by_mob[product]
                and score in matrices_by_mob[product][adj_mob]
            ):
                print(f"   ℹ️ Using adjacent MOB {adj_mob} for (product={product}, score={score}, mob={mob})")
                return matrices_by_mob[product][adj_mob][score]["P"]
    
    # 3. Try score-level
    key = (product, score)
    if key in fallback_hierarchy['score_level']:
        print(f"   ℹ️ Using score-level fallback for (product={product}, score={score}, mob={mob})")
        return fallback_hierarchy['score_level'][key]
    
    # 4. Try product-level
    if product in fallback_hierarchy['product_level']:
        print(f"   ℹ️ Using product-level fallback for (product={product}, score={score}, mob={mob})")
        return fallback_hierarchy['product_level'][product]
    
    # 5. Portfolio-level
    print(f"   ⚠️ Using portfolio-level fallback for (product={product}, score={score}, mob={mob})")
    return fallback_hierarchy['portfolio_level']
```

### **Cách sử dụng:**

Sửa trong `compute_transition_by_mob`:

```python
def compute_transition_by_mob(df: pd.DataFrame):
    pairs = make_pairs(df)
    if pairs.empty:
        return {}, {}
    
    # Build fallback hierarchy
    fallback_hierarchy = build_fallback_hierarchy(matrices_by_mob={}, pairs=pairs)
    
    matrices_by_mob = defaultdict(lambda: defaultdict(dict))
    
    # ... existing code ...
    
    # Khi cần fallback, dùng get_fallback_matrix_smart thay vì parent_fallback
    
    return matrices_by_mob, fallback_hierarchy
```

---

## 3️⃣ ADAPTIVE ROLL_WINDOW

### **File cần sửa:** `src/config.py`

Thêm function:

```python
def compute_adaptive_roll_window(
    df: pd.DataFrame,
    product: str | None = None,
    min_window: int = 12,
    max_window: int = 24,
    min_obs_per_month: int = 100,
) -> int:
    """
    Tự động chọn ROLL_WINDOW tối ưu dựa trên data availability.
    
    Logic:
    - Nếu có đủ data (>= max_window months với >= min_obs_per_month) → max_window
    - Nếu ít data → min_window
    - Nếu rất ít → dùng toàn bộ
    """
    
    cutoff_col = CFG["cutoff"]
    
    # Filter by product if specified
    if product:
        df = df[df["PRODUCT_TYPE"] == product]
    
    # Count observations per month
    obs_per_month = df.groupby(
        pd.to_datetime(df[cutoff_col]).dt.to_period("M")
    ).size()
    
    # Count months with sufficient observations
    n_good_months = (obs_per_month >= min_obs_per_month).sum()
    
    if n_good_months >= max_window:
        return max_window
    elif n_good_months >= min_window:
        return min_window
    else:
        return max(n_good_months, 6)  # Minimum 6 months
```

### **File cần sửa:** `src/rollrate/transition.py`

Sửa trong `make_pairs`:

```python
def make_pairs(df: pd.DataFrame) -> pd.DataFrame:
    # ... existing code ...
    
    # ✅ Adaptive ROLL_WINDOW
    product = df["PRODUCT_TYPE"].iloc[0] if "PRODUCT_TYPE" in df.columns else None
    ROLL_WINDOW = compute_adaptive_roll_window(
        df=df,
        product=product,
        min_window=12,
        max_window=24,
    )
    
    print(f"   ℹ️ Using ROLL_WINDOW = {ROLL_WINDOW} for product {product}")
    
    # ... rest of code ...
```

---

## 4️⃣ DECAY_LAMBDA PER PRODUCT

### **File cần sửa:** `src/config.py`

Thêm mapping:

```python
# Decay lambda per product
# Products ổn định → decay nhẹ (0.95)
# Products biến động → decay mạnh (0.85)
DECAY_LAMBDA_MAP = {
    "SALPIL": 0.95,   # Salary loan - ổn định
    "CDLPIL": 0.95,   # Cash loan - ổn định
    "TWLPIL": 0.90,   # Two-wheeler - trung bình
    "SPLPIL": 0.90,   # Special loan - trung bình
    "TOPUP": 0.85,    # Top-up - biến động
    "XSELL": 0.85,    # Cross-sell - biến động
}
DEFAULT_DECAY_LAMBDA = 0.90
```

### **File cần sửa:** `src/rollrate/transition.py`

Sửa trong `make_pairs`:

```python
def make_pairs(df: pd.DataFrame) -> pd.DataFrame:
    # ... existing code ...
    
    # ✅ Adaptive DECAY_LAMBDA
    product = df["PRODUCT_TYPE"].iloc[0] if "PRODUCT_TYPE" in df.columns else None
    DECAY_LAMBDA = DECAY_LAMBDA_MAP.get(product, DEFAULT_DECAY_LAMBDA)
    
    print(f"   ℹ️ Using DECAY_LAMBDA = {DECAY_LAMBDA} for product {product}")
    
    # ====== TIME WEIGHT ======
    if WEIGHT_METHOD == "exp":
        time_w = (DECAY_LAMBDA ** age).astype(float)
    # ... rest of code ...
```

---

## 📋 CHECKLIST TRIỂN KHAI

### **Ngày 1:**
- [ ] Tạo file `src/rollrate/validation.py`
- [ ] Test validation functions với data mẫu
- [ ] Thêm validation vào notebook `Final_Workflow.ipynb`
- [ ] Chạy validation và fix các issues phát hiện

### **Ngày 2:**
- [ ] Implement `build_fallback_hierarchy` trong `transition.py`
- [ ] Implement `get_fallback_matrix_smart` trong `transition.py`
- [ ] Test fallback hierarchy với data thiếu
- [ ] Implement `compute_adaptive_roll_window` trong `config.py`
- [ ] Implement `DECAY_LAMBDA_MAP` trong `config.py`
- [ ] Update `make_pairs` để dùng adaptive parameters
- [ ] Chạy full pipeline và so sánh kết quả

### **Ngày 3:**
- [ ] Backtest với data cũ để đo improvement
- [ ] Document kết quả
- [ ] Commit code

---

## 📊 EXPECTED RESULTS

### **Trước khi cải thiện:**
- EAD mismatch: ~10-15%
- DEL90 mismatch: ~15-20%
- Fallback rate: ~30-40%

### **Sau khi cải thiện:**
- EAD mismatch: ~3-5% ✅
- DEL90 mismatch: ~5-10% ✅
- Fallback rate: ~15-20% ✅
- Forecast accuracy: +5-10% ✅

---

**Tác giả:** Roll Rate Model Team  
**Ngày tạo:** 2026-02-09
