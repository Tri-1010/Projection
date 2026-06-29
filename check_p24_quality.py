"""
Script kiểm tra chất lượng ma trận P_24
Để xác định xem P_24 có gây ra DEL tăng liên tục không
"""

import pandas as pd
import numpy as np

def check_p24_quality(matrices_by_mob, parent_fallback, product="C", score="650+_10M-_POS"):
    """
    Kiểm tra chất lượng ma trận P_24
    """
    
    print("="*80)
    print("KIỂM TRA CHẤT LƯỢNG MA TRẬN P_24")
    print("="*80)
    
    prod_str = str(product)
    score_str = str(score)
    
    # Kiểm tra P_24 có tồn tại không
    if prod_str not in matrices_by_mob:
        print(f"❌ Product {prod_str} không tồn tại trong matrices_by_mob")
        return
    
    if 24 not in matrices_by_mob[prod_str]:
        print(f"❌ MOB 24 không tồn tại cho product {prod_str}")
        return
    
    if score_str not in matrices_by_mob[prod_str][24]:
        print(f"❌ Score {score_str} không tồn tại ở MOB 24")
        return
    
    P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
    is_fallback = matrices_by_mob[prod_str][24][score_str].get("is_fallback", False)
    
    print(f"\n📊 Product: {product}")
    print(f"📊 Score: {score}")
    print(f"📊 Is fallback: {is_fallback}")
    
    if is_fallback:
        print("⚠️ MOB 24 đang dùng fallback (parent hoặc last MOB)")
        print("   → Có thể đây là nguyên nhân gây tăng liên tục")
    
    # Lấy parent fallback để so sánh
    key_parent = (prod_str, score_str)
    if key_parent in parent_fallback:
        P_parent = parent_fallback[key_parent]
    else:
        P_parent = None
        print("⚠️ Không tìm thấy parent fallback")
    
    print("\n" + "="*80)
    print("1️⃣ KIỂM TRA ABSORBING STATES")
    print("="*80)
    
    absorbing_states = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]
    for state in absorbing_states:
        if state in P_24.index and state in P_24.columns:
            self_prob = P_24.loc[state, state]
            other_sum = P_24.loc[state].drop(state).sum()
            
            if abs(self_prob - 1.0) < 0.01 and other_sum < 0.01:
                status = "✅"
            else:
                status = "❌"
            
            print(f"{status} {state:10s}: P[{state},{state}] = {self_prob:.4f}, sum(others) = {other_sum:.4f}")
    
    print("\n" + "="*80)
    print("2️⃣ KIỂM TRA TRANSITION RATES TỪ DPD0")
    print("="*80)
    
    if "DPD0" in P_24.index:
        dpd0_row = P_24.loc["DPD0"]
        
        # Kiểm tra DPD0 → DPD0 (stay)
        stay_prob = dpd0_row["DPD0"] if "DPD0" in dpd0_row.index else 0
        print(f"\nDPD0 → DPD0 (stay): {stay_prob:.4f} ({stay_prob*100:.2f}%)")
        if stay_prob < 0.90:
            print(f"   ⚠️ Quá thấp! Nên > 90%")
        else:
            print(f"   ✅ Hợp lý")
        
        # Kiểm tra DPD0 → PREPAY
        prepay_prob = dpd0_row["PREPAY"] if "PREPAY" in dpd0_row.index else 0
        print(f"\nDPD0 → PREPAY: {prepay_prob:.4f} ({prepay_prob*100:.2f}%)")
        if prepay_prob < 0.01:
            print(f"   ⚠️ Quá thấp! Nên > 1%")
        elif prepay_prob > 0.10:
            print(f"   ⚠️ Quá cao! Nên < 10%")
        else:
            print(f"   ✅ Hợp lý")
        
        # Kiểm tra DPD0 → DEL30+ states
        del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
        to_del30 = sum(dpd0_row[s] for s in del30_states if s in dpd0_row.index)
        print(f"\nDPD0 → DEL30+ states: {to_del30:.4f} ({to_del30*100:.2f}%)")
        if to_del30 > 0.03:
            print(f"   ❌ QUÁ CAO! Nên < 3% mỗi tháng")
            print(f"   → Đây có thể là nguyên nhân gây DEL tăng liên tục")
        elif to_del30 > 0.02:
            print(f"   ⚠️ Hơi cao! Nên < 2%")
        else:
            print(f"   ✅ Hợp lý")
        
        # Chi tiết
        print(f"\n   Chi tiết DPD0 row:")
        for state in ["DPD0", "DPD1+", "DPD30+", "DPD60+", "DPD90+", "WRITEOFF", "PREPAY"]:
            if state in dpd0_row.index:
                val = dpd0_row[state]
                print(f"   {state:10s}: {val:.4f} ({val*100:.2f}%)")
    
    print("\n" + "="*80)
    print("3️⃣ KIỂM TRA TRANSITION RATES TỪ DPD30+")
    print("="*80)
    
    if "DPD30+" in P_24.index:
        dpd30_row = P_24.loc["DPD30+"]
        
        # Kiểm tra DPD30+ → DPD30+ (stay)
        stay_prob = dpd30_row["DPD30+"] if "DPD30+" in dpd30_row.index else 0
        print(f"\nDPD30+ → DPD30+ (stay): {stay_prob:.4f} ({stay_prob*100:.2f}%)")
        if stay_prob > 0.50:
            print(f"   ⚠️ Quá cao! Nên < 50%")
        else:
            print(f"   ✅ Hợp lý")
        
        # Kiểm tra DPD30+ → DPD90+
        to_dpd90 = dpd30_row["DPD90+"] if "DPD90+" in dpd30_row.index else 0
        print(f"\nDPD30+ → DPD90+: {to_dpd90:.4f} ({to_dpd90*100:.2f}%)")
        if to_dpd90 < 0.10:
            print(f"   ⚠️ Quá thấp! Nên > 10%")
        else:
            print(f"   ✅ Hợp lý")
        
        # Kiểm tra DPD30+ → WRITEOFF
        to_writeoff = dpd30_row["WRITEOFF"] if "WRITEOFF" in dpd30_row.index else 0
        print(f"\nDPD30+ → WRITEOFF: {to_writeoff:.4f} ({to_writeoff*100:.2f}%)")
        if to_writeoff < 0.02:
            print(f"   ⚠️ Quá thấp! Nên > 2%")
        else:
            print(f"   ✅ Hợp lý")
        
        # Chi tiết
        print(f"\n   Chi tiết DPD30+ row:")
        for state in ["DPD0", "DPD30+", "DPD60+", "DPD90+", "WRITEOFF", "PREPAY"]:
            if state in dpd30_row.index:
                val = dpd30_row[state]
                print(f"   {state:10s}: {val:.4f} ({val*100:.2f}%)")
    
    print("\n" + "="*80)
    print("4️⃣ SO SÁNH P_24 vs PARENT FALLBACK")
    print("="*80)
    
    if P_parent is not None:
        print("\nSo sánh DPD0 row:")
        print("State      | P_24    | P_parent | Diff     | Status")
        print("-----------|---------|----------|----------|--------")
        
        if "DPD0" in P_24.index and "DPD0" in P_parent.index:
            for state in ["DPD0", "DPD1+", "DPD30+", "WRITEOFF", "PREPAY"]:
                if state in P_24.columns and state in P_parent.columns:
                    p24_val = P_24.loc["DPD0", state]
                    parent_val = P_parent.loc["DPD0", state]
                    diff = p24_val - parent_val
                    
                    if abs(diff) > 0.05:
                        status = "❌ Khác biệt lớn"
                    elif abs(diff) > 0.02:
                        status = "⚠️ Khác biệt"
                    else:
                        status = "✅ Tương tự"
                    
                    print(f"{state:10s} | {p24_val:7.4f} | {parent_val:8.4f} | {diff:+8.4f} | {status}")
        
        # Tính tổng khác biệt
        if "DPD0" in P_24.index and "DPD0" in P_parent.index:
            total_diff = abs(P_24.loc["DPD0"] - P_parent.loc["DPD0"]).sum()
            print(f"\nTổng khác biệt (L1 distance): {total_diff:.4f}")
            if total_diff > 0.20:
                print(f"   ❌ P_24 RẤT KHÁC so với parent fallback")
                print(f"   → Nên dùng parent fallback cho MOB 25+")
            elif total_diff > 0.10:
                print(f"   ⚠️ P_24 khác biệt so với parent fallback")
            else:
                print(f"   ✅ P_24 tương tự parent fallback")
    
    print("\n" + "="*80)
    print("5️⃣ KẾT LUẬN & KHUYẾN NGHỊ")
    print("="*80)
    
    issues = []
    
    # Check absorbing
    for state in absorbing_states:
        if state in P_24.index and state in P_24.columns:
            self_prob = P_24.loc[state, state]
            if abs(self_prob - 1.0) > 0.01:
                issues.append(f"{state} không phải absorbing state đúng cách")
    
    # Check DPD0 → DEL30+
    if "DPD0" in P_24.index:
        dpd0_row = P_24.loc["DPD0"]
        del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
        to_del30 = sum(dpd0_row[s] for s in del30_states if s in dpd0_row.index)
        if to_del30 > 0.03:
            issues.append(f"DPD0 → DEL30+ quá cao ({to_del30*100:.2f}%)")
    
    # Check P_24 vs parent
    if P_parent is not None and "DPD0" in P_24.index and "DPD0" in P_parent.index:
        total_diff = abs(P_24.loc["DPD0"] - P_parent.loc["DPD0"]).sum()
        if total_diff > 0.20:
            issues.append(f"P_24 rất khác so với parent fallback (diff={total_diff:.4f})")
    
    if issues:
        print("\n❌ PHÁT HIỆN VẤN ĐỀ:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        
        print("\n💡 KHUYẾN NGHỊ:")
        print("   1. Dùng parent fallback thay vì P_24 cho MOB 25+")
        print("   2. Hoặc smooth P_24 với parent fallback")
        print("   3. Hoặc giảm K ở MOB 25+")
    else:
        print("\n✅ P_24 có vẻ hợp lý")
        print("   → Vấn đề có thể do K values hoặc nguyên nhân khác")
    
    print("\n" + "="*80)
    
    return P_24, P_parent


if __name__ == "__main__":
    print("Chạy script này từ notebook với:")
    print("check_p24_quality(matrices_by_mob, parent_fallback, product='C', score='650+_10M-_POS')")
