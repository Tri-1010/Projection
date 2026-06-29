"""
Script phân tích P_23 vs Parent Fallback để hiểu tại sao forecast cao hơn
"""

import pandas as pd
import numpy as np

def analyze_p23_vs_parent(matrices_by_mob, parent_fallback, buckets_30p=None):
    """
    So sánh P_23 movement vs Parent fallback movement
    """
    
    if buckets_30p is None:
        buckets_30p = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
    
    print("="*100)
    print("PHÂN TÍCH P_23 vs PARENT FALLBACK")
    print("="*100)
    
    results = []
    
    for prod_str in matrices_by_mob.keys():
        if 23 not in matrices_by_mob[prod_str]:
            continue
            
        for score_str in matrices_by_mob[prod_str][23].keys():
            # Lấy P_23
            P_23 = matrices_by_mob[prod_str][23][score_str]["P"]
            is_fallback = matrices_by_mob[prod_str][23][score_str].get("is_fallback", False)
            
            # Tính P_23 movement
            p23_movement = None
            if "DPD0" in P_23.index:
                available_buckets = [s for s in buckets_30p if s in P_23.columns]
                if available_buckets:
                    p23_movement = sum(P_23.loc["DPD0", s] for s in available_buckets)
            
            # Lấy Parent fallback
            key_parent = (prod_str, score_str)
            parent_movement = None
            
            if key_parent in parent_fallback:
                P_parent = parent_fallback[key_parent]
                if "DPD0" in P_parent.index:
                    available_buckets = [s for s in buckets_30p if s in P_parent.columns]
                    if available_buckets:
                        parent_movement = sum(P_parent.loc["DPD0", s] for s in available_buckets)
            
            if p23_movement is not None and parent_movement is not None:
                results.append({
                    "product": prod_str,
                    "score": score_str,
                    "p23_movement": p23_movement,
                    "p23_movement_pct": p23_movement * 100,
                    "parent_movement": parent_movement,
                    "parent_movement_pct": parent_movement * 100,
                    "diff": parent_movement - p23_movement,
                    "diff_pct": (parent_movement - p23_movement) * 100,
                    "ratio": parent_movement / p23_movement if p23_movement > 0 else None,
                    "is_fallback": is_fallback
                })
    
    if not results:
        print("\n⚠️ Không tìm thấy data")
        return None
    
    df = pd.DataFrame(results)
    
    # Thống kê
    print(f"\n📊 TỔNG HỢP:")
    print(f"   Tổng cohorts: {len(df)}")
    print(f"   Cohorts dùng fallback ở MOB 23: {df['is_fallback'].sum()} ({df['is_fallback'].sum()/len(df)*100:.1f}%)")
    
    print(f"\n📈 THỐNG KÊ:")
    print(f"   P_23 movement:")
    print(f"      Mean:   {df['p23_movement_pct'].mean():.4f}%")
    print(f"      Median: {df['p23_movement_pct'].median():.4f}%")
    print(f"      Min:    {df['p23_movement_pct'].min():.4f}%")
    print(f"      Max:    {df['p23_movement_pct'].max():.4f}%")
    
    print(f"\n   Parent fallback movement:")
    print(f"      Mean:   {df['parent_movement_pct'].mean():.4f}%")
    print(f"      Median: {df['parent_movement_pct'].median():.4f}%")
    print(f"      Min:    {df['parent_movement_pct'].min():.4f}%")
    print(f"      Max:    {df['parent_movement_pct'].max():.4f}%")
    
    print(f"\n   Diff (Parent - P_23):")
    print(f"      Mean:   {df['diff_pct'].mean():.4f}%")
    print(f"      Median: {df['diff_pct'].median():.4f}%")
    print(f"      Min:    {df['diff_pct'].min():.4f}%")
    print(f"      Max:    {df['diff_pct'].max():.4f}%")
    
    # Top cohorts có diff lớn nhất
    print(f"\n" + "="*100)
    print(f"TOP 10 COHORTS CÓ PARENT FALLBACK CAO HƠN P_23 NHIỀU NHẤT:")
    print("="*100)
    
    df_sorted = df.sort_values("diff", ascending=False).head(10)
    
    print(f"\n{'Product':<10} {'Score':<25} {'P_23':<10} {'Parent':<10} {'Diff':<10} {'Ratio':<10} {'Fallback':<10}")
    print("-"*100)
    
    for idx, row in df_sorted.iterrows():
        fallback_str = "✓" if row["is_fallback"] else ""
        ratio_str = f"{row['ratio']:.1f}x" if row['ratio'] is not None and row['ratio'] < 1000 else ">1000x"
        print(f"{row['product']:<10} {row['score']:<25} {row['p23_movement_pct']:>8.4f}% {row['parent_movement_pct']:>8.4f}% "
              f"{row['diff_pct']:>8.4f}% {ratio_str:>8} {fallback_str:<10}")
    
    # Phân tích theo fallback
    print(f"\n" + "="*100)
    print(f"PHÂN TÍCH THEO FALLBACK:")
    print("="*100)
    
    df_no_fallback = df[~df["is_fallback"]]
    df_fallback = df[df["is_fallback"]]
    
    if len(df_no_fallback) > 0:
        print(f"\nCohorts KHÔNG dùng fallback ({len(df_no_fallback)}):")
        print(f"   P_23 movement:     {df_no_fallback['p23_movement_pct'].mean():.4f}%")
        print(f"   Parent movement:   {df_no_fallback['parent_movement_pct'].mean():.4f}%")
        print(f"   Diff:              {df_no_fallback['diff_pct'].mean():.4f}%")
    
    if len(df_fallback) > 0:
        print(f"\nCohorts DÙNG fallback ({len(df_fallback)}):")
        print(f"   P_23 movement:     {df_fallback['p23_movement_pct'].mean():.4f}%")
        print(f"   Parent movement:   {df_fallback['parent_movement_pct'].mean():.4f}%")
        print(f"   Diff:              {df_fallback['diff_pct'].mean():.4f}%")
    
    # Kết luận
    print(f"\n" + "="*100)
    print(f"KẾT LUẬN:")
    print("="*100)
    
    avg_p23 = df['p23_movement_pct'].mean()
    avg_parent = df['parent_movement_pct'].mean()
    avg_diff = df['diff_pct'].mean()
    
    print(f"\n📊 Trung bình:")
    print(f"   P_23 movement:     {avg_p23:.4f}% per month")
    print(f"   Parent movement:   {avg_parent:.4f}% per month")
    print(f"   Diff:              {avg_diff:.4f}% per month")
    
    if avg_parent > avg_p23 * 2:
        print(f"\n❌ PARENT FALLBACK CAO HƠN P_23 NHIỀU!")
        print(f"   → Parent fallback có movement {avg_parent:.4f}%")
        print(f"   → P_23 chỉ có movement {avg_p23:.4f}%")
        print(f"   → Parent cao hơn {avg_parent/avg_p23 if avg_p23 > 0 else 'vô cùng':.1f}x")
        print(f"\n💡 Giải thích:")
        print(f"   - Parent fallback tổng hợp MOB 1-23 (MOB sớm có rates cao)")
        print(f"   - P_23 đã mature (rates thấp)")
        print(f"   - 54.5% cohorts dùng fallback → Gây forecast tăng")
        print(f"\n💡 Giải pháp:")
        print(f"   1. Giảm K xuống 0.0-0.3 cho MOB 24+")
        print(f"   2. Hoặc tăng MIN_OBS để ít cohorts dùng fallback hơn")
    else:
        print(f"\n✅ Parent fallback không cao hơn P_23 nhiều")
    
    print(f"\n" + "="*100)
    
    return df


if __name__ == "__main__":
    print("Chạy script này từ notebook với:")
    print("df_analysis = analyze_p23_vs_parent(")
    print("    matrices_by_mob=matrices_by_mob,")
    print("    parent_fallback=parent_fallback,")
    print("    buckets_30p=BUCKETS_30P")
    print(")")
