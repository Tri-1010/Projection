# 🎯 ENSEMBLE FORECASTING - THIẾT KẾ CHI TIẾT

## 📌 TỔNG QUAN

**Ensemble Forecasting** là phương pháp kết hợp nhiều models/methods khác nhau để tạo ra forecast chính xác hơn. Thay vì dựa vào 1 method duy nhất, ta kết hợp điểm mạnh của nhiều methods.

### **Nguyên lý cốt lõi:**
```
Forecast_Final = w1 × Method1 + w2 × Method2 + w3 × Method3 + ...

Trong đó:
- w1, w2, w3 là trọng số (weights)
- Tổng weights = 1
- Weights được tính dựa trên historical performance
```

### **Lợi ích:**
1. ✅ **Giảm variance**: Trung bình nhiều methods → ít bị ảnh hưởng bởi outliers
2. ✅ **Robust hơn**: Nếu 1 method sai → các methods khác bù đắp
3. ✅ **Tận dụng điểm mạnh**: Mỗi method tốt ở điều kiện khác nhau
4. ✅ **Tăng accuracy**: Thường tốt hơn best single method 5-15%

---

## 🔬 CÁC METHODS ĐỀ XUẤT

### **Method 1: Transition Matrix (Hiện tại)**

#### **Mô tả:**
- Dùng transition matrix từ historical data
- EAD-weighted, WHA (Weighted Historical Average)
- Product × MOB × Score segmentation

#### **Điểm mạnh:**
- ✅ Capture được state transitions
- ✅ Risk-aware (dựa trên STATE_CURRENT)
- ✅ Segment-specific (Product × Score)

#### **Điểm yếu:**
- ❌ Giả định stationary (behavior không đổi)
- ❌ Không capture trends
- ❌ Cần nhiều data để ổn định

#### **Khi nào tốt:**
- Data đủ lớn (> 12 tháng)
- Behavior ổn định
- Không có structural breaks

---

### **Method 2: Time Series (ARIMA/Prophet)**

#### **Mô tả:**
- Forecast DEL90_PCT theo time series
- Dùng ARIMA hoặc Prophet
- Forecast theo (Product × Score × MOB)

#### **Implementation:**
```python
from statsmodels.tsa.arima.model import ARIMA
from prophet import Prophet

def forecast_with_arima(df_historical, product, score, mob, horizon=12):
    """
    Forecast DEL90_PCT using ARIMA.
    
    Input:
        df_historical: Historical DEL90_PCT per vintage
        product, score, mob: Segment
        horizon: Số tháng forecast
    
    Output:
        Series of forecasted DEL90_PCT
    """
    
    # Filter segment
    df_seg = df_historical[
        (df_historical['PRODUCT_TYPE'] == product) &
        (df_historical['RISK_SCORE'] == score) &
        (df_historical['MOB'] == mob)
    ].sort_values('VINTAGE_DATE')
    
    if len(df_seg) < 24:  # Cần ít nhất 24 points
        return None
    
    # Prepare time series
    ts = df_seg.set_index('VINTAGE_DATE')['DEL90_PCT']
    
    # Fit ARIMA
    # Auto-select (p,d,q) hoặc dùng (1,1,1) default
    model = ARIMA(ts, order=(1, 1, 1))
    fitted = model.fit()
    
    # Forecast
    forecast = fitted.forecast(steps=horizon)
    
    return forecast


def forecast_with_prophet(df_historical, product, score, mob, horizon=12):
    """
    Forecast DEL90_PCT using Prophet (better for seasonality).
    """
    
    # Filter segment
    df_seg = df_historical[
        (df_historical['PRODUCT_TYPE'] == product) &
        (df_historical['RISK_SCORE'] == score) &
        (df_historical['MOB'] == mob)
    ].sort_values('VINTAGE_DATE')
    
    if len(df_seg) < 24:
        return None
    
    # Prepare for Prophet (needs 'ds' and 'y')
    df_prophet = pd.DataFrame({
        'ds': pd.to_datetime(df_seg['VINTAGE_DATE']),
        'y': df_seg['DEL90_PCT']
    })
    
    # Fit Prophet
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
    )
    model.fit(df_prophet)
    
    # Create future dataframe
    future = model.make_future_dataframe(periods=horizon, freq='MS')
    
    # Forecast
    forecast = model.predict(future)
    
    # Return only future values
    return forecast.tail(horizon)['yhat']
```

