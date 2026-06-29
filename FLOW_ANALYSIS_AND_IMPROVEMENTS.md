# 📊 PHÂN TÍCH FLOW VÀ GỢI Ý CẢI THIỆN ĐỘ CHÍNH XÁC

## 🎯 TỔNG QUAN FLOW HIỆN TẠI

### **Pipeline Chính**

```
1. DATA LOADING (data_loader.py)
   ↓
2. TRANSITION MATRIX (transition.py)
   - Weighted Historical Average (WHA)
   - EAD-weighted
   - Product × MOB × Score
   ↓
3. FORECAST (forecast.py)
   - EAD vector × Transition Matrix
   - Full history forecast
   ↓
4. LIFECYCLE (lifecycle.py)
   - Merge Actual + Forecast
   - Calculate DEL30/60/90 metrics
   ↓
5. CALIBRATION (calibration.py)
   - Compute k-factor (actual vs forecast)
   - Apply k to adjust forecast
   ↓
6. ALLOCATION (allocation_v2_fast.py / allocation_v2_optimized.py)
   - Loan-level allocation
   - State sampling + EAD distribution
```

---

## ✅ ĐIỂM MẠNH HIỆN TẠI

### 1. **Transition Matrix Quality**
- ✅ **WHA (Weighted Historical Average)**: Trọng số theo thời gian (exponential decay)
- ✅ **EAD-weighted**: Không đếm số lượng loans mà dùng EAD → chính xác hơn
- ✅ **Product × MOB × Score**: Phân tách chi tiết theo segment
- ✅ **Parent Fallback**: Xử lý trường hợp thiếu data

### 2. **Forecast Engine**
- ✅ **Amount-based**: Forecast theo EAD thay vì count
- ✅ **Full history**: Có thể backtest để validate
- ✅ **Macro layer**: Có sẵn hook để thêm macro adjustment

### 3. **Calibration**
- ✅ **K-factor per product**: Điều chỉnh forecast theo actual
- ✅ **K-factor per MOB**: Có thể điều chỉnh chi tiết theo từng MOB
- ✅ **Trimmed mean**: Loại bỏ outliers khi tính k
- ✅ **Blend period**: Không áp k đột ngột mà blend dần

### 4. **Allocation Logic**
- ✅ **Risk-aware**: Dùng STATE_CURRENT + Transition Matrix
- ✅ **EAD proportional**: Phân bổ theo tỷ lệ EAD, không chia đều
- ✅ **Optimized version**: Lấy actual trước, forecast sau

---

## 🔍 PHÂN TÍCH CHI TIẾT TỪNG BƯỚC

### **BƯỚC 1: Transition Matrix (transition.py)**

#### **Logic hiện tại:**
```python
# 1. Make pairs (t → t+1)
# 2. Weight = EAD × time_weight (exponential decay)
# 3. Crosstab weighted → Matrix
# 4. Normalize rows → Probability
# 5. Backfill zero rows với parent fallback
```

#### **Thông số quan trọng:**
- `ROLL_WINDOW = 12`: Chỉ lấy 12 tháng gần nhất
- `DECAY_LAMBDA = 0.9`: Trọng số giảm theo thời gian
- `MIN_OBS`: Ngưỡng tối thiểu số quan sát
- `MIN_EAD`: Ngưỡng tối thiểu tổng EAD

#### **⚠️ Vấn đề tiềm ẩn:**
1. **ROLL_WINDOW = 12 có thể quá ngắn**
   - Nếu behavior thay đổi theo mùa (seasonality) → 12 tháng không đủ
   - Một số segment có ít data → 12 tháng không đủ quan sát

2. **DECAY_LAMBDA = 0.9 có thể quá mạnh**
   - Data 12 tháng trước chỉ còn weight = 0.9^12 ≈ 0.28
   - Nếu behavior ổn định → không cần decay mạnh

3. **Parent Fallback có thể không đủ tốt**
   - Parent = average toàn bộ scores → mất đi đặc thù của từng score
   - Nên có fallback hierarchy: MOB → Score → Product

