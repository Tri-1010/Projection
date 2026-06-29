"""
Test script để verify allocation_v2_optimized
Kiểm tra xem có lấy actual từ df_raw không
"""

import sys
from pathlib import Path
project_root = Path(".").resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
from src.config import CFG, parse_date_column, create_segment_columns
from src.data_loader import load_data
from src.rollrate.transition import compute_transition_by_mob
from src.rollrate.lifecycle import get_actual_all_vintages_amount
from src.rollrate.calibration_kmob import fit_k_raw, smooth_k, fit_alpha, forecast_all_vintages_partial_step
from src.rollrate.lifecycle import combine_all_lifecycle_amount, lifecycle_to_long_df_amount, tag_forecast_rows_amount
from src.rollrate.allocation_v2_optimized import allocate_multi_mob_optimized

print("="*60)
print("TEST: ALLOCATION V2 OPTIMIZED")
print("="*60)

# ============================
# 1. LOAD DATA (sample nhỏ để test nhanh)
# ============================
print("\n1️⃣ Loading data...")
DATA_PATH = 'C:/Users/User/Projection_PB/Projection_pb/ETB_Parquet_YYYYMM'
df_raw = load_data(DATA_PATH)
df_raw['DISBURSAL_DATE'] = parse_date_column(df_raw['DISBURSAL_DATE'])
df_raw = create_segment_columns(df_raw)

print(f"   Total data: {len(df_raw):,} rows")

# Sample 1 product để test nhanh
df_raw = df_raw[df_raw['PRODUCT_TYPE'] == 'X'].copy()
print(f"   Filtered to product X: {len(df_raw):,} rows")

# ============================
# 2. BUILD MATRICES
# ============================
print("\n2️⃣ Building transition matrices...")
matrices_by_mob, parent_fallback = compute_transition_by_mob(df_raw)
print(f"   ✅ Built matrices")

# ============================
# 3. BUILD LIFECYCLE
# ============================
print("\n3️⃣ Building lifecycle...")
MAX_MOB = 24
TARGET_MOB = 24

actual_results = get_actual_all_vintages_amount(df_raw)

# Fit k (simplified)
loan_disb = df_raw.groupby(["PRODUCT_TYPE", "RISK_SCORE", CFG["orig_date"], CFG["loan"]])[CFG["disb"]].first()
disb_total_by_vintage = loan_disb.groupby(level=[0, 1, 2]).sum().to_dict()

from src.config import BUCKETS_CANON, BUCKETS_30P

k_raw_by_mob, weight_by_mob, _ = fit_k_raw(
    actual_results=actual_results,
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    states=BUCKETS_CANON,
    s30_states=BUCKETS_30P,
    include_co=True,
    denom_mode="disb",
    disb_total_by_vintage=disb_total_by_vintage,
    weight_mode="equal",
    method="wls_reg",
    lambda_k=1e-4,
    k_prior=0.0,
    min_obs=5,
    fallback_k=1.0,
    fallback_weight=0.0,
    return_detail=True,
)

mob_min = min(k_raw_by_mob.keys()) if k_raw_by_mob else 0
mob_max = max(k_raw_by_mob.keys()) if k_raw_by_mob else 0
k_smooth_by_mob, _, _ = smooth_k(k_raw_by_mob, weight_by_mob, mob_min, mob_max)

alpha, k_final_by_mob, _ = fit_alpha(
    actual_results=actual_results,
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    states=BUCKETS_CANON,
    s30_states=BUCKETS_30P,
    k_smooth_by_mob=k_smooth_by_mob,
    mob_target=min(MAX_MOB, mob_max) if mob_max else MAX_MOB,
    include_co=True,
)

forecast_calibrated = forecast_all_vintages_partial_step(
    actual_results=actual_results,
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    max_mob=MAX_MOB,
    k_by_mob=k_final_by_mob,
    states=BUCKETS_CANON,
)

