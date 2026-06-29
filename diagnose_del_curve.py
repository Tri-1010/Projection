"""
Script để chẩn đoán tại sao DEL curve tăng liên tục thay vì flatten
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.config import ABSORBING_BASE, BUCKETS_CANON

def diagnose_del_curve(
    matrices_by_mob,
    parent_fallback,
    k_final_by_mob,
    forecast_results,
    disb_total_by_vintage,
    product="C",
    score="650+_10M-_POS",
    vintage="2023-12-01"
):
    """
    Chẩn đoán tại sao DEL curve tăng liên tục
    """
    
    print("="*80)
    print("CHẨN ĐOÁN DEL CURVE")
    print("="*80)
    
    # ===========================
    # 1. Kiểm tra Absorbing States
    # ===========================
    print("\n1️⃣ ABSORBING STATES:")
    print(f"   Absorbing states: {ABSORBING_BASE}")
    print(f"   All states: {BUCKETS_CANON}")
    
    # Kiểm tra ma trận P_24
    prod_str = str(product)
    score_str = str(score)
    
    if prod_str in matrices_by_mob and 24 in matrices_by_mob[prod_str]:
        if score_str in matrices_by_mob[prod_str][24]:
            P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
            
            print(f"\n   Kiểm tra ma trận P_24 cho {product}/{score}:")
            for state in ABSORBING_BASE:
                if state in P_24.index:
                    self_prob = P_24.loc[state, state]
                    other_sum = P_24.loc[state].drop(state).sum()
                    status = "✅" if abs(self_prob - 1.0) < 0.01 else "❌"
                    print(f"   {status} {state}: P[{state},{state}] = {self_prob:.4f}, sum(others) = {other_sum:.4f}")
        else:
            print(f"   ⚠️ Không tìm thấy score {score_str} trong MOB 24")
    else:
        print(f"   ⚠️ Không tìm thấy MOB 24 cho product {prod_str}")
    
    # ===========================
    # 2. Kiểm tra K values
    # ===========================
    print("\n2️⃣ K VALUES ở MOB cao:")
    print("   MOB  |  K value  |  Status")
    print("   -----|-----------|----------")
    for mob in range(20, 37):
        k = k_final_by_mob.get(mob, 1.0)
        if k > 0.9:
            status = "⚠️ Rất cao (tin Markov hoàn toàn)"
        elif k > 0.7:
            status = "⚠️ Cao"
        elif k > 0.5:
            status = "✅ Trung bình"
        else:
            status = "✅ Thấp (ít tin Markov)"
        print(f"   {mob:4d} | {k:9.3f} | {status}")
    
    # ===========================
    # 3. Kiểm tra Transition Rates trong P_24
    # ===========================
    print("\n3️⃣ TRANSITION RATES trong P_24:")
    if prod_str in matrices_by_mob and 24 in matrices_by_mob[prod_str]:
        if score_str in matrices_by_mob[prod_str][24]:
            P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
            
            # Kiểm tra DPD0 → DPD30+
            if "DPD0" in P_24.index:
                dpd0_row = P_24.loc["DPD0"]
                to_dpd30 = dpd0_row[["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]].sum()
                print(f"\n   DPD0 → DEL30+ states: {to_dpd30:.4f} ({to_dpd30*100:.2f}%)")
                if to_dpd30 > 0.03:
                    print(f"   ⚠️ Quá cao! Nên < 3% mỗi tháng")
                else:
                    print(f"   ✅ Hợp lý")
                
                print(f"\n   Chi tiết DPD0 row:")
                print(dpd0_row)
            
            # Kiểm tra DPD30+ → WRITEOFF
            if "DPD30+" in P_24.index:
                dpd30_row = P_24.loc["DPD30+"]
                to_writeoff = dpd30_row["WRITEOFF"] if "WRITEOFF" in dpd30_row.index else 0
                print(f"\n   DPD30+ → WRITEOFF: {to_writeoff:.4f} ({to_writeoff*100:.2f}%)")
                if to_writeoff < 0.02:
                    print(f"   ⚠️ Quá thấp! Nên > 2% mỗi tháng")
                else:
                    print(f"   ✅ Hợp lý")
    
    # ===========================
    # 4. So sánh P_24 vs Parent Fallback
    # ===========================
    print("\n4️⃣ SO SÁNH P_24 vs PARENT FALLBACK:")
    key_parent = (prod_str, score_str)
    if key_parent in parent_fallback:
        P_parent = parent_fallback[key_parent]
        
        if prod_str in matrices_by_mob and 24 in matrices_by_mob[prod_str]:
            if score_str in matrices_by_mob[prod_str][24]:
                P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
                
                # So sánh DPD0 row
                if "DPD0" in P_24.index and "DPD0" in P_parent.index:
                    print("\n   DPD0 row comparison:")
                    print("   State    | P_24    | P_parent | Diff")
                    print("   ---------|---------|----------|--------")
                    for state in ["DPD0", "DPD1+", "DPD30+", "WRITEOFF", "PREPAY"]:
                        if state in P_24.columns and state in P_parent.columns:
                            p24_val = P_24.loc["DPD0", state]
                            parent_val = P_parent.loc["DPD0", state]
                            diff = p24_val - parent_val
                            status = "⚠️" if abs(diff) > 0.05 else "✅"
                            print(f"   {state:8s} | {p24_val:7.4f} | {parent_val:8.4f} | {diff:+7.4f} {status}")
    
    # ===========================
    # 5. Kiểm tra DEL Curve
    # ===========================
    print("\n5️⃣ DEL CURVE:")
    cohort_key = (product, score, vintage)
    
    if cohort_key in forecast_results:
        forecast = forecast_results[cohort_key]
        disb_total = disb_total_by_vintage.get(cohort_key, 1.0)
        
        BUCKETS_30P = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
        
        del30_by_mob = {}
        for mob, ead_vec in forecast.items():
            del30_amt = ead_vec[BUCKETS_30P].sum()
            del30_pct = del30_amt / disb_total
            del30_by_mob[mob] = del30_pct
        
        # Tính slope ở MOB 24-30 và 30-36
        mobs = sorted(del30_by_mob.keys())
        
        if 24 in del30_by_mob and 30 in del30_by_mob:
            slope_24_30 = (del30_by_mob[30] - del30_by_mob[24]) / 6
            print(f"\n   Slope MOB 24-30: {slope_24_30:.6f} ({slope_24_30*100:.4f}% per month)")
            if abs(slope_24_30) > 0.001:
                print(f"   ⚠️ Slope quá cao! Nên gần 0 (flatten)")
            else:
                print(f"   ✅ Slope hợp lý (flatten)")
        
        if 30 in del30_by_mob and 36 in del30_by_mob:
            slope_30_36 = (del30_by_mob[36] - del30_by_mob[30]) / 6
            print(f"   Slope MOB 30-36: {slope_30_36:.6f} ({slope_30_36*100:.4f}% per month)")
            if abs(slope_30_36) > 0.001:
                print(f"   ⚠️ Slope quá cao! Nên gần 0 (flatten)")
            else:
                print(f"   ✅ Slope hợp lý (flatten)")
        
        # Print values
        print("\n   DEL30+ values:")
        print("   MOB  | DEL30+  | Change from prev")
        print("   -----|---------|------------------")
        prev_val = None
        for mob in mobs:
            val = del30_by_mob[mob]
            if prev_val is not None:
                change = val - prev_val
                status = "⚠️" if change > 0.005 else "✅"
                print(f"   {mob:4d} | {val:7.4f} | {change:+7.4f} {status}")
            else:
                print(f"   {mob:4d} | {val:7.4f} | -")
            prev_val = val
        
        # Plot
        plt.figure(figsize=(12, 6))
        plt.plot(mobs, [del30_by_mob[m] for m in mobs], marker='o', linewidth=2)
        plt.axvline(x=24, color='red', linestyle='--', linewidth=2, label='Last historical MOB')
        plt.xlabel('MOB', fontsize=12)
        plt.ylabel('DEL30+', fontsize=12)
        plt.title(f'DEL30+ Curve - {product}/{score}/{vintage}', fontsize=14)
        plt.legend(fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig('del30_curve_diagnosis.png', dpi=150)
        print(f"\n   📊 Chart saved: del30_curve_diagnosis.png")
        plt.show()
    else:
        print(f"   ⚠️ Không tìm thấy forecast cho cohort {cohort_key}")
    
    # ===========================
    # 6. Khuyến nghị
    # ===========================
    print("\n" + "="*80)
    print("KHUYẾN NGHỊ:")
    print("="*80)
    
    # Check absorbing
    has_issue = False
    if prod_str in matrices_by_mob and 24 in matrices_by_mob[prod_str]:
        if score_str in matrices_by_mob[prod_str][24]:
            P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
            for state in ABSORBING_BASE:
                if state in P_24.index:
                    self_prob = P_24.loc[state, state]
                    if abs(self_prob - 1.0) > 0.01:
                        has_issue = True
                        print(f"❌ {state} không phải absorbing state đúng cách!")
                        print(f"   → Kiểm tra lại _enforce_absorbing() trong transition.py")
    
    # Check K
    high_k_count = sum(1 for mob in range(25, 37) if k_final_by_mob.get(mob, 1.0) > 0.8)
    if high_k_count > 6:
        has_issue = True
        print(f"❌ Có {high_k_count} MOBs (25-36) có K > 0.8 (quá cao)")
        print(f"   → Xem xét giảm K ở MOB cao hoặc giảm alpha")
    
    # Check slope
    if cohort_key in forecast_results:
        if 24 in del30_by_mob and 30 in del30_by_mob:
            slope_24_30 = (del30_by_mob[30] - del30_by_mob[24]) / 6
            if abs(slope_24_30) > 0.001:
                has_issue = True
                print(f"❌ Slope MOB 24-30 quá cao: {slope_24_30*100:.4f}% per month")
                print(f"   → DEL curve không flatten như mong đợi")
    
    if not has_issue:
        print("✅ Không phát hiện vấn đề rõ ràng")
        print("   → Có thể là do data hoặc business logic")
    
    print("\n" + "="*80)
    print("Xem file DIAGNOSIS_CONTINUOUS_INCREASE.md để biết thêm chi tiết")
    print("="*80)


if __name__ == "__main__":
    print("Chạy script này từ notebook hoặc script chính với các biến:")
    print("- matrices_by_mob")
    print("- parent_fallback")
    print("- k_final_by_mob")
    print("- forecast_results")
    print("- disb_total_by_vintage")