---

### **BƯỚC 2: Forecast (forecast.py)**

#### **Logic hiện tại:**
```python
# 1. Get initial EAD vector (tại MOB hiện tại)
# 2. Loop MOB: EAD_{t+1} = EAD_t @ P
# 3. Lưu EAD theo state tại mỗi MOB
```

#### **✅ Điểm mạnh:**
- Forecast theo EAD (amount-based) → chính xác hơn count-based
- Có thể forecast full history để backtest

#### **⚠️ Vấn đề tiềm ẩn:**
1. **Không có macro adjustment**
   - Hiện tại `enable_macro=False` → không tính đến yếu tố kinh tế vĩ mô
   - Nếu có recession/boom → forecast sẽ sai

2. **Không có seasonality adjustment**
   - Behavior có thể thay đổi theo mùa (Tết, cuối năm, ...)
   - Hiện tại không có layer xử lý seasonality

3. **Matrix fallback đơn giản**
   - Nếu không có matrix tại MOB → dùng matrix MOB cuối cùng
   - Có thể interpolate giữa các MOB để smooth hơn

---

### **BƯỚC 3: Lifecycle (lifecycle.py)**

#### **Logic hiện tại:**
```python
# 1. Merge actual + forecast
# 2. Calculate DEL30/60/90 amount
# 3. Calculate DEL30/60/90 % (trên DISB_TOTAL)
# 4. Tag IS_FORECAST flag
```

#### **✅ Điểm mạnh:**
- Tính DEL metrics chuẩn (amount + %)
- Có IS_FORECAST flag để phân biệt actual vs forecast

#### **⚠️ Vấn đề tiềm ẩn:**
1. **DISB_TOTAL có thể bị duplicate**
   - Nếu merge không cẩn thận → DISB_TOTAL bị nhân đôi
   - Code đã có xử lý nhưng cần kiểm tra kỹ

2. **Aggregate to product có thể sai weight**
   - Weight = DISB_TOTAL_score / PRODUCT_DISB
   - Nếu DISB_TOTAL không unique per cohort → weight sai

---

### **BƯỚC 4: Calibration (calibration.py)**

#### **Logic hiện tại:**
```python
# 1. Extract actual DEL90 @ anchor MOB (H)
# 2. Extract forecast DEL90 @ anchor MOB (H)
# 3. k = actual / forecast (trimmed mean)
# 4. Apply k từ MOB = m_apply (blend 2 kỳ đầu)
```

#### **✅ Điểm mạnh:**
- K-factor điều chỉnh forecast theo actual
- Trimmed mean loại bỏ outliers
- Blend period tránh shock đột ngột

#### **⚠️ Vấn đề tiềm ẩn:**
1. **Anchor MOB (H) có thể không phù hợp**
   - H = 12 hoặc 24 tuỳ product
   - Nếu behavior thay đổi sau H → k không còn chính xác

2. **K-factor per product có thể quá thô**
   - Một product có nhiều scores khác nhau
   - Nên có k per (product, score) hoặc k per MOB

3. **Blend period = 2 có thể quá ngắn**
   - Từ k=1 → k=target trong 2 kỳ có thể gây shock
   - Nên blend dài hơn (3-4 kỳ)

---

### **BƯỚC 5: Allocation (allocation_v2_fast.py)**

#### **Logic hiện tại:**
```python
# 1. Tính state probabilities từ transition matrix
# 2. Sample STATE_FORECAST theo probabilities
# 3. Lấy DEL30/60/90_PCT từ lifecycle (cohort-level)
# 4. EAD_DEL = DISBURSAL_AMOUNT × DEL_PCT
# 5. Phân bổ EAD_FORECAST theo STATE_FORECAST
```

#### **✅ Điểm mạnh:**
- State sampling theo transition matrix → risk-aware
- DEL_PCT từ lifecycle → đảm bảo tổng khớp
- EAD phân bổ proportional theo lifecycle

