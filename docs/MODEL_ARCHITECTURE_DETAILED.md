# Roll Rate Model - Kiến Trúc Chi Tiết

## Tổng Quan

Roll Rate Model là một hệ thống dự báo nợ xấu (DEL30+, DEL60+, DEL90+) dựa trên Markov Chain với hiệu chỉnh hệ số K. Model hoạt động theo các bước chính:

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   1. Load Data  │ ──▶ │ 2. Transition Matrix │ ──▶ │ 3. Calibration  │
│   (df_raw)      │     │    (matrices_by_mob) │     │    (K values)   │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
                                                              │
                                                              ▼
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   6. Export     │ ◀── │  5. Aggregate        │ ◀── │ 4. Forecast     │
│   (Excel)       │     │  (Product/Portfolio) │     │ (Partial-Step)  │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
```

---

## 1. Load Data (`src/data_loader.py`, `src/config.py`)

### Input Data Structure
```
df_raw columns:
├── AGREEMENT_ID      : ID khoản vay (loan)
├── CUTOFF_DATE       : Ngày snapshot (YYYYMM)
├── DISBURSAL_DATE    : Ngày giải ngân
├── DISBURSAL_AMOUNT  : Số tiền giải ngân
├── PRINCIPLE_OUTSTANDING : Dư nợ gốc (EAD)
├── MOB               : Months on Book
├── PRODUCT_TYPE      : Loại sản phẩm (C, S, T)
├── STATE_MODEL       : Trạng thái nợ (DPD0, DPD1+, DPD30+, ...)
├── RISK_SCORE        : Điểm rủi ro
└── [Các cột segment khác]
```

### State Space (BUCKETS_CANON)
```python
BUCKETS_CANON = [
    "DPD0",      # Current (không quá hạn)
    "DPD1+",     # 1-29 ngày quá hạn
    "DPD30+",    # 30-59 ngày quá hạn
    "DPD60+",    # 60-89 ngày quá hạn
    "DPD90+",    # 90-119 ngày quá hạn
    "DPD120+",   # 120-179 ngày quá hạn
    "DPD180+",   # 180+ ngày quá hạn
    "PREPAY",    # Tất toán sớm (absorbing)
    "WRITEOFF",  # Xóa nợ (absorbing)
    "SOLDOUT"    # Bán nợ (absorbing)
]
```

### Segmentation
```python
# Cohort = (PRODUCT_TYPE, RISK_SCORE, VINTAGE_DATE)
# Ví dụ: ("C", "650+_10M-_POS", "2023-12-01")
```

---

## 2. Build Transition Matrices (`src/rollrate/transition.py`)

### 2.1 Tạo Pairs (make_pairs)

Chuyển đổi loan-level data thành các cặp chuyển trạng thái:

```
Loan A: MOB=3, STATE=DPD0  ──▶  MOB=4, STATE=DPD1+
        ↓
Pair: (state_t=DPD0, state_t1=DPD1+, mob_t=3, ead_t=100,000)
```

**Time Weighting (WHA - Weighted Historical Average):**
```python
# Exponential decay: gần đây quan trọng hơn
time_weight = DECAY_LAMBDA ** age
# DECAY_LAMBDA = 0.5^(1/12) ≈ 0.944
# ROLL_WINDOW = 12 tháng
```

**EAD Weighting:**
```python
ead_t = ead_raw * time_weight
# Khoản vay lớn có trọng số cao hơn
```

### 2.2 Compute Transition Matrix

**Cấu trúc output:**
```python
matrices_by_mob[product][mob][score] = {
    "P": DataFrame,      # Ma trận transition (10x10)
    "is_fallback": bool, # True nếu dùng parent fallback
    "reason": str        # Lý do fallback
}

parent_fallback[(product, score)] = DataFrame  # Ma trận parent
```

**Quy trình:**
```
1. Group pairs theo (product, score) → tính P_parent
2. Group tiếp theo mob:
   - Nếu n_obs >= MIN_OBS (100) và total_ead >= MIN_EAD (100):
     → Tính P_child từ pairs
   - Ngược lại:
     → Dùng P_parent (fallback)
```

**Ma trận Transition (P):**
```
           DPD0   DPD1+  DPD30+  DPD60+  DPD90+  ...  WRITEOFF
