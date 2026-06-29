"""
Demo script để minh họa allocation logic
Hiển thị cách phân bổ EAD theo tỉ lệ EAD_CURRENT
"""

import pandas as pd
import numpy as np

print("="*80)
print("DEMO: ALLOCATION LOGIC")
print("="*80)

# ============================
# SETUP: Giả lập data
# ============================
print("\n📊 SETUP: Cohort data")
print("-"*80)

# Lifecycle forecast @ MOB 24
lifecycle_forecast = {
    'DPD0': 1000,
    'DPD1+': 150,
    'DPD30+': 200,
    'DPD60+': 50,
    'DPD90+': 30,
}

print("\n1️⃣ Lifecycle Forecast @ MOB 24:")
for state, ead in lifecycle_forecast.items():
    print(f"   {state:10s}: {ead:8.0f}")

# Loans hiện tại @ MOB 20
loans_data = [
    {'LOAN_ID': 'LOAN_001', 'STATE_CURRENT': 'DPD0', 'EAD_CURRENT': 300},
    {'LOAN_ID': 'LOAN_002', 'STATE_CURRENT': 'DPD0', 'EAD_CURRENT': 400},
    {'LOAN_ID': 'LOAN_003', 'STATE_CURRENT': 'DPD0', 'EAD_CURRENT': 100},
    {'LOAN_ID': 'LOAN_004', 'STATE_CURRENT': 'DPD1+', 'EAD_CURRENT': 80},
    {'LOAN_ID': 'LOAN_005', 'STATE_CURRENT': 'DPD30+', 'EAD_CURRENT': 50},
    {'LOAN_ID': 'LOAN_006', 'STATE_CURRENT': 'DPD30+', 'EAD_CURRENT': 50},
]

df_loans = pd.DataFrame(loans_data)

print("\n2️⃣ Loans hiện tại @ MOB 20:")
print(df_loans.to_string(index=False))

# ============================
# BƯỚC 1: Assign STATE_FORECAST
# ============================
print("\n" + "="*80)
print("BƯỚC 1: ASSIGN STATE_FORECAST (Transition Matrix)")
print("="*80)

# Giả lập transition probabilities
# (Trong thực tế, tính từ transition matrix)
transition_probs = {
    'LOAN_001': {'DPD0': 0.85, 'DPD1+': 0.10, 'DPD30+': 0.03, 'DPD60+': 0.01, 'DPD90+': 0.01},
    'LOAN_002': {'DPD0': 0.85, 'DPD1+': 0.10, 'DPD30+': 0.03, 'DPD60+': 0.01, 'DPD90+': 0.01},
    'LOAN_003': {'DPD0': 0.70, 'DPD1+': 0.15, 'DPD30+': 0.10, 'DPD60+': 0.03, 'DPD90+': 0.02},
    'LOAN_004': {'DPD0': 0.50, 'DPD1+': 0.30, 'DPD30+': 0.15, 'DPD60+': 0.03, 'DPD90+': 0.02},
    'LOAN_005': {'DPD0': 0.10, 'DPD1+': 0.20, 'DPD30+': 0.40, 'DPD60+': 0.20, 'DPD90+': 0.10},
    'LOAN_006': {'DPD0': 0.10, 'DPD1+': 0.20, 'DPD30+': 0.40, 'DPD60+': 0.20, 'DPD90+': 0.10},
}

print("\n📊 Transition Probabilities (STATE_CURRENT → STATE @ MOB 24):")
print("-"*80)
for loan_id, probs in transition_probs.items():
    state_current = df_loans[df_loans['LOAN_ID'] == loan_id]['STATE_CURRENT'].values[0]
    print(f"\n{loan_id} (Current: {state_current}):")
    for state, prob in probs.items():
        print(f"   → {state:10s}: {prob*100:5.1f}%")

# Sample states (giả lập random sampling)
np.random.seed(42)
state_forecast_map = {
    'LOAN_001': 'DPD0',    # Sampled từ probs
    'LOAN_002': 'DPD0',    # Sampled từ probs
    'LOAN_003': 'DPD30+',  # Sampled từ probs (unlucky!)
    'LOAN_004': 'DPD1+',   # Sampled từ probs
    'LOAN_005': 'DPD30+',  # Sampled từ probs
    'LOAN_006': 'DPD60+',  # Sampled từ probs
}

df_loans['STATE_FORECAST'] = df_loans['LOAN_ID'].map(state_forecast_map)

print("\n✅ STATE_FORECAST assigned:")
print(df_loans[['LOAN_ID', 'STATE_CURRENT', 'STATE_FORECAST', 'EAD_CURRENT']].to_string(index=False))

