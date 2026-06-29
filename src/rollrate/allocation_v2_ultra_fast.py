# ============================================================
#  allocation_v2_ultra_fast.py – Phân bổ forecast CỰC NHANH (vectorized)
#  
#  TỐI ƯU:
#  - Loại bỏ nested loops
#  - Dùng vectorized operations (merge + groupby)
#  - Performance: 10-15x faster than allocation_v2_fast.py
#  
#  OUTPUT: Giống hệt allocation_v2_fast.py
# ============================================================

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from src.config import CFG, BUCKETS_CANON, BUCKETS_30P, BUCKETS_60P, BUCKETS_90P, parse_date_column

# Absorbing states - dư nợ = 0
ABSORBING_STATES = ['WRITEOFF', 'PREPAY', 'SOLDOUT']


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid for cohort-level probability calibration."""
    x = np.clip(x, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-x))


def _calibrate_probs_to_target(
    raw_probs: np.ndarray,
    exposures: np.ndarray,
    target_rate: float,
    eps: float = 1e-6,
    max_iter: int = 80,
) -> np.ndarray:
    """
    Shift loan-level raw probabilities on the logit scale so the exposure-weighted
    cohort total matches the lifecycle target rate.
    """
    probs = np.asarray(raw_probs, dtype=float)
    ead = np.asarray(exposures, dtype=float)

    if probs.size == 0:
        return probs

    total_exposure = float(ead.sum())
    if total_exposure <= 0:
        return np.clip(probs, 0.0, 1.0)

    if pd.isna(target_rate):
        return np.clip(probs, 0.0, 1.0)

    target_rate = float(np.clip(target_rate, 0.0, 1.0))
    target_total = target_rate * total_exposure

    if target_total <= 0:
        return np.zeros_like(probs)
    if target_total >= total_exposure:
        return np.ones_like(probs)

    probs_clip = np.clip(probs, eps, 1.0 - eps)
    logits = np.log(probs_clip / (1.0 - probs_clip))

    lo, hi = -30.0, 30.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        shifted = _sigmoid(logits + mid)
        mid_total = float(np.sum(ead * shifted))
        if mid_total < target_total:
            lo = mid
        else:
            hi = mid

    calibrated = _sigmoid(logits + 0.5 * (lo + hi))
    return np.clip(calibrated, 0.0, 1.0)


def _assign_ranked_flags_to_target(
    calibrated_probs: np.ndarray,
    exposures: np.ndarray,
    target_rate: float,
    fixed_positive: Optional[np.ndarray] = None,
    fixed_negative: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Select highest-risk loans with exposure closest to the cohort target."""
    probs = np.asarray(calibrated_probs, dtype=float)
    ead = np.maximum(np.asarray(exposures, dtype=float), 0.0)
    flags = np.zeros(len(probs), dtype=int)
    if len(probs) == 0 or ead.sum() <= 0 or pd.isna(target_rate):
        return flags

    fixed_positive = (
        np.asarray(fixed_positive, dtype=bool)
        if fixed_positive is not None
        else np.zeros(len(probs), dtype=bool)
    )
    fixed_negative = (
        np.asarray(fixed_negative, dtype=bool)
        if fixed_negative is not None
        else np.zeros(len(probs), dtype=bool)
    )
    fixed_negative = fixed_negative & ~fixed_positive
    variable = ~(fixed_positive | fixed_negative)
    flags[fixed_positive] = 1

    target_total = float(np.clip(target_rate, 0.0, 1.0) * ead.sum())
    residual_target = target_total - float(ead[fixed_positive].sum())
    if residual_target <= 0 or not variable.any():
        return flags
    if residual_target >= ead[variable].sum():
        flags[variable] = 1
        return flags

    variable_idx = np.flatnonzero(variable)
    order = variable_idx[np.argsort(-probs[variable], kind="mergesort")]
    cumulative = np.cumsum(ead[order])
    crossing = int(np.searchsorted(cumulative, residual_target, side="left"))
    candidates = [crossing]
    if crossing > 0:
        candidates.append(crossing - 1)
    best_crossing = min(
        candidates,
        key=lambda idx: abs(float(cumulative[idx]) - residual_target),
    )
    flags[order[: best_crossing + 1]] = 1
    return flags


def _calibrate_probs_with_fixed_states(
    raw_probs: np.ndarray,
    exposures: np.ndarray,
    target_rate: float,
    fixed_positive: np.ndarray,
    fixed_negative: np.ndarray,
) -> np.ndarray:
    probs = np.asarray(raw_probs, dtype=float).copy()
    ead = np.maximum(np.asarray(exposures, dtype=float), 0.0)
    fixed_positive = np.asarray(fixed_positive, dtype=bool)
    fixed_negative = np.asarray(fixed_negative, dtype=bool) & ~fixed_positive
    variable = ~(fixed_positive | fixed_negative)
    probs[fixed_positive] = 1.0
    probs[fixed_negative] = 0.0

    variable_exposure = float(ead[variable].sum())
    if variable_exposure <= 0 or pd.isna(target_rate):
        return np.clip(probs, 0.0, 1.0)

    target_total = float(np.clip(target_rate, 0.0, 1.0) * ead.sum())
    fixed_total = float(ead[fixed_positive].sum())
    variable_target_rate = np.clip(
        (target_total - fixed_total) / variable_exposure,
        0.0,
        1.0,
    )
    probs[variable] = _calibrate_probs_to_target(
        probs[variable],
        ead[variable],
        variable_target_rate,
    )
    return np.clip(probs, 0.0, 1.0)


