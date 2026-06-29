# Fix: Pure Forecast Comparison in Markovchainv2.ipynb

## Issue Identified by User

User correctly identified that the forecast comparison was **biased** because both "With K" and "No K" forecasts were using `combine_all_lifecycle_amount(actual_results, forecast_xxx)`, which means:

- Both forecasts contained the SAME actual data
- The comparison was not fair because actual data dominated the metrics
- The difference between "With K" and "No K" was artificially small

## Root Cause

The original code in Section 7.2 created:
```python
# WRONG: Both contain actual data
lifecycle_combined = combine_all_lifecycle_amount(actual_results, forecast_calibrated)
df_lifecycle_final = lifecycle_to_long_df_amount(lifecycle_combined)  # With K

lifecycle_no_k = combine_all_lifecycle_amount(actual_results, forecast_no_k)
df_lifecycle_no_k = lifecycle_to_long_df_amount(lifecycle_no_k)  # No K
```

This meant both DataFrames had:
- MOB 1-12: Actual data (same for both)
- MOB 13-24: Forecast data (different)

When comparing, the actual portion (MOB 1-12) was identical, making the comparison unfair.

## Solution Applied

### Section 7.2: Create Pure Forecast DataFrames

**FIXED CODE:**
```python
# Build PURE forecast WITHOUT K factor (k=1.0 = Markov thuần túy)
k_no_k = {m: 1.0 for m in range(1, MAX_MOB + 1)}

# Forecast without K (Markov thuần túy)
forecast_no_k = forecast_all_vintages_partial_step(
    actual_results=actual_results,
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    max_mob=MAX_MOB,
    k_by_mob=k_no_k,
    states=BUCKETS_CANON
)

# Convert to DataFrame - CHỈ LẤY FORECAST (không merge actual)
df_forecast_no_k = lifecycle_to_long_df_amount(forecast_no_k)
df_forecast_no_k = tag_forecast_rows_amount(df_forecast_no_k, df_raw)
df_forecast_no_k = add_del_metrics(df_forecast_no_k, df_raw)

# Lấy PHẦN FORECAST từ df_lifecycle_final (With K)
df_forecast_with_k = df_lifecycle_final[df_lifecycle_final['IS_FORECAST'] == 1].copy()

# Lấy PHẦN ACTUAL để reference
df_actual_only = df_lifecycle_final[df_lifecycle_final['IS_FORECAST'] == 0].copy()
```

**KEY CHANGES:**
1. `df_forecast_no_k` = PURE forecast without K (no actual data merged)
2. `df_forecast_with_k` = PURE forecast with K (extracted from df_lifecycle_final)
3. `df_actual_only` = PURE actual data (for reference)

### Section 7.3: DEL30+ Rate Curves Comparison

**FIXED CODE:**
```python
# Only Actual (IS_FORECAST=0) - để reference
agg_actual = df_actual_only.groupby('MOB')['DEL30_PCT'].mean() * 100

# PURE Forecast No K (Markov thuần túy)
agg_fc_no_k = df_forecast_no_k.groupby('MOB')['DEL30_PCT'].mean() * 100

# PURE Forecast With K (có calibration)
agg_fc_with_k = df_forecast_with_k.groupby('MOB')['DEL30_PCT'].mean() * 100
```

**RESULT:** Now comparing PURE forecasts only (no actual data contamination)

### Section 7.4: MAE & MAPE Analysis

Already using pure forecasts correctly from Section 7.3.

### Section 7.5: MAE & MAPE by Cohort Level

**FIXED CODE:**
```python
# Get actual data (for reference)
df_actual_cohort = df_actual_only[['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'MOB', 'DEL30_PCT']].copy()
df_actual_cohort = df_actual_cohort.rename(columns={'DEL30_PCT': 'DEL30_PCT_ACTUAL'})

# Get PURE forecast data (With K) - already created in Section 7.2
df_fc_with_k_cohort = df_forecast_with_k[['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'MOB', 'DEL30_PCT']].copy()
df_fc_with_k_cohort = df_fc_with_k_cohort.rename(columns={'DEL30_PCT': 'DEL30_PCT_WITH_K'})

# Get PURE forecast data (No K) - already created in Section 7.2
df_fc_no_k_cohort = df_forecast_no_k[['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'MOB', 'DEL30_PCT']].copy()
df_fc_no_k_cohort = df_fc_no_k_cohort.rename(columns={'DEL30_PCT': 'DEL30_PCT_NO_K'})
```

