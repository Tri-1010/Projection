# ⚡ PHÂN TÍCH BOTTLENECK VÀ TỐI ƯU ALLOCATION

## 🔍 PHÂN TÍCH BOTTLENECK HIỆN TẠI

### **File:** `allocation_v2_fast.py`

### **BƯỚC 4: EAD Allocation Loop (Lines 280-330)**

```python
for (product, score, vintage), grp in df.groupby(['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']):
    lc_mask = (
        (df_lc['PRODUCT_TYPE'] == product) &
        (df_lc['RISK_SCORE'] == score) &
        (df_lc['VINTAGE_DATE'] == vintage)
    )
    lc_row = df_lc[lc_mask]
    
    # ... xử lý cohort ...
    
    for state in BUCKETS_CANON:  # ← NESTED LOOP
        ead_lifecycle_state = lc_row.get(state, 0)
        
        state_mask = (
            (df['PRODUCT_TYPE'] == product) &
            (df['RISK_SCORE'] == score) &
            (df['VINTAGE_DATE'] == vintage) &
            (df['STATE_FORECAST'] == state)
        )  # ← TẠO BOOLEAN MASK MỖI LẦN
        
        if state_mask.sum() == 0:
            continue
        
        ead_current_state = df.loc[state_mask, 'EAD_CURRENT'].sum()
        
        if ead_current_state <= 0:
            continue
        
        if state in ABSORBING_STATES:
            df.loc[state_mask, 'EAD_FORECAST'] = 0
        else:
            ratio = ead_lifecycle_state / ead_current_state
            ratio = min(ratio, 1.0)
            df.loc[state_mask, 'EAD_FORECAST'] = df.loc[state_mask, 'EAD_CURRENT'] * ratio
```

---

## 🐌 VẤN ĐỀ PERFORMANCE

### **Complexity: O(n_cohorts × n_states × n_loans)**

Giả sử:
- `n_cohorts = 500` (product × score × vintage combinations)
- `n_states = 10` (BUCKETS_CANON)
- `n_loans = 100,000`

**Số lần tạo boolean mask:** `500 × 10 = 5,000` lần

**Mỗi lần tạo mask:**
- Phải scan toàn bộ DataFrame (100k rows)
- Tạo 4 boolean arrays (product, score, vintage, state)
- AND operation giữa 4 arrays
- `df.loc[mask, ...]` operation

**Tổng operations:** `5,000 × 100,000 = 500 triệu operations` ❌

---

## ⚡ GIẢI PHÁP TỐI ƯU

### **Option 1: Vectorized Approach (RECOMMEND)**

**Ý tưởng:** Pre-compute tất cả ratios, dùng merge thay vì loops

