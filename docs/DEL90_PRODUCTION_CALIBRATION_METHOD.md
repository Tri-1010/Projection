# Phương pháp DEL90 Production Calibration

## 1. Mục tiêu

Notebook production mới:

`notebooks/Group_Master_Total_Production_Calibrated.ipynb`

bổ sung một lớp calibration DEL90 trên kết quả Markov để:

- Giảm sai lệch có hệ thống giữa DEL90 forecast và actual.
- Sử dụng đúng điểm xuất phát hiện tại của từng cohort.
- Cập nhật theo hành vi gần nhất nhưng không phụ thuộc một tháng duy nhất.
- Giữ tổng loan-level EAD DEL90 khớp với lifecycle target.
- Có guardrail để calibration không làm kết quả lịch sử xấu hơn base model.

Lớp calibration này không thay thế Markov chain. Markov vẫn là model nền để tạo
transition, đường state và loan-level raw probability.

---

## 2. Luồng model cũ

Notebook cũ:

`notebooks/Group_Master_Total.ipynb`

có luồng chính:

1. Tạo transition matrix theo MOB và segment.
2. Fit hệ số K và alpha.
3. Forecast state vector của cohort đến target MOB.
4. Tính `DEL30_PCT`, `DEL60_PCT`, `DEL90_PCT`.
5. Phân bổ lifecycle target xuống từng loan.

Nói chính xác hơn, bản cũ đã có calibration, nhưng là các loại calibration khác:

- `K calibration` trong lifecycle forecast.
- `Loan-level probability reconciliation` để tổng loan-level khớp lifecycle.

Điểm bản cũ chưa có là lớp `portfolio residual calibration` riêng cho DEL90 theo
anchor MOB và theo các vintage gần nhất.

Kết quả DEL90 cũ về cơ bản là:

```text
DEL90_PCT_FINAL = DEL90_PCT_MARKOV_K
```

Nếu model có xu hướng thấp hơn actual 2pp trong các vintage gần đây, sai lệch
này chưa được sửa bằng một lớp residual DEL90 riêng. K có thể giảm một phần sai
lệch, nhưng K được fit trên toàn bộ đường lifecycle và không nhất thiết sửa đúng
level DEL90 tại MOB12.

### Bản cũ đang calibrate cái gì?

#### 2.1. K calibration

Trong pipeline cũ, `run_full_pipeline(...)` gọi:

- `compute_k_per_product_anchor(...)`
- `apply_k_to_lifecycle(...)`
- `apply_k_to_sale_plan(...)`

Mục đích của lớp này là hiệu chỉnh forecast lifecycle bằng hệ số K. Có thể hiểu
đây là calibration ở tầng forecast curve.

#### 2.2. Loan-level probability reconciliation

Ở tầng phân bổ xuống loan, code cũng có bước hiệu chỉnh xác suất để tổng
loan-level expected amount khớp với target lifecycle. Đây cũng là một dạng
calibration, nhưng là calibration ở tầng allocation chứ không phải calibration
riêng cho DEL90 portfolio bias.

### Hạn chế của bản cũ

- Không có adjustment riêng theo MOB hiện tại của cohort.
- Cohort đang ở MOB2 và cohort đang ở MOB10 có thể cùng chịu một logic level.
- Không có rolling residual từ các cohort đã mature gần nhất.
- Không có guardrail so sánh base MAE và calibrated MAE.
- Không lưu rõ base forecast và phần adjustment để audit.

---

## 3. Luồng production mới

Luồng mới có ba lớp:

```text
Transition Markov
    -> K + alpha forecast
    -> DEL90 portfolio residual calibration
    -> loan-level probability reconciliation
```

### 3.1. Markov và K

Transition matrix vẫn được tính theo:

```text
PRODUCT_TYPE
RISK_SCORE composite
MOB
```

Với segmentation production:

```python
['PRODUCT_TYPE', 'RISK_SCORE', 'SALE_CHANNEL', 'GENDER']
```

pipeline chuyển các biến ngoài `PRODUCT_TYPE` thành một composite key:

```text
RISK_SCORE = original risk + sale channel + gender
```

Ví dụ:

```text
H + D + M -> H_D_M
```

Notebook hiện tại cấu hình:

```python
'del90_k_source': 'del30'
```

Nghĩa là DEL90 forecast sử dụng đường K fit trên metric states DEL30. Lý do là
backtest gần nhất cho thấy đường K DEL30 ổn định hơn khi dự báo DEL90. Tuy
nhiên, target calibration, actual và output cuối vẫn là DEL90.

Có thể chuyển sang K DEL90 riêng:

```python
'del90_k_source': 'del90'
```

mà không thay đổi logic residual calibration.

---

## 4. Residual calibration là gì?

Với mỗi historical vintage đã đủ MOB12:

