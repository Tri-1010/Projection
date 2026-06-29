# Allocation Logic - Validation Checklist

## 📋 Checklist để xác định logic có hợp lý

### ✅ **PHẦN 1: Technical Validation**

- [ ] **Aggregate match lifecycle**
  ```python
  # Check: Tổng EAD_FORECAST = Tổng EAD_LIFECYCLE?
  total_forecast = df_result.groupby('STATE_FORECAST')['EAD_FORECAST'].sum()
  total_lifecycle = df_lifecycle[BUCKETS_CANON].sum()
  diff = abs(total_forecast - total_lifecycle).sum()
  assert diff < 1.0, f"Mismatch: {diff}"
  ```

- [ ] **Proportional preserved**
  ```python
  # Check: Tỉ lệ giữa loans được giữ?
  ratio_current = loan_A.EAD_CURRENT / loan_B.EAD_CURRENT
  ratio_forecast = loan_A.EAD_FORECAST / loan_B.EAD_FORECAST
  assert abs(ratio_current - ratio_forecast) < 0.01
  ```

- [ ] **Risk reflected in STATE assignment**
  ```python
  # Check: Loan ở DPD30+ có xác suất cao ở bad states?
  loans_dpd30 = df[df['STATE_CURRENT'] == 'DPD30+']
  bad_state_rate = loans_dpd30['STATE_FORECAST'].isin(BUCKETS_90P).mean()
  assert bad_state_rate > 0.3, "Risk not reflected"
  ```

- [ ] **Transition matrix used correctly**
  ```python
  # Check: Score A có better outcome than Score D?
  score_a_del90 = df[df['RISK_SCORE']=='A']['DEL90_FLAG'].mean()
  score_d_del90 = df[df['RISK_SCORE']=='D']['DEL90_FLAG'].mean()
  assert score_a_del90 < score_d_del90, "Risk score not working"
  ```

---

### ✅ **PHẦN 2: Business Validation**

- [ ] **Kết quả có reasonable không?**
  - DEL90 rate trong khoảng expected? (ví dụ: 2-5%)
  - Không có outliers (loan forecast 1000x EAD_CURRENT)
  - Distribution hợp lý (không quá concentrated)

- [ ] **Có match với business intuition không?**
  - High-risk loans có higher DEL rate?
  - Large loans có larger EAD_FORECAST?
  - Seasoned loans (MOB cao) có better performance?

- [ ] **Có satisfy regulatory requirements không?**
  - IFRS 9 / Basel requirements
  - Audit trail đầy đủ
  - Methodology documented

---

### ✅ **PHẦN 3: Data Quality**

- [ ] **Input data quality**
  - Không có missing values quan trọng
  - STATE_CURRENT valid (trong BUCKETS_CANON)
  - EAD_CURRENT > 0
  - VINTAGE_DATE valid

- [ ] **Lifecycle data quality**
  - Có đủ cohorts @ target_mob
  - IS_FORECAST flag correct
  - EAD values reasonable

- [ ] **Transition matrix quality**
  - Matrix sum to 1.0 per row
  - Không có negative values
  - Có đủ matrices cho các segments

---

### ✅ **PHẦN 4: Performance**

- [ ] **Speed acceptable?**
  - 100k loans: < 5 phút
  - 1M loans: < 30 phút
  - Có thể optimize nếu cần

- [ ] **Memory usage acceptable?**
  - Không bị out of memory
  - Có thể process full dataset

- [ ] **Reproducible?**
  - Cùng seed → Cùng kết quả
  - Documented seed value

---

### ✅ **PHẦN 5: Backtest (Nếu có actual data)**

- [ ] **Accuracy**
  ```python
  # So sánh forecast vs actual
  df_backtest = df_forecast.merge(df_actual, on='LOAN_ID')
  
  # State accuracy
  state_accuracy = (df_backtest['STATE_FORECAST'] == df_backtest['STATE_ACTUAL']).mean()
  print(f"State accuracy: {state_accuracy:.2%}")
  
  # EAD accuracy
  ead_mape = abs(df_backtest['EAD_FORECAST'] - df_backtest['EAD_ACTUAL']).mean() / df_backtest['EAD_ACTUAL'].mean()
  print(f"EAD MAPE: {ead_mape:.2%}")
  ```

- [ ] **Bias check**
  ```python
  # Check systematic over/under forecast
  bias = (df_backtest['EAD_FORECAST'] - df_backtest['EAD_ACTUAL']).mean()
  print(f"Bias: {bias:,.0f}")
  ```

