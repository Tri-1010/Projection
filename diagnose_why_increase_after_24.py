"""
🔍 DIAGNOSTIC: Tại sao K=1.0 gây DEL tăng sau MOB 24?

Câu hỏi của user:
- P_23 movement = 0.0004% (rất nhỏ, ổn định)
- Parent fallback = 0.0008% (chỉ cao hơn 2.2x)
- Nhưng forecast slope = 0.5636% (cao hơn 1400x!)
- Tại sao K=1.0 lại gây vấn đề nếu transitions đã ổn định?

Giả thuyết cần kiểm tra:
1. K values trước MOB 24 thấp hơn (0.5-0.7), sau MOB 24 nhảy lên 1.0
2. Có bug trong forecast logic (accumulation/amplification)
3. Partial-step formula có behavior bất thường với transitions nhỏ
4. Parent fallback được dùng nhiều hơn sau MOB 24

Công thức forecast:
v_{m+1} = v_m + k_m * (v_hat - v_m)
where v_hat = v_m @ P_m

Nếu P_m ổn định (v_hat ≈ v_m), thì:
- k_m = 1.0 → v_{m+1} = v_hat (full Markov)
- k_m = 0.0 → v_{m+1} = v_m (no change)
- k_m = 0.5 → v_{m+1} = v_m + 0.5 * (v_hat - v_m) (partial step)

Nếu v_hat ≈ v_m, thì k_m không quan trọng!
→ Vậy tại sao K=1.0 lại gây vấn đề?
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
from src.rollrate.calibration_kmob import (
    fit_k_raw, smooth_k, fit_alpha,
    forecast_all_vintages_partial_step,
)


def analyze_k_values_by_mob(k_final_by_mob, mob_range=(1, 36)):
    """Phân tích K values theo MOB để xem có pattern gì không."""
    print("=" * 100)
    print("1️⃣ PHÂN TÍCH K VALUES THEO MOB")
    print("=" * 100)
    
    print("\n   MOB  |  K value  |  Change  |  Status")
    print("   -----|-----------|----------|----------")
    
    prev_k = None
    k_jumps = []
    
    for mob in range(mob_range[0], mob_range[1] + 1):
        k = k_final_by_mob.get(mob, 1.0)
        
        if prev_k is not None:
            change = k - prev_k
            change_str = f"{change:+.3f}"
            
            # Detect jumps
            if abs(change) > 0.2:
                k_jumps.append((mob, prev_k, k, change))
                status = "⚠️ JUMP!"
            elif k > 0.9:
                status = "❌ Rất cao"
            elif k > 0.7:
                status = "⚠️ Cao"
            else:
                status = "✅ OK"
        else:
            change_str = "N/A"
            status = "✅ Start"
        
        print(f"   {mob:4d} | {k:9.3f} | {change_str:8s} | {status}")
        prev_k = k
    
    print("\n" + "-" * 100)
    
    if k_jumps:
        print(f"\n❌ PHÁT HIỆN {len(k_jumps)} K JUMPS:")
        for mob, k_before, k_after, change in k_jumps:
            print(f"   - MOB {mob}: {k_before:.3f} → {k_after:.3f} (change: {change:+.3f})")
        
        print("\n💡 Giải thích:")
        print("   - K jumps có thể gây DEL tăng đột ngột")
        print("   - Nếu K jump từ 0.5 → 1.0 ở MOB 24, forecast sẽ tin Markov nhiều hơn")
        print("   - Ngay cả khi P_24 ổn định, việc thay đổi K cũng gây thay đổi forecast")
    else:
        print("\n✅ Không có K jumps lớn")
    
    return k_jumps


def analyze_transition_stability(matrices_by_mob, parent_fallback, buckets_30p, mob_range=(20, 30)):
    """Phân tích xem transitions có thực sự ổn định không."""
    print("\n" + "=" * 100)
    print("2️⃣ PHÂN TÍCH TRANSITION STABILITY")
    print("=" * 100)
    
    # Lấy 1 cohort để test
    test_prod = None
    test_score = None
    
    for prod_str in matrices_by_mob.keys():
        if 23 in matrices_by_mob[prod_str]:
            for score_str in matrices_by_mob[prod_str][23].keys():
                if not matrices_by_mob[prod_str][23][score_str].get("is_fallback", False):
                    test_prod = prod_str
                    test_score = score_str
                    break
        if test_prod:
            break
    
    if not test_prod or not test_score:
        print("\n⚠️ Không tìm thấy cohort để test")
        return None
    
    print(f"\n   Test cohort: {test_prod}/{test_score}")
    print("\n   MOB  |  DPD0→DEL30+  |  Change  |  Status")
    print("   -----|---------------|----------|----------")
    
    prev_rate = None
    movements = []
    
    for mob in range(mob_range[0], mob_range[1] + 1):
        if mob not in matrices_by_mob[test_prod]:
            continue
        
        if test_score not in matrices_by_mob[test_prod][mob]:
            continue
        
        P = matrices_by_mob[test_prod][mob][test_score]["P"]
        is_fallback = matrices_by_mob[test_prod][mob][test_score].get("is_fallback", False)
        
        if "DPD0" not in P.index:
            continue
        
        # Calculate DPD0 → DEL30+ rate
        del30_states = [s for s in buckets_30p if s in P.columns]
        rate = sum(P.loc["DPD0", s] for s in del30_states)
        
        if prev_rate is not None:
            change = rate - prev_rate
            change_str = f"{change:+.6f}"
            movements.append((mob, change))
            
            if abs(change) > 0.001:
                status = "⚠️ Movement"
            else:
                status = "✅ Stable"
        else:
            change_str = "N/A"
            status = "✅ Start"
        
        fallback_str = " (FALLBACK)" if is_fallback else ""
        print(f"   {mob:4d} | {rate:13.6f} | {change_str:8s} | {status}{fallback_str}")
        prev_rate = rate
    
    print("\n" + "-" * 100)
    
    if movements:
        avg_movement = np.mean([abs(m[1]) for m in movements])
        max_movement = max([abs(m[1]) for m in movements])
        
        print(f"\n📊 THỐNG KÊ MOVEMENT:")
        print(f"   - Average movement: {avg_movement:.6f} ({avg_movement*100:.4f}%)")
        print(f"   - Max movement:     {max_movement:.6f} ({max_movement*100:.4f}%)")
        
        if avg_movement > 0.001:
            print(f"\n❌ TRANSITIONS KHÔNG ỔN ĐỊNH!")
            print(f"   - Average movement {avg_movement*100:.4f}% > 0.1%")
            print(f"   - Đây là lý do DEL tăng!")
        else:
            print(f"\n✅ Transitions ổn định (movement < 0.1%)")
    
    return movements


def simulate_forecast_with_different_k(
    matrices_by_mob,
    parent_fallback,
    actual_results,
    disb_total_by_vintage,
    buckets_canon,
    buckets_30p,
    k_scenarios=None,
):
    """Simulate forecast với các K scenarios khác nhau để xem impact."""
    print("\n" + "=" * 100)
    print("3️⃣ SIMULATE FORECAST VỚI CÁC K SCENARIOS")
    print("=" * 100)
    
    if k_scenarios is None:
        k_scenarios = {
            "K=0.0 (No Markov)": {mob: 0.0 for mob in range(1, 37)},
            "K=0.3 (Low)": {mob: 0.3 for mob in range(1, 37)},
            "K=0.5 (Medium)": {mob: 0.5 for mob in range(1, 37)},
            "K=1.0 (Full Markov)": {mob: 1.0 for mob in range(1, 37)},
        }
    
    results = {}
    
    for scenario_name, k_by_mob in k_scenarios.items():
        print(f"\n   Simulating: {scenario_name}...")
        
        forecast_results = forecast_all_vintages_partial_step(
            actual_results=actual_results,
            matrices_by_mob=matrices_by_mob,
            parent_fallback=parent_fallback,
            max_mob=36,
            k_by_mob=k_by_mob,
            states=buckets_canon,
        )
        
        # Calculate average DEL slope from MOB 23 → 29
        slopes = []
        for cohort_key, forecast in forecast_results.items():
            if 23 in forecast and 29 in forecast:
                disb_total = disb_total_by_vintage.get(cohort_key, 1.0)
                if disb_total <= 0:
                    continue
                
                del30_23 = forecast[23][buckets_30p].sum() / disb_total
                del30_29 = forecast[29][buckets_30p].sum() / disb_total
                slope = (del30_29 - del30_23) / 6
                slopes.append(slope)
        
        if slopes:
            avg_slope = np.mean(slopes)
            results[scenario_name] = avg_slope
        else:
            results[scenario_name] = np.nan
    
    print("\n" + "-" * 100)
    print("\n📊 KẾT QUẢ:")
    print("\n   Scenario           |  Avg Slope (MOB 23→29)  |  Status")
    print("   -------------------|-------------------------|----------")
    
    for scenario_name, avg_slope in results.items():
        if np.isnan(avg_slope):
            print(f"   {scenario_name:18s} | {'N/A':23s} | ⚠️ No data")
        else:
            status = "❌ Tăng cao" if avg_slope > 0.005 else "✅ OK"
            print(f"   {scenario_name:18s} | {avg_slope:10.6f} ({avg_slope*100:6.4f}%) | {status}")
    
    print("\n" + "-" * 100)
    
    # Compare K=1.0 vs K=0.3
    if "K=1.0 (Full Markov)" in results and "K=0.3 (Low)" in results:
        k1_slope = results["K=1.0 (Full Markov)"]
        k03_slope = results["K=0.3 (Low)"]
        
        if not np.isnan(k1_slope) and not np.isnan(k03_slope):
            diff = k1_slope - k03_slope
            print(f"\n💡 SO SÁNH K=1.0 vs K=0.3:")
            print(f"   - K=1.0 slope: {k1_slope:.6f} ({k1_slope*100:.4f}%)")
            print(f"   - K=0.3 slope: {k03_slope:.6f} ({k03_slope*100:.4f}%)")
            print(f"   - Diff:        {diff:.6f} ({diff*100:.4f}%)")
            
            if diff > 0.003:
                print(f"\n❌ K=1.0 GÂY DEL TĂNG CAO HƠN K=0.3 NHIỀU!")
                print(f"   → Giảm K xuống 0.3 sẽ giảm slope {diff*100:.4f}%")
            else:
                print(f"\n✅ K không ảnh hưởng nhiều đến slope")
    
    return results


def main():
    """Main diagnostic function."""
    print("=" * 100)
    print("🔍 DIAGNOSTIC: TẠI SAO K=1.0 GÂY DEL TĂNG SAU MOB 24?")
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
    
    # Run diagnostics
    print("\n" + "=" * 100)
    print("BẮT ĐẦU DIAGNOSTIC")
    print("=" * 100)
    
    # 1. Analyze K values
    k_jumps = analyze_k_values_by_mob(k_final_by_mob, mob_range=(1, 36))
    
    # 2. Analyze transition stability
    movements = analyze_transition_stability(
        matrices_by_mob, parent_fallback, BUCKETS_30P, mob_range=(20, 30)
    )
    
    # 3. Simulate forecast with different K
    results = simulate_forecast_with_different_k(
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        actual_results=actual_results,
        disb_total_by_vintage=disb_total_by_vintage,
        buckets_canon=BUCKETS_CANON,
        buckets_30p=BUCKETS_30P,
    )
    
    # Final conclusion
    print("\n" + "=" * 100)
    print("KẾT LUẬN")
    print("=" * 100)
    
    conclusions = []
    
    if k_jumps:
        conclusions.append("❌ K values có jumps lớn → Gây thay đổi forecast behavior")
    
    if movements:
        avg_movement = np.mean([abs(m[1]) for m in movements])
        if avg_movement > 0.001:
            conclusions.append(f"❌ Transitions KHÔNG ổn định (avg movement: {avg_movement*100:.4f}%)")
        else:
            conclusions.append(f"✅ Transitions ổn định (avg movement: {avg_movement*100:.4f}%)")
    
    if "K=1.0 (Full Markov)" in results and "K=0.3 (Low)" in results:
        k1_slope = results["K=1.0 (Full Markov)"]
        k03_slope = results["K=0.3 (Low)"]
        if not np.isnan(k1_slope) and not np.isnan(k03_slope):
            diff = k1_slope - k03_slope
            if diff > 0.003:
                conclusions.append(f"❌ K=1.0 gây slope cao hơn K=0.3 {diff*100:.4f}%")
    
    if not conclusions:
        conclusions.append("⚠️ Không phát hiện vấn đề rõ ràng")
    
    for conclusion in conclusions:
        print(f"\n{conclusion}")
    
    print("\n" + "=" * 100)
    print("KHUYẾN NGHỊ")
    print("=" * 100)
    
    if k_jumps:
        print("\n1️⃣ Smooth K values để tránh jumps")
        print("   → Tăng gamma trong smooth_k()")
    
    if movements and np.mean([abs(m[1]) for m in movements]) > 0.001:
        print("\n2️⃣ Transitions không ổn định → Đây là nguyên nhân chính!")
        print("   → Kiểm tra lại data quality")
        print("   → Xem xét tăng MIN_OBS để lọc cohorts không ổn định")
    
    if "K=1.0 (Full Markov)" in results and "K=0.3 (Low)" in results:
        k1_slope = results["K=1.0 (Full Markov)"]
        k03_slope = results["K=0.3 (Low)"]
        if not np.isnan(k1_slope) and not np.isnan(k03_slope):
            diff = k1_slope - k03_slope
            if diff > 0.003:
                print("\n3️⃣ Giảm K xuống 0.3 cho MOB 25+")
                print(f"   → Sẽ giảm slope {diff*100:.4f}%")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