def recalibrate_existing_loan_forecast_del90(
    df_loan_forecast: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    target_mobs: List[int],
) -> pd.DataFrame:
    """
    Reconcile stored raw DEL90 loan probabilities to updated lifecycle DEL90 targets
    without rerunning transition/state allocation.
    """
    if df_loan_forecast.empty or not target_mobs:
        return df_loan_forecast.copy()

    df = df_loan_forecast.copy()
    lifecycle = df_lifecycle_final.copy()
    cohort_cols = ['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']

    if 'STATE_CURRENT' not in df.columns or 'DISBURSAL_AMOUNT' not in df.columns:
        raise KeyError(
            "Loan forecast must contain STATE_CURRENT and DISBURSAL_AMOUNT for recalibration."
        )

    df['VINTAGE_DATE'] = pd.to_datetime(df['VINTAGE_DATE'])
    lifecycle['VINTAGE_DATE'] = pd.to_datetime(lifecycle['VINTAGE_DATE'])

    for target_mob in sorted({int(mob) for mob in target_mobs}):
        raw_prob_col = f'PROB_DEL90_RAW_MOB{target_mob}'
        prob_col = f'PROB_DEL90_MOB{target_mob}'
        ead_col = f'EAD_DEL90_MOB{target_mob}'
        flag_col = f'DEL90_FLAG_MOB{target_mob}'

        if raw_prob_col not in df.columns:
            continue

        target_df = lifecycle[
            (pd.to_numeric(lifecycle['MOB'], errors='coerce') == int(target_mob))
        ][cohort_cols + ['DEL90_PCT']].copy()
        target_df = target_df.rename(columns={'DEL90_PCT': '__TARGET_DEL90_PCT'})

        out = df.merge(target_df, on=cohort_cols, how='left')
        if '__TARGET_DEL90_PCT' not in out.columns:
            continue

        if prob_col not in out.columns:
            out[prob_col] = out[raw_prob_col].astype(float)
        if flag_col not in out.columns:
            out[flag_col] = 0

        for _, idx in out.groupby(cohort_cols, sort=False).groups.items():
            group_idx = list(idx)
            target_del90 = out.loc[group_idx[0], '__TARGET_DEL90_PCT']
            if pd.isna(target_del90):
                continue

            exposures = out.loc[group_idx, 'DISBURSAL_AMOUNT'].to_numpy(dtype=float)
            states_current = out.loc[group_idx, 'STATE_CURRENT'].astype(str).to_numpy()
            fixed_positive = states_current == 'WRITEOFF'
            fixed_negative = np.isin(states_current, ['PREPAY', 'SOLDOUT'])

            calibrated = _calibrate_probs_with_fixed_states(
                out.loc[group_idx, raw_prob_col].to_numpy(dtype=float),
                exposures,
                float(target_del90),
                fixed_positive,
                fixed_negative,
            )
            out.loc[group_idx, prob_col] = calibrated
            out.loc[group_idx, flag_col] = _assign_ranked_flags_to_target(
                calibrated,
                exposures,
                float(target_del90),
                fixed_positive,
                fixed_negative,
            )

        out[ead_col] = out['DISBURSAL_AMOUNT'].astype(float) * out[prob_col].astype(float)
        df = out.drop(columns=['__TARGET_DEL90_PCT'])

    return df


def _get_combined_matrix(
    matrices_by_mob: Dict,
    parent_fallback: Dict,
    product: str,
    score: str,
    mob_from: int,
    mob_to: int,
) -> np.ndarray:
    """Tính combined transition matrix từ mob_from đến mob_to."""
    n_states = len(BUCKETS_CANON)
    state_to_idx = {s: i for i, s in enumerate(BUCKETS_CANON)}
    
    combined = np.eye(n_states)
    
    for mob in range(mob_from, mob_to):
        P = None
        
        if product in matrices_by_mob:
            if mob in matrices_by_mob[product]:
                if score in matrices_by_mob[product][mob]:
                    matrix_data = matrices_by_mob[product][mob][score]
                    if isinstance(matrix_data, dict) and "P" in matrix_data:
                        P = matrix_data["P"]
        
        if P is None and parent_fallback:
            parent_key = (product, score)
            if parent_key in parent_fallback:
                P = parent_fallback[parent_key]
        
        if P is None:
            continue
        
        if isinstance(P, pd.DataFrame):
            P_arr = np.zeros((n_states, n_states))
            for from_state in P.index:
                if from_state in state_to_idx:
                    for to_state in P.columns:
                        if to_state in state_to_idx:
                            P_arr[state_to_idx[from_state], state_to_idx[to_state]] = P.loc[from_state, to_state]
            combined = combined @ P_arr
    
    return combined