- [ ] **Segment analysis**
  ```python
  # Check accuracy per segment
  for segment in ['A', 'B', 'C', 'D']:
      df_seg = df_backtest[df_backtest['RISK_SCORE'] == segment]
      accuracy = (df_seg['STATE_FORECAST'] == df_seg['STATE_ACTUAL']).mean()
      print(f"Segment {segment}: {accuracy:.2%}")
  ```

---

## 🎯 Decision Matrix

### **Nếu TẤT CẢ checklist PASS:**
→ ✅ **Logic HỢP LÝ, GIỮ NGUYÊN**

### **Nếu có 1-2 items FAIL:**
→ ⚠️ **INVESTIGATE và FIX**

### **Nếu có 3+ items FAIL:**
→ ❌ **XEM XÉT THAY ĐỔI logic**

---

## 📊 Validation Script

```python
"""
Script để validate allocation logic
"""

import pandas as pd
import numpy as np

def validate_allocation(df_result, df_lifecycle, df_raw):
    """
    Validate allocation results
    
    Returns:
        dict: Validation results
    """
    
    results = {}
    
    # 1. Aggregate match
    total_forecast = df_result['EAD_FORECAST'].sum()
    total_lifecycle = df_lifecycle[BUCKETS_CANON].sum().sum()
    diff_pct = abs(total_forecast - total_lifecycle) / total_lifecycle * 100
    
    results['aggregate_match'] = diff_pct < 1.0
    results['aggregate_diff_pct'] = diff_pct
    
    # 2. Proportional check (sample)
    sample_cohort = df_result.groupby(['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']).first()
    if len(sample_cohort) > 0:
        cohort = sample_cohort.iloc[0]
        loans = df_result[
            (df_result['PRODUCT_TYPE'] == cohort['PRODUCT_TYPE']) &
            (df_result['RISK_SCORE'] == cohort['RISK_SCORE']) &
            (df_result['VINTAGE_DATE'] == cohort['VINTAGE_DATE'])
        ].head(2)
        
        if len(loans) == 2:
            ratio_current = loans.iloc[0]['EAD_CURRENT'] / loans.iloc[1]['EAD_CURRENT']
            ratio_forecast = loans.iloc[0]['EAD_FORECAST'] / loans.iloc[1]['EAD_FORECAST']
            results['proportional_preserved'] = abs(ratio_current - ratio_forecast) < 0.1
        else:
            results['proportional_preserved'] = None
    
    # 3. Risk reflection
    if 'STATE_CURRENT' in df_result.columns:
        loans_dpd30 = df_result[df_result['STATE_CURRENT'].isin(['DPD30+', 'DPD60+', 'DPD90+'])]
        if len(loans_dpd30) > 0:
            bad_rate = loans_dpd30['STATE_FORECAST'].isin(BUCKETS_90P).mean()
            results['risk_reflected'] = bad_rate > 0.2
            results['bad_state_rate'] = bad_rate
        else:
            results['risk_reflected'] = None
    
    # 4. Reasonable DEL rate
    if 'DEL90_FLAG' in df_result.columns:
        del90_rate = df_result['DEL90_FLAG'].mean()
        results['del90_reasonable'] = 0.01 < del90_rate < 0.15
        results['del90_rate'] = del90_rate
    
    # Summary
    passed = sum([v for v in results.values() if isinstance(v, bool) and v])
    total = sum([1 for v in results.values() if isinstance(v, bool)])
    results['summary'] = f"{passed}/{total} checks passed"
    
    return results

# Usage
results = validate_allocation(df_result, df_lifecycle_final, df_raw)
print(results)
```

---

## 🔍 Red Flags

### ⚠️ **Cần investigate nếu:**

1. **Aggregate mismatch > 5%**
   - Check lifecycle data
   - Check missing cohorts

2. **DEL90 rate < 1% hoặc > 20%**
   - Too optimistic hoặc pessimistic
   - Check transition matrices

3. **Proportional không preserved**
   - Bug trong allocation code
   - Check ratio calculation

4. **Risk không reflected**
   - Transition matrix không work
   - Check STATE_CURRENT mapping

5. **Backtest accuracy < 60%**
   - Model không predictive
   - Cần retrain hoặc adjust

---

## 📝 Documentation Requirements

Để pass audit, cần document:

- [ ] Methodology explanation
- [ ] Assumptions và limitations
- [ ] Validation results
- [ ] Backtest results (nếu có)
- [ ] Known issues và mitigations
- [ ] Change log

---

**Author**: Kiro AI  
**Date**: 2026-02-09  
**Version**: 1.0