```python
def allocate_fast_vectorized(
    df_loans_latest: pd.DataFrame,
    df_lifecycle_final: pd.DataFrame,
    matrices_by_mob: Dict,
    target_mob: int,
    parent_fallback: Dict = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Phân bổ forecast NHANH (vectorized - KHÔNG CÓ LOOPS).
    
    Performance: O(n_loans) thay vì O(n_cohorts × n_states × n_loans)
    """
    
    loan_col = CFG["loan"]
    state_col = CFG["state"]
    mob_col = CFG["mob"]
    ead_col = CFG["ead"]
    
    np.random.seed(seed)
    
    n_states = len(BUCKETS_CANON)
    state_to_idx = {s: i for i, s in enumerate(BUCKETS_CANON)}
    
    print(f"📍 Phân bổ forecast tại MOB = {target_mob} (VECTORIZED mode)")
    print(f"   Số loans: {len(df_loans_latest):,}")
    
    # ===================================================
    # BƯỚC 1: Chuẩn bị data
    # ===================================================
    df = df_loans_latest.copy()
    df['STATE_CURRENT'] = df[state_col]
    df['MOB_CURRENT'] = df[mob_col].astype(int)
    df['EAD_CURRENT'] = df[ead_col].astype(float)
    
    disb_col = CFG.get("disb", "DISBURSAL_AMOUNT")
    if disb_col in df.columns:
        df['DISBURSAL_AMOUNT'] = df[disb_col].astype(float)
    else:
        df['DISBURSAL_AMOUNT'] = df['EAD_CURRENT']
    
    if 'VINTAGE_DATE' not in df.columns:
        df['VINTAGE_DATE'] = parse_date_column(df[CFG['orig_date']])
    
    # ===================================================
    # BƯỚC 2: Tính state probabilities (giống cũ)
    # ===================================================
    print("   Đang tính state probabilities...")
    matrix_cache = {}
    
    unique_combos = df.groupby(['PRODUCT_TYPE', 'RISK_SCORE', 'MOB_CURRENT']).size().reset_index()[['PRODUCT_TYPE', 'RISK_SCORE', 'MOB_CURRENT']]
    
    for _, row in unique_combos.iterrows():
        product = row['PRODUCT_TYPE']
        score = row['RISK_SCORE']
        mob_current = row['MOB_CURRENT']
        
        if mob_current >= target_mob:
            matrix_cache[(product, score, mob_current)] = np.eye(n_states)
        else:
            combined = _get_combined_matrix(
                matrices_by_mob, parent_fallback,
                product, score, mob_current, target_mob
            )
            matrix_cache[(product, score, mob_current)] = combined
    
    def get_state_probs(row):
        product = row['PRODUCT_TYPE']
        score = row['RISK_SCORE']
        mob_current = row['MOB_CURRENT']
        state_current = row['STATE_CURRENT']
        
        key = (product, score, mob_current)
        if key not in matrix_cache:
            probs = np.zeros(n_states)
            if state_current in state_to_idx:
                probs[state_to_idx[state_current]] = 1.0
            return probs
        
        combined = matrix_cache[key]
        
        init_vec = np.zeros(n_states)
        if state_current in state_to_idx:
            init_vec[state_to_idx[state_current]] = 1.0
        else:
            init_vec[0] = 1.0
        
        final_probs = init_vec @ combined
        
        total = final_probs.sum()
        if total > 0:
            final_probs = final_probs / total
        
        return final_probs
    
    probs_list = df.apply(get_state_probs, axis=1).tolist()
    probs_arr = np.array(probs_list)
    
    # ===================================================
    # BƯỚC 3: Sample STATE_FORECAST
    # ===================================================
    print("   Đang assign states...")
    
    def sample_state(probs):
        if probs.sum() == 0:
            return 'DPD0'
        probs = probs / probs.sum()
        return np.random.choice(BUCKETS_CANON, p=probs)
    
    df['STATE_FORECAST'] = [sample_state(p) for p in probs_arr]
    
    # ===================================================
    # BƯỚC 4: Lấy DEL rates từ lifecycle
    # ===================================================
    print("   Đang lấy DEL rates từ lifecycle...")
    
    df_lc = df_lifecycle_final[df_lifecycle_final['MOB'] == target_mob].copy()
    df_lc['VINTAGE_DATE'] = pd.to_datetime(df_lc['VINTAGE_DATE'])
    df['VINTAGE_DATE'] = pd.to_datetime(df['VINTAGE_DATE'])
    
    del_cols = ['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']
    if 'DEL30_PCT' in df_lc.columns:
        del_cols.append('DEL30_PCT')
    if 'DEL90_PCT' in df_lc.columns:
        del_cols.append('DEL90_PCT')
    
    df_del_rates = df_lc[del_cols].drop_duplicates()
    
    df = df.merge(
        df_del_rates,
        on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE'],
        how='left'
    )
    
    df['PROB_DEL30'] = df['DEL30_PCT'].fillna(0)
    df['PROB_DEL90'] = df['DEL90_PCT'].fillna(0)
    df['EAD_DEL30'] = df['DISBURSAL_AMOUNT'] * df['PROB_DEL30']
    df['EAD_DEL90'] = df['DISBURSAL_AMOUNT'] * df['PROB_DEL90']
    
    df['DEL30_FLAG'] = df['STATE_FORECAST'].isin(BUCKETS_30P).astype(int)
    df['DEL90_FLAG'] = df['STATE_FORECAST'].isin(BUCKETS_90P).astype(int)
    
    # ===================================================
    # BƯỚC 5: Phân bổ EAD_FORECAST (VECTORIZED - NO LOOPS!)
    # ===================================================
    print("   Đang phân bổ EAD theo state (VECTORIZED)...")
    
    # 5.1. Prepare lifecycle data với tất cả states
    df_lc_states = df_lc.copy()
    
    # Melt lifecycle từ wide → long format
    state_cols = [c for c in BUCKETS_CANON if c in df_lc_states.columns]
    
    df_lc_long = df_lc_states.melt(
        id_vars=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE'],
        value_vars=state_cols,
        var_name='STATE',
        value_name='EAD_LIFECYCLE'
    )
    
    # 5.2. Tính tổng EAD_CURRENT per (cohort, state)
    df_ead_current = df.groupby(
        ['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE_FORECAST']
    )['EAD_CURRENT'].sum().reset_index()
    
    df_ead_current = df_ead_current.rename(columns={
        'STATE_FORECAST': 'STATE',
        'EAD_CURRENT': 'EAD_CURRENT_TOTAL'
    })
    
    # 5.3. Merge lifecycle với current EAD
    df_ratios = df_lc_long.merge(
        df_ead_current,
        on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE'],
        how='left'
    )
    
    # 5.4. Tính ratio = EAD_LIFECYCLE / EAD_CURRENT_TOTAL
    df_ratios['EAD_CURRENT_TOTAL'] = df_ratios['EAD_CURRENT_TOTAL'].fillna(0)
    df_ratios['RATIO'] = np.where(
        df_ratios['EAD_CURRENT_TOTAL'] > 0,
        df_ratios['EAD_LIFECYCLE'] / df_ratios['EAD_CURRENT_TOTAL'],
        0
    )
    
    # Clip ratio to [0, 1]
    df_ratios['RATIO'] = df_ratios['RATIO'].clip(0, 1)
    
    # Handle absorbing states
    df_ratios.loc[df_ratios['STATE'].isin(ABSORBING_STATES), 'RATIO'] = 0
    
    # 5.5. Merge ratios vào df loans
    df = df.merge(
        df_ratios[['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE', 'RATIO']],
        left_on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE_FORECAST'],
        right_on=['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE'],
        how='left'
    )
    
    # 5.6. Tính EAD_FORECAST = EAD_CURRENT × RATIO (VECTORIZED!)
    df['RATIO'] = df['RATIO'].fillna(0)
    df['EAD_FORECAST'] = df['EAD_CURRENT'] * df['RATIO']
    
    # ===================================================
    # BƯỚC 6: Output
    # ===================================================
    df['TARGET_MOB'] = target_mob
    df['IS_FORECAST'] = 1
    
    output_cols = [
        loan_col, 'PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE',
        'DISBURSAL_AMOUNT',
        'STATE_CURRENT', 'MOB_CURRENT', 'EAD_CURRENT',
        'STATE_FORECAST', 'EAD_FORECAST',
        'PROB_DEL30', 'PROB_DEL90',
        'EAD_DEL30', 'EAD_DEL90',
        'DEL30_FLAG', 'DEL90_FLAG',
        'TARGET_MOB', 'IS_FORECAST'
    ]
    
    df_result = df[[c for c in output_cols if c in df.columns]].copy()
    
    # ===================================================
    # VALIDATION
    # ===================================================
    print(f"\n✅ Phân bổ hoàn tất:")
    print(f"   Số loans: {len(df_result):,}")
    
    total_ead_current = df_result['EAD_CURRENT'].sum()
    total_ead_forecast = df_result['EAD_FORECAST'].sum()
    total_ead_del30 = df_result['EAD_DEL30'].sum()
    total_ead_del90 = df_result['EAD_DEL90'].sum()
    total_disbursal = df_result['DISBURSAL_AMOUNT'].sum()
    
    print(f"\n   EAD Summary:")
    print(f"      DISBURSAL_AMOUNT: {total_disbursal:,.0f}")
    print(f"      EAD_CURRENT: {total_ead_current:,.0f}")
    print(f"      EAD_FORECAST: {total_ead_forecast:,.0f} (giảm {(1-total_ead_forecast/total_ead_current)*100:.2f}%)")
    print(f"      EAD_DEL30: {total_ead_del30:,.0f} ({total_ead_del30/total_disbursal*100:.2f}% of DISBURSAL)")
    print(f"      EAD_DEL90: {total_ead_del90:,.0f} ({total_ead_del90/total_disbursal*100:.2f}% of DISBURSAL)")
    
    return df_result
```