#### **⚠️ Vấn đề tiềm ẩn:**
1. **Random sampling có variance cao**
   - Mỗi lần chạy với seed khác → kết quả khác
   - Nên có option để dùng expected value thay vì sampling

2. **DEL_PCT từ lifecycle có thể missing**
   - Nếu cohort không có trong lifecycle → DEL_PCT = 0
   - Cần fallback tốt hơn (dùng parent cohort)

3. **EAD allocation có thể không khớp lifecycle**
   - Nếu STATE_FORECAST distribution khác lifecycle → EAD sẽ sai
   - Cần có validation step để check

---

## 🚀 GỢI Ý CẢI THIỆN ĐỘ CHÍNH XÁC

### **CẢI THIỆN CẤP ĐỘ 1: NHANH & DỄ (1-2 ngày)**

#### **1.1. Tối ưu ROLL_WINDOW**
```python
# Thay vì fix ROLL_WINDOW = 12, tự động chọn theo data availability
def adaptive_roll_window(df, min_window=12, max_window=24):
    """
    Chọn ROLL_WINDOW tối ưu:
    - Nếu có đủ data → dùng 24 tháng
    - Nếu ít data → dùng 12 tháng
    - Nếu rất ít → dùng toàn bộ
    """
    n_months = df['CUTOFF_DATE'].nunique()
    if n_months >= max_window:
        return max_window
    elif n_months >= min_window:
        return min_window
    else:
        return n_months
```

**Impact:** ⭐⭐⭐ (Cao)
- Tăng số quan sát cho transition matrix
- Giảm noise từ data quá ít

---

#### **1.2. Điều chỉnh DECAY_LAMBDA theo product**
```python
# Products ổn định → decay nhẹ (0.95)
# Products biến động → decay mạnh (0.85)
DECAY_LAMBDA_MAP = {
    "SALPIL": 0.95,  # Salary loan ổn định
    "CARD": 0.85,    # Card biến động
    "TOPUP": 0.90,   # Trung bình
}
```

**Impact:** ⭐⭐ (Trung bình)
- Phù hợp hơn với từng product
- Tận dụng tốt hơn historical data

---

#### **1.3. Cải thiện Parent Fallback Hierarchy**
```python
# Thay vì chỉ có 1 level parent, dùng hierarchy:
# 1. MOB-level (product, score, mob)
# 2. Score-level (product, score) ← hiện tại
# 3. Product-level (product, all scores)
# 4. Portfolio-level (all products)

def get_fallback_matrix(product, score, mob, matrices_by_mob):
    # Try MOB-level
    if mob in matrices_by_mob[product] and score in matrices_by_mob[product][mob]:
        return matrices_by_mob[product][mob][score]["P"]
    
    # Try adjacent MOB
    for delta in [1, -1, 2, -2]:
        adj_mob = mob + delta
        if adj_mob in matrices_by_mob[product] and score in matrices_by_mob[product][adj_mob]:
            return matrices_by_mob[product][adj_mob][score]["P"]
    
    # Try score-level parent
    if (product, score) in parent_fallback:
        return parent_fallback[(product, score)]
    
    # Try product-level
    if product in product_fallback:
        return product_fallback[product]
    
    # Last resort: portfolio
    return portfolio_fallback
```

**Impact:** ⭐⭐⭐⭐ (Rất cao)
- Giảm mất mát thông tin khi fallback
- Tận dụng tốt hơn data có sẵn

---