```text
residual_vintage = ACTUAL_DEL90_MOB12 - PREDICTED_DEL90_MOB12
```

Ví dụ:

```text
Actual DEL90 MOB12 = 24.0%
Base prediction    = 21.5%
Residual           = +2.5pp
```

Residual dương nghĩa là base model đang dự báo thấp.

Residual âm nghĩa là base model đang dự báo cao.

### 4.1. Trọng số theo quy mô và độ gần

Mỗi residual được gán trọng số:

```text
weight_vintage = DISB_TOTAL * recency_weight
```

Trong đó:

```text
recency_weight = 0.5 ** (age_months / half_life_months)
```

Cấu hình hiện tại:

```python
'del90_calibration_half_life_months': 3.0
```

Do đó:

| Độ cũ của vintage | Recency weight |
|---:|---:|
| 0 tháng | 1.000 |
| 3 tháng | 0.500 |
| 6 tháng | 0.250 |

Vintage gần và có disbursal lớn sẽ có ảnh hưởng cao hơn.

### 4.2. Raw adjustment

```text
RAW_ADJ =
    sum(residual_vintage * weight_vintage)
    / sum(weight_vintage)
```

Đây là sai lệch level trung bình có trọng số của base model.

### 4.3. Shrink

Không áp toàn bộ residual ngay lập tức:

```text
adjustment_before_cap = RAW_ADJ * SHRINK
```

Cấu hình production:

```python
'del90_calibration_shrink': 0.5
```

Ví dụ:

```text
RAW_ADJ = +2.5pp
SHRINK  = 0.5
ADJ     = +1.25pp
```

Shrink làm calibration bớt nhạy với noise hoặc behavior tạm thời.

### 4.4. Residual cap

Adjustment bị giới hạn:

```text
ADJ = clip(RAW_ADJ * SHRINK, -5pp, +5pp)
```

Cấu hình:

```python
'del90_calibration_residual_cap': 0.05
```

Ngay cả khi historical residual rất lớn, một lần calibration không được dịch
forecast quá 5 điểm phần trăm.

---

## 5. Calibration theo anchor MOB

`anchor MOB` là MOB actual mới nhất của cohort tại thời điểm forecast.

Ví dụ:

```text
Target MOB = 12
Cohort đã có data đến MOB = 6
Anchor MOB = 6
```

Production curve được fit cho từng anchor:

```python
'del90_calibration_anchor_mobs': list(range(12))
```

Tương ứng MOB0 đến MOB11.

### Tại sao phải tách theo anchor?

Sai số forecast từ MOB2 đến MOB12 khác sai số từ MOB10 đến MOB12:

- MOB2 còn 10 transition steps.
- MOB10 chỉ còn 2 transition steps.
- Sai số tích lũy và uncertainty khác nhau.
- Ảnh hưởng của current state cũng khác nhau.

Do đó mỗi anchor có:

```text
RAW_ADJ(anchor)
ADJ(anchor)
BASE_MAE(anchor)
CALIBRATED_MAE(anchor)
```

Nếu vì lý do dữ liệu một anchor không có curve, pipeline có thể nội suy từ các
anchor lân cận. Cấu hình MOB0-MOB11 giúp hạn chế tối đa nhu cầu nội suy.

---

## 6. True as-of calibration

Historical forecast không được phép nhìn thấy tương lai.

Ví dụ backtest target MOB12 từ anchor MOB6:

```text
Lookback = 12 - 6 = 6 tháng
```

Với historical vintage:

1. Xác định cutoff khi vintage đạt MOB12.
2. Lùi cutoff 6 tháng.
3. Chỉ dùng data có `CUTOFF_DATE <= as-of cutoff`.
4. Fit transition và K trên tập data tại thời điểm đó.
5. Forecast từ MOB6 đến MOB12.
6. So sánh với actual MOB12.

Vì vậy residual là residual out-of-time giả lập, không phải fitted error sử dụng
dữ liệu tương lai.

---

## 7. Guardrail production

### 7.1. Minimum number of vintages

```python
'del90_calibration_n_vintages': 6
'del90_calibration_min_vintages': 4
```

Pipeline lấy tối đa 6 mature vintages gần nhất. Nếu một anchor chỉ có dưới 4
historical forecast hợp lệ, calibration cho anchor đó không được tạo.

### 7.2. Minimum exposure

```python
'del90_calibration_min_disb': 1.0
```

Nếu tổng disbursal calibration thấp hơn ngưỡng, adjustment không được tạo.
Đơn vị phụ thuộc đơn vị `DISBURSAL_AMOUNT` của data nguồn.

### 7.3. MAE guardrail

Pipeline tính:

```text
BASE_MAE =
    weighted mean(abs(base prediction - actual))

CALIBRATED_MAE =
    weighted mean(abs(base prediction + ADJ - actual))
```