#### **Điểm mạnh:**
- ✅ Capture trends (tăng/giảm theo thời gian)
- ✅ Capture seasonality (Prophet)
- ✅ Không cần transition matrix

#### **Điểm yếu:**
- ❌ Không capture state transitions
- ❌ Cần nhiều historical points (>24)
- ❌ Không risk-aware

#### **Khi nào tốt:**
- Có trend rõ ràng
- Có seasonality
- Data đủ dài (>24 tháng)

---

### **Method 3: Regression-based**

#### **Mô tả:**
- Dùng regression để predict DEL90_PCT
- Features: MOB, PRODUCT, SCORE, MACRO, SEASONALITY, ...
- Model: Linear Regression, Random Forest, XGBoost

#### **Implementation:**
```python
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
import xgboost as xgb

def prepare_regression_features(df_historical, df_macro=None):
    """
    Chuẩn bị features cho regression.
    
    Features:
    - MOB (numeric)
    - PRODUCT_TYPE (one-hot encoded)
    - RISK_SCORE (one-hot encoded)
    - VINTAGE_MONTH (1-12, for seasonality)
    - VINTAGE_QUARTER (1-4)
    - VINTAGE_YEAR (numeric)
    - AGE_OF_VINTAGE (months since vintage)
    - MACRO features (GDP, unemployment, ...) if available
    - LAG features (DEL90 tại MOB-1, MOB-2, ...)
    """
    
    df = df_historical.copy()
    
    # Basic features
    df['VINTAGE_DATE'] = pd.to_datetime(df['VINTAGE_DATE'])
    df['VINTAGE_MONTH'] = df['VINTAGE_DATE'].dt.month
    df['VINTAGE_QUARTER'] = df['VINTAGE_DATE'].dt.quarter
    df['VINTAGE_YEAR'] = df['VINTAGE_DATE'].dt.year
    
    # Age of vintage (tháng từ vintage đến hiện tại)
    df['AGE_OF_VINTAGE'] = (
        pd.Timestamp.now() - df['VINTAGE_DATE']
    ).dt.days / 30
    
    # One-hot encode categorical
    df = pd.get_dummies(
        df,
        columns=['PRODUCT_TYPE', 'RISK_SCORE'],
        drop_first=True
    )
    
    # Lag features (DEL90 tại MOB trước)
    df = df.sort_values(['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE', 'MOB'])
    
    for lag in [1, 2, 3]:
        df[f'DEL90_LAG{lag}'] = df.groupby(
            ['PRODUCT_TYPE', 'RISK_SCORE', 'VINTAGE_DATE']
        )['DEL90_PCT'].shift(lag)
    
    # Merge macro features if available
    if df_macro is not None:
        df = df.merge(
            df_macro,
            left_on='VINTAGE_DATE',
            right_on='DATE',
            how='left'
        )
    
    return df


def train_regression_model(df_train, model_type='xgboost'):
    """
    Train regression model.
    """
    
    # Prepare features
    feature_cols = [
        'MOB',
        'VINTAGE_MONTH',
        'VINTAGE_QUARTER',
        'VINTAGE_YEAR',
        'AGE_OF_VINTAGE',
        'DEL90_LAG1',
        'DEL90_LAG2',
        'DEL90_LAG3',
    ]
    
    # Add one-hot encoded columns
    feature_cols += [c for c in df_train.columns if c.startswith('PRODUCT_TYPE_')]
    feature_cols += [c for c in df_train.columns if c.startswith('RISK_SCORE_')]
    
    # Add macro columns if available
    feature_cols += [c for c in df_train.columns if c in ['GDP_GROWTH', 'UNEMPLOYMENT']]
    
    X = df_train[feature_cols].fillna(0)
    y = df_train['DEL90_PCT']
    
    # Train model
    if model_type == 'xgboost':
        model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
    elif model_type == 'random_forest':
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
    elif model_type == 'gradient_boosting':
        model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
    else:  # linear
        model = Ridge(alpha=1.0)
    
    model.fit(X, y)
    
    return model, feature_cols


def forecast_with_regression(model, df_future, feature_cols):
    """
    Forecast using trained regression model.
    """
    
    X_future = df_future[feature_cols].fillna(0)
    forecast = model.predict(X_future)
    
    return forecast
```

