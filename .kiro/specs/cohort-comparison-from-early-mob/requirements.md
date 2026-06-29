# Spec: So sánh Cohort với Forecast từ MOB sớm (Early MOB Forecast Comparison)

## Mục tiêu
Thêm section mới vào notebook `Markovchainv2.ipynb` để so sánh công bằng giữa Forecast (With K) và Forecast (No K) bằng cách forecast từ MOB sớm (ví dụ: MOB=3) thay vì từ MOB cuối cùng của actual.

## Status: ✅ COMPLETED (Updated 2026-01-20)

## Thay đổi mới nhất (2026-01-20 - Session 2)
- **Fix VINTAGE_DATE matching**: Thêm `pd.to_datetime(vintage)` để đảm bảo match với `df_lifecycle_final`
- **Fix code duplicate**: Loại bỏ code bị duplicate trong section 7.13.4
- **Thêm debug chi tiết**:
  - In ra data types của product, score, vintage
  - So sánh `disb_total_from_df` với `loan_disb_cohort`
  - In sample DEL30_PCT và DEL30_AMT cho các MOB 3, 6, 12, 18, 24
  - Verify tại START_MOB: cả 3 đường phải bằng nhau
- **Thêm debug cho initial_ead** trong section 7.13.3:
  - In Total EAD và DEL30_AMT từ initial_ead
  - Verify forecast tại START_MOB = initial_ead

## Logic đúng
1. **Actual**: Lấy từ `df_lifecycle_final` với filter:
   - `PRODUCT_TYPE == product_str`
   - `RISK_SCORE == score_str`
   - `VINTAGE_DATE == vintage_dt` (converted to datetime)
   - `IS_FORECAST == 0`
   - DEL30_PCT đã được tính đúng trong `add_del_metrics()`

2. **Forecast (No K và With K)**: Tính từ `forecast_segment_partial_step`:
   - `initial_ead = mob_dict[START_MOB]` (từ actual_results)
   - DEL30_AMT = sum(EAD[bucket] for bucket in BUCKETS_30P)
   - DEL30_PCT = DEL30_AMT / DISB_TOTAL

3. **Verify**: Tại START_MOB, cả 3 đường phải BẰNG NHAU vì dùng cùng initial_ead

## Công thức
- **DEL30_PCT = DEL30_AMT / DISB_TOTAL**
- DISB_TOTAL: Tổng giải ngân ban đầu của cohort (không đổi theo MOB)
- DEL30_AMT: Sum of EAD in buckets DPD30+, DPD60+, DPD90+, DPD120+, DPD180+, WRITEOFF

## Files đã chỉnh sửa
- `notebooks/Markovchainv2.ipynb`: Section 7.13.3 và 7.13.4

## Bối cảnh vấn đề
- **Vấn đề hiện tại**: So sánh hiện tại không công bằng vì `forecast_all_vintages_partial_step` bắt đầu từ `max(mob_dict.keys())` (MOB cuối cùng của actual)
- **Hệ quả**: Forecast chỉ cover 1-2 MOBs beyond actual → không thể thấy rõ impact của K factor
- **Giải pháp**: Forecast từ MOB sớm (MOB=3) để thấy sự khác biệt thực sự giữa With K và No K

## User Stories

### US-1: So sánh cohort cụ thể từ MOB sớm
**As a** risk analyst  
**I want to** xem so sánh Actual vs Forecast (No K) vs Forecast (With K) cho cohort '2023-12' với forecast bắt đầu từ MOB=3  
**So that** tôi có thể đánh giá đúng impact của K calibration trên toàn bộ lifecycle

**Acceptance Criteria:**
- [x] Chọn cohort '2023-12' (hoặc cohort có đủ data actual)
- [x] Forecast bắt đầu từ MOB=3 (không phải từ MOB cuối cùng)
- [x] Hiển thị 3 đường: Actual, Forecast (No K), Forecast (With K)
- [x] Chart rõ ràng với legend và annotation

### US-2: Hiển thị K values được sử dụng
**As a** risk analyst  
**I want to** thấy K values được áp dụng tại mỗi MOB  
**So that** tôi hiểu tại sao Forecast (With K) khác Forecast (No K)

**Acceptance Criteria:**
- [x] In ra K values từ MOB 3 đến MOB max
- [x] Giải thích: K < 1 → With K thấp hơn No K

### US-3: Tính toán error metrics
**As a** risk analyst  
**I want to** xem MAE/MAPE giữa Actual và 2 loại forecast  
**So that** tôi có thể định lượng improvement từ K calibration

**Acceptance Criteria:**
- [x] Tính MAE cho Forecast (No K) vs Actual
- [x] Tính MAE cho Forecast (With K) vs Actual
- [x] So sánh và kết luận loại nào tốt hơn
- [x] **NEW**: Chart MAE/MAPE theo MOB (4 charts)

## Technical Details

### Function cần sử dụng
```python
from src.rollrate.calibration_kmob import forecast_segment_partial_step
```

### Logic forecast từ MOB sớm
```python
# Lấy initial state từ MOB=3 (không phải MOB cuối)
start_mob = 3
initial_ead = actual_results[vintage_key][start_mob]

# Forecast với K
fc_with_k = forecast_segment_partial_step(
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    product=product,
    score=score,
    start_mob=start_mob,
    initial_ead=initial_ead,
    max_mob=MAX_MOB,
    k_by_mob=k_final_by_mob,
    states=BUCKETS_CANON
)

# Forecast không K (k=1.0)
k_no_k = {m: 1.0 for m in range(1, MAX_MOB + 1)}
fc_no_k = forecast_segment_partial_step(
    matrices_by_mob=matrices_by_mob,
    parent_fallback=parent_fallback,
    product=product,
    score=score,
    start_mob=start_mob,
    initial_ead=initial_ead,
    max_mob=MAX_MOB,
    k_by_mob=k_no_k,
    states=BUCKETS_CANON
)
```

### Công thức K calibration
```
v_{m+1} = v_m + k_m * (v_hat - v_m)
```
- Nếu k=1.0 (No K): Full Markov step → `v_{m+1} = v_hat`
- Nếu k<1.0 (With K): Partial step → `v_{m+1}` nằm giữa `v_m` và `v_hat`

### DEL30+ Rate formula
```
DEL30_PCT = DEL30_AMT / DISB_TOTAL
```
- DISB_TOTAL: Tổng giải ngân ban đầu của cohort (không đổi theo MOB)

## Files cần chỉnh sửa
- `notebooks/Markovchainv2.ipynb`: Thêm section 7.13 (hoặc sau 7.12)

## References
- `src/rollrate/calibration_kmob.py`: Chứa `forecast_segment_partial_step()`
- `src/rollrate/lifecycle.py`: Chứa `get_actual_all_vintages_amount()`, `add_del_metrics()`