def _get_actual_loans_at_mob(
    df_raw: pd.DataFrame,
    product: str,
    score: str,
    vintage_date: pd.Timestamp,
    target_mob: int,
) -> Optional[pd.DataFrame]:
    """
    Lấy actual loan-level data từ df_raw tại MOB cụ thể.
    (Legacy function - kept for compatibility)
    """
    loan_col = CFG["loan"]
    mob_col = CFG["mob"]
    state_col = CFG["state"]
    ead_col = CFG["ead"]
    orig_date_col = CFG.get("orig_date", "DISBURSAL_DATE")
    disb_col = CFG.get("disb", "DISBURSAL_AMOUNT")
    
    df_raw_copy = df_raw.copy()
    if 'VINTAGE_DATE' not in df_raw_copy.columns:
        df_raw_copy['VINTAGE_DATE'] = parse_date_column(df_raw_copy[orig_date_col])
    else:
        df_raw_copy['VINTAGE_DATE'] = pd.to_datetime(df_raw_copy['VINTAGE_DATE'])
    
    mask = (
        (df_raw_copy['PRODUCT_TYPE'] == product) &
        (df_raw_copy['RISK_SCORE'] == score) &
        (df_raw_copy['VINTAGE_DATE'] == vintage_date)
    )
    df_cohort = df_raw_copy[mask]
    
    if len(df_cohort) == 0:
        return None
    
    df_at_mob = df_cohort[df_cohort[mob_col] == target_mob]
    
    if len(df_at_mob) == 0:
        return None
    
    output_cols = [loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']
    
    if state_col in df_at_mob.columns:
        output_cols.append(state_col)
    if ead_col in df_at_mob.columns:
        output_cols.append(ead_col)
    if disb_col in df_at_mob.columns:
        output_cols.append(disb_col)
    
    df_result = df_at_mob[[c for c in output_cols if c in df_at_mob.columns]].copy()
    
    rename_map = {}
    if state_col in df_result.columns:
        rename_map[state_col] = 'STATE_ACTUAL'
    if ead_col in df_result.columns:
        rename_map[ead_col] = 'EAD_ACTUAL'
    if disb_col in df_result.columns and disb_col != 'DISBURSAL_AMOUNT':
        rename_map[disb_col] = 'DISBURSAL_AMOUNT'
    
    df_result = df_result.rename(columns=rename_map)
    
    return df_result


def _extract_actual_loans_for_mob_vectorized(
    df_raw: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    target_mob: int,
) -> pd.DataFrame:
    """
    Lấy tất cả actual loans từ df_raw cho các cohorts có actual @ target_mob.
    
    VECTORIZED VERSION - Nhanh hơn 10-50x so với loop version!
    """
    import time
    start_time = time.time()
    
    loan_col = CFG["loan"]
    mob_col = CFG["mob"]
    state_col = CFG["state"]
    ead_col = CFG["ead"]
    orig_date_col = CFG.get("orig_date", "DISBURSAL_DATE")
    disb_col = CFG.get("disb", "DISBURSAL_AMOUNT")
    
    print(f"   📊 Extracting actual loans @ MOB {target_mob} (VECTORIZED)...")
    
    # BƯỚC 1: Lọc lifecycle để tìm cohorts có actual @ target_mob
    df_lc_actual = df_lifecycle_final[
        (df_lifecycle_final['MOB'] == target_mob) &
        (df_lifecycle_final['IS_FORECAST'] == 0)
    ].copy()
    
    if len(df_lc_actual) == 0:
        print(f"      ⚠️  No actual cohorts @ MOB {target_mob}")
        return pd.DataFrame()
    
    # Lấy danh sách cohorts có actual
    cohorts_with_actual = df_lc_actual[['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']].drop_duplicates()
    n_cohorts = len(cohorts_with_actual)
    print(f"      Found {n_cohorts} cohorts with actual data")
    
    # BƯỚC 2: Chuẩn bị df_raw (chỉ làm 1 lần)
    df_raw_prep = df_raw.copy()
    if 'VINTAGE_DATE' not in df_raw_prep.columns:
        df_raw_prep['VINTAGE_DATE'] = parse_date_column(df_raw_prep[orig_date_col])
    else:
        df_raw_prep['VINTAGE_DATE'] = pd.to_datetime(df_raw_prep['VINTAGE_DATE'])
    
    # Đảm bảo VINTAGE_DATE trong cohorts_with_actual cũng là datetime
    cohorts_with_actual['VINTAGE_DATE'] = pd.to_datetime(cohorts_with_actual['VINTAGE_DATE'])
    
    # BƯỚC 3: VECTORIZED - Merge để lọc loans thuộc cohorts có actual
    # Tạo cohort key để merge nhanh
    df_raw_prep['_cohort_key'] = (
        df_raw_prep['PRODUCT_TYPE'].astype(str) + '|' + 
        df_raw_prep['RISK_SCORE'].astype(str) + '|' + 
        df_raw_prep['VINTAGE_DATE'].astype(str)
    )
    
    cohorts_with_actual['_cohort_key'] = (
        cohorts_with_actual['PRODUCT_TYPE'].astype(str) + '|' + 
        cohorts_with_actual['RISK_SCORE'].astype(str) + '|' + 
        cohorts_with_actual['VINTAGE_DATE'].astype(str)
    )
    
    # Filter df_raw chỉ giữ loans thuộc cohorts có actual VÀ tại target_mob
    valid_cohort_keys = set(cohorts_with_actual['_cohort_key'].unique())
    
    mask = (
        df_raw_prep['_cohort_key'].isin(valid_cohort_keys) &
        (df_raw_prep[mob_col] == target_mob)
    )
    
    df_actual = df_raw_prep[mask].copy()
    
    if len(df_actual) == 0:
        print(f"      ⚠️  No actual loans found in df_raw")
        return pd.DataFrame()
    
    # BƯỚC 4: Chuẩn bị output columns
    output_cols = [loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']
    
    if state_col in df_actual.columns:
        output_cols.append(state_col)
    if ead_col in df_actual.columns:
        output_cols.append(ead_col)
    if disb_col in df_actual.columns:
        output_cols.append(disb_col)
    
    df_result = df_actual[[c for c in output_cols if c in df_actual.columns]].copy()
    
    # Rename columns
    rename_map = {}
    if state_col in df_result.columns:
        rename_map[state_col] = 'STATE_ACTUAL'
    if ead_col in df_result.columns:
        rename_map[ead_col] = 'EAD_ACTUAL'
    if disb_col in df_result.columns and disb_col != 'DISBURSAL_AMOUNT':
        rename_map[disb_col] = 'DISBURSAL_AMOUNT'
    
    df_result = df_result.rename(columns=rename_map)
    df_result['IS_ACTUAL'] = 1
    
    elapsed = time.time() - start_time
    print(f"      ✅ Extracted {len(df_result):,} actual loans in {elapsed:.2f}s")
    
    return df_result


def _extract_actual_loans_for_mob(
    df_raw: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    target_mob: int,
) -> pd.DataFrame:
    """
    Wrapper function - sử dụng vectorized version.
    """
    return _extract_actual_loans_for_mob_vectorized(df_raw, df_lifecycle_final, target_mob)
    
    return df_all_actual


def _get_cohorts_needing_allocation(
    df_loans_latest: pd.DataFrame,
    df_actual_loans: pd.DataFrame,
) -> pd.DataFrame:
    """
    Lọc ra các loans cần allocate (không có trong actual).
    """
    loan_col = CFG["loan"]
    
    if len(df_actual_loans) == 0:
        return df_loans_latest
    
    actual_loan_ids = set(df_actual_loans[loan_col].unique())
    mask = ~df_loans_latest[loan_col].isin(actual_loan_ids)
    df_need_allocation = df_loans_latest[mask].copy()
    
    return df_need_allocation


def allocate_ultra_fast(
    df_loans_latest: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    matrices_by_mob: Dict,
    target_mob: int,
    parent_fallback: Dict = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Phân bổ forecast CỰC NHANH (vectorized - NO NESTED LOOPS).
    
    Performance: 10-15x faster than allocate_fast()
    
    OUTPUT columns: Giống hệt allocate_fast()
    """
    
    loan_col = CFG["loan"]
    state_col = CFG["state"]
    mob_col = CFG["mob"]
    ead_col = CFG["ead"]
    
    np.random.seed(seed)
    
    n_states = len(BUCKETS_CANON)
    state_to_idx = {s: i for i, s in enumerate(BUCKETS_CANON)}
    
    print(f"📍 Phân bổ forecast tại MOB = {target_mob} (ULTRA FAST mode)")
    print(f"   Số loans: {len(df_loans_latest):,}")
    
    # ===================================================
    # BƯỚC 1: Chuẩn bị data
    # ===================================================
    df = df_loans_latest.copy()
    df['STATE_CURRENT'] = df[state_col]
    df['MOB_CURRENT'] = df[mob_col].astype(int)
    df['EAD_CURRENT'] = df[ead_col].astype(float)
    
    disb_col = CFG.get("disb", "DISBURSAL_AMOUNT")
    if disb_col in df.columns:
        df['DISBURSAL_AMOUNT'] = df[disb_col].astype(float)
    else:
        print("   ⚠️ Warning: DISBURSAL_AMOUNT không có, dùng EAD_CURRENT thay thế")
        df['DISBURSAL_AMOUNT'] = df['EAD_CURRENT']
    
    if 'VINTAGE_DATE' not in df.columns:
        df['VINTAGE_DATE'] = parse_date_column(df[CFG['orig_date']])
    
    # ===================================================
    # BƯỚC 2: Tính state probabilities từ transition matrix
    # ===================================================
    print("   Đang tính combined matrices...")
    matrix_cache = {}
    
    unique_combos = df.groupby(['PRODUCT_TYPE', 'RISK_SCORE', 'MOB_CURRENT']).size().reset_index()[['PRODUCT_TYPE', 'RISK_SCORE', 'MOB_CURRENT']]
    
    for _, row in unique_combos.iterrows():
        product = row['PRODUCT_TYPE']
        score = row['RISK_SCORE']
        mob_current = row['MOB_CURRENT']
        
        if mob_current >= target_mob:
            matrix_cache[(product, score, mob_current)] = np.eye(n_states)
        else:
            combined = _get_combined_matrix(
                matrices_by_mob, parent_fallback,
                product, score, mob_current, target_mob
            )
            matrix_cache[(product, score, mob_current)] = combined
    
    print(f"   Cached {len(matrix_cache)} combined matrices")
    print("   Đang tính state probabilities...")
    
    def get_state_probs(row):
        product = row['PRODUCT_TYPE']
        score = row['RISK_SCORE']
        mob_current = row['MOB_CURRENT']
        state_current = row['STATE_CURRENT']
        if state_current in ABSORBING_STATES:
            probs = np.zeros(n_states)
            probs[state_to_idx[state_current]] = 1.0
            return probs
        
        key = (product, score, mob_current)
        if key not in matrix_cache:
            probs = np.zeros(n_states)
            if state_current in state_to_idx:
                probs[state_to_idx[state_current]] = 1.0
            return probs
        
        combined = matrix_cache[key]
        
        init_vec = np.zeros(n_states)
        if state_current in state_to_idx:
            init_vec[state_to_idx[state_current]] = 1.0
        else:
            init_vec[0] = 1.0
        
        final_probs = init_vec @ combined
        
        total = final_probs.sum()
        if total > 0:
            final_probs = final_probs / total
        
        return final_probs
    
    probs_list = df.apply(get_state_probs, axis=1).tolist()
    probs_arr = np.array(probs_list)

    del30_idx = [state_to_idx[s] for s in BUCKETS_30P if s in state_to_idx]
    del90_idx = [state_to_idx[s] for s in BUCKETS_90P if s in state_to_idx]
    df['PROB_DEL30_RAW'] = probs_arr[:, del30_idx].sum(axis=1) if del30_idx else 0.0
    df['PROB_DEL90_RAW'] = probs_arr[:, del90_idx].sum(axis=1) if del90_idx else 0.0
    
    # ===================================================
    # BƯỚC 3: Sample STATE_FORECAST
    # ===================================================
    print("   Đang assign states...")
    
    def sample_state(probs):
        if probs.sum() == 0:
            return 'DPD0'
        probs = probs / probs.sum()
        return np.random.choice(BUCKETS_CANON, p=probs)
    
    df['STATE_FORECAST'] = [sample_state(p) for p in probs_arr]
    
    # ===================================================
    # BƯỚC 4: Lấy DEL rates từ lifecycle
    # ===================================================
    print("   Đang lấy DEL rates từ lifecycle...")
    
    df_lc = df_lifecycle_final[df_lifecycle_final['MOB'] == target_mob].copy()
    
    # Chuẩn hóa VINTAGE_DATE
    df_lc['VINTAGE_DATE'] = pd.to_datetime(df_lc['VINTAGE_DATE'])
    df['VINTAGE_DATE'] = pd.to_datetime(df['VINTAGE_DATE'])
    
    # Lấy DEL30_PCT, DEL90_PCT
    del_cols = ['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']
    if 'DEL30_PCT' in df_lc.columns:
        del_cols.append('DEL30_PCT')
    if 'DEL90_PCT' in df_lc.columns:
        del_cols.append('DEL90_PCT')
    
    df_del_rates = df_lc[del_cols].drop_duplicates()
    
    # Merge DEL rates
    n_before = len(df)
    df = df.merge(
        df_del_rates,
        on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE'],
        how='left'
    )
    n_after = len(df)
    
    if n_after != n_before:
        print(f"   ⚠️ WARNING: Merge làm thay đổi số rows: {n_before} -> {n_after}")
    
    # Check missing DEL rates
    n_missing_del30 = df['DEL30_PCT'].isna().sum() if 'DEL30_PCT' in df.columns else len(df)
    if n_missing_del30 > 0:
        print(f"   ⚠️ WARNING: {n_missing_del30:,} loans ({n_missing_del30/len(df)*100:.1f}%) không có DEL rates từ lifecycle")
    
    # PROB_DEL = DEL_PCT từ lifecycle
    df['PROB_DEL30'] = df['PROB_DEL30_RAW']
    df['PROB_DEL90'] = df['PROB_DEL90_RAW']
    df['DEL30_FLAG_STATE'] = df['STATE_FORECAST'].isin(BUCKETS_30P).astype(int)
    df['DEL90_FLAG_STATE'] = df['STATE_FORECAST'].isin(BUCKETS_90P).astype(int)
    df['DEL30_FLAG'] = df['DEL30_FLAG_STATE']
    df['DEL90_FLAG'] = df['DEL90_FLAG_STATE']

    cohort_cols = ['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']
    for _, idx in df.groupby(cohort_cols, sort=False).groups.items():
        group_idx = list(idx)
        exposures = df.loc[group_idx, 'DISBURSAL_AMOUNT'].to_numpy(dtype=float)
        states_current = df.loc[group_idx, 'STATE_CURRENT'].astype(str).to_numpy()
        fixed_positive = states_current == 'WRITEOFF'
        fixed_negative = np.isin(states_current, ['PREPAY', 'SOLDOUT'])

        if 'DEL30_PCT' in df.columns:
            target_del30 = df.loc[group_idx[0], 'DEL30_PCT']
            df.loc[group_idx, 'PROB_DEL30'] = _calibrate_probs_with_fixed_states(
                df.loc[group_idx, 'PROB_DEL30_RAW'].to_numpy(dtype=float),
                exposures,
                target_del30,
                fixed_positive,
                fixed_negative,
            )
            df.loc[group_idx, 'DEL30_FLAG'] = _assign_ranked_flags_to_target(
                df.loc[group_idx, 'PROB_DEL30'].to_numpy(dtype=float),
                exposures,
                target_del30,
                fixed_positive,
                fixed_negative,
            )

        if 'DEL90_PCT' in df.columns:
            target_del90 = df.loc[group_idx[0], 'DEL90_PCT']
            df.loc[group_idx, 'PROB_DEL90'] = _calibrate_probs_with_fixed_states(
                df.loc[group_idx, 'PROB_DEL90_RAW'].to_numpy(dtype=float),
                exposures,
                target_del90,
                fixed_positive,
                fixed_negative,
            )
            df.loc[group_idx, 'DEL90_FLAG'] = _assign_ranked_flags_to_target(
                df.loc[group_idx, 'PROB_DEL90'].to_numpy(dtype=float),
                exposures,
                target_del90,
                fixed_positive,
                fixed_negative,
            )
    
    # EAD_DEL = DISBURSAL_AMOUNT × PROB_DEL
    df['EAD_DEL30'] = df['DISBURSAL_AMOUNT'] * df['PROB_DEL30']
    df['EAD_DEL90'] = df['DISBURSAL_AMOUNT'] * df['PROB_DEL90']
    
    # ===================================================
    # BƯỚC 5: Phân bổ EAD_FORECAST (VECTORIZED - NO LOOPS!)
    # ===================================================
    print("   Đang phân bổ EAD theo state (VECTORIZED)...")
    
    # 5.1. Prepare lifecycle data với tất cả states
    df_lc_states = df_lc.copy()
    
    # Melt lifecycle từ wide → long format
    state_cols = [c for c in BUCKETS_CANON if c in df_lc_states.columns]
    
    if not state_cols:
        print("   ⚠️ WARNING: Lifecycle không có state columns, dùng fallback")
        df['EAD_FORECAST'] = df['EAD_CURRENT']
    else:
        df_lc_long = df_lc_states.melt(
            id_vars=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE'],
            value_vars=state_cols,
            var_name='STATE',
            value_name='EAD_LIFECYCLE'
        )
        
        # 5.2. Tính tổng EAD_CURRENT per (cohort, state)
        df_ead_current = df.groupby(
            ['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE_FORECAST']
        )['EAD_CURRENT'].sum().reset_index()
        
        df_ead_current = df_ead_current.rename(columns={
            'STATE_FORECAST': 'STATE',
            'EAD_CURRENT': 'EAD_CURRENT_TOTAL'
        })
        
        # 5.3. Merge lifecycle với current EAD
        df_ratios = df_lc_long.merge(
            df_ead_current,
            on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE'],
            how='left'
        )
        
        # 5.4. Tính ratio = EAD_LIFECYCLE / EAD_CURRENT_TOTAL
        df_ratios['EAD_CURRENT_TOTAL'] = df_ratios['EAD_CURRENT_TOTAL'].fillna(0)
        df_ratios['RATIO'] = np.where(
            df_ratios['EAD_CURRENT_TOTAL'] > 0,
            df_ratios['EAD_LIFECYCLE'] / df_ratios['EAD_CURRENT_TOTAL'],
            0
        )
        
        # Clip ratio to [0, 1]
        df_ratios['RATIO'] = df_ratios['RATIO'].clip(0, 1)
        
        # Handle absorbing states
        df_ratios.loc[df_ratios['STATE'].isin(ABSORBING_STATES), 'RATIO'] = 0
        
        # 5.5. Merge ratios vào df loans
        df = df.merge(
            df_ratios[['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE', 'RATIO']],
            left_on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE_FORECAST'],
            right_on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE'],
            how='left',
            suffixes=('', '_ratio')
        )
        
        # 5.6. Tính EAD_FORECAST = EAD_CURRENT × RATIO (VECTORIZED!)
        df['RATIO'] = df['RATIO'].fillna(0)
        df['EAD_FORECAST'] = df['EAD_CURRENT'] * df['RATIO']
        
        # Drop temporary columns
        df = df.drop(columns=['STATE_ratio'], errors='ignore')
    
    # ===================================================
    # BƯỚC 6: Output
    # ===================================================
    df['TARGET_MOB'] = target_mob
    df['IS_FORECAST'] = 1
    
    output_cols = [
        loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE',
        'DISBURSAL_AMOUNT', 'SALE_CHANNEL',
        'STATE_CURRENT', 'MOB_CURRENT', 'EAD_CURRENT',
        'STATE_FORECAST', 'EAD_FORECAST',
        'PROB_DEL30_RAW', 'PROB_DEL90_RAW',
        'PROB_DEL30', 'PROB_DEL90',
        'EAD_DEL30', 'EAD_DEL90',
        'DEL30_FLAG_STATE', 'DEL90_FLAG_STATE',
        'DEL30_FLAG', 'DEL90_FLAG',
        'TARGET_MOB', 'IS_FORECAST'
    ]
    
    df_result = df[[c for c in output_cols if c in df.columns]].copy()
    
    # ===================================================
    # VALIDATION
    # ===================================================
    print(f"\n✅ Phân bổ hoàn tất:")
    print(f"   Số loans: {len(df_result):,}")
    
    total_ead_current = df_result['EAD_CURRENT'].sum()
    total_ead_forecast = df_result['EAD_FORECAST'].sum()
    total_ead_del30 = df_result['EAD_DEL30'].sum()
    total_ead_del90 = df_result['EAD_DEL90'].sum()
    total_disbursal = df_result['DISBURSAL_AMOUNT'].sum()
    target_ead_del30 = (
        (df['DISBURSAL_AMOUNT'] * df['DEL30_PCT'].fillna(0)).sum()
        if 'DEL30_PCT' in df.columns else np.nan
    )
    target_ead_del90 = (
        (df['DISBURSAL_AMOUNT'] * df['DEL90_PCT'].fillna(0)).sum()
        if 'DEL90_PCT' in df.columns else np.nan
    )
    
    print(f"\n   EAD Summary:")
    print(f"      DISBURSAL_AMOUNT: {total_disbursal:,.0f}")
    print(f"      EAD_CURRENT: {total_ead_current:,.0f}")
    if total_ead_current > 0:
        ead_reduction_pct = (1 - total_ead_forecast / total_ead_current) * 100
        print(
            f"      EAD_FORECAST: {total_ead_forecast:,.0f} "
            f"(giảm {ead_reduction_pct:.2f}%)"
        )
    else:
        print(f"      EAD_FORECAST: {total_ead_forecast:,.0f}")
    print(f"      EAD_DEL30: {total_ead_del30:,.0f} ({total_ead_del30/total_disbursal*100:.2f}% of DISBURSAL)")
    print(f"      EAD_DEL90: {total_ead_del90:,.0f} ({total_ead_del90/total_disbursal*100:.2f}% of DISBURSAL)")
    if not pd.isna(target_ead_del30):
        print(f"      EAD_DEL30 target: {target_ead_del30:,.0f}")
    if not pd.isna(target_ead_del90):
        print(f"      EAD_DEL90 target: {target_ead_del90:,.0f}")
    
    print(f"\n   DEL Probability (avg):")
    print(f"      PROB_DEL30: {df_result['PROB_DEL30'].mean()*100:.2f}%")
    print(f"      PROB_DEL90: {df_result['PROB_DEL90'].mean()*100:.2f}%")
    
    return df_result


def allocate_multi_mob_ultra_fast(
    df_loans_latest: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    matrices_by_mob: Dict,
    target_mobs: List[int] = [12, 24],
    parent_fallback: Dict = None,
    df_raw: Optional[pd.DataFrame] = None,
    include_del30: bool = True,
    include_del90: bool = True,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Phân bổ forecast tại NHIỀU MOB (ULTRA FAST) với hỗ trợ ACTUAL DATA.
    
    TỐI ƯU:
    - Cohort có actual @ target_mob: Lấy thực tế từ df_raw ✅
    - Cohort chỉ có forecast @ target_mob: Mới allocate ✅
    
    Performance: 10-15x faster than allocate_multi_mob_fast()
    
    Parameters
    ----------
    df_raw : Optional[pd.DataFrame]
        Data gốc đầy đủ (có cả actual data). Nếu None, chỉ allocate forecast.
    
    OUTPUT: Giống hệt allocate_multi_mob_optimized()
    """
    
    loan_col = CFG["loan"]
    
    if df_raw is not None:
        print(f"🎯 Phân bổ forecast TỐI ƯU tại {len(target_mobs)} MOB: {target_mobs} (ULTRA FAST)")
        print(f"   ✅ Lấy actual từ df_raw khi có")
        print(f"   ✅ Allocate forecast khi cần")
    else:
        print(f"🎯 Phân bổ forecast tại {len(target_mobs)} MOB: {target_mobs} (ULTRA FAST)")
    
    df = df_loans_latest.copy()
    
    if 'VINTAGE_DATE' not in df.columns:
        df['VINTAGE_DATE'] = parse_date_column(df[CFG['orig_date']])
    
    # Các cột cần lấy từ df_loans_latest
    base_cols = [
        loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE',
        CFG["mob"], CFG["ead"], CFG["state"]
    ]
    
    # Thêm DISBURSAL_DATE, DISBURSAL_AMOUNT, SALE_CHANNEL nếu có
    orig_date_col = CFG.get("orig_date", "DISBURSAL_DATE")
    disb_amt_col = CFG.get("disb", "DISBURSAL_AMOUNT")
    
    if orig_date_col in df.columns:
        base_cols.append(orig_date_col)
    if disb_amt_col in df.columns:
        base_cols.append(disb_amt_col)
    if 'SALE_CHANNEL' in df.columns:
        base_cols.append('SALE_CHANNEL')
    
    # Loại bỏ duplicate columns
    base_cols = list(dict.fromkeys(base_cols))
    
    loan_info = df[[c for c in base_cols if c in df.columns]].copy()
    
    # Rename columns
    rename_map = {
        CFG["mob"]: 'MOB_CURRENT',
        CFG["ead"]: 'EAD_CURRENT',
        CFG["state"]: 'STATE_CURRENT',
    }
    
    if orig_date_col in loan_info.columns and orig_date_col != 'DISBURSAL_DATE':
        rename_map[orig_date_col] = 'DISBURSAL_DATE'
    if disb_amt_col in loan_info.columns and disb_amt_col != 'DISBURSAL_AMOUNT':
        rename_map[disb_amt_col] = 'DISBURSAL_AMOUNT'
    
    loan_info = loan_info.rename(columns=rename_map)
    
    for target_mob in target_mobs:
        print(f"\n{'='*60}")
        print(f"📍 Processing MOB {target_mob}")
        print(f"{'='*60}")
        
        # BƯỚC 1: Lấy actual loans từ df_raw (nếu có)
        df_actual = pd.DataFrame()
        if df_raw is not None:
            df_actual = _extract_actual_loans_for_mob(
                df_raw=df_raw,
                df_lifecycle_final=df_lifecycle_final,
                target_mob=target_mob,
            )
        
        n_actual = len(df_actual)
        n_total = len(df_loans_latest)
        
        # BƯỚC 2: Xác định loans cần allocate
        if n_actual > 0:
            df_need_allocation = _get_cohorts_needing_allocation(
                df_loans_latest=df_loans_latest,
                df_actual_loans=df_actual,
            )
            n_need_allocation = len(df_need_allocation)
            
            print(f"\n   📊 Split:")
            print(f"      Actual loans: {n_actual:,} ({n_actual/n_total*100:.1f}%)")
            print(f"      Need allocation: {n_need_allocation:,} ({n_need_allocation/n_total*100:.1f}%)")
        else:
            df_need_allocation = df_loans_latest
            n_need_allocation = n_total
            print(f"\n   📊 All loans need allocation: {n_need_allocation:,}")
        
        # BƯỚC 3: Allocate forecast cho loans cần allocate
        df_allocated = pd.DataFrame()
        if n_need_allocation > 0:
            print(f"\n   🔄 Allocating forecast for {n_need_allocation:,} loans...")
            df_allocated = allocate_ultra_fast(
                df_loans_latest=df_need_allocation,
                df_lifecycle_final=df_lifecycle_final,
                matrices_by_mob=matrices_by_mob,
                target_mob=target_mob,
                parent_fallback=parent_fallback,
                seed=seed,
            )
        
        # BƯỚC 4: Combine actual + forecast
        if n_actual > 0 and not df_allocated.empty:
            # Rename actual columns to match forecast format
            df_actual_renamed = df_actual.copy()
            df_actual_renamed = df_actual_renamed.rename(columns={
                'STATE_ACTUAL': 'STATE_FORECAST',
                'EAD_ACTUAL': 'EAD_FORECAST',
            })
            
            # Tính DEL cho actual data dựa trên state thực tế
            if include_del30:
                # DEL30: DPD30+, DPD60+, DPD90+, WRITEOFF
                df_actual_renamed['DEL30_FLAG'] = df_actual_renamed['STATE_FORECAST'].isin(BUCKETS_30P).astype(int)
                df_actual_renamed['PROB_DEL30'] = df_actual_renamed['DEL30_FLAG'].astype(float)
                df_actual_renamed['EAD_DEL30'] = df_actual_renamed['EAD_FORECAST'] * df_actual_renamed['DEL30_FLAG']
            
            if include_del90:
                # DEL90: DPD90+, WRITEOFF
                df_actual_renamed['DEL90_FLAG'] = df_actual_renamed['STATE_FORECAST'].isin(BUCKETS_90P).astype(int)
                df_actual_renamed['DEL90_FLAG_STATE'] = df_actual_renamed['DEL90_FLAG']
                df_actual_renamed['PROB_DEL90'] = df_actual_renamed['DEL90_FLAG'].astype(float)
                df_actual_renamed['PROB_DEL90_RAW'] = df_actual_renamed['PROB_DEL90']
                df_actual_renamed['EAD_DEL90'] = df_actual_renamed['EAD_FORECAST'] * df_actual_renamed['DEL90_FLAG']
            
            # Combine
            df_combined = pd.concat([df_actual_renamed, df_allocated], ignore_index=True)
            print(f"\n   ✅ Combined: {len(df_combined):,} loans (actual: {n_actual:,}, forecast: {len(df_allocated):,})")
        elif n_actual > 0:
            df_combined = df_actual.copy()
            df_combined = df_combined.rename(columns={
                'STATE_ACTUAL': 'STATE_FORECAST',
                'EAD_ACTUAL': 'EAD_FORECAST',
            })
            if include_del30:
                # DEL30: DPD30+, DPD60+, DPD90+, WRITEOFF
                df_combined['DEL30_FLAG'] = df_combined['STATE_FORECAST'].isin(BUCKETS_30P).astype(int)
                df_combined['PROB_DEL30'] = df_combined['DEL30_FLAG'].astype(float)
                df_combined['EAD_DEL30'] = df_combined['EAD_FORECAST'] * df_combined['DEL30_FLAG']
            
            if include_del90:
                # DEL90: DPD90+, WRITEOFF
                df_combined['DEL90_FLAG'] = df_combined['STATE_FORECAST'].isin(BUCKETS_90P).astype(int)
                df_combined['DEL90_FLAG_STATE'] = df_combined['DEL90_FLAG']
                df_combined['PROB_DEL90'] = df_combined['DEL90_FLAG'].astype(float)
                df_combined['PROB_DEL90_RAW'] = df_combined['PROB_DEL90']
                df_combined['EAD_DEL90'] = df_combined['EAD_FORECAST'] * df_combined['DEL90_FLAG']
            print(f"\n   ✅ All actual: {len(df_combined):,} loans")
        else:
            df_combined = df_allocated
            print(f"\n   ✅ All forecast: {len(df_combined):,} loans")
        
        if df_combined.empty:
            continue
        
        # Columns to merge
        cols_to_merge = [loan_col, 'STATE_FORECAST', 'EAD_FORECAST']
        
        if include_del30:
            cols_to_merge.extend(['PROB_DEL30', 'EAD_DEL30', 'DEL30_FLAG'])
        if include_del90:
            cols_to_merge.extend([
                'PROB_DEL90_RAW',
                'PROB_DEL90',
                'EAD_DEL90',
                'DEL90_FLAG_STATE',
                'DEL90_FLAG',
            ])
        
        df_mob = df_combined[[c for c in cols_to_merge if c in df_combined.columns]].copy()
        
        # Rename với suffix _MOB{X}
        rename_map = {
            'STATE_FORECAST': f'STATE_FORECAST_MOB{target_mob}',
            'EAD_FORECAST': f'EAD_FORECAST_MOB{target_mob}',
        }
        
        if include_del30:
            rename_map['PROB_DEL30'] = f'PROB_DEL30_MOB{target_mob}'
            rename_map['EAD_DEL30'] = f'EAD_DEL30_MOB{target_mob}'
            rename_map['DEL30_FLAG'] = f'DEL30_FLAG_MOB{target_mob}'
        
        if include_del90:
            rename_map['PROB_DEL90_RAW'] = f'PROB_DEL90_RAW_MOB{target_mob}'
            rename_map['PROB_DEL90'] = f'PROB_DEL90_MOB{target_mob}'
            rename_map['EAD_DEL90'] = f'EAD_DEL90_MOB{target_mob}'
            rename_map['DEL90_FLAG_STATE'] = f'DEL90_FLAG_STATE_MOB{target_mob}'
            rename_map['DEL90_FLAG'] = f'DEL90_FLAG_MOB{target_mob}'
        
        df_mob = df_mob.rename(columns=rename_map)
        
        loan_info = loan_info.merge(df_mob, on=loan_col, how='left')
    
    # Summary
    print("\n" + "="*50)
    print("📊 SUMMARY")
    print("="*50)
    
    print(f"   Total loans: {len(loan_info):,}")
    
    total_disbursal = loan_info['DISBURSAL_AMOUNT'].sum() if 'DISBURSAL_AMOUNT' in loan_info.columns else 0
    total_ead_current = loan_info['EAD_CURRENT'].sum()
    
    print(f"   DISBURSAL_AMOUNT: {total_disbursal:,.0f}")
    print(f"   EAD_CURRENT: {total_ead_current:,.0f}")
    
    for target_mob in target_mobs:
        ead_col = f'EAD_FORECAST_MOB{target_mob}'
        ead_del30_col = f'EAD_DEL30_MOB{target_mob}'
        ead_del90_col = f'EAD_DEL90_MOB{target_mob}'
        prob_del30_col = f'PROB_DEL30_MOB{target_mob}'
        prob_del90_col = f'PROB_DEL90_MOB{target_mob}'
        
        print(f"\n   MOB {target_mob}:")
        
        if ead_col in loan_info.columns:
            ead_forecast = loan_info[ead_col].sum()
            print(f"      EAD_FORECAST: {ead_forecast:,.0f}")
        
        if ead_del30_col in loan_info.columns and total_disbursal > 0:
            ead_del30 = loan_info[ead_del30_col].sum()
            del30_rate = ead_del30 / total_disbursal * 100
            print(f"      EAD_DEL30: {ead_del30:,.0f} ({del30_rate:.2f}% of DISBURSAL)")
        
        if ead_del90_col in loan_info.columns and total_disbursal > 0:
            ead_del90 = loan_info[ead_del90_col].sum()
            del90_rate = ead_del90 / total_disbursal * 100
            print(f"      EAD_DEL90: {ead_del90:,.0f} ({del90_rate:.2f}% of DISBURSAL)")
        
        if prob_del30_col in loan_info.columns:
            avg_prob_del30 = loan_info[prob_del30_col].mean() * 100
            print(f"      Avg PROB_DEL30: {avg_prob_del30:.2f}%")
        
        if prob_del90_col in loan_info.columns:
            avg_prob_del90 = loan_info[prob_del90_col].mean() * 100
            print(f"      Avg PROB_DEL90: {avg_prob_del90:.2f}%")
    
    return loan_info