DPD0      0.85   0.10   0.03    0.01    0.005   ...  0.005
DPD1+     0.30   0.40   0.20    0.05    0.03    ...  0.02
DPD30+    0.10   0.15   0.35    0.25    0.10    ...  0.05
...
WRITEOFF  0.00   0.00   0.00    0.00    0.00    ...  1.00  ← Absorbing
```

**Absorbing States:**
```python
ABSORBING_BASE = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]
# Các state này có P[state, state] = 1.0 (không chuyển đi đâu)
```

---

## 3. Calibration - Fit K Values (`src/rollrate/calibration_kmob.py`)

### 3.1 Tại sao cần hệ số K?

Markov Chain thuần túy có thể over/under-estimate DEL rates vì:
- Không tính đến yếu tố kinh tế vĩ mô
- Không tính đến seasonality
- Historical data có thể không đại diện cho tương lai

**Hệ số K điều chỉnh:**
- K > 1: Model đang under-estimate → scale up
- K < 1: Model đang over-estimate → scale down
- K ≈ 1: Model dự đoán tốt

### 3.2 Fit K_raw (fit_k_raw)

**Input:**
```python
actual_results = {
    (product, score, vintage): {
        mob: pd.Series(EAD theo state)
    }
}
```

**Công thức WLS Regularized:**
```
Với mỗi cohort và cặp MOB liên tiếp (m → m+1):

1. v_m = vector EAD tại MOB m (normalized)
2. v_hat = v_m @ P_m (one-step Markov forecast)
3. v_m1 = vector EAD actual tại MOB m+1

4. Tính increments:
   - y_vm = DEL30(v_m) / DISB_TOTAL
   - y_hat = DEL30(v_hat) / DISB_TOTAL
   - y_tar = DEL30(v_m1) / DISB_TOTAL
   
   - a = y_hat - y_vm  (Markov increment)
   - d = y_tar - y_vm  (Actual increment)

5. Aggregate theo MOB:
   numerator = Σ(w × a × d)
   denominator = Σ(w × a²)
   
   k_m = (numerator + λ × k_prior) / (denominator + λ)
   k_m = clip(k_m, 0, 1)
```

**Parameters:**
```python
method = "wls_reg"      # Weighted Least Squares với regularization
weight_mode = "equal"   # Trọng số bằng nhau cho các cohort
denom_mode = "disb"     # Tính DEL trên DISB_TOTAL
lambda_k = 1e-4         # Regularization strength
k_prior = 0.0           # Prior value (bias toward 0)
min_obs = 5             # Số quan sát tối thiểu
fallback_k = 1.0        # K mặc định nếu không đủ data
```

### 3.3 Smooth K (smooth_k)

Làm mượt đường K qua các MOB bằng second-difference penalty:

```
Minimize: Σ w_m × (k_m - k_raw_m)² + γ × Σ (k_{m+2} - 2×k_{m+1} + k_m)²

Subject to: 0 ≤ k_m ≤ 1
```

**Parameters:**
```python
gamma = 10.0      # Smoothing strength
monotone = False  # Không bắt buộc monotonic
```

**Ví dụ:**
```
MOB:      5     6     7     8     9
k_raw:   0.76  0.60  0.95  0.50  0.70
k_smooth: 0.74  0.68  0.78  0.65  0.68  ← Mượt hơn
```

### 3.4 Fit Alpha (fit_alpha)

Scale toàn bộ đường K để fit tốt nhất tại MOB target:

```
k_final[m] = clip(alpha × k_smooth[m], 0, 1)
```

**Quy trình:**
```
1. Chia cohorts: 80% train, 20% validation (vintages mới nhất)
2. Grid search alpha ∈ [0.5, 1.5] với step 0.01
3. Với mỗi alpha:
   - Forecast từ MOB đầu đến MOB target
   - Tính MAE giữa forecast và actual tại MOB target
4. Chọn alpha có MAE nhỏ nhất
```

---

## 4. Forecast với Partial-Step K (`forecast_segment_partial_step`)

### 4.1 Công thức Partial-Step

```
v_{m+1} = v_m + k_m × (v_hat - v_m)
        = (1 - k_m) × v_m + k_m × v_hat
```

**Ý nghĩa:**
- k_m = 1.0: Hoàn toàn tin Markov → v_{m+1} = v_hat
- k_m = 0.0: Giữ nguyên → v_{m+1} = v_m
- k_m = 0.5: Đi nửa đường → v_{m+1} = 0.5×v_m + 0.5×v_hat

### 4.2 Ví dụ số

```
MOB 5 → MOB 6:
- v_m (current):  [DPD0=900, DPD30+=80, WRITEOFF=20]
- v_hat (Markov): [DPD0=850, DPD30+=110, WRITEOFF=40]
- k_m = 0.78

