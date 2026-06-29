# Next Steps: Diagnosing DEL Curve Increase Issue

## Current Status

✅ **Confirmed**: Parent fallback is NOT used for MOB 25-36 in normal cases
✅ **Confirmed**: P_24 (last available MOB) is used for MOB 25-36
✅ **Confirmed**: Absorbing states are configured: `["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]`

## Your Observation is Correct

You correctly identified that:
- P_24 should have LOW transition rates (mature portfolio at MOB 24)
- Parent fallback has HIGHER rates (aggregates early MOBs 1-24)
- The curve starts flattening from MOB 24 but then increases again

## Three Potential Root Causes

### 1. K Values Too High at MOB 25+
If K ≈ 1.0 at MOB 25+, the model fully trusts the Markov forecast, causing movement even with P_24.

### 2. Some Cohorts Using Parent Fallback at MOB 24
If many cohorts don't have sufficient data at MOB 24 (n_obs < MIN_OBS or EAD < MIN_EAD), they use parent fallback which has higher transition rates.

### 3. Aggregation/Weighting Effect
When combining cohorts to product level, some cohorts with high weights might be driving the increase.

---

## ACTION REQUIRED: Run Diagnostic Script

You need to run the diagnostic script to identify the exact cause:

```python
# In your notebook (e.g., Final_Workflow.ipynb or Markovchain.ipynb)

from diagnose_why_increase_after_24 import diagnose_why_increase_after_24

# Run the diagnostic
diagnose_why_increase_after_24(
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    k_final_by_mob=k_final_by_mob,
    forecast_results=forecast_results,
    disb_total_by_vintage=disb_total_by_vintage,
    df_del_product=df_del_product  # Optional: if you have product-level DEL data
)
```

### Required Variables

Make sure these variables exist in your notebook:
- `matrices_by_mob`: Transition matrices by product/MOB/score
- `parent_fallback`: Parent fallback matrices
- `k_final_by_mob`: K values by MOB (after smoothing and alpha scaling)
- `forecast_results`: Forecast results by cohort
- `disb_total_by_vintage`: Total disbursement by cohort
- `df_del_product`: (Optional) Product-level DEL data

---

## What the Diagnostic Will Tell You

The script will check:

1. **K Values**: Are K values > 0.9 at MOB 25+?
2. **Fallback Usage**: What % of cohorts use parent fallback at MOB 24?
3. **P_24 vs Parent Comparison**: How different are they?
4. **Aggregation Effect**: Which cohorts are driving the increase?
5. **Cohort-Level Analysis**: Which specific cohorts have increasing DEL curves?

---

## Based on Results, Apply the Appropriate Fix

### If K Too High (K > 0.9 at MOB 25+)

**Solution**: Reduce K at MOB 25+

```python
# After fitting K, cap K at MOB 25+
for mob in range(25, 37):
    if mob in k_final_by_mob:
        k_final_by_mob[mob] = min(k_final_by_mob[mob], 0.3)
    else:
        k_final_by_mob[mob] = 0.3
```

### If Many Cohorts Use Fallback at MOB 24 (> 30%)

**Solution A**: Increase MIN_OBS/MIN_EAD thresholds

```python
# In src/config.py
MIN_OBS = 200  # Instead of 100
MIN_EAD = 500  # Instead of 100
```

**Solution B**: Force use parent fallback for MOB 25+

```python
# Modify _get_P_for_segment() in src/rollrate/calibration_kmob.py
def _get_P_for_segment(matrices_by_mob, parent_fallback, product, score, mob, states):
    prod_str = str(product)
    score_str = str(score)

    # ⭐ NEW: Force use parent fallback for MOB > 24
    if mob > 24:
        if parent_fallback is not None:
            key_exact = (prod_str, score_str)
            if key_exact in parent_fallback:
                return parent_fallback[key_exact].reindex(index=states, columns=states, fill_value=0.0)
    
    # Original logic for MOB <= 24
    mob_dict = matrices_by_mob.get(prod_str, {})
    P_df = None

    if mob in mob_dict and score_str in mob_dict[mob]:
        P_df = mob_dict[mob][score_str]["P"]
    else:
        if mob_dict:
            last_mob = max(mob_dict.keys())
            if score_str in mob_dict[last_mob]:
                P_df = mob_dict[last_mob][score_str]["P"]

    if P_df is None and parent_fallback is not None:
        key_exact = (prod_str, score_str)
        if key_exact in parent_fallback:
            P_df = parent_fallback[key_exact]
        else:
            candidate = [k for k in parent_fallback.keys() if k[0] == prod_str]
            if candidate:
                P_df = parent_fallback[candidate[0]]

    if P_df is None:
        eye = np.eye(len(states))
        P_df = pd.DataFrame(eye, index=states, columns=states)

    return P_df.reindex(index=states, columns=states, fill_value=0.0)
```

### If Aggregation Issue

**Solution**: Investigate cohort-level weights and identify which cohorts are driving the increase. The diagnostic script will show you the top cohorts with increasing slopes.

---

## Additional Diagnostic Scripts Available

### Check P_24 Quality

```python
from check_p24_quality import check_p24_quality

# Check a specific cohort
check_p24_quality(
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    product="C",
    score="650+_10M-_POS"
)
```

### General DEL Curve Diagnosis

```python
from diagnose_del_curve import diagnose_del_curve

diagnose_del_curve(
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    k_final_by_mob=k_final_by_mob,
    forecast_results=forecast_results,
    disb_total_by_vintage=disb_total_by_vintage,
    product="C",
    score="650+_10M-_POS",
    vintage="2023-12-01"
)
```

---

## Summary

1. ✅ **Run the diagnostic script first** to identify the exact cause
2. ✅ **Based on the results**, apply one of the three solutions above
3. ✅ **Re-run the forecast** and check if the DEL curve flattens
4. ✅ **Iterate** if needed

The diagnostic script will give you clear indicators (❌ or ✅) for each potential cause, making it easy to decide which fix to apply.

---

**Created**: 2026-01-21
**Status**: Ready to run diagnostics