**BEFORE (WRONG):**
```python
# WRONG: Used df_lifecycle_no_k which doesn't exist
df_fc_no_k = df_lifecycle_no_k[df_lifecycle_no_k['IS_FORECAST'] == 1][...].copy()

# WRONG: Used df_lifecycle_final which contains actual data
agg_fc_no_k_prod = df_lifecycle_no_k[df_lifecycle_no_k['IS_FORECAST'] == 1].groupby([...])
```

**AFTER (CORRECT):**
```python
# CORRECT: Use df_forecast_no_k (pure forecast)
df_fc_no_k_cohort = df_forecast_no_k[...].copy()

# CORRECT: Use pure forecast DataFrames
agg_fc_no_k_prod = df_forecast_no_k.groupby(['PRODUCT_TYPE', 'MOB'])['DEL30_PCT'].mean()
```

### Section 7.6: DEL30+ Analysis Charts

Already correct - uses `df_backtest` which is filtered from actual only:
```python
df_backtest = df_lifecycle_final[df_lifecycle_final['IS_FORECAST'] == 0].copy()
```

## Impact of Fix

### Before Fix (Biased Comparison)
- Both "With K" and "No K" contained same actual data
- Comparison showed minimal difference
- User couldn't see true impact of K calibration

### After Fix (Fair Comparison)
- "With K" = Pure forecast with K factor
- "No K" = Pure forecast without K factor (Markov only)
- Comparison now shows TRUE difference between calibrated and uncalibrated forecasts
- User can properly evaluate if K calibration is helping

## Expected Results

Based on user's chart showing "Forecast With K is closer to Actual than Forecast No K":

1. **MAE/MAPE should show improvement**: With K should have lower error than No K
2. **DEL30+ curves should diverge**: Clear visual difference between With K and No K
3. **K factor is working**: Calibration is improving forecast accuracy

## Calibration Method Used

From `src/rollrate/calibration_kmob.py`:

- **Method**: `WLS_REG` (Weighted Least Squares with Regularization)
- **Parameters**:
  - `lambda_k=1e-4` (regularization coefficient)
  - `k_prior=0.0` (prior value for K)
  - `denom_mode='disb'` (uses DISB_TOTAL as denominator)
  - `weight_mode='equal'` (equal weight for all cohorts)

- **Forecast Formula**: Partial-step K adjustment
  ```
  v_{m+1} = v_m + k_m * (v_hat - v_m)
  ```
  where `v_hat = v_m @ P_m` (Markov forecast)

## Files Modified

1. `notebooks/Markovchainv2.ipynb`:
   - Section 7.2: Create pure forecast DataFrames
   - Section 7.3: Use pure forecasts for comparison
   - Section 7.5: Fix to use pure forecasts (removed df_lifecycle_no_k references)

## Verification Steps

Run the notebook and verify:

1. ✅ Section 7.2 creates 3 separate DataFrames:
   - `df_forecast_no_k` (pure forecast, no K)
   - `df_forecast_with_k` (pure forecast, with K)
   - `df_actual_only` (actual data only)

2. ✅ Section 7.3 shows clear difference between With K and No K curves

3. ✅ Section 7.4 shows MAE/MAPE improvement with K factor

4. ✅ Section 7.5 runs without errors (no more df_lifecycle_no_k references)

5. ✅ Charts show realistic DEL30+ rates (single digit %, not 60%)

## Conclusion

The fix ensures a **fair comparison** between calibrated (With K) and uncalibrated (No K) forecasts by:
- Removing actual data contamination from forecast comparison
- Using pure forecast DataFrames throughout
- Properly evaluating the impact of K calibration

User can now confidently assess whether K calibration is improving forecast accuracy.
