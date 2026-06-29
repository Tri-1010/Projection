"""
Script so sánh P_24 movement (actual) vs forecast slope để hiểu tại sao DEL tăng
"""

import pandas as pd
import numpy as np

def compare_p24_vs_forecast(
    matrices_by_mob,
    forecast_results,
    actual_results,
    disb_total_by_vintage,
    buckets_30p=None,
    target_mob=24,  # MOB để kiểm tra (có thể là 23, 24, 25, etc.)
    forecast_mob_end=30  # MOB cuối để tính slope
):
    """
    So sánh P_MOB movement (từ transition matrix) vs forecast slope (từ forecast results)
    
    Args:
        matrices_by_mob: Dict transition matrices by MOB
        forecast_results: Dict forecast results
        actual_results: Dict actual results
        disb_total_by_vintage: Dict disb total by vintage
        buckets_30p: List of DEL30+ states
        target_mob: MOB để kiểm tra (default 24)
        forecast_mob_end: MOB cuối để tính slope (default 30)
    
    Returns:
        DataFrame với comparison
    """
    
    if buckets_30p is None:
        buckets_30p = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
    
    print("="*100)
    print(f"SO SÁNH P_{target_mob} MOVEMENT (ACTUAL) vs FORECAST SLOPE (MOB {target_mob} → {forecast_mob_end})")
    print("="*100)
    
    results = []
    
    for cohort_key in forecast_results.keys():
        product, score, vintage = cohort_key
        prod_str = str(product)
        score_str = str(score)
        
        # 1. Lấy P_MOB movement (actual transition rate)
        p_mob_movement = None
        is_fallback = False
        fallback_reason = None
        
        if prod_str in matrices_by_mob and target_mob in matrices_by_mob[prod_str]:
            if score_str in matrices_by_mob[prod_str][target_mob]:
                P_MOB = matrices_by_mob[prod_str][target_mob][score_str]["P"]
                is_fallback = matrices_by_mob[prod_str][target_mob][score_str].get("is_fallback", False)
                fallback_reason = matrices_by_mob[prod_str][target_mob][score_str].get("reason", "")
                
                # Tính movement từ DPD0 → DEL30+
                if "DPD0" in P_MOB.index:
                    # Chỉ dùng các states có trong P_MOB
                    available_buckets = [s for s in buckets_30p if s in P_MOB.columns]
                    if available_buckets:
                        p_mob_movement = sum(P_MOB.loc["DPD0", s] for s in available_buckets)
        
        # 2. Lấy actual DEL at target MOB (từ actual_results)
        actual_del_mob = None
        if cohort_key in actual_results and target_mob in actual_results[cohort_key]:
            disb_total = disb_total_by_vintage.get(cohort_key, 1.0)
            if disb_total > 0:
                # Chỉ dùng các states có trong actual_results
                available_buckets = [s for s in buckets_30p if s in actual_results[cohort_key][target_mob].index]
                if available_buckets:
                    actual_del_mob = actual_results[cohort_key][target_mob][available_buckets].sum() / disb_total
        
        # 3. Lấy forecast slope (target_mob → forecast_mob_end)
        forecast_slope = None
        forecast_del_start = None
        forecast_del_end = None
        
        forecast = forecast_results[cohort_key]
        disb_total = disb_total_by_vintage.get(cohort_key, 1.0)
        
        if target_mob in forecast and forecast_mob_end in forecast and disb_total > 0:
            # Chỉ dùng các states có trong forecast
            available_buckets_start = [s for s in buckets_30p if s in forecast[target_mob].index]
            available_buckets_end = [s for s in buckets_30p if s in forecast[forecast_mob_end].index]
            
            if available_buckets_start and available_buckets_end:
                forecast_del_start = forecast[target_mob][available_buckets_start].sum() / disb_total
                forecast_del_end = forecast[forecast_mob_end][available_buckets_end].sum() / disb_total
                forecast_slope = (forecast_del_end - forecast_del_start) / (forecast_mob_end - target_mob)  # Per month
        
        # 4. So sánh
        if p_mob_movement is not None and forecast_slope is not None:
            diff = forecast_slope - p_mob_movement
            ratio = forecast_slope / p_mob_movement if p_mob_movement > 0 else None
            
            results.append({
                "product": product,
                "score": score,
                "vintage": vintage,
                "p_mob_movement": p_mob_movement,
                "p_mob_movement_pct": p_mob_movement * 100,
                "forecast_slope": forecast_slope,
                "forecast_slope_pct": forecast_slope * 100,
                "diff": diff,
                "diff_pct": diff * 100,
                "ratio": ratio,
                "is_fallback": is_fallback,
                "fallback_reason": fallback_reason,
                "actual_del_mob": actual_del_mob,
                "forecast_del_start": forecast_del_start,
                "forecast_del_end": forecast_del_end,
                "disb_total": disb_total,
                "target_mob": target_mob,
                "forecast_mob_end": forecast_mob_end
            })
    
    if not results:
        print("\n⚠️ Không tìm thấy cohorts nào có đủ data")
        return None
    
    df = pd.DataFrame(results)
    
    # Thống kê
    print(f"\n📊 TỔNG HỢP:")
    print(f"   Tổng cohorts: {len(df)}")
    print(f"   Cohorts dùng fallback: {df['is_fallback'].sum()} ({df['is_fallback'].sum()/len(df)*100:.1f}%)")
    
    # Phân loại
    df["status"] = "✅ Match"
    df.loc[df["diff"] > 0.001, "status"] = "❌ Forecast > P_24"
    df.loc[df["diff"] < -0.001, "status"] = "⬇️ Forecast < P_24"
    
    n_match = len(df[abs(df["diff"]) <= 0.001])
    n_higher = len(df[df["diff"] > 0.001])
    n_lower = len(df[df["diff"] < -0.001])
    
    print(f"   - Forecast ≈ P_24 (diff < 0.1%): {n_match} ({n_match/len(df)*100:.1f}%)")
    print(f"   - Forecast > P_24 (diff > 0.1%): {n_higher} ({n_higher/len(df)*100:.1f}%)")
    print(f"   - Forecast < P_24 (diff < -0.1%): {n_lower} ({n_lower/len(df)*100:.1f}%)")
    
    # Thống kê số liệu
    print(f"\n📈 THỐNG KÊ:")
    print(f"   P_{target_mob} movement:")
    print(f"      Mean:   {df['p_mob_movement_pct'].mean():.4f}%")
    print(f"      Median: {df['p_mob_movement_pct'].median():.4f}%")
    print(f"      Min:    {df['p_mob_movement_pct'].min():.4f}%")
    print(f"      Max:    {df['p_mob_movement_pct'].max():.4f}%")
    
    print(f"\n   Forecast slope:")
    print(f"      Mean:   {df['forecast_slope_pct'].mean():.4f}%")
    print(f"      Median: {df['forecast_slope_pct'].median():.4f}%")
    print(f"      Min:    {df['forecast_slope_pct'].min():.4f}%")
    print(f"      Max:    {df['forecast_slope_pct'].max():.4f}%")
    
    print(f"\n   Diff (Forecast - P_24):")
    print(f"      Mean:   {df['diff_pct'].mean():.4f}%")
    print(f"      Median: {df['diff_pct'].median():.4f}%")
    print(f"      Min:    {df['diff_pct'].min():.4f}%")
    print(f"      Max:    {df['diff_pct'].max():.4f}%")
    
    # Top cohorts có diff lớn nhất
    print(f"\n" + "="*100)
    print(f"TOP 10 COHORTS CÓ FORECAST > P_{target_mob} NHIỀU NHẤT:")
    print("="*100)
    
    df_sorted = df.sort_values("diff", ascending=False).head(10)
    
    print(f"\n{'Product':<10} {'Score':<25} {'Vintage':<12} P_{target_mob:<10} {'Forecast':<10} {'Diff':<10} {'Fallback':<10}")
    print("-"*100)
    
    for idx, row in df_sorted.iterrows():
        fallback_str = "✓" if row["is_fallback"] else ""
        print(f"{row['product']:<10} {str(row['score']):<25} {str(row['vintage']):<12} "
              f"{row['p_mob_movement_pct']:>8.4f}% {row['forecast_slope_pct']:>8.4f}% "
              f"{row['diff_pct']:>8.4f}% {fallback_str:<10}")
    
    # Phân tích theo fallback
    print(f"\n" + "="*100)
    print(f"PHÂN TÍCH THEO FALLBACK:")
    print("="*100)
    
    df_no_fallback = df[~df["is_fallback"]]
    df_fallback = df[df["is_fallback"]]
    
    if len(df_no_fallback) > 0:
        print(f"\nCohorts KHÔNG dùng fallback ({len(df_no_fallback)}):")
        print(f"   P_{target_mob} movement:   {df_no_fallback['p_mob_movement_pct'].mean():.4f}%")
        print(f"   Forecast slope:  {df_no_fallback['forecast_slope_pct'].mean():.4f}%")
        print(f"   Diff:            {df_no_fallback['diff_pct'].mean():.4f}%")
    
    if len(df_fallback) > 0:
        print(f"\nCohorts DÙNG fallback ({len(df_fallback)}):")
        print(f"   P_{target_mob} movement:   {df_fallback['p_mob_movement_pct'].mean():.4f}%")
        print(f"   Forecast slope:  {df_fallback['forecast_slope_pct'].mean():.4f}%")
        print(f"   Diff:            {df_fallback['diff_pct'].mean():.4f}%")
    
    # Phân tích theo product
    print(f"\n" + "="*100)
    print(f"PHÂN TÍCH THEO PRODUCT:")
    print("="*100)
    
    for product in df["product"].unique():
        df_prod = df[df["product"] == product]
        print(f"\n{product}:")
        print(f"   N cohorts:       {len(df_prod)}")
        print(f"   P_{target_mob} movement:   {df_prod['p_mob_movement_pct'].mean():.4f}%")
        print(f"   Forecast slope:  {df_prod['forecast_slope_pct'].mean():.4f}%")
        print(f"   Diff:            {df_prod['diff_pct'].mean():.4f}%")
        print(f"   % Fallback:      {df_prod['is_fallback'].sum()/len(df_prod)*100:.1f}%")
    
    # Phân tích theo score
    print(f"\n" + "="*100)
    print(f"PHÂN TÍCH THEO SCORE:")
    print("="*100)
    
    score_analysis = df.groupby("score").agg({
        "p_mob_movement_pct": "mean",
        "forecast_slope_pct": "mean",
        "diff_pct": "mean",
        "is_fallback": ["sum", "count"],
        "disb_total": "sum"
    }).reset_index()
    
    score_analysis.columns = ["score", "p_mob_movement", "forecast_slope", "diff", "n_fallback", "n_total", "total_disb"]
    score_analysis["pct_fallback"] = score_analysis["n_fallback"] / score_analysis["n_total"] * 100
    score_analysis = score_analysis.sort_values("diff", ascending=False)
    
    print(f"\n{'Score':<25} P_{target_mob:<10} {'Forecast':<10} {'Diff':<10} {'% Fallback':<12} {'N Cohorts':<10}")
    print("-"*100)
    
    for idx, row in score_analysis.head(10).iterrows():
        print(f"{str(row['score']):<25} {row['p_mob_movement']:>8.4f}% {row['forecast_slope']:>8.4f}% "
              f"{row['diff']:>8.4f}% {row['pct_fallback']:>10.1f}% {row['n_total']:>8.0f}")
    
    # Kết luận
    print(f"\n" + "="*100)
    print(f"KẾT LUẬN:")
    print("="*100)
    
    avg_p_mob = df['p_mob_movement_pct'].mean()
    avg_forecast = df['forecast_slope_pct'].mean()
    avg_diff = df['diff_pct'].mean()
    
    print(f"\n📊 Trung bình:")
    print(f"   P_{target_mob} movement:   {avg_p_mob:.4f}% per month")
    print(f"   Forecast slope:  {avg_forecast:.4f}% per month")
    print(f"   Diff:            {avg_diff:.4f}% per month")
    
    if abs(avg_diff) < 0.05:
        print(f"\n✅ FORECAST MATCH VỚI P_{target_mob}!")
        print(f"   → Forecast slope ≈ P_{target_mob} movement")
        print(f"   → K = 1.0 đang work đúng")
        print(f"   → Vấn đề là P_{target_mob} có movement {avg_p_mob:.4f}%")
        print(f"   → Nếu muốn flatten, cần giảm K hoặc chấp nhận reality")
    elif avg_diff > 0.1:
        print(f"\n❌ FORECAST CAO HƠN P_{target_mob} NHIỀU!")
        print(f"   → Forecast slope cao hơn P_{target_mob} movement {avg_diff:.4f}%")
        print(f"   → Có vấn đề trong forecast logic hoặc K values")
        print(f"   → Cần kiểm tra lại code")
    else:
        print(f"\n⚠️ FORECAST HƠI CAO HƠN P_{target_mob}")
        print(f"   → Forecast slope cao hơn P_{target_mob} movement {avg_diff:.4f}%")
        print(f"   → Có thể do rounding hoặc partial-step formula")
    
    # Kiểm tra cohorts có diff lớn
    df_large_diff = df[df["diff_pct"] > 0.5]
    if len(df_large_diff) > 0:
        print(f"\n⚠️ CÓ {len(df_large_diff)} COHORTS CÓ DIFF > 0.5%:")
        print(f"   → Cần kiểm tra chi tiết các cohorts này")
        print(f"   → Có thể có vấn đề với forecast logic")
    
    print(f"\n" + "="*100)
    
    return df


if __name__ == "__main__":
    print("Chạy script này từ notebook với:")
    print("df_comparison = compare_p24_vs_forecast(")
    print("    matrices_by_mob=matrices_by_mob,")
    print("    forecast_results=forecast_results,")
    print("    actual_results=actual_results,")
    print("    disb_total_by_vintage=disb_total_by_vintage,")
    print("    buckets_30p=BUCKETS_30P")
    print(")")
