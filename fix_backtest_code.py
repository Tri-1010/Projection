# ============================================================
# 7.3 BACKTEST: Compare Forecast vs Actual
# ============================================================

print("🔄 Running backtest comparison...")

# Get cohorts that have actual data at multiple MOBs
backtest_results = []

for (product, score, vintage), actual_data in actual_results.items():
    max_actual_mob = max(actual_data.keys())
    
    if max_actual_mob < 6:  # Need at least 6 MOBs for meaningful comparison
        continue
    
    # For each MOB, compare actual vs what forecast would have predicted
    for mob in range(3, max_actual_mob + 1):
        if mob not in actual_data:
            continue
        
        actual_amounts = actual_data[mob]
        
        # actual_amounts is a pd.Series, not dict
        # Calculate DEL30+ from actual
        del30_actual = 0
        for s in BUCKETS_30P:
            if s in actual_amounts.index:
                del30_actual += actual_amounts[s]
        
        total_actual = actual_amounts.sum()
        
        if total_actual > 0:
            del30_rate_actual = del30_actual / total_actual
        else:
            del30_rate_actual = 0
        
        backtest_results.append({
            'product': product,
            'score': score,
            'vintage': vintage,
            'mob': mob,
            'del30_actual': del30_actual,
            'total_actual': total_actual,
            'del30_rate': del30_rate_actual,
        })

df_backtest = pd.DataFrame(backtest_results)

print(f"✅ Backtest data: {len(df_backtest):,} observations")
print(f"   Products: {df_backtest['product'].nunique()}")
print(f"   MOB range: {df_backtest['mob'].min()} - {df_backtest['mob'].max()}")