#### **Điểm mạnh:**
- ✅ Flexible (có thể thêm nhiều features)
- ✅ Capture non-linear relationships (RF, XGBoost)
- ✅ Có thể dùng macro features
- ✅ Có thể dùng lag features

#### **Điểm yếu:**
- ❌ Cần nhiều data để train
- ❌ Risk overfitting
- ❌ Không capture state transitions

#### **Khi nào tốt:**
- Có nhiều features (macro, seasonality, ...)
- Relationship phức tạp (non-linear)
- Data đủ lớn để train

---

### **Method 4: Exponential Smoothing**

#### **Mô tả:**
- Dùng exponential smoothing (Holt-Winters)
- Tốt cho data có trend + seasonality
- Đơn giản, nhanh

#### **Implementation:**
```python
from statsmodels.tsa.holtwinters import ExponentialSmoothing

def forecast_with_exponential_smoothing(df_historical, product, score, mob, horizon=12):
    """
    Forecast DEL90_PCT using Exponential Smoothing (Holt-Winters).
    """
    
    # Filter segment
    df_seg = df_historical[
        (df_historical['PRODUCT_TYPE'] == product) &
        (df_historical['RISK_SCORE'] == score) &
        (df_historical['MOB'] == mob)
    ].sort_values('VINTAGE_DATE')
    
    if len(df_seg) < 24:
        return None
    
    # Prepare time series
    ts = df_seg.set_index('VINTAGE_DATE')['DEL90_PCT']
    
    # Fit Holt-Winters
    # seasonal_periods = 12 (monthly seasonality)
    model = ExponentialSmoothing(
        ts,
        trend='add',           # additive trend
        seasonal='add',        # additive seasonality
        seasonal_periods=12,   # 12 months
    )
    fitted = model.fit()
    
    # Forecast
    forecast = fitted.forecast(steps=horizon)
    
    return forecast
```

#### **Điểm mạnh:**
- ✅ Đơn giản, nhanh
- ✅ Capture trend + seasonality
- ✅ Ít parameters

#### **Điểm yếu:**
- ❌ Giả định linear trend
- ❌ Không capture state transitions
- ❌ Cần data đủ dài

#### **Khi nào tốt:**
- Trend + seasonality rõ ràng
- Cần forecast nhanh
- Data đủ dài (>24 tháng)

---

## 🎯 ENSEMBLE STRATEGY

### **Strategy 1: Simple Average**

```python
def ensemble_simple_average(forecasts: List[pd.Series]) -> pd.Series:
    """
    Trung bình đơn giản của tất cả methods.
    
    Forecast_Final = (F1 + F2 + F3 + ...) / N
    """
    
    # Stack all forecasts
    df_stack = pd.concat(forecasts, axis=1)
    
    # Average
    forecast_avg = df_stack.mean(axis=1)
    
    return forecast_avg
```

**Ưu điểm:** Đơn giản, robust
**Nhược điểm:** Không tận dụng được performance khác nhau của từng method

---

### **Strategy 2: Weighted Average (Performance-based)**

