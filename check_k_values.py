"""
Script đơn giản để kiểm tra K values và hiểu tại sao K là vấn đề.
"""

import sys
from pathlib import Path
project_root = Path(".").resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np

from src.config import CFG, BUCKETS_CANON, BUCKETS_30P
from src.config import parse_date_column, create_segment_columns
from src.data_loader import load_data
from src.rollrate.transition import compute_transition_by_mob
from src.rollrate.lifecycle import get_actual_all_vintages_amount
from src.rollrate.calibration_kmob import fit_k_raw, smooth_k, fit_alpha


def main():
    print("=" * 100)
    print("🔍 KIỂM TRA K VALUES")
    print("=" * 100)
    
    # Load data
    print("\n📊 Loading data...")
    DATA_PATH = 'C:/Users/User/Projection_PB/Projection_pb/ETB_Parquet_YYYYMM'
    df_raw = load_data(DATA_PATH)
    df_raw['DISBURSAL_DATE'] = parse_date_column(df_raw['DISBURSAL_DATE'])
    df_raw = create_segment_columns(df_raw)
    print(f"   ✅ Loaded {len(df_raw):,} rows")
    
    # Build matrices
    print("\n🔨 Building transition matrices...")
    matrices_by_mob, parent_fallback = compute_transition_by_mob(df_raw)
    print(f"   ✅ Built {sum(len(m) for m in matrices_by_mob.values())} matrices")
    
    # Get actual results
    print("\n📊 Getting actual results...")
    actual_results = get_actual_all_vintages_amount(df_raw)
    print(f"   ✅ Got {len(actual_results)} cohorts")
    
    # DISB_TOTAL map
    loan_disb = df_raw.groupby(["PRODUCT_TYPE", "RISK_SCORE", CFG["orig_date"], CFG["loan"]])[CFG["disb"]].first()
    disb_total_by_vintage = loan_disb.groupby(level=[0, 1, 2]).sum().to_dict()
    
    # Fit k_raw
    print("\n🔨 Calibrating k values...")
    k_raw_by_mob, weight_by_mob, df_k = fit_k_raw(
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
    
    # Smooth k
    mob_min = min(k_raw_by_mob.keys()) if k_raw_by_mob else 0
    mob_max = max(k_raw_by_mob.keys()) if k_raw_by_mob else 0
    k_smooth_by_mob, _, _ = smooth_k(k_raw_by_mob, weight_by_mob, mob_min, mob_max)
    
    # Fit alpha
    alpha, k_final_by_mob, _ = fit_alpha(
        actual_results=actual_results,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        states=BUCKETS_CANON,
        s30_states=BUCKETS_30P,
        k_smooth_by_mob=k_smooth_by_mob,
        mob_target=min(36, mob_max) if mob_max else 36,
        include_co=True,
    )
    print(f"   ✅ Alpha: {alpha:.4f}")
    
    # Analyze K values
    print("\n" + "=" * 100)
    print("📊 K VALUES THEO MOB")
    print("=" * 100)
    
    print("\n   MOB  |  K_raw  |  K_smooth  |  K_final  |  Change  |  Status")
    print("   -----|---------|------------|-----------|----------|----------")
    
    prev_k = None
    k_jumps = []
    
    for mob in range(1, 37):
        k_raw = k_raw_by_mob.get(mob, np.nan)
        k_smooth = k_smooth_by_mob.get(mob, np.nan)
        k_final = k_final_by_mob.get(mob, 1.0)
        
        if prev_k is not None and not np.isnan(k_final):
            change = k_final - prev_k
            change_str = f"{change:+.3f}"
            
            # Detect jumps
            if abs(change) > 0.2:
                k_jumps.append((mob, prev_k, k_final, change))
                status = "⚠️ JUMP!"
            elif k_final > 0.9:
                status = "❌ Rất cao"
            elif k_final > 0.7:
                status = "⚠️ Cao"
            else:
                status = "✅ OK"
        else:
            change_str = "N/A"
            status = "✅ Start"
        
        k_raw_str = f"{k_raw:.3f}" if not np.isnan(k_raw) else "N/A"
        k_smooth_str = f"{k_smooth:.3f}" if not np.isnan(k_smooth) else "N/A"
        
        print(f"   {mob:4d} | {k_raw_str:7s} | {k_smooth_str:10s} | {k_final:9.3f} | {change_str:8s} | {status}")
        
        if not np.isnan(k_final):
            prev_k = k_final
    
    # Summary
    print("\n" + "=" * 100)
    print("📊 THỐNG KÊ")
    print("=" * 100)
    
    # K values before and after MOB 24
    k_before_24 = [k_final_by_mob.get(m, np.nan) for m in range(12, 24)]
    k_after_24 = [k_final_by_mob.get(m, np.nan) for m in range(24, 30)]
    
    k_before_24 = [k for k in k_before_24 if not np.isnan(k)]
    k_after_24 = [k for k in k_after_24 if not np.isnan(k)]
    
    if k_before_24 and k_after_24:
        avg_before = np.mean(k_before_24)
        avg_after = np.mean(k_after_24)
        
        print(f"\n   K trung bình TRƯỚC MOB 24 (MOB 12-23): {avg_before:.3f}")
        print(f"   K trung bình SAU MOB 24 (MOB 24-29):   {avg_after:.3f}")
        print(f"   Chênh lệch:                             {avg_after - avg_before:+.3f} ({(avg_after/avg_before - 1)*100:+.1f}%)")
        
        if avg_after > avg_before * 1.2:
            print(f"\n   ❌ K SAU MOB 24 CAO HƠN TRƯỚC MOB 24 NHIỀU!")
            print(f"   → Đây là lý do slope SAU mature cao hơn slope TRƯỚC mature")
            print(f"   → Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng")
        else:
            print(f"\n   ✅ K không thay đổi nhiều")
    
    # K jumps
    if k_jumps:
        print(f"\n   ❌ PHÁT HIỆN {len(k_jumps)} K JUMPS:")
        for mob, k_before, k_after, change in k_jumps:
            print(f"      - MOB {mob}: {k_before:.3f} → {k_after:.3f} (change: {change:+.3f})")
    else:
        print(f"\n   ✅ Không có K jumps lớn (>0.2)")
    
    # Explanation
    print("\n" + "=" * 100)
    print("💡 GIẢI THÍCH")
    print("=" * 100)
    
    print("\n   Công thức forecast:")
    print("   v_{m+1} = v_m + k_m * (v_hat - v_m)")
    print("   where v_hat = v_m @ P_m")
    
    print("\n   Nếu P_m có movement (ví dụ: DPD0 → DEL30+ = 0.0004%):")
    
    if k_before_24 and k_after_24:
        avg_before = np.mean(k_before_24)
        avg_after = np.mean(k_after_24)
        
        movement = 0.0004  # P_23 movement từ kết quả của bạn
        
        forecast_before = avg_before * movement
        forecast_after = avg_after * movement
        
        print(f"\n   TRƯỚC MOB 24 (K = {avg_before:.3f}):")
        print(f"      Forecast movement = {avg_before:.3f} * {movement:.4f}% = {forecast_before:.6f}%")
        
        print(f"\n   SAU MOB 24 (K = {avg_after:.3f}):")
        print(f"      Forecast movement = {avg_after:.3f} * {movement:.4f}% = {forecast_after:.6f}%")
        
        print(f"\n   Chênh lệch: {forecast_after - forecast_before:.6f}% ({(forecast_after/forecast_before - 1)*100:+.1f}%)")
        
        if forecast_after > forecast_before * 1.2:
            print(f"\n   ❌ FORECAST MOVEMENT SAU MOB 24 CAO HƠN TRƯỚC MOB 24!")
            print(f"   → Đây là lý do slope tăng")
            print(f"   → Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng")
    
    print("\n" + "=" * 100)
    print("KẾT LUẬN")
    print("=" * 100)
    
    print("\n   'Ổn định' có 2 nghĩa:")
    print("   1. P_m không thay đổi theo MOB (P_23 ≈ P_24 ≈ P_25)")
    print("   2. P_m không gây movement (v_hat ≈ v_m)")
    
    print("\n   P_m có thể 'ổn định' theo nghĩa 1 nhưng vẫn có movement!")
    print("   → K quyết định bao nhiêu % movement được áp dụng")
    print("   → K tăng → Forecast movement tăng → Slope tăng")
    
    if k_before_24 and k_after_24:
        avg_before = np.mean(k_before_24)
        avg_after = np.mean(k_after_24)
        
        if avg_after > avg_before * 1.2:
            print(f"\n   ❌ K SAU MOB 24 ({avg_after:.3f}) cao hơn TRƯỚC MOB 24 ({avg_before:.3f})")
            print(f"   → Đây là lý do slope SAU mature cao hơn slope TRƯỚC mature")
            print(f"   → Giải pháp: Giảm K sau MOB 24 xuống {avg_before:.3f}")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
