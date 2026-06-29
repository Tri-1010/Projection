"""
test_allocation_quick.py
-------------------------
Quick test allocation_v2_fast vs allocation_v2_ultra_fast
Chỉ test với sample nhỏ để nhanh
"""

import pandas as pd
import numpy as np
import time
from pathlib import Path

# Import both versions
from src.rollrate.allocation_v2_fast import allocate_fast
from src.rollrate.allocation_v2_ultra_fast import allocate_ultra_fast
from src.config import CFG, BUCKETS_CANON


def create_sample_data(n_loans=1000, n_cohorts=10):
    """
    Tạo sample data để test.
    """
    
    print(f"📊 Creating sample data: {n_loans} loans, {n_cohorts} cohorts")
    
    # Sample loans
    np.random.seed(42)
    
    products = ['SALPIL', 'CDLPIL', 'TWLPIL']
    scores = ['A', 'B', 'C', 'D']
    states = ['DPD0', 'DPD1+', 'DPD30+', 'DPD60+', 'DPD90+']
    
    df_loans = pd.DataFrame({
        CFG['loan']: [f'LOAN_{i:06d}' for i in range(n_loans)],
        'PRODUCT_TYPE': np.random.choice(products, n_loans),
        'RISK_SCORE': np.random.choice(scores, n_loans),
        'VINTAGE_DATE': pd.date_range('2024-01-01', periods=n_cohorts, freq='MS')[np.random.randint(0, n_cohorts, n_loans)],
        CFG['state']: np.random.choice(states, n_loans, p=[0.7, 0.15, 0.08, 0.05, 0.02]),
        CFG['mob']: np.random.randint(1, 12, n_loans),
        CFG['ead']: np.random.uniform(10000, 100000, n_loans),
        'DISBURSAL_AMOUNT': np.random.uniform(10000, 100000, n_loans),
    })
    
    # Sample lifecycle
    df_lifecycle = []
    
    for product in products:
        for score in scores:
            for vintage in pd.date_range('2024-01-01', periods=n_cohorts, freq='MS'):
                for mob in [12, 24]:
                    row = {
                        'PRODUCT_TYPE': product,
                        'RISK_SCORE': score,
                        'VINTAGE_DATE': vintage,
                        'MOB': mob,
                        'IS_FORECAST': 0,
                        'DEL30_PCT': np.random.uniform(0.05, 0.15),
                        'DEL90_PCT': np.random.uniform(0.02, 0.08),
                    }
                    
                    # Add state columns
                    total_ead = 100000
                    for state in BUCKETS_CANON:
                        if state == 'DPD0':
                            row[state] = total_ead * 0.7
                        elif state == 'DPD1+':
                            row[state] = total_ead * 0.15
                        elif state == 'DPD30+':
                            row[state] = total_ead * 0.08
                        elif state == 'DPD60+':
                            row[state] = total_ead * 0.05
                        elif state == 'DPD90+':
                            row[state] = total_ead * 0.02
                        else:
                            row[state] = 0
                    
                    df_lifecycle.append(row)
    
    df_lifecycle = pd.DataFrame(df_lifecycle)
    
    print(f"   ✅ Created {len(df_loans):,} loans")
    print(f"   ✅ Created {len(df_lifecycle):,} lifecycle rows")
    
    return df_loans, df_lifecycle


def create_dummy_matrices(df_loans):
    """
    Tạo dummy transition matrices.
    """
    
    print("🔨 Creating dummy matrices...")
    
    matrices_by_mob = {}
    
    products = df_loans['PRODUCT_TYPE'].unique()
    scores = df_loans['RISK_SCORE'].unique()
    
    n_states = len(BUCKETS_CANON)
    
    for product in products:
        matrices_by_mob[product] = {}
        
        for mob in range(1, 25):
            matrices_by_mob[product][mob] = {}
            
            for score in scores:
                # Create identity matrix (no transition)
                P = pd.DataFrame(
                    np.eye(n_states),
                    index=BUCKETS_CANON,
                    columns=BUCKETS_CANON
                )
                
                matrices_by_mob[product][mob][score] = {"P": P}
    
    # Parent fallback
    parent_fallback = {}
    for product in products:
        for score in scores:
            P = pd.DataFrame(
                np.eye(n_states),
                index=BUCKETS_CANON,
                columns=BUCKETS_CANON
            )
            parent_fallback[(product, score)] = P
    
    print(f"   ✅ Created matrices for {len(products)} products")
    
    return matrices_by_mob, parent_fallback