#### **1.4. Validation & Monitoring**
```python
def validate_allocation(df_loan_forecast, df_lifecycle_final, target_mob):
    """
    Kiểm tra allocation có khớp lifecycle không:
    1. Tổng EAD_FORECAST vs lifecycle
    2. DEL30/60/90 rate vs lifecycle
    3. State distribution vs lifecycle
    """
    
    # 1. Check total EAD
    total_ead_loan = df_loan_forecast[f'EAD_FORECAST_MOB{target_mob}'].sum()
    total_ead_lc = df_lifecycle_final[
        df_lifecycle_final['MOB'] == target_mob
    ][BUCKETS_CANON].sum().sum()
    
    ead_diff_pct = abs(total_ead_loan - total_ead_lc) / total_ead_lc * 100
    
    # 2. Check DEL rates
    del90_loan = df_loan_forecast[f'EAD_DEL90_MOB{target_mob}'].sum() / \
                 df_loan_forecast['DISBURSAL_AMOUNT'].sum()
    
    del90_lc = df_lifecycle_final[
        df_lifecycle_final['MOB'] == target_mob
    ]['DEL90_PCT'].mean()
    
    del90_diff_pct = abs(del90_loan - del90_lc) / del90_lc * 100
    
    print(f"📊 Validation @ MOB {target_mob}:")
    print(f"   EAD difference: {ead_diff_pct:.2f}%")
    print(f"   DEL90 difference: {del90_diff_pct:.2f}%")
    
    if ead_diff_pct > 5:
        print("   ⚠️ WARNING: EAD mismatch > 5%")
    if del90_diff_pct > 10:
        print("   ⚠️ WARNING: DEL90 mismatch > 10%")
```

**Impact:** ⭐⭐⭐⭐⭐ (Cực cao)
- Phát hiện sớm các vấn đề
- Đảm bảo consistency giữa các layers

---

### **CẢI THIỆN CẤP ĐỘ 2: TRUNG BÌNH (3-5 ngày)**

#### **2.1. Thêm Seasonality Adjustment**
```python
def compute_seasonality_factors(df_raw):
    """
    Tính seasonality factors theo tháng:
    - Tháng nào có DEL rate cao hơn average → factor > 1
    - Tháng nào có DEL rate thấp hơn average → factor < 1
    """
    
    df = df_raw.copy()
    df['MONTH'] = pd.to_datetime(df['CUTOFF_DATE']).dt.month
    
    # Tính DEL90 rate theo tháng
    monthly_del = df.groupby(['PRODUCT_TYPE', 'MONTH']).apply(
        lambda g: (g['STATE'].isin(BUCKETS_90P)).sum() / len(g)
    ).reset_index(name='DEL90_RATE')
    
    # Tính average DEL90 rate
    avg_del = monthly_del.groupby('PRODUCT_TYPE')['DEL90_RATE'].mean()
    
    # Seasonality factor = monthly / average
    monthly_del = monthly_del.merge(
        avg_del.rename('AVG_DEL90'),
        on='PRODUCT_TYPE'
    )
    monthly_del['SEASONALITY_FACTOR'] = monthly_del['DEL90_RATE'] / monthly_del['AVG_DEL90']
    
    return monthly_del[['PRODUCT_TYPE', 'MONTH', 'SEASONALITY_FACTOR']]

def apply_seasonality_to_forecast(df_forecast, seasonality_factors, forecast_date):
    """
    Áp dụng seasonality factors vào forecast
    """
    month = pd.to_datetime(forecast_date).month
    
    df = df_forecast.copy()
    df = df.merge(
        seasonality_factors[seasonality_factors['MONTH'] == month],
        on='PRODUCT_TYPE',
        how='left'
    )
    
    # Adjust risk buckets
    risk_cols = ['DPD30+', 'DPD60+', 'DPD90+', 'DPD120+', 'DPD180+', 'WRITEOFF']
    df[risk_cols] = df[risk_cols].multiply(df['SEASONALITY_FACTOR'], axis=0)
    
    return df
```

**Impact:** ⭐⭐⭐ (Cao)
- Capture seasonal patterns (Tết, cuối năm, ...)
- Tăng độ chính xác forecast ngắn hạn

---