v_{m+1} = [900, 80, 20] + 0.78 × ([850, 110, 40] - [900, 80, 20])
        = [900, 80, 20] + 0.78 × [-50, 30, 20]
        = [900 - 39, 80 + 23.4, 20 + 15.6]
        = [861, 103.4, 35.6]
```

### 4.3 Forecast All Vintages

```python
for (product, score, vintage) in actual_results:
    start_mob = max(actual_mobs)  # MOB actual cuối cùng
    initial_ead = actual_results[key][start_mob]
    
    for mob in range(start_mob, MAX_MOB):
        P_m = get_transition_matrix(product, score, mob)
        v_hat = current @ P_m
        k_m = k_final_by_mob.get(mob, 1.0)
        current = current + k_m × (v_hat - current)
        forecast[mob + 1] = current
```

---

## 5. Lifecycle & Aggregation (`src/rollrate/lifecycle.py`)

### 5.1 Combine Actual + Forecast

```python
lifecycle[(product, score, vintage)] = {
    mob_1: actual_ead,    # Actual
    mob_2: actual_ead,    # Actual
    ...
    mob_n: actual_ead,    # Actual (cuối)
    mob_n+1: forecast_ead, # Forecast
    mob_n+2: forecast_ead, # Forecast
    ...
    MAX_MOB: forecast_ead  # Forecast
}
```

### 5.2 Convert to Long Format

```
PRODUCT_TYPE | RISK_SCORE | VINTAGE_DATE | MOB | DPD0 | DPD30+ | ... | IS_FORECAST
-------------|------------|--------------|-----|------|--------|-----|------------
C            | 650+_POS   | 2023-12      | 1   | 900  | 50     | ... | 0
C            | 650+_POS   | 2023-12      | 2   | 850  | 80     | ... | 0
C            | 650+_POS   | 2023-12      | 12  | 600  | 200    | ... | 1  ← Forecast
```

### 5.3 Add DEL Metrics

```python
# DEL30+ = DPD30+ + DPD60+ + DPD90+ + DPD120+ + DPD180+ + WRITEOFF
DEL30_AMT = df[BUCKETS_30P].sum(axis=1)
DEL30_PCT = DEL30_AMT / DISB_TOTAL

# DISB_TOTAL = Tổng giải ngân của cohort (cố định, không đổi theo MOB)
```

### 5.4 Aggregate to Product Level

```
Từ: (Product × Score × Vintage × MOB)
Lên: (Product × Vintage × MOB)

Weight = DISB_SCORE / DISB_PRODUCT

DEL30_PCT_product = Σ(DEL30_PCT_score × Weight_score)
```

### 5.5 Aggregate to Portfolio Level

```
Từ: (Product × Vintage × MOB)
Lên: (Portfolio × Vintage × MOB)

Weight = DISB_PRODUCT / DISB_PORTFOLIO

DEL30_PCT_portfolio = Σ(DEL30_PCT_product × Weight_product)
```

---

## 6. Export (`src/rollrate/lifecycle_export_enhanced.py`)

### 6.1 Lifecycle Excel

```
Sheet: C_DEL30, C_DEL60, C_DEL90, S_DEL30, ..., PORTFOLIO_DEL30, ...

Format:
- Heatmap: Xanh (thấp) → Vàng → Đỏ (cao)
- Forecast cells: Nền vàng nhạt
- Actual cuối: Viền đỏ đậm
- Values: % format (0.00%)
```

### 6.2 Config Info Sheet

```
Parameter        | Value
-----------------|------------------
DATA_PATH        | C:/Users/.../ETB_Parquet
MAX_MOB          | 24
TARGET_MOBS      | [24]
SEGMENT_COLS     | [PRODUCT_TYPE, RISK_SCORE]
MIN_OBS          | 100
DECAY_LAMBDA     | 0.944
...
```

---

## 7. Allocation to Loan-Level (`src/rollrate/allocation_v2_optimized.py`)

### 7.1 Logic Tối Ưu

```
Với mỗi cohort tại TARGET_MOB:
├── Nếu có actual data tại TARGET_MOB:
│   └── Lấy trực tiếp từ df_raw (không cần allocate)
└── Nếu chỉ có forecast:
    └── Allocate forecast xuống từng loan