# ============================
# BƯỚC 2: Phân bổ EAD
# ============================
print("\n" + "="*80)
print("BƯỚC 2: PHÂN BỔ EAD (Proportional by EAD_CURRENT)")
print("="*80)

# Group loans by STATE_FORECAST
grouped = df_loans.groupby('STATE_FORECAST')

print("\n📊 Phân bổ EAD cho từng state:")
print("-"*80)

df_loans['EAD_FORECAST'] = 0.0

for state, group in grouped:
    print(f"\n🔹 State: {state}")
    
    # EAD target từ lifecycle
    ead_target = lifecycle_forecast.get(state, 0)
    print(f"   EAD target (lifecycle): {ead_target:,.0f}")
    
    # Tổng EAD_CURRENT của loans trong state này
    total_ead_current = group['EAD_CURRENT'].sum()
    print(f"   Total EAD_CURRENT: {total_ead_current:,.0f}")
    
    # Tính ratio
    if total_ead_current > 0:
        ratio = ead_target / total_ead_current
    else:
        ratio = 0
    
    print(f"   Ratio: {ratio:.4f}")
    
    # Phân bổ cho từng loan
    print(f"\n   Loans trong {state}:")
    print(f"   {'LOAN_ID':<12} {'EAD_CURRENT':>12} {'×':>3} {'Ratio':>8} {'=':>3} {'EAD_FORECAST':>12}")
    print(f"   {'-'*12} {'-'*12} {'-'*3} {'-'*8} {'-'*3} {'-'*12}")
    
    for idx, row in group.iterrows():
        loan_id = row['LOAN_ID']
        ead_current = row['EAD_CURRENT']
        ead_forecast = ead_current * ratio
        
        df_loans.loc[df_loans['LOAN_ID'] == loan_id, 'EAD_FORECAST'] = ead_forecast
        
        print(f"   {loan_id:<12} {ead_current:>12.0f} {'×':>3} {ratio:>8.4f} {'=':>3} {ead_forecast:>12.2f}")
    
    # Verify tổng
    total_ead_forecast = group['EAD_CURRENT'].sum() * ratio
    print(f"   {'-'*12} {'-'*12} {'-'*3} {'-'*8} {'-'*3} {'-'*12}")
    print(f"   {'TOTAL':<12} {total_ead_current:>12.0f} {'':>3} {'':>8} {'':>3} {total_ead_forecast:>12.2f}")
    
    # Check match với lifecycle
    diff = abs(total_ead_forecast - ead_target)
    if diff < 0.01:
        print(f"   ✅ Match với lifecycle! (diff = {diff:.2f})")
    else:
        print(f"   ⚠️  Mismatch với lifecycle (diff = {diff:.2f})")

# ============================
# SUMMARY
# ============================
print("\n" + "="*80)
print("📊 FINAL RESULTS")
print("="*80)

print("\n✅ Loan-level forecast:")
print(df_loans[['LOAN_ID', 'STATE_CURRENT', 'EAD_CURRENT', 'STATE_FORECAST', 'EAD_FORECAST']].to_string(index=False))

print("\n📊 Aggregated by STATE_FORECAST:")
summary = df_loans.groupby('STATE_FORECAST').agg({
    'EAD_CURRENT': 'sum',
    'EAD_FORECAST': 'sum',
    'LOAN_ID': 'count'
}).rename(columns={'LOAN_ID': 'N_LOANS'})

summary['EAD_LIFECYCLE'] = summary.index.map(lifecycle_forecast)
summary['DIFF'] = summary['EAD_FORECAST'] - summary['EAD_LIFECYCLE']

print(summary.to_string())

print("\n" + "="*80)
print("🎯 KEY INSIGHTS")
print("="*80)

print("\n1️⃣ STATE assignment:")
print("   - Dựa trên STATE_CURRENT + Transition Matrix")
print("   - Loan ở DPD0 có xác suất cao ở DPD0 @ target_mob")
print("   - Loan ở DPD30+ có xác suất cao ở bad states")

print("\n2️⃣ EAD allocation:")
print("   - Phân bổ theo TỈ LỆ EAD_CURRENT (proportional)")
print("   - KHÔNG phân bổ đều (equal)")
print("   - Loan lớn → EAD_FORECAST lớn")
print("   - Loan nhỏ → EAD_FORECAST nhỏ")

print("\n3️⃣ Risk consideration:")
print("   - Risk được xét qua STATE_CURRENT")
print("   - Risk được xét qua Transition Matrix")
print("   - KHÔNG cần thêm risk weight trong EAD allocation")

print("\n" + "="*80)
print("✅ DEMO COMPLETE!")
print("="*80)