#### **2.2. Macro Adjustment Layer**
```python
def compute_macro_adjustment(gdp_growth, unemployment_rate, base_scenario):
    """
    Tính macro adjustment factors dựa trên:
    - GDP growth
    - Unemployment rate
    - Base scenario assumptions
    """
    
    # Stress scenarios
    if gdp_growth < 0:  # Recession
        stress_factor = 1 + abs(gdp_growth) * 0.5  # DEL tăng 50% cho mỗi 1% GDP giảm
    elif gdp_growth > base_scenario['gdp']:  # Boom
        stress_factor = 1 - (gdp_growth - base_scenario['gdp']) * 0.3
    else:
        stress_factor = 1.0
    
    # Unemployment impact
    if unemployment_rate > base_scenario['unemployment']:
        unemp_factor = 1 + (unemployment_rate - base_scenario['unemployment']) * 0.2
    else:
        unemp_factor = 1.0
    
    # Combined factor
    macro_factor = stress_factor * unemp_factor
    
    return macro_factor

def apply_macro_to_transition_matrix(P, macro_factor):
    """
    Điều chỉnh transition matrix theo macro factors:
    - Tăng probability chuyển sang bad states
    - Giảm probability ở lại good states
    """
    
    P_adj = P.copy()
    
    # Good states: DPD0, DPD1+
    # Bad states: DPD30+, DPD60+, DPD90+, ...
    
    good_states = ['DPD0', 'DPD1+']
    bad_states = ['DPD30+', 'DPD60+', 'DPD90+', 'DPD120+', 'DPD180+', 'WRITEOFF']
    
    for from_state in good_states:
        if from_state not in P_adj.index:
            continue
        
        # Tăng prob chuyển sang bad states
        for to_state in bad_states:
            if to_state in P_adj.columns:
                P_adj.loc[from_state, to_state] *= macro_factor
        
        # Giảm prob ở lại good state
        P_adj.loc[from_state, from_state] /= macro_factor
        
        # Normalize row
        row_sum = P_adj.loc[from_state].sum()
        P_adj.loc[from_state] = P_adj.loc[from_state] / row_sum
    
    return P_adj
```

**Impact:** ⭐⭐⭐⭐ (Rất cao)
- Capture macro trends
- Hỗ trợ stress testing
- Tăng độ chính xác trong môi trường kinh tế thay đổi

---

#### **2.3. K-factor per (Product, Score)**
```python
def compute_k_per_product_score(df_actual, df_forecast, H_map):
    """
    Tính k-factor chi tiết hơn: per (product, score) thay vì chỉ per product
    """
    
    results = {}
    
    for (product, score), grp_act in df_actual.groupby(['PRODUCT_TYPE', 'RISK_SCORE']):
        H = H_map.get(product, 24)
        
        act_h = grp_act[grp_act['MOB'] == H]
        fc_h = df_forecast[
            (df_forecast['PRODUCT_TYPE'] == product) &
            (df_forecast['RISK_SCORE'] == score) &
            (df_forecast['MOB'] == H)
        ]
        
        merged = act_h.merge(fc_h, on=['VINTAGE_DATE'], how='inner')
        
        if len(merged) < 3:
            results[(product, score)] = 1.0
            continue
        
        ratios = merged['DEL90_ACT'] / merged['DEL90_FC'].replace(0, np.nan)
        ratios = ratios.replace([np.inf, -np.inf], np.nan).dropna()
        
        k = trimmed_mean(ratios.values, trim=0.2)
        k = float(np.clip(k, 0.5, 1.5))
        
        results[(product, score)] = k
    
    return results
```

**Impact:** ⭐⭐⭐⭐ (Rất cao)
- Chính xác hơn k per product
- Capture đặc thù từng risk score

---

### **CẢI THIỆN CẤP ĐỘ 3: DÀI HẠN (1-2 tuần)**