```

### 7.2 Allocation Formula

```
Với mỗi loan trong cohort:
- loan_ead = EAD của loan tại snapshot cuối
- cohort_ead = Tổng EAD của cohort
- loan_share = loan_ead / cohort_ead

Forecast cho loan:
- DEL30_AMT_loan = DEL30_AMT_cohort × loan_share
- DEL90_FLAG = 1 nếu STATE ∈ BUCKETS_90P
```

---

## 8. Diagram Tổng Hợp

```
                                    ┌─────────────────────────────────┐
                                    │         RAW DATA (df_raw)       │
                                    │  Loan × Cutoff × MOB × State    │
                                    └─────────────┬───────────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │                             │                             │
                    ▼                             ▼                             ▼
        ┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
        │   make_pairs()    │         │ get_actual_all_   │         │ disb_total_by_    │
        │   Tạo cặp state   │         │ vintages_amount() │         │ vintage           │
        │   transitions     │         │ Actual EAD/MOB    │         │ DISB cố định      │
        └─────────┬─────────┘         └─────────┬─────────┘         └─────────┬─────────┘
                  │                             │                             │
                  ▼                             │                             │
        ┌───────────────────┐                   │                             │
        │ compute_transition│                   │                             │
        │ _by_mob()         │                   │                             │
        │ P[prod][mob][scr] │                   │                             │
        └─────────┬─────────┘                   │                             │
                  │                             │                             │
                  └──────────────┬──────────────┴─────────────────────────────┘
                                 │
                                 ▼
                    ┌───────────────────────────┐
                    │      fit_k_raw()          │
                    │  K_raw = WLS regression   │
                    │  trên (actual - Markov)   │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │      smooth_k()           │
                    │  K_smooth = 2nd-diff      │
                    │  penalty smoothing        │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │      fit_alpha()          │
                    │  K_final = α × K_smooth   │
                    │  Grid search α            │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ forecast_all_vintages_    │
                    │ partial_step()            │
                    │ v_{m+1} = v_m + k×(v̂-v_m) │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ combine_all_lifecycle_    │
                    │ amount()                  │
                    │ Actual + Forecast merged  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐
        │ add_del_metrics() │       │ aggregate_to_     │
        │ DEL30/60/90 AMT   │       │ product()         │
        │ DEL30/60/90 PCT   │       │ Score → Product   │
        └─────────┬─────────┘       └─────────┬─────────┘
                  │                           │
                  │                           ▼
                  │               ┌───────────────────┐
                  │               │ aggregate_products│
                  │               │ _to_portfolio()   │
                  │               │ Product → Port    │
                  │               └─────────┬─────────┘
                  │                         │
                  └────────────┬────────────┘
                               │
                               ▼
                    ┌───────────────────────────┐
                    │ export_lifecycle_with_    │
                    │ config_info()             │
                    │ Excel với heatmap         │
                    └───────────────────────────┘
```

---

## 9. Key Parameters Summary

| Parameter | Default | Mô tả |
|-----------|---------|-------|
| MAX_MOB | 24 | Forecast đến MOB này |
| TARGET_MOBS | [24] | MOB để allocate loan-level |
| MIN_OBS | 100 | Số quan sát tối thiểu cho transition matrix |
| MIN_EAD | 100 | Tổng EAD tối thiểu |
| ROLL_WINDOW | 12 | Số tháng historical data |
| DECAY_LAMBDA | 0.944 | Exponential decay factor |
| lambda_k | 1e-4 | Regularization cho WLS |
| k_prior | 0.0 | Prior value cho K |
| gamma | 10.0 | Smoothing strength |
| alpha_grid | [0.5, 1.5] | Range tìm kiếm alpha |

---

## 10. Files Reference

```
src/
├── config.py                    # Configuration & column mappings
├── data_loader.py               # Load parquet/excel data
└── rollrate/
    ├── transition.py            # Build transition matrices
    ├── calibration_kmob.py      # Fit K values (k_raw, k_smooth, alpha)
    ├── lifecycle.py             # Actual/Forecast lifecycle, aggregation
    ├── lifecycle_export_enhanced.py  # Excel export with config info
    ├── allocation_v2_optimized.py    # Loan-level allocation
    └── forecast.py              # Basic forecast functions

notebooks/
├── Final_Workflow.ipynb         # Main workflow notebook
├── Markovchain_Cohort_Comparison.ipynb  # Cohort comparison analysis
└── Markovchainv2.ipynb          # Extended analysis
```