Nếu:

```text
CALIBRATED_MAE > BASE_MAE
```

thì:

```text
ADJ = 0
STATUS = guardrail_rejected
```

Cấu hình:

```python
'del90_calibration_mae_guardrail': True
```

Calibration chỉ được áp nếu nó cải thiện hoặc ít nhất không làm xấu historical
weighted MAE.

### 7.4. DEL90 không vượt DEL30

Sau calibration:

```text
DEL90_PCT =
    min(DEL90_PCT_BASE + ADJ, DEL30_PCT)
```

Đồng thời kết quả bị clip trong khoảng `[0, 1]`.

Điều này đảm bảo tính chất:

```text
DEL90 subset of DEL30
```

---

## 8. Residual ảnh hưởng đến kết quả như thế nào?

### 8.1. Tại lifecycle level

Pipeline lưu:

```text
DEL90_PCT_BASE
DEL90_CAL_ADJ
DEL90_PCT
DEL90_AMT
```

Công thức:

```text
DEL90_PCT = DEL90_PCT_BASE + DEL90_CAL_ADJ
DEL90_AMT = DEL90_PCT * DISB_TOTAL
```

Ví dụ:

```text
DISB_TOTAL     = 100 tỷ
DEL90_PCT_BASE = 20.0%
DEL90_CAL_ADJ  = +1.5pp
DEL90_PCT      = 21.5%
DEL90_AMT      = 21.5 tỷ
```

Residual +1.5pp làm EAD DEL90 tăng:

```text
100 tỷ * 1.5% = 1.5 tỷ
```

### 8.2. Residual không thay state path

Calibration chỉ overwrite:

```text
DEL90_PCT
DEL90_AMT
```

Nó không overwrite:

- Transition matrix.
- DEL30 state vector.
- DEL60.
- State-level EAD path.
- `EAD_FORECAST`.
- Actual rows.

Vì vậy residual là một adjustment cho DEL90 reporting hoặc expected amount, chứ
không phải một lần forecast lại toàn bộ state lifecycle.

### 8.3. Tại loan level

Mỗi loan đầu tiên có raw DEL90 probability từ Markov:

```text
PROB_DEL90_RAW(loan)
```

Sau đó probability được dịch trên logit scale để:

```text
sum(DISBURSAL_AMOUNT * PROB_DEL90)
    = lifecycle calibrated DEL90 target
```

Kết quả:

- Loan có raw probability cao vẫn được xếp trên loan có probability thấp.
- Tổng expected EAD DEL90 khớp lifecycle.
- Residual dương làm probability của các loan trong cohort tăng.
- Residual âm làm probability giảm.

Residual không chia đều một tỷ lệ cơ học cho mọi loan. Logit shift giữ được thứ
tự rủi ro của raw Markov probability.

### 8.4. DEL90 flag

`DEL90_FLAG` được chọn deterministic:

1. Xếp loan theo `PROB_DEL90` từ cao xuống thấp.
2. Chọn các loan rủi ro cao nhất.
3. Tổng exposure của danh sách được đưa gần nhất với lifecycle target.

Hai cột được lưu riêng:

```text
DEL90_FLAG_STATE
DEL90_FLAG
```

- `DEL90_FLAG_STATE`: kết quả state sampling.
- `DEL90_FLAG`: danh sách ranked theo calibrated probability.

Để báo cáo danh sách loan có khả năng DEL90, nên dùng `DEL90_FLAG` và
`PROB_DEL90`.

### 8.5. Fixed states

Loan đang ở absorbing state được khóa:

```text
WRITEOFF -> PROB_DEL90 = 1
PREPAY   -> PROB_DEL90 = 0
SOLDOUT  -> PROB_DEL90 = 0
```

Calibration không được làm write-off trở thành performing hoặc prepay trở thành
delinquent.

---

## 9. So sánh model cũ và mới

| Thành phần | Model cũ | Production calibrated |
|---|---|---|
| Markov transition | Có | Có |
| K/alpha | Có | Có |
| DEL90 K source | Theo code/config cũ | Config rõ `del30` hoặc `del90` |
| Residual DEL90 | Không | Có |
| Calibration theo anchor MOB | Không | MOB0-MOB11 |
| Historical calibration | Không | 6 mature vintages |
| Recency weighting | Transition có weighting | Residual có half-life 3 tháng |
| Shrink | Không | 0.5 |
| Residual cap | Không | +/-5pp |
| MAE guardrail | Không | Có |
| DEL90 <= DEL30 | Không phải calibration guardrail | Bắt buộc |
| Drift warning | Không | Thay đổi adjustment > 1pp |
| Base/calibrated audit | Hạn chế | Lưu đầy đủ |
| Loan probability reconciliation | Có | Có, thêm fixed states |
| Loan DEL90 list | Dựa nhiều vào sampled state | Ranked deterministic |