```python
def compute_ensemble_weights(
    forecasts: List[pd.Series],
    actuals: pd.Series,
    method: str = 'inverse_mape'
) -> np.ndarray:
    """
    Tính weights dựa trên historical performance.
    
    Methods:
    - 'inverse_mape': w_i = (1/MAPE_i) / sum(1/MAPE_j)
    - 'inverse_rmse': w_i = (1/RMSE_i) / sum(1/RMSE_j)
    - 'softmax': w_i = exp(-MAPE_i) / sum(exp(-MAPE_j))
    """
    
    n_methods = len(forecasts)
    errors = []
    
    for fc in forecasts:
        # Align forecast with actuals
        aligned = pd.concat([fc, actuals], axis=1, join='inner')
        
        if method == 'inverse_mape':
            # MAPE = mean(|actual - forecast| / actual)
            mape = (
                (aligned.iloc[:, 1] - aligned.iloc[:, 0]).abs() / 
                aligned.iloc[:, 1].replace(0, np.nan)
            ).mean()
            errors.append(mape)
        
        elif method == 'inverse_rmse':
            # RMSE = sqrt(mean((actual - forecast)^2))
            rmse = np.sqrt(
                ((aligned.iloc[:, 1] - aligned.iloc[:, 0]) ** 2).mean()
            )
            errors.append(rmse)
    
    errors = np.array(errors)
    
    # Compute weights
    if method in ['inverse_mape', 'inverse_rmse']:
        # w_i = (1/error_i) / sum(1/error_j)
        inv_errors = 1 / (errors + 1e-6)  # avoid division by zero
        weights = inv_errors / inv_errors.sum()
    
    elif method == 'softmax':
        # w_i = exp(-error_i) / sum(exp(-error_j))
        weights = np.exp(-errors)
        weights = weights / weights.sum()
    
    return weights


def ensemble_weighted_average(
    forecasts: List[pd.Series],
    weights: np.ndarray
) -> pd.Series:
    """
    Weighted average của các methods.
    
    Forecast_Final = w1×F1 + w2×F2 + w3×F3 + ...
    """
    
    # Stack all forecasts
    df_stack = pd.concat(forecasts, axis=1)
    
    # Weighted average
    forecast_weighted = (df_stack * weights).sum(axis=1)
    
    return forecast_weighted
```

**Ưu điểm:** Tận dụng performance khác nhau
**Nhược điểm:** Cần historical data để tính weights

---

### **Strategy 3: Dynamic Weighting (Adaptive)**

```python
def ensemble_dynamic_weighting(
    forecasts: List[pd.Series],
    actuals_recent: pd.Series,
    window: int = 6
) -> pd.Series:
    """
    Weights thay đổi theo thời gian dựa trên recent performance.
    
    Logic:
    - Tính performance trong window gần nhất (6 tháng)
    - Update weights mỗi tháng
    - Methods tốt gần đây → weight cao hơn
    """
    
    n_methods = len(forecasts)
    n_periods = len(forecasts[0])
    
    result = []
    
    for t in range(n_periods):
        # Get recent actuals (window gần nhất)
        if t < window:
            # Chưa đủ history → dùng equal weights
            weights = np.ones(n_methods) / n_methods
        else:
            # Tính performance trong window
            recent_actuals = actuals_recent.iloc[t-window:t]
            recent_forecasts = [fc.iloc[t-window:t] for fc in forecasts]
            
            # Compute weights based on recent performance
            weights = compute_ensemble_weights(
                recent_forecasts,
                recent_actuals,
                method='inverse_mape'
            )
        
        # Weighted forecast tại thời điểm t
        fc_t = sum(fc.iloc[t] * w for fc, w in zip(forecasts, weights))
        result.append(fc_t)
    
    return pd.Series(result, index=forecasts[0].index)
```

**Ưu điểm:** Adaptive, phản ứng với thay đổi
**Nhược điểm:** Phức tạp hơn, cần nhiều data

---

### **Strategy 4: Stacking (Meta-Model)**

```python
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor

def ensemble_stacking(
    forecasts_train: List[pd.Series],
    actuals_train: pd.Series,
    forecasts_test: List[pd.Series],
    meta_model_type: str = 'ridge'
) -> pd.Series:
    """
    Stacking: Train meta-model để combine forecasts.
    
    Level 0: Base models (Transition Matrix, ARIMA, Regression, ...)
    Level 1: Meta-model (Ridge, RF, ...) học cách combine
    
    Input:
        forecasts_train: List of forecasts from base models (training)
        actuals_train: Actual values (training)
        forecasts_test: List of forecasts from base models (test)
        meta_model_type: 'ridge', 'random_forest', 'xgboost'
    
    Output:
        Final forecast (test)
    """
    
    # Prepare training data for meta-model
    # X = [forecast1, forecast2, forecast3, ...]
    # y = actuals
    X_train = pd.concat(forecasts_train, axis=1).values
    y_train = actuals_train.values
    
    # Train meta-model
    if meta_model_type == 'ridge':
        meta_model = Ridge(alpha=1.0)
    elif meta_model_type == 'random_forest':
        meta_model = RandomForestRegressor(n_estimators=50, max_depth=5)
    else:  # xgboost
        meta_model = xgb.XGBRegressor(n_estimators=50, max_depth=3)
    
    meta_model.fit(X_train, y_train)
    
    # Predict on test
    X_test = pd.concat(forecasts_test, axis=1).values
    forecast_final = meta_model.predict(X_test)
    
    return pd.Series(forecast_final, index=forecasts_test[0].index)
```