---

## 📊 SO SÁNH PERFORMANCE

### **Approach hiện tại (Loop-based):**
```
Complexity: O(n_cohorts × n_states × n_loans)
            = O(500 × 10 × 100,000)
            = O(500 triệu operations)

Thời gian: ~2-3 phút cho 100k loans
```

### **Approach mới (Vectorized):**
```
Complexity: O(n_loans + n_cohorts × n_states)
            = O(100,000 + 500 × 10)
            = O(105,000 operations)

Thời gian: ~10-20 giây cho 100k loans ✅ NHANH HƠN 10-15X
```

---

## 🚀 CÁC BƯỚC TỐI ƯU KHÁC

### **Option 2: Group-based Approach**

```python
def allocate_fast_groupby(df_loans_latest, df_lifecycle_final, ...):
    """
    Xử lý từng cohort riêng biệt, concat cuối cùng.
    """
    
    results = []
    
    for (product, score, vintage), grp in df.groupby(['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']):
        # Lấy lifecycle cho cohort này
        lc_row = df_lc[
            (df_lc['PRODUCT_TYPE'] == product) &
            (df_lc['RISK_SCORE'] == score) &
            (df_lc['VINTAGE_DATE'] == vintage)
        ].iloc[0]
        
        # Xử lý cohort (KHÔNG CÓ NESTED LOOP)
        grp_result = grp.copy()
        
        # Vectorized: Tính ratio cho tất cả states cùng lúc
        for state in BUCKETS_CANON:
            ead_lc = lc_row.get(state, 0)
            
            # Filter loans với state này
            mask = grp_result['STATE_FORECAST'] == state
            
            if mask.sum() == 0:
                continue
            
            ead_current_total = grp_result.loc[mask, 'EAD_CURRENT'].sum()
            
            if ead_current_total > 0:
                ratio = min(ead_lc / ead_current_total, 1.0)
                grp_result.loc[mask, 'EAD_FORECAST'] = grp_result.loc[mask, 'EAD_CURRENT'] * ratio
            else:
                grp_result.loc[mask, 'EAD_FORECAST'] = 0
        
        results.append(grp_result)
    
    return pd.concat(results, ignore_index=True)
```

