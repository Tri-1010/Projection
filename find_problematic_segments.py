"""
Script tìm segments/cohorts nào đang tăng đột biến sau MOB 24
"""

import pandas as pd
import numpy as np

def find_problematic_segments(
    forecast_results,
    disb_total_by_vintage,
    buckets_30p=None,
    threshold_slope=0.002  # 0.2% per month
):
    """
    Tìm segments/cohorts nào đang tăng đột biến sau MOB 24
    
    Args:
        forecast_results: Dict forecast results
        disb_total_by_vintage: Dict disb total by vintage
        buckets_30p: List of DEL30+ states
        threshold_slope: Threshold để coi là "tăng đột biến"
    
    Returns:
        DataFrame với các segments tăng mạnh
    """
    
    if buckets_30p is None:
        buckets_30p = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
    
    print("="*80)
    print("TÌM SEGMENTS TĂNG ĐỘT BIẾN SAU MOB 24")
    print("="*80)
    
    results = []
    
    for cohort_key in forecast_results.keys():
        forecast = forecast_results[cohort_key]
        disb_total = disb_total_by_vintage.get(cohort_key, 1.0)
        
        product, score, vintage = cohort_key
        
        # Tính DEL30+ at MOB 24 and 30
        if 24 in forecast and 30 in forecast:
            try:
                # Chỉ dùng các states có trong forecast
                available_buckets_24 = [s for s in buckets_30p if s in forecast[24].index]
                available_buckets_30 = [s for s in buckets_30p if s in forecast[30].index]
                
                if available_buckets_24 and available_buckets_30:
                    del30_24 = forecast[24][available_buckets_24].sum() / disb_total
                    del30_30 = forecast[30][available_buckets_30].sum() / disb_total
                    slope = (del30_30 - del30_24) / 6  # Per month
                    
                    results.append({
                        "product": product,
                        "score": score,
                        "vintage": vintage,
                        "del30_mob24": del30_24,
                        "del30_mob30": del30_30,
                        "slope": slope,
                        "slope_pct": slope * 100,
                        "total_increase": (del30_30 - del30_24) * 100,
                        "disb_total": disb_total
                    })
            except Exception as e:
                continue
    
    if not results:
        print("\n⚠️ Không tìm thấy cohorts nào có data MOB 24-30")
        return None
    
    df = pd.DataFrame(results)
    
    # Phân loại
    df["status"] = "✅ Flatten"
    df.loc[df["slope"] > threshold_slope, "status"] = "❌ Tăng"
    df.loc[df["slope"] < -threshold_slope, "status"] = "⬇️ Giảm"
    
    # Sắp xếp theo slope giảm dần
    df = df.sort_values("slope", ascending=False)
    
    # Thống kê
    n_total = len(df)
    n_increasing = len(df[df["slope"] > threshold_slope])
    n_flat = len(df[abs(df["slope"]) <= threshold_slope])
    n_decreasing = len(df[df["slope"] < -threshold_slope])
    
    print(f"\n📊 TỔNG HỢP:")
    print(f"   Tổng cohorts: {n_total}")
    print(f"   - Tăng (slope > {threshold_slope:.4f}): {n_increasing} ({n_increasing/n_total*100:.1f}%)")
    print(f"   - Flatten: {n_flat} ({n_flat/n_total*100:.1f}%)")
    print(f"   - Giảm: {n_decreasing} ({n_decreasing/n_total*100:.1f}%)")
    
    # Top cohorts tăng mạnh
    print(f"\n" + "="*80)
    print(f"TOP 10 COHORTS TĂNG MẠNH NHẤT:")
    print("="*80)
    
    df_increasing = df[df["slope"] > 0].head(10)
    
    if len(df_increasing) == 0:
        print("\n✅ Không có cohorts nào tăng!")
        return df
    
    print(f"\n{'Product':<10} {'Score':<25} {'Vintage':<12} {'Slope':<10} {'Increase':<10} {'Weight':<10}")
    print("-"*80)
    
    total_disb = df["disb_total"].sum()
    
    for idx, row in df_increasing.iterrows():
        weight = row["disb_total"] / total_disb * 100
        print(f"{row['product']:<10} {str(row['score']):<25} {str(row['vintage']):<12} "
              f"{row['slope_pct']:>8.4f}% {row['total_increase']:>8.2f}% {weight:>8.2f}%")
    
    # Phân tích theo product
    print(f"\n" + "="*80)
    print(f"PHÂN TÍCH THEO PRODUCT:")
    print("="*80)
    
    for product in df["product"].unique():
        df_prod = df[df["product"] == product]
        n_prod_total = len(df_prod)
        n_prod_increasing = len(df_prod[df_prod["slope"] > threshold_slope])
        
        avg_slope = df_prod["slope"].mean()
        
        print(f"\n{product}:")
        print(f"   Tổng cohorts: {n_prod_total}")
        print(f"   Cohorts tăng: {n_prod_increasing} ({n_prod_increasing/n_prod_total*100:.1f}%)")
        print(f"   Avg slope: {avg_slope*100:.4f}% per month")
        
        if n_prod_increasing > 0:
            print(f"   Top cohorts tăng:")
            for idx, row in df_prod[df_prod["slope"] > threshold_slope].head(3).iterrows():
                print(f"      - {row['score']}/{row['vintage']}: {row['slope_pct']:.4f}% per month")
    
    # Phân tích theo score
    print(f"\n" + "="*80)
    print(f"PHÂN TÍCH THEO SCORE:")
    print("="*80)
    
    score_analysis = df.groupby("score").agg({
        "slope": ["mean", "count"],
        "disb_total": "sum"
    }).reset_index()
    
    score_analysis.columns = ["score", "avg_slope", "n_cohorts", "total_disb"]
    score_analysis["weight"] = score_analysis["total_disb"] / total_disb * 100
    score_analysis = score_analysis.sort_values("avg_slope", ascending=False)
    
    print(f"\n{'Score':<25} {'Avg Slope':<12} {'N Cohorts':<12} {'Weight':<10}")
    print("-"*80)
    
    for idx, row in score_analysis.head(10).iterrows():
        print(f"{str(row['score']):<25} {row['avg_slope']*100:>10.4f}% {row['n_cohorts']:>10.0f} {row['weight']:>8.2f}%")
    
    # Kết luận
    print(f"\n" + "="*80)
    print(f"KẾT LUẬN:")
    print("="*80)
    
    if n_increasing > n_total * 0.5:
        print(f"\n❌ NHIỀU COHORTS TĂNG ({n_increasing}/{n_total})")
        print(f"   → Vấn đề phổ biến, không phải aggregation effect")
        print(f"   → Cần kiểm tra lại P_24 hoặc K values")
    elif n_increasing > 0:
        print(f"\n⚠️ MỘT SỐ COHORTS TĂNG ({n_increasing}/{n_total})")
        print(f"   → Có thể là aggregation effect")
        print(f"   → Kiểm tra xem cohorts tăng có weight cao không")
        
        # Tính tổng weight của cohorts tăng
        total_weight_increasing = df[df["slope"] > threshold_slope]["disb_total"].sum() / total_disb * 100
        print(f"   → Tổng weight cohorts tăng: {total_weight_increasing:.1f}%")
        
        if total_weight_increasing > 20:
            print(f"   → ❌ Weight cao! Đây là vấn đề lớn")
        elif total_weight_increasing > 10:
            print(f"   → ⚠️ Weight trung bình")
        else:
            print(f"   → ✅ Weight thấp, ảnh hưởng nhỏ")
    else:
        print(f"\n✅ KHÔNG CÓ COHORTS NÀO TĂNG")
        print(f"   → Vấn đề không phải ở cohort level")
        print(f"   → Có thể là cách tính DEL hoặc aggregation")
    
    print(f"\n" + "="*80)
    
    return df


if __name__ == "__main__":
    print("Chạy script này từ notebook với:")
    print("df_results = find_problematic_segments(")
    print("    forecast_results=forecast_results,")
    print("    disb_total_by_vintage=disb_total_by_vintage,")
    print("    buckets_30p=BUCKETS_30P,")
    print("    threshold_slope=0.002  # 0.2% per month")
    print(")")