def benchmark_quick():
    """
    Quick benchmark.
    """
    
    print("="*60)
    print("🔬 QUICK BENCHMARK: allocation_v2_fast vs allocation_v2_ultra_fast")
    print("="*60)
    
    # Create sample data
    df_loans, df_lifecycle = create_sample_data(n_loans=5000, n_cohorts=10)
    matrices_by_mob, parent_fallback = create_dummy_matrices(df_loans)
    
    target_mob = 12
    
    # ===================================================
    # BENCHMARK 1: allocation_v2_fast
    # ===================================================
    print("\n" + "="*60)
    print("🏃 BENCHMARK 1: allocation_v2_fast (current)")
    print("="*60)
    
    start_time = time.time()
    
    df_result_fast = allocate_fast(
        df_loans_latest=df_loans,
        df_lifecycle_final=df_lifecycle,
        matrices_by_mob=matrices_by_mob,
        target_mob=target_mob,
        parent_fallback=parent_fallback,
        seed=42,
    )
    
    elapsed_fast = time.time() - start_time
    
    print(f"\n⏱️  Time: {elapsed_fast:.2f} seconds")
    
    # ===================================================
    # BENCHMARK 2: allocation_v2_ultra_fast
    # ===================================================
    print("\n" + "="*60)
    print("🚀 BENCHMARK 2: allocation_v2_ultra_fast (new)")
    print("="*60)
    
    start_time = time.time()
    
    df_result_ultra = allocate_ultra_fast(
        df_loans_latest=df_loans,
        df_lifecycle_final=df_lifecycle,
        matrices_by_mob=matrices_by_mob,
        target_mob=target_mob,
        parent_fallback=parent_fallback,
        seed=42,
    )
    
    elapsed_ultra = time.time() - start_time
    
    print(f"\n⏱️  Time: {elapsed_ultra:.2f} seconds")
    
    # ===================================================
    # COMPARISON
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
    
    if len(df_result_fast) == len(df_result_ultra):
        ead_fast = df_result_fast['EAD_FORECAST'].sum()
        ead_ultra = df_result_ultra['EAD_FORECAST'].sum()
        
        diff_pct = abs(ead_fast - ead_ultra) / ead_fast * 100 if ead_fast > 0 else 0
        
        print(f"\n   EAD_FORECAST:")
        print(f"      Fast: {ead_fast:,.0f}")
        print(f"      Ultra: {ead_ultra:,.0f}")
        print(f"      Diff: {diff_pct:.4f}% {'✅' if diff_pct < 1 else '⚠️'}")
    
    # ===================================================
    # SUMMARY
    # ===================================================
    print("\n" + "="*60)
    print("🎯 SUMMARY")
    print("="*60)
    
    if speedup > 5:
        print(f"\n✅ ULTRA FAST version is {speedup:.1f}x FASTER!")
        print(f"   Recommend: Switch to allocation_v2_ultra_fast")
    elif speedup > 2:
        print(f"\n✅ ULTRA FAST version is {speedup:.1f}x faster")
        print(f"   Recommend: Consider switching")
    elif speedup > 1:
        print(f"\n⚠️  ULTRA FAST version is only {speedup:.1f}x faster")
        print(f"   Recommend: Test with larger dataset")
    else:
        print(f"\n❌ ULTRA FAST version is SLOWER ({speedup:.1f}x)")
        print(f"   Recommend: Keep current version")
    
    print(f"\n💡 Note: This is a quick test with sample data.")
    print(f"   For accurate results, test with real data using test_allocation_ultra_fast.py")


if __name__ == "__main__":
    try:
        benchmark_quick()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