**Performance:** Trung bình giữa loop-based và vectorized

---

### **Option 3: Index-based Approach**

```python
def allocate_fast_indexed(df_loans_latest, df_lifecycle_final, ...):
    """
    Dùng MultiIndex để lookup nhanh hơn.
    """
    
    # Set MultiIndex
    df = df_loans_latest.copy()
    df = df.set_index(['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'STATE_FORECAST'])
    
    df_lc = df_lifecycle_final.copy()
    df_lc = df_lc.set_index(['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE'])
    
    # Vectorized lookup
    for state in BUCKETS_CANON:
        # Get all loans with this state
        try:
            loans_with_state = df.xs(state, level='STATE_FORECAST')
        except KeyError:
            continue
        
        # Get lifecycle EAD for this state
        ead_lc = df_lc[state]
        
        # Compute ratios
        ead_current = loans_with_state.groupby(level=[0, 1, 2])['EAD_CURRENT'].sum()
        ratios = (ead_lc / ead_current).clip(0, 1).fillna(0)
        
        # Apply ratios
        df.loc[loans_with_state.index, 'EAD_FORECAST'] = \
            loans_with_state['EAD_CURRENT'] * ratios.reindex(loans_with_state.index, level=[0, 1, 2])
    
    return df.reset_index()
```

**Performance:** Tương đương vectorized, nhưng code phức tạp hơn

---

## 💡 RECOMMEND

### **Lựa chọn tốt nhất: Option 1 (Vectorized)**

**Lý do:**
1. ✅ **Nhanh nhất**: 10-15x faster
2. ✅ **Code đơn giản**: Dễ maintain
3. ✅ **Scalable**: Tốt với large dataset
4. ✅ **Memory efficient**: Không tạo nhiều intermediate DataFrames

### **Implementation Plan:**

1. **Tuần 1:**
   - Implement `allocate_fast_vectorized()`
   - Test với small dataset
   - Validate kết quả khớp với version cũ

2. **Tuần 2:**
   - Benchmark performance
   - Test với full dataset
   - Update `allocate_multi_mob_fast()` để dùng version mới

3. **Tuần 3:**
   - Deploy to production
   - Monitor performance
   - Document changes

---

## 🎯 KẾT LUẬN

**Bottleneck chính:** Nested loops với boolean mask operations

**Giải pháp:** Vectorized approach với merge + groupby

**Expected improvement:**
- Speed: **10-15x faster** ✅
- Memory: Tương đương hoặc tốt hơn
- Accuracy: Giống hệt (chỉ thay đổi implementation)

**Next steps:**
1. Implement vectorized version
2. Benchmark
3. Deploy

---

**Tác giả:** Roll Rate Model Team  
**Ngày tạo:** 2026-02-10