lifecycle_combined = combine_all_lifecycle_amount(actual_results, forecast_calibrated)
df_lifecycle_final = lifecycle_to_long_df_amount(lifecycle_combined)
df_lifecycle_final = tag_forecast_rows_amount(df_lifecycle_final, df_raw)

print(f"   ✅ Lifecycle built: {len(df_lifecycle_final):,} rows")

# Kiểm tra có bao nhiêu cohorts có actual vs forecast @ MOB 24
df_lc_24 = df_lifecycle_final[df_lifecycle_final['MOB'] == TARGET_MOB]
n_actual_cohorts = (df_lc_24['IS_FORECAST'] == 0).sum()
n_forecast_cohorts = (df_lc_24['IS_FORECAST'] == 1).sum()

print(f"\n   📊 Cohorts @ MOB {TARGET_MOB}:")
print(f"      Actual: {n_actual_cohorts}")
print(f"      Forecast: {n_forecast_cohorts}")

# ============================
# 4. PREPARE LOANS LATEST
# ============================
print("\n4️⃣ Preparing loans latest...")
latest_cutoff = df_raw['CUTOFF_DATE'].max()
df_loans_latest = df_raw[df_raw['CUTOFF_DATE'] == latest_cutoff].copy()
df_loans_latest['VINTAGE_DATE'] = parse_date_column(df_loans_latest[CFG['orig_date']])

print(f"   Latest cutoff: {latest_cutoff}")
print(f"   Loans: {len(df_loans_latest):,}")

# ============================
# 5. TEST ALLOCATION OPTIMIZED
# ============================
print("\n5️⃣ Testing allocation_v2_optimized...")
print("="*60)

df_result = allocate_multi_mob_optimized(
    df_raw=df_raw,
    df_loans_latest=df_loans_latest,
    df_lifecycle_final=df_lifecycle_final,
    matrices_by_mob=matrices_by_mob,
    target_mobs=[TARGET_MOB],
    parent_fallback=parent_fallback,
    include_del30=False,
    include_del90=True,
    seed=42,
)

print("\n" + "="*60)
print("✅ TEST COMPLETE")
print("="*60)

# ============================
# 6. VERIFY RESULTS
# ============================
print("\n6️⃣ Verifying results...")

is_actual_col = f'IS_ACTUAL_MOB{TARGET_MOB}'
state_col = f'STATE_FORECAST_MOB{TARGET_MOB}'
ead_col = f'EAD_FORECAST_MOB{TARGET_MOB}'

if is_actual_col in df_result.columns:
    n_actual = df_result[is_actual_col].sum()
    n_forecast = (df_result[is_actual_col] == 0).sum()
    
    print(f"\n   📊 Results @ MOB {TARGET_MOB}:")
    print(f"      Total loans: {len(df_result):,}")
    print(f"      Actual loans: {n_actual:,} ({n_actual/len(df_result)*100:.1f}%)")
    print(f"      Forecast loans: {n_forecast:,} ({n_forecast/len(df_result)*100:.1f}%)")
    
    if n_actual > 0:
        print(f"\n   ✅ SUCCESS: Actual data được lấy từ df_raw!")
    else:
        print(f"\n   ⚠️  WARNING: Không có actual data (có thể do không có cohort nào có actual @ MOB {TARGET_MOB})")
else:
    print(f"\n   ❌ ERROR: Column {is_actual_col} không tồn tại!")

# Sample một vài loans để xem
print(f"\n   📋 Sample results:")
sample_cols = [CFG['loan'], 'PRODUCT_TYPE', 'RISK_SCORE', 'MOB_CURRENT']
if state_col in df_result.columns:
    sample_cols.append(state_col)
if ead_col in df_result.columns:
    sample_cols.append(ead_col)
if is_actual_col in df_result.columns:
    sample_cols.append(is_actual_col)

print(df_result[sample_cols].head(10))

print("\n" + "="*60)
print("🎉 TEST HOÀN TẤT!")
print("="*60)
