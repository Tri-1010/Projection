# ============================================================
#  allocation_v2_optimized.py – Phân bổ forecast TỐI ƯU
#  
#  TỐI ƯU:
#  - Cohort có actual @ target_mob: Lấy thực tế từ df_raw
#  - Cohort chỉ có forecast @ target_mob: Mới allocate
#  
#  => Giảm thời gian chạy, tăng độ chính xác
# ============================================================

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from src.config import CFG, BUCKETS_CANON, BUCKETS_30P, BUCKETS_60P, BUCKETS_90P, parse_date_column

# Import hàm allocate_multi_mob_fast từ allocation_v2_fast
#from src.rollrate.allocation_v2_fast import allocate_multi_mob_fast
# Thay vì:
#from src.rollrate.allocation_v2_fast import allocate_multi_mob_fast

# Dùng:
from src.rollrate.allocation_v2_ultra_fast import allocate_multi_mob_ultra_fast


def _get_actual_loans_at_mob(
    df_raw: pd.DataFrame,
    product: str,
    score: str,
    vintage_date: pd.Timestamp,
    target_mob: int,
) -> Optional[pd.DataFrame]:
    """
    Lấy actual loan-level data từ df_raw tại MOB cụ thể.
    
    Parameters
    ----------
    df_raw : pd.DataFrame
        Data gốc đầy đủ
    product : str
        Product type
    score : str
        Risk score
    vintage_date : pd.Timestamp
        Vintage date
    target_mob : int
        MOB cần lấy
    
    Returns
    -------
    pd.DataFrame hoặc None
        Loan-level data tại target_mob, hoặc None nếu không có
    """
    
    loan_col = CFG["loan"]
    mob_col = CFG["mob"]
    state_col = CFG["state"]
    ead_col = CFG["ead"]
    orig_date_col = CFG.get("orig_date", "DISBURSAL_DATE")
    disb_col = CFG.get("disb", "DISBURSAL_AMOUNT")
    
    # Chuẩn bị VINTAGE_DATE trong df_raw nếu chưa có
    df_raw_copy = df_raw.copy()
    if 'VINTAGE_DATE' not in df_raw_copy.columns:
        df_raw_copy['VINTAGE_DATE'] = parse_date_column(df_raw_copy[orig_date_col])
    else:
        df_raw_copy['VINTAGE_DATE'] = pd.to_datetime(df_raw_copy['VINTAGE_DATE'])
    
    # Filter cohort
    mask = (
        (df_raw_copy['PRODUCT_TYPE'] == product) &
        (df_raw_copy['RISK_SCORE'] == score) &
        (df_raw_copy['VINTAGE_DATE'] == vintage_date)
    )
    df_cohort = df_raw_copy[mask]
    
    if len(df_cohort) == 0:
        return None
    
    # Filter tại target_mob
    df_at_mob = df_cohort[df_cohort[mob_col] == target_mob]
    
    if len(df_at_mob) == 0:
        return None
    
    # Chuẩn bị output columns
    output_cols = [loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']
    
    # State và EAD
    if state_col in df_at_mob.columns:
        output_cols.append(state_col)
    if ead_col in df_at_mob.columns:
        output_cols.append(ead_col)
    if disb_col in df_at_mob.columns:
        output_cols.append(disb_col)
    
    df_result = df_at_mob[[c for c in output_cols if c in df_at_mob.columns]].copy()
    
    # Rename columns
    rename_map = {}
    if state_col in df_result.columns:
        rename_map[state_col] = 'STATE_ACTUAL'
    if ead_col in df_result.columns:
        rename_map[ead_col] = 'EAD_ACTUAL'
    if disb_col in df_result.columns and disb_col != 'DISBURSAL_AMOUNT':
        rename_map[disb_col] = 'DISBURSAL_AMOUNT'
    
    df_result = df_result.rename(columns=rename_map)
    
    return df_result


def _extract_actual_loans_for_mob(
    df_raw: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    target_mob: int,
) -> pd.DataFrame:
    """
    Lấy tất cả actual loans từ df_raw cho các cohorts có actual @ target_mob.
    
    Parameters
    ----------
    df_raw : pd.DataFrame
        Data gốc đầy đủ
    df_lifecycle_final : pd.DataFrame
        Lifecycle forecast (để biết cohort nào có actual)
    target_mob : int
        MOB cần lấy
    
    Returns
    -------
    pd.DataFrame
        Loan-level actual data với columns:
        - AGREEMENT_ID
        - PRODUCT_TYPE, RISK_SCORE, VINTAGE_DATE
        - STATE_ACTUAL, EAD_ACTUAL
        - DISBURSAL_AMOUNT
        - IS_ACTUAL (=1)
    """
    
    loan_col = CFG["loan"]
    
    print(f"   📊 Extracting actual loans @ MOB {target_mob} from df_raw...")
    
    # Lọc lifecycle tại target_mob với IS_FORECAST = 0 (actual)
    df_lc_actual = df_lifecycle_final[
        (df_lifecycle_final['MOB'] == target_mob) &
        (df_lifecycle_final['IS_FORECAST'] == 0)
    ].copy()
    
    if len(df_lc_actual) == 0:
        print(f"      ⚠️  No actual cohorts @ MOB {target_mob}")
        return pd.DataFrame()
    
    # Lấy danh sách cohorts có actual
    cohorts_with_actual = df_lc_actual[['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']].drop_duplicates()
    
    print(f"      Found {len(cohorts_with_actual)} cohorts with actual data")
    
    # Lấy actual loans cho từng cohort
    actual_loans_list = []
    
    for _, row in cohorts_with_actual.iterrows():
        product = row['PRODUCT_TYPE']
        score = row['RISK_SCORE']
        vintage_date = pd.to_datetime(row['VINTAGE_DATE'])
        
        df_actual = _get_actual_loans_at_mob(
            df_raw=df_raw,
            product=product,
            score=score,
            vintage_date=vintage_date,
            target_mob=target_mob,
        )
        
        if df_actual is not None and len(df_actual) > 0:
            actual_loans_list.append(df_actual)
    
    if not actual_loans_list:
        print(f"      ⚠️  No actual loans found in df_raw")
        return pd.DataFrame()
    
    # Combine tất cả actual loans
    df_all_actual = pd.concat(actual_loans_list, ignore_index=True)
    df_all_actual['IS_ACTUAL'] = 1
    
    print(f"      ✅ Extracted {len(df_all_actual):,} actual loans")
    
    return df_all_actual


def _get_cohorts_needing_allocation(
    df_loans_latest: pd.DataFrame,
    df_actual_loans: pd.DataFrame,
) -> pd.DataFrame:
    """
    Lọc ra các loans cần allocate (không có trong actual).
    
    Parameters
    ----------
    df_loans_latest : pd.DataFrame
        Tất cả loans hiện tại
    df_actual_loans : pd.DataFrame
        Loans đã có actual
    
    Returns
    -------
    pd.DataFrame
        Loans cần allocate
    """
    
    loan_col = CFG["loan"]
    
    if len(df_actual_loans) == 0:
        # Không có actual → allocate tất cả
        return df_loans_latest
    
    # Lấy danh sách loan IDs đã có actual
    actual_loan_ids = set(df_actual_loans[loan_col].unique())
    
    # Filter loans cần allocate
    mask = ~df_loans_latest[loan_col].isin(actual_loan_ids)
    df_need_allocation = df_loans_latest[mask].copy()
    
    return df_need_allocation


def allocate_multi_mob_optimized(
    df_raw: pd.DataFrame,
    df_loans_latest: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    matrices_by_mob: Dict,
    target_mobs: List[int] = [12, 24],
    parent_fallback: Dict = None,
    include_del30: bool = True,
    include_del90: bool = True,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Phân bổ forecast TỐI ƯU tại NHIỀU MOB.
    
    TỐI ƯU:
    - Cohort có actual @ target_mob: Lấy thực tế từ df_raw
    - Cohort chỉ có forecast @ target_mob: Mới allocate
    
    Parameters
    ----------
    df_raw : pd.DataFrame
        Data gốc đầy đủ (có cả actual data)
    df_loans_latest : pd.DataFrame
        Snapshot loans mới nhất
    df_lifecycle_final : pd.DataFrame
        Lifecycle forecast (có cột IS_FORECAST)
    matrices_by_mob : Dict
        Transition matrices
    target_mobs : List[int]
        Các MOB cần forecast
    parent_fallback : Dict
        Fallback matrices
    include_del30 : bool
        Có tính DEL30 không
    include_del90 : bool
        Có tính DEL90 không
    seed : int
        Random seed
    
    Returns
    -------
    pd.DataFrame
        Loan-level forecast với actual + forecast
    """
    
    loan_col = CFG["loan"]
    
    print(f"🎯 Phân bổ forecast TỐI ƯU tại {len(target_mobs)} MOB: {target_mobs}")
    print(f"   ✅ Lấy actual từ df_raw khi có")
    print(f"   ✅ Allocate forecast khi cần")
    
    # Chuẩn bị VINTAGE_DATE trong df_loans_latest
    df_loans = df_loans_latest.copy()
    if 'VINTAGE_DATE' not in df_loans.columns:
        orig_date_col = CFG.get("orig_date", "DISBURSAL_DATE")
        df_loans['VINTAGE_DATE'] = parse_date_column(df_loans[orig_date_col])
    else:
        df_loans['VINTAGE_DATE'] = pd.to_datetime(df_loans['VINTAGE_DATE'])
    
    # Base info của loans
    base_cols = [loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']
    
    mob_col = CFG["mob"]
    ead_col = CFG["ead"]
    state_col = CFG["state"]
    disb_col = CFG.get("disb", "DISBURSAL_AMOUNT")
    
    if mob_col in df_loans.columns:
        base_cols.append(mob_col)
    if ead_col in df_loans.columns:
        base_cols.append(ead_col)
    if state_col in df_loans.columns:
        base_cols.append(state_col)
    if disb_col in df_loans.columns:
        base_cols.append(disb_col)
    
    base_cols = list(dict.fromkeys(base_cols))
    loan_info = df_loans[[c for c in base_cols if c in df_loans.columns]].copy()
    
    # Rename
    rename_map = {}
    if mob_col in loan_info.columns:
        rename_map[mob_col] = 'MOB_CURRENT'
    if ead_col in loan_info.columns:
        rename_map[ead_col] = 'EAD_CURRENT'
    if state_col in loan_info.columns:
        rename_map[state_col] = 'STATE_CURRENT'
    if disb_col in loan_info.columns and disb_col != 'DISBURSAL_AMOUNT':
        rename_map[disb_col] = 'DISBURSAL_AMOUNT'
    
    loan_info = loan_info.rename(columns=rename_map)
    
    # Process từng MOB
    for target_mob in target_mobs:
        print(f"\n{'='*60}")
        print(f"📍 Processing MOB {target_mob}")
        print(f"{'='*60}")
        
        # BƯỚC 1: Lấy actual loans từ df_raw
        df_actual = _extract_actual_loans_for_mob(
            df_raw=df_raw,
            df_lifecycle_final=df_lifecycle_final,
            target_mob=target_mob,
        )
        
        n_actual = len(df_actual)
        n_total = len(df_loans)
        
        # BƯỚC 2: Xác định loans cần allocate
        if n_actual > 0:
            df_need_allocation = _get_cohorts_needing_allocation(
                df_loans_latest=df_loans,
                df_actual_loans=df_actual,
            )
            n_need_allocation = len(df_need_allocation)
            
            print(f"\n   📊 Split:")
            print(f"      Actual loans: {n_actual:,} ({n_actual/n_total*100:.1f}%)")
            print(f"      Need allocation: {n_need_allocation:,} ({n_need_allocation/n_total*100:.1f}%)")
        else:
            df_need_allocation = df_loans
            n_need_allocation = len(df_need_allocation)
            
            print(f"\n   📊 All loans need allocation: {n_need_allocation:,}")
        
        # BƯỚC 3: Allocate cho loans cần forecast
        if n_need_allocation > 0:
            print(f"\n   🔨 Allocating forecast for {n_need_allocation:,} loans...")
            
            from src.rollrate.allocation_v2_fast import allocate_fast
            
            df_allocated = allocate_fast(
                df_loans_latest=df_need_allocation,
                df_lifecycle_final=df_lifecycle_final,
                matrices_by_mob=matrices_by_mob,
                target_mob=target_mob,
                parent_fallback=parent_fallback,
                seed=seed,
            )
            
            # Rename columns
            df_allocated = df_allocated.rename(columns={
                'STATE_FORECAST': 'STATE_RESULT',
                'EAD_FORECAST': 'EAD_RESULT',
            })
            df_allocated['IS_ACTUAL'] = 0
        else:
            df_allocated = pd.DataFrame()
        
        # BƯỚC 4: Combine actual + allocated
        if n_actual > 0:
            # Rename actual columns
            df_actual = df_actual.rename(columns={
                'STATE_ACTUAL': 'STATE_RESULT',
                'EAD_ACTUAL': 'EAD_RESULT',
            })
            
            # Ensure same columns
            common_cols = [loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 
                          'STATE_RESULT', 'EAD_RESULT', 'IS_ACTUAL']
            
            if 'DISBURSAL_AMOUNT' in df_actual.columns:
                common_cols.append('DISBURSAL_AMOUNT')
            
            # Add missing columns
            for col in common_cols:
                if col not in df_actual.columns:
                    df_actual[col] = None
                if n_need_allocation > 0 and col not in df_allocated.columns:
                    df_allocated[col] = None
            
            # Combine
            if n_need_allocation > 0:
                df_combined = pd.concat([
                    df_actual[common_cols],
                    df_allocated[common_cols]
                ], ignore_index=True)
            else:
                df_combined = df_actual[common_cols]
        else:
            df_combined = df_allocated
            common_cols = [c for c in df_combined.columns if c in [
                loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE',
                'STATE_RESULT', 'EAD_RESULT', 'IS_ACTUAL', 'DISBURSAL_AMOUNT'
            ]]
            df_combined = df_combined[common_cols]
        
        # BƯỚC 5: Tính DEL flags
        if 'STATE_RESULT' in df_combined.columns:
            if include_del30:
                df_combined['DEL30_FLAG'] = df_combined['STATE_RESULT'].isin(BUCKETS_30P).astype(int)
            if include_del90:
                df_combined['DEL90_FLAG'] = df_combined['STATE_RESULT'].isin(BUCKETS_90P).astype(int)
        
        # BƯỚC 6: Merge vào loan_info
        cols_to_merge = [loan_col, 'STATE_RESULT', 'EAD_RESULT', 'IS_ACTUAL']
        
        if include_del30 and 'DEL30_FLAG' in df_combined.columns:
            cols_to_merge.append('DEL30_FLAG')
        if include_del90 and 'DEL90_FLAG' in df_combined.columns:
            cols_to_merge.append('DEL90_FLAG')
        
        df_mob = df_combined[[c for c in cols_to_merge if c in df_combined.columns]].copy()
        
        # Rename với suffix
        rename_map = {
            'STATE_RESULT': f'STATE_FORECAST_MOB{target_mob}',
            'EAD_RESULT': f'EAD_FORECAST_MOB{target_mob}',
            'IS_ACTUAL': f'IS_ACTUAL_MOB{target_mob}',
        }
        
        if include_del30 and 'DEL30_FLAG' in df_mob.columns:
            rename_map['DEL30_FLAG'] = f'DEL30_FLAG_MOB{target_mob}'
        if include_del90 and 'DEL90_FLAG' in df_mob.columns:
            rename_map['DEL90_FLAG'] = f'DEL90_FLAG_MOB{target_mob}'
        
        df_mob = df_mob.rename(columns=rename_map)
        
        loan_info = loan_info.merge(df_mob, on=loan_col, how='left')
        
        # Summary
        print(f"\n   ✅ MOB {target_mob} complete:")
        print(f"      Total: {len(df_combined):,} loans")
        print(f"      Actual: {n_actual:,} ({n_actual/len(df_combined)*100:.1f}%)")
        print(f"      Allocated: {n_need_allocation:,} ({n_need_allocation/len(df_combined)*100:.1f}%)")
    
    # Final summary
    print("\n" + "="*60)
    print("📊 FINAL SUMMARY")
    print("="*60)
    print(f"   Total loans: {len(loan_info):,}")
    
    for target_mob in target_mobs:
        is_actual_col = f'IS_ACTUAL_MOB{target_mob}'
        del90_col = f'DEL90_FLAG_MOB{target_mob}'
        
        if is_actual_col in loan_info.columns:
            n_actual = loan_info[is_actual_col].sum()
            n_forecast = (loan_info[is_actual_col] == 0).sum()
            
            print(f"\n   MOB {target_mob}:")
            print(f"      Actual: {n_actual:,}")
            print(f"      Forecast: {n_forecast:,}")
            
            if del90_col in loan_info.columns:
                del90_rate = loan_info[del90_col].mean() * 100
                print(f"      DEL90 rate: {del90_rate:.2f}%")
    
    return loan_info