**Ưu điểm:** Tự động học cách combine tốt nhất
**Nhược điểm:** Cần nhiều data, risk overfitting

---

## 📊 IMPLEMENTATION ROADMAP

### **Phase 1: Setup Infrastructure (Tuần 1)**

```python
# File: src/rollrate/ensemble.py

class EnsembleForecaster:
    """
    Ensemble forecaster kết hợp nhiều methods.
    """
    
    def __init__(self, methods: List[str]):
        """
        methods: ['transition_matrix', 'arima', 'prophet', 'regression', 'exp_smoothing']
        """
        self.methods = methods
        self.models = {}
        self.weights = None
    
    def fit(self, df_train, df_macro=None):
        """
        Train tất cả methods.
        """
        for method in self.methods:
            if method == 'transition_matrix':
                # Đã có sẵn
                pass
            elif method == 'arima':
                # Train ARIMA per segment
                pass
            elif method == 'prophet':
                # Train Prophet per segment
                pass
            elif method == 'regression':
                # Train regression model
                self.models[method] = train_regression_model(df_train)
            elif method == 'exp_smoothing':
                # Train Holt-Winters per segment
                pass
    
    def forecast(self, df_latest, horizon=12):
        """
        Forecast bằng tất cả methods và combine.
        """
        forecasts = []
        
        for method in self.methods:
            if method == 'transition_matrix':
                fc = self._forecast_transition_matrix(df_latest, horizon)
            elif method == 'arima':
                fc = self._forecast_arima(df_latest, horizon)
            # ... other methods
            
            forecasts.append(fc)
        
        # Combine
        if self.weights is None:
            # Simple average
            forecast_final = ensemble_simple_average(forecasts)
        else:
            # Weighted average
            forecast_final = ensemble_weighted_average(forecasts, self.weights)
        
        return forecast_final
    
    def compute_weights(self, df_validation):
        """
        Tính weights dựa trên validation set.
        """
        # Forecast on validation
        forecasts_val = []
        for method in self.methods:
            fc = self._forecast_method(method, df_validation)
            forecasts_val.append(fc)
        
        # Compute weights
        actuals_val = df_validation['DEL90_PCT']
        self.weights = compute_ensemble_weights(
            forecasts_val,
            actuals_val,
            method='inverse_mape'
        )
        
        print("📊 Ensemble weights:")
        for method, w in zip(self.methods, self.weights):
            print(f"   {method}: {w:.3f}")
```

---

### **Phase 2: Implement Base Methods (Tuần 2-3)**

1. ✅ Transition Matrix (đã có)
2. ✅ ARIMA/Prophet
3. ✅ Regression (XGBoost)
4. ✅ Exponential Smoothing

---

### **Phase 3: Ensemble & Validation (Tuần 4)**

1. ✅ Implement ensemble strategies
2. ✅ Backtest trên historical data
3. ✅ Compare performance
4. ✅ Select best strategy

---

## 📈 EXPECTED RESULTS

### **Baseline (Transition Matrix only):**
- MAPE: ~15-20%
- Coverage: ~80%

### **After Ensemble:**
- MAPE: ~10-15% (giảm 25-33%) ✅
- Coverage: ~90% ✅
- Robustness: Tăng đáng kể ✅

---

## 🎯 KẾT LUẬN

**Ensemble Forecasting là cải thiện mạnh nhất** nhưng cần:
1. Thời gian triển khai: 3-4 tuần
2. Data đủ lớn: >24 tháng historical
3. Computational resources: Tăng 3-4x

**Recommend:**
- Bắt đầu với **Simple Average** của 2-3 methods
- Sau đó nâng cấp lên **Weighted Average**
- Cuối cùng thử **Stacking** nếu cần

**Priority methods:**
1. Transition Matrix (đã có) ← Base
2. Regression (XGBoost) ← Thêm features
3. Prophet ← Capture seasonality tốt

---

**Tác giả:** Roll Rate Model Team  
**Ngày tạo:** 2026-02-09
