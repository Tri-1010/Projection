"""
Script so sánh DEL tích lũy (cumulative) để hiểu forecast
"""

import pandas as pd
import numpy as np

def compare_cumulative_del(
    forecast_results,
    actual_results,
    disb_total_by_vintage,
    buckets_30p=None,
    target_mob=23,
    forecast_mob_end=29
):
    """
    So sánh DEL tích lũy (cumulative) thay vì transition rate
    """
    
    if buckets_30p is None:
        buckets_30p = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
    
    print("="*100)
    print(f"SO SÁNH DEL TÍCH LŨY (CUMULATIVE) - MOB {target_mob} vs MOB {forecast_mob_end}")
    print("="*100)
    
    results = []
    
    for cohort_key in forecast_results.keys():
        product, score, vintage = cohort_key
        
        forecast = forecast_results[cohort_key]
        disb_total = disb_total_by_vintage.get(cohort_key, 1.0)
        
        if target_mob not in forecast or forecast_mob_end not in forecast or disb_total <= 0:
            continue
        
        # Lấy DEL tích lũy
        available_buckets_start = [s for s in buckets_30p if s in forecast[target_mob].index]
        available_buckets_end = [s for s in buckets_30p if s in forecast[forecast_mob_end].index]
        
        if not available_buckets_start or not available_buckets_end:
            continue
        
        del_cumulative_start = forecast[target_mob][available_buckets_start].sum() / disb_total
        del_cumulative_end = forecast[forecast_mob_end][available_buckets_end].sum() / disb_total
        
        # Tính slope (tăng thêm bao nhiêu % per month)
        slope = (del_cumulative_end - del_cumulative_start) / (forecast_mob_end - target_mob)
        
        # Tính % tăng so với MOB 23
        pct_increase = (del_cumulative_end - del_cumulative_start) / del_cumulative_start * 100 if del_cumulative_start > 0 else None
        
        results.append({
            "product": product,
            "score": score,
            "vintage": vintage,
            "del_mob_start": del_cumulative_start,
            "del_mob_start_pct": del_cumulative_start * 100,
            "del_mob_end": del_cumulative_end,
            "del_mob_end_pct": del_cumulative_end * 100,
            "slope": slope,
            "slope_pct": slope * 100,
            "pct_increase": pct_increase,
            "disb_total": disb_total
        })
    
    if not results:
        print("\n⚠️ Không tìm thấy data")
        return None
    
    df = pd.DataFrame(results)
    
    # Thống kê
    print(f"\n📊 TỔNG HỢP:")
    print(f"   Tổng cohorts: {len(df)}")
    
    print(f"\n📈 THỐNG KÊ:")
    print(f"   DEL tích lũy tại MOB {target_mob}:")
    print(f"      Mean:   {df['del_mob_start_pct'].mean():.2f}%")
    print(f"      Median: {df['del_mob_start_pct'].median():.2f}%")
    print(f"      Min:    {df['del_mob_start_pct'].min():.2f}%")
    print(f"      Max:    {df['del_mob_start_pct'].max():.2f}%")
    
    print(f"\n   DEL tích lũy tại MOB {forecast_mob_end}:")
    print(f"      Mean:   {df['del_mob_end_pct'].mean():.2f}%")
    print(f"      Median: {df['del_mob_end_pct'].median():.2f}%")
    print(f"      Min:    {df['del_mob_end_pct'].min():.2f}%")
    print(f"      Max:    {df['del_mob_end_pct'].max():.2f}%")
    
    print(f"\n   Slope (tăng thêm per month):")
    print(f"      Mean:   {df['slope_pct'].mean():.4f}%")
    print(f"      Median: {df['slope_pct'].median():.4f}%")
    print(f"      Min:    {df['slope_pct'].min():.4f}%")
    print(f"      Max:    {df['slope_pct'].max():.4f}%")
    
    print(f"\n   % Tăng (MOB {target_mob} → {forecast_mob_end}):")
    print(f"      Mean:   {df['pct_increase'].mean():.2f}%")
    print(f"      Median: {df['pct_increase'].median():.2f}%")
    print(f"      Min:    {df['pct_increase'].min():.2f}%")
    print(f"      Max:    {df['pct_increase'].max():.2f}%")
    
    # Kết luận
    print(f"\n" + "="*100)
    print(f"KẾT LUẬN:")
    print("="*100)
    
    avg_del_start = df['del_mob_start_pct'].mean()
    avg_del_end = df['del_mob_end_pct'].mean()
    avg_slope = df['slope_pct'].mean()
    avg_pct_increase = df['pct_increase'].mean()
    
    print(f"\n📊 Trung bình:")
    print(f"   DEL tích lũy tại MOB {target_mob}:  {avg_del_start:.2f}%")
    print(f"   DEL tích lũy tại MOB {forecast_mob_end}:  {avg_del_end:.2f}%")
    print(f"   Slope (tăng thêm):      {avg_slope:.4f}% per month")
    print(f"   % Tăng tổng:            {avg_pct_increase:.2f}%")
    
    print(f"\n💡 Giải thích:")
    print(f"   - DEL tích lũy = Tổng accounts ở DEL30+ từ MOB 1 đến MOB hiện tại")
    print(f"   - Slope = Tăng thêm bao nhiêu % per month")
    print(f"   - Slope {avg_slope:.4f}% = Forecast slope bạn thấy trước đó!")
    
    if avg_slope > 0.5:
        print(f"\n⚠️ SLOPE CAO ({avg_slope:.4f}%/month):")
        print(f"   → DEL tích lũy tăng {avg_slope:.4f}% mỗi tháng")
        print(f"   → Từ MOB {target_mob} → {forecast_mob_end}: Tăng {avg_pct_increase:.2f}%")
        print(f"   → Đây là do K values cao hoặc transition rates cao")
    elif avg_slope > 0.1:
        print(f"\n⚠️ SLOPE TRUNG BÌNH ({avg_slope:.4f}%/month):")
        print(f"   → DEL tích lũy tăng nhẹ")
    else:
        print(f"\n✅ SLOPE THẤP ({avg_slope:.4f}%/month):")
        print(f"   → DEL tích lũy gần như flatten")
    
    print(f"\n" + "="*100)
    
    return df


if __name__ == "__main__":
    print("Chạy script này từ notebook với:")
    print("df_cumulative = compare_cumulative_del(")
    print("    forecast_results=forecast_results,")
    print("    actual_results=actual_results,")
    print("    disb_total_by_vintage=disb_total_by_vintage,")
    print("    buckets_30p=BUCKETS_30P,")
    print("    target_mob=23,")
    print("    forecast_mob_end=29")
    print(")")