---

## 10. Output audit

Mỗi group lưu:

### K curve

```text
<GROUP>_K_Curves_<timestamp>.csv
```

Có các cột:

```text
METRIC
FIT_STATES
MOB
K_RAW
K_WEIGHT
K_SMOOTH
K_FINAL
ALPHA
ALPHA_TARGET_MOB
```

### DEL90 calibration curve

```text
<GROUP>_DEL90_Calibration_<timestamp>.csv
```

Có các cột quan trọng:

```text
TARGET_MOB
ANCHOR_MOB
RAW_ADJ
SHRINK
ADJ
CALIBRATION_DISB
N_CALIBRATION_VINTAGES
BASE_MAE
CALIBRATED_MAE
MAE_GUARDRAIL_PASSED
STATUS
PREVIOUS_ADJ
ADJ_CHANGE
DRIFT_WARNING
```

### Lifecycle

Lifecycle full cache có:

```text
DEL90_PCT_BASE
DEL90_CAL_ADJ
DEL90_CAL_ANCHOR_MOB
DEL90_CAL_SOURCE_N
DEL90_CAL_APPLIED
DEL90_PCT
DEL90_AMT
```

### Loan forecast

Loan output có:

```text
PROB_DEL90_RAW_MOB12
PROB_DEL90_MOB12
EAD_DEL90_MOB12
DEL90_FLAG_STATE_MOB12
DEL90_FLAG_MOB12
```

---

## 11. Quy trình cập nhật hàng tháng

Notebook production đặt:

```python
FORCE_GROUPS = ['POS']
```

Mỗi tháng:

1. Bổ sung parquet hoặc cutoff mới.
2. Chạy lại group production.
3. Fit lại transition và K.
4. Rebuild residual curve MOB0-MOB11.
5. So sánh `ADJ` với `PREVIOUS_ADJ`.
6. Kiểm tra `DRIFT_WARNING`.
7. Kiểm tra các dòng `guardrail_rejected`.
8. Kiểm tra loan-level reconciliation.
9. Xuất lifecycle, loan forecast và master workbook.

Cache format hiện tại là version 5, nên stage của logic cũ không được dùng lại
nhầm cho model mới.

---

## 12. Cách đọc adjustment

| Kết quả | Ý nghĩa |
|---|---|
| `RAW_ADJ > 0` | Base model đang underpredict DEL90 |
| `RAW_ADJ < 0` | Base model đang overpredict DEL90 |
| `ADJ = RAW_ADJ * 0.5` | Chỉ áp một nửa residual |
| `ADJ = +/-0.05` | Adjustment đã chạm cap 5pp |
| `STATUS = applied` | Calibration vượt qua guardrail |
| `STATUS = guardrail_rejected` | Calibration làm historical MAE xấu hơn |
| `DRIFT_WARNING = True` | Adjustment thay đổi trên 1pp so với lần trước |

Không nên đánh giá calibration chỉ dựa trên portfolio bias gần 0. Cần xem đồng
thời:

- `BASE_MAE`
- `CALIBRATED_MAE`
- Số vintage calibration
- Tổng calibration disbursal
- Adjustment có chạm cap hay không
- Drift so với tháng trước

---

## 13. Giới hạn

- Residual calibration là level adjustment, không phải true loan-level PD model.
- Hiệu quả phụ thuộc chất lượng historical as-of backtest.
- Chạy MOB0-MOB11 và 6 vintage có chi phí tính toán cao.
- Nếu behavior thay đổi đột ngột, residual lịch sử vẫn có độ trễ.
- K source `del30` hiện được chọn từ kết quả backtest gần nhất; cần tiếp tục so
  sánh với `del90` K trong các kỳ review model.
- `del90_calibration_min_disb` phải được đặt theo đúng đơn vị của portfolio.

---

## 14. Cấu hình production hiện tại

```python
DEL90_MOB12_CALIBRATION = {
    'del90_k_source': 'del30',
    'del90_portfolio_calibration_enabled': True,
    'del90_calibration_anchor_mobs': list(range(12)),
    'del90_calibration_n_vintages': 6,
    'del90_calibration_min_vintages': 4,
    'del90_calibration_half_life_months': 3.0,
    'del90_calibration_min_disb': 1.0,
    'del90_calibration_shrink': 0.5,
    'del90_calibration_shrink_by_anchor': {},
    'del90_calibration_residual_cap': 0.05,
    'del90_calibration_enforce_del30_cap': True,
    'del90_calibration_mae_guardrail': True,
    'del90_calibration_drift_warning': 0.01,
}
```

Đây là cấu hình conservative: ưu tiên tính ổn định, khả năng audit và hạn chế
over-calibration hơn là ép portfolio prediction khớp actual bằng mọi giá.
