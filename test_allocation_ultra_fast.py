"""
test_allocation_ultra_fast.py
------------------------------
Benchmark allocation_v2_fast vs allocation_v2_ultra_fast

So sánh:
1. Thời gian chạy
2. Memory usage
3. Kết quả (phải giống nhau)
"""

import pandas as pd
import numpy as np
import time
import tracemalloc
from pathlib import Path

# Import both versions
from src.rollrate.allocation_v2_fast import allocate_multi_mob_fast
from src.rollrate.allocation_v2_ultra_fast import allocate_multi_mob_ultra_fast
from src.rollrate.lifecycle import build_lifecycle
from src.rollrate.transition import build_matrices_by_mob
from src.data_loader import load_data_from_parquet


def benchmark_allocation():
    """
    Benchmark allocation performance.
    """
    
    print("="*60)
    print("🔬 BENCHMARK: allocation_v2_fast vs allocation_v2_ultra_fast")
    print("="*60)
    
    # ===================================================
    # BƯỚC 1: Load data
    # ===================================================
    print("\n📂 Loading data...")
    
    data_path = Path("ETB_Parquet_YYYYMM")
    
    if not data_path.exists():
        print(f"❌ Data path not found: {data_path}")
        return
    
    df_raw = load_data_from_parquet(str(data_path))
    
    if df_raw.empty:
        print("❌ No data loaded")
        return
    
    print(f"   ✅ Loaded {len(df_raw):,} rows")
    
    # ===================================================
    # BƯỚC 2: Build transition matrices
    # ===================================================
    print("\n🔨 Building transition matrices...")
    
    matrices_by_mob, parent_fallback = build_matrices_by_mob(
        df_raw,
        roll_window=12,
        decay_lambda=0.9,
        min_obs=30,
        min_ead=1e6,
    )
    
    print(f"   ✅ Built matrices for {len(matrices_by_mob)} products")
    
    # ===================================================
    # BƯỚC 3: Build lifecycle
    # ===================================================
    print("\n📊 Building lifecycle...")
    
    df_lifecycle = build_lifecycle(
        df_raw,
        matrices_by_mob,
        parent_fallback=parent_fallback,
        enable_macro=False,
    )
    
    print(f"   ✅ Built lifecycle: {len(df_lifecycle):,} rows")
    
    # ===================================================
    # BƯỚC 4: Get latest snapshot
    # ===================================================
    print("\n📸 Getting latest snapshot...")
    
    latest_cutoff = df_raw['CUTOFF_DATE'].max()
    df_loans_latest = df_raw[df_raw['CUTOFF_DATE'] == latest_cutoff].copy()
    
    print(f"   ✅ Latest snapshot @ {latest_cutoff}: {len(df_loans_latest):,} loans")
    
    # Limit to 50k loans for faster testing
    if len(df_loans_latest) > 50000:
        print(f"   ⚠️  Limiting to 50k loans for testing")
        df_loans_latest = df_loans_latest.sample(n=50000, random_state=42)
    
    # ===================================================
    # BƯỚC 5: Benchmark allocation_v2_fast
    # ===================================================
    print("\n" + "="*60)
    print("🏃 BENCHMARK 1: allocation_v2_fast (current)")
    print("="*60)
    
    # Start memory tracking
    tracemalloc.start()
    
    # Start timer
    start_time = time.time()
    
    # Run allocation
    df_result_fast = allocate_multi_mob_fast(
        df_loans_latest=df_loans_latest,
        df_lifecycle_final=df_lifecycle,
        matrices_by_mob=matrices_by_mob,
        target_mobs=[12, 24],
        parent_fallback=parent_fallback,
        seed=42,
    )
    
    # End timer
    end_time = time.time()
    elapsed_fast = end_time - start_time
    
    # Get memory usage
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"\n⏱️  Time: {elapsed_fast:.2f} seconds")
    print(f"💾 Memory: {peak_mem / 1024 / 1024:.2f} MB (peak)")
    
    # ===================================================
    # BƯỚC 6: Benchmark allocation_v2_ultra_fast
    # ===================================================
    print("\n" + "="*60)
    print("🚀 BENCHMARK 2: allocation_v2_ultra_fast (new)")
    print("="*60)
    
    # Start memory tracking
    tracemalloc.start()
    
    # Start timer
    start_time = time.time()
    
    # Run allocation
    df_result_ultra = allocate_multi_mob_ultra_fast(
        df_loans_latest=df_loans_latest,
        df_lifecycle_final=df_lifecycle,
        matrices_by_mob=matrices_by_mob,
        target_mobs=[12, 24],
        parent_fallback=parent_fallback,
        seed=42,
    )
    
    # End timer
    end_time = time.time()
    elapsed_ultra = end_time - start_time
    
    # Get memory usage
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"\n⏱️  Time: {elapsed_ultra:.2f} seconds")
    print(f"💾 Memory: {peak_mem / 1024 / 1024:.2f} MB (peak)")
    
    # ===================================================
    # BƯỚC 7: Compare results
    # ===================================================
    print("\n" + "="*60)
    print("📊 COMPARISON")
    print("="*60)
    
    speedup = elapsed_fast / elapsed_ultra
    
    print(f"\n⏱️  Speed:")
    print(f"   allocation_v2_fast: {elapsed_fast:.2f}s")
    print(f"   allocation_v2_ultra_fast: {elapsed_ultra:.2f}s")
    print(f"   Speedup: {speedup:.2f}x {'✅' if speedup > 1 else '❌'}")
    
    # Compare results
    print(f"\n📋 Results:")
    print(f"   Fast version: {len(df_result_fast):,} loans")
    print(f"   Ultra version: {len(df_result_ultra):,} loans")
    
    # Check if results are similar
    if len(df_result_fast) == len(df_result_ultra):
        # Compare EAD_FORECAST
        for mob in [12, 24]:
            col = f'EAD_FORECAST_MOB{mob}'
            
            if col in df_result_fast.columns and col in df_result_ultra.columns:
                ead_fast = df_result_fast[col].sum()
                ead_ultra = df_result_ultra[col].sum()
                
                diff_pct = abs(ead_fast - ead_ultra) / ead_fast * 100
                
                print(f"\n   MOB {mob}:")
                print(f"      Fast: {ead_fast:,.0f}")
                print(f"      Ultra: {ead_ultra:,.0f}")
                print(f"      Diff: {diff_pct:.4f}% {'✅' if diff_pct < 0.01 else '⚠️'}")
    
    # ===================================================
    # BƯỚC 8: Summary
    # ===================================================
    print("\n" + "="*60)
    print("🎯 SUMMARY")
    print("="*60)
    
    if speedup > 5:
        print(f"\n✅ ULTRA FAST version is {speedup:.1f}x FASTER!")
        print(f"   Recommend: Switch to allocation_v2_ultra_fast")
    elif speedup > 2:
        print(f"\n✅ ULTRA FAST version is {speedup:.1f}x faster")
        print(f"   Recommend: Consider switching to allocation_v2_ultra_fast")
    elif speedup > 1:
        print(f"\n⚠️  ULTRA FAST version is only {speedup:.1f}x faster")
        print(f"   Recommend: Keep current version")
    else:
        print(f"\n❌ ULTRA FAST version is SLOWER ({speedup:.1f}x)")
        print(f"   Recommend: Keep current version")


if __name__ == "__main__":
    benchmark_allocation()