#### **3.1. Machine Learning Enhancement**
```python
# Thay vì dùng transition matrix cố định, train ML model để predict:
# - Probability chuyển state
# - Dựa trên features: MOB, STATE_CURRENT, PRODUCT, SCORE, MACRO, SEASONALITY

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

def train_state_transition_model(df_raw):
    """
    Train ML model để predict state transition
    """
    
    # Make pairs
    pairs = make_pairs(df_raw)
    
    # Features
    features = [
        'mob_t',
        'product_t',
        'score_t',
        'state_t',
        'ead_raw',
        # Thêm macro features
        'gdp_growth',
        'unemployment',
        # Thêm seasonality
        'month',
        'quarter',
    ]
    
    # Encode categorical
    le_state = LabelEncoder()
    pairs['state_t_encoded'] = le_state.fit_transform(pairs['state_t'])
    pairs['state_t1_encoded'] = le_state.transform(pairs['state_t1'])
    
    # Train model
    X = pairs[features]
    y = pairs['state_t1_encoded']
    
    model = RandomForestClassifier(n_estimators=100, max_depth=10)
    model.fit(X, y)
    
    return model, le_state

def predict_with_ml(model, le_state, loan_features):
    """
    Predict state transition probabilities using ML
    """
    
    # Predict probabilities
    probs = model.predict_proba(loan_features)
    
    # Convert to state probabilities
    state_probs = pd.Series(probs[0], index=le_state.classes_)
    
    return state_probs
```

**Impact:** ⭐⭐⭐⭐⭐ (Cực cao)
- Capture non-linear relationships
- Tự động học patterns từ data
- Có thể thêm nhiều features hơn

---

#### **3.2. Ensemble Forecasting**
```python
def ensemble_forecast(df_raw, matrices_by_mob, ml_model):
    """
    Kết hợp nhiều phương pháp forecast:
    1. Transition matrix (hiện tại)
    2. ML model
    3. Time series (ARIMA, Prophet)
    
    Weighted average theo performance
    """
    
    # Method 1: Transition matrix
    fc_tm = forecast_all_vintages(df_raw, matrices_by_mob)
    
    # Method 2: ML
    fc_ml = forecast_with_ml(df_raw, ml_model)
    
    # Method 3: Time series
    fc_ts = forecast_with_timeseries(df_raw)
    
    # Backtest để tính weights
    weights = compute_ensemble_weights([fc_tm, fc_ml, fc_ts], df_actual)
    
    # Weighted average
    fc_ensemble = (
        fc_tm * weights[0] +
        fc_ml * weights[1] +
        fc_ts * weights[2]
    )
    
    return fc_ensemble
```

**Impact:** ⭐⭐⭐⭐⭐ (Cực cao)
- Giảm variance
- Robust hơn với outliers
- Tận dụng ưu điểm của nhiều phương pháp

---

## 📋 ROADMAP TRIỂN KHAI

### **Phase 1: Quick Wins (Tuần 1)**
1. ✅ Implement validation & monitoring
2. ✅ Optimize ROLL_WINDOW
3. ✅ Improve parent fallback hierarchy
4. ✅ Adjust DECAY_LAMBDA per product

**Expected improvement:** +5-10% accuracy

---

### **Phase 2: Medium Enhancements (Tuần 2-3)**
1. ✅ Add seasonality adjustment
2. ✅ Implement macro adjustment layer
3. ✅ K-factor per (product, score)
4. ✅ Improve allocation validation

**Expected improvement:** +10-15% accuracy

---

### **Phase 3: Advanced Features (Tuần 4-6)**
1. ✅ Train ML model for state transition
2. ✅ Implement ensemble forecasting
3. ✅ Add more features (macro, seasonality, ...)
4. ✅ Continuous monitoring & retraining

**Expected improvement:** +15-25% accuracy

---

## 🎯 KẾT LUẬN

### **Độ ưu tiên cao nhất:**
1. **Validation & Monitoring** → Phát hiện vấn đề sớm
2. **Parent Fallback Hierarchy** → Tận dụng tốt hơn data
3. **K-factor per (Product, Score)** → Chính xác hơn calibration

### **Độ ưu tiên trung bình:**
1. **Seasonality Adjustment** → Tăng accuracy ngắn hạn
2. **Macro Adjustment** → Hỗ trợ stress testing
3. **Optimize ROLL_WINDOW** → Tăng số quan sát

### **Độ ưu tiên thấp (long-term):**
1. **ML Enhancement** → Cần nhiều thời gian & data
2. **Ensemble Forecasting** → Phức tạp, cần maintain nhiều models

---

**Tác giả:** Roll Rate Model Team  
**Ngày tạo:** 2026-02-09
