# Roll Rate Model - Theory & Methodology
# Lý Thuyết & Phương Pháp Luận

> **Bilingual Document / Tài liệu Song ngữ**
> - Primary: English
> - Secondary: Vietnamese (Tiếng Việt)

---

## Table of Contents / Mục Lục

1. [Introduction / Giới thiệu](#1-introduction--giới-thiệu)
2. [Transition Matrix Construction / Xây dựng Ma trận Chuyển đổi](#2-transition-matrix-construction--xây-dựng-ma-trận-chuyển-đổi)
3. [Weighting Methods / Phương pháp Trọng số](#3-weighting-methods--phương-pháp-trọng-số)
4. [K Calibration Methodology / Phương pháp Hiệu chỉnh K](#4-k-calibration-methodology--phương-pháp-hiệu-chỉnh-k)
5. [Smoothing & Regularization / Làm mượt & Điều chuẩn](#5-smoothing--regularization--làm-mượt--điều-chuẩn)
6. [Alpha Scaling / Hệ số Alpha](#6-alpha-scaling--hệ-số-alpha)
7. [Partial-Step Forecast / Dự báo Bước Từng phần](#7-partial-step-forecast--dự-báo-bước-từng-phần)
8. [Numerical Examples / Ví dụ Số học](#8-numerical-examples--ví-dụ-số-học)
9. [Summary of Formulas / Tổng hợp Công thức](#9-summary-of-formulas--tổng-hợp-công-thức)

---

## 1. Introduction / Giới thiệu

### English

The Roll Rate Model is a Markov Chain-based credit risk forecasting system that predicts delinquency rates (DEL30+, DEL60+, DEL90+) for loan portfolios. The model addresses a fundamental challenge: **pure Markov forecasts often over- or under-estimate actual delinquency rates** due to:

- Economic cycle effects not captured in historical transitions
- Seasonality patterns
- Portfolio composition changes over time

The solution is a **calibration factor K** that adjusts the Markov forecast to better match observed outcomes.

### Tiếng Việt

Roll Rate Model là hệ thống dự báo rủi ro tín dụng dựa trên Markov Chain, dự đoán tỷ lệ nợ xấu (DEL30+, DEL60+, DEL90+) cho danh mục cho vay. Model giải quyết thách thức cơ bản: **dự báo Markov thuần túy thường ước tính quá cao hoặc quá thấp tỷ lệ nợ xấu thực tế** do:

- Ảnh hưởng chu kỳ kinh tế không được phản ánh trong chuyển đổi lịch sử
- Các mẫu theo mùa (seasonality)
- Thay đổi cấu trúc danh mục theo thời gian

Giải pháp là **hệ số hiệu chỉnh K** điều chỉnh dự báo Markov để khớp tốt hơn với kết quả thực tế.

---

## 2. Transition Matrix Construction / Xây dựng Ma trận Chuyển đổi

### 2.1 State Space Definition / Định nghĩa Không gian Trạng thái

**States (Trạng thái):**
```
S = {DPD0, DPD1+, DPD30+, DPD60+, DPD90+, DPD120+, DPD180+, PREPAY, WRITEOFF, SOLDOUT}
```

- **Transient states**: DPD0 → DPD180+ (có thể chuyển đổi)
- **Absorbing states**: PREPAY, WRITEOFF, SOLDOUT (trạng thái hấp thụ - không chuyển đi)

### 2.2 Transition Probability / Xác suất Chuyển đổi

**English:**
The transition probability from state $i$ to state $j$ is estimated from observed loan-level transitions:

**Tiếng Việt:**
Xác suất chuyển đổi từ trạng thái $i$ sang trạng thái $j$ được ước tính từ các chuyển đổi quan sát được ở cấp khoản vay:

$$P_{ij} = \frac{\sum_{n} w_n \cdot \mathbf{1}_{(s_n^t = i, s_n^{t+1} = j)}}{\sum_{n} w_n \cdot \mathbf{1}_{(s_n^t = i)}}$$

Where / Trong đó:
- $w_n$ = weight of observation $n$ (trọng số của quan sát $n$)
- $s_n^t$ = state of loan $n$ at time $t$ (trạng thái khoản vay $n$ tại thời điểm $t$)
- $\mathbf{1}_{(\cdot)}$ = indicator function (hàm chỉ báo)

### 2.3 Matrix Structure / Cấu trúc Ma trận

```
P = [P_ij] where Σ_j P_ij = 1 for all i (row-stochastic)
```

**Absorbing state constraint / Ràng buộc trạng thái hấp thụ:**
$$P_{ii} = 1 \text{ for } i \in \{PREPAY, WRITEOFF, SOLDOUT\}$$

---

## 3. Weighting Methods / Phương pháp Trọng số

The model uses two types of weights that are multiplied together:
Model sử dụng hai loại trọng số được nhân với nhau:

### 3.1 Time Weighting (WHA - Weighted Historical Average) / Trọng số Thời gian

**English:**
Recent observations are more relevant than older ones. We apply exponential decay weighting:

**Tiếng Việt:**
Các quan sát gần đây có ý nghĩa hơn các quan sát cũ. Chúng ta áp dụng trọng số suy giảm theo hàm mũ:

$$w_{time}(t) = \lambda^{age(t)}$$

Where / Trong đó:
- $\lambda$ = decay factor (hệ số suy giảm), typically $\lambda = 0.5^{1/12} \approx 0.944$
- $age(t)$ = months from observation to current date (số tháng từ quan sát đến hiện tại)
- $age(t) = \max(0, \min(age_{raw}, ROLL\_WINDOW))$
- $ROLL\_WINDOW$ = 12 months (cửa sổ lăn = 12 tháng)

**Interpretation / Giải thích:**
- $\lambda = 0.944$: After 12 months, weight = $0.944^{12} \approx 0.5$ (50% of original)
- Sau 12 tháng, trọng số = $0.944^{12} \approx 0.5$ (50% ban đầu)

**Alternative: Linear Decay / Phương án thay thế: Suy giảm Tuyến tính:**
$$w_{time}(t) = \max\left(0, 1 - \frac{age(t)}{ROLL\_WINDOW}\right)$$

### 3.2 EAD Weighting / Trọng số theo Dư nợ (EAD)

**English:**
Larger loans have more impact on portfolio risk. Weight by Exposure at Default:

**Tiếng Việt:**
Các khoản vay lớn hơn có tác động nhiều hơn đến rủi ro danh mục. Trọng số theo Dư nợ tại thời điểm vỡ nợ:

$$w_{EAD}(n) = EAD_n = \text{PRINCIPLE\_OUTSTANDING}_n$$

### 3.3 Combined Weight / Trọng số Kết hợp

$$w_n = w_{time}(t_n) \times w_{EAD}(n)$$

**In code / Trong code:**
```python
ead_t = ead_raw * time_weight
```

This combined weight is used for:
Trọng số kết hợp này được sử dụng cho:
1. Building transition matrices (Xây dựng ma trận chuyển đổi)
2. WLS regression for K calibration (Hồi quy WLS cho hiệu chỉnh K)

---

## 4. K Calibration Methodology / Phương pháp Hiệu chỉnh K

### 4.1 Why K is Needed / Tại sao cần K

**English:**
Pure Markov forecast: $\hat{v}_{m+1} = v_m \cdot P_m$

This often deviates from actual outcomes because:
- Historical transitions may not represent future behavior
- Economic conditions change
- Portfolio mix evolves

**K adjusts the forecast** to match observed delinquency increments.

**Tiếng Việt:**
Dự báo Markov thuần túy: $\hat{v}_{m+1} = v_m \cdot P_m$

Điều này thường lệch khỏi kết quả thực tế vì:
- Chuyển đổi lịch sử có thể không đại diện cho hành vi tương lai
- Điều kiện kinh tế thay đổi
- Cấu trúc danh mục phát triển

**K điều chỉnh dự báo** để khớp với gia tăng nợ xấu quan sát được.

### 4.2 One-Step Forecast Setup / Thiết lập Dự báo Một bước

For each cohort $(product, score, vintage)$ and consecutive MOB pair $(m, m+1)$:
Với mỗi cohort $(product, score, vintage)$ và cặp MOB liên tiếp $(m, m+1)$:

**Step 1: Normalize state vectors / Bước 1: Chuẩn hóa vector trạng thái**
$$v_m = \frac{EAD_m}{\sum_s EAD_m^{(s)}}$$

**Step 2: One-step Markov forecast / Bước 2: Dự báo Markov một bước**
$$\hat{v}_{m+1} = v_m \cdot P_m$$

**Step 3: Calculate DEL30 metrics / Bước 3: Tính chỉ số DEL30**

Let $S_{30+} = \{DPD30+, DPD60+, DPD90+, DPD120+, DPD180+, WRITEOFF\}$

$$DEL30(v) = \sum_{s \in S_{30+}} v^{(s)}$$

### 4.3 Increment Calculation / Tính Gia tăng

**Using DISB_TOTAL as denominator (denom_mode="disb"):**
Sử dụng DISB_TOTAL làm mẫu số:

$$y_{vm} = \frac{DEL30(v_m) \times TotalEAD_m}{DISB\_TOTAL}$$

$$y_{hat} = \frac{DEL30(\hat{v}_{m+1}) \times TotalEAD_m}{DISB\_TOTAL}$$

$$y_{tar} = \frac{DEL30(v_{m+1}^{actual}) \times TotalEAD_{m+1}}{DISB\_TOTAL}$$

**Increments / Gia tăng:**
$$a = y_{hat} - y_{vm} \quad \text{(Markov increment / Gia tăng Markov)}$$
$$d = y_{tar} - y_{vm} \quad \text{(Actual increment / Gia tăng Thực tế)}$$

### 4.4 WLS Regression for K / Hồi quy WLS cho K

**English:**
We want to find $k_m$ such that the adjusted increment $k_m \cdot a$ best approximates the actual increment $d$.

**Tiếng Việt:**
Chúng ta muốn tìm $k_m$ sao cho gia tăng điều chỉnh $k_m \cdot a$ xấp xỉ tốt nhất gia tăng thực tế $d$.

**Objective / Mục tiêu:**
$$\min_{k_m} \sum_{vintages} w \cdot (k_m \cdot a - d)^2$$

**Closed-form solution / Nghiệm dạng đóng:**
$$k_m = \frac{\sum w \cdot a \cdot d}{\sum w \cdot a^2}$$

Where the sum is over all cohorts at MOB $m$.
Trong đó tổng được tính trên tất cả cohort tại MOB $m$.

---

## 5. Smoothing & Regularization / Làm mượt & Điều chuẩn

### 5.1 WLS with Regularization (wls_reg) / WLS với Điều chuẩn

**English:**
To prevent overfitting and handle sparse data, we add a regularization term that pulls K toward a prior value:

**Tiếng Việt:**
Để ngăn overfitting và xử lý dữ liệu thưa, chúng ta thêm số hạng điều chuẩn kéo K về giá trị prior:

**Regularized objective / Mục tiêu có điều chuẩn:**
$$\min_{k_m} \left[ \sum w \cdot (k_m \cdot a - d)^2 + \lambda_k \cdot (k_m - k_{prior})^2 \right]$$

**Closed-form solution / Nghiệm dạng đóng:**
$$k_m = \frac{\sum w \cdot a \cdot d + \lambda_k \cdot k_{prior}}{\sum w \cdot a^2 + \lambda_k}$$

**Parameters / Tham số:**
- $\lambda_k$ = regularization strength (cường độ điều chuẩn), typically $10^{-4}$
- $k_{prior}$ = prior value (giá trị prior), typically $0$ or $1$

**Interpretation / Giải thích:**
- When $\lambda_k = 0$: Pure WLS (WLS thuần túy)
- When $\lambda_k \to \infty$: $k_m \to k_{prior}$
- Small $\lambda_k$: Slight bias toward prior, reduces variance (Thiên lệch nhẹ về prior, giảm phương sai)

### 5.2 Clipping / Cắt ngưỡng

**English:**
K values are constrained to $[0, 1]$ for interpretability:

**Tiếng Việt:**
Giá trị K được ràng buộc trong $[0, 1]$ để dễ giải thích:

$$k_m^{clipped} = \max(0, \min(1, k_m))$$

**Meaning / Ý nghĩa:**
- $k = 0$: No movement toward Markov forecast (Không di chuyển về dự báo Markov)
- $k = 1$: Full Markov forecast (Dự báo Markov hoàn toàn)
- $k = 0.5$: Halfway between current and Markov (Nửa đường giữa hiện tại và Markov)

### 5.3 Smoothing K across MOB / Làm mượt K qua các MOB

**English:**
Raw K values can be noisy. We smooth them using a second-difference penalty:

**Tiếng Việt:**
Giá trị K thô có thể nhiễu. Chúng ta làm mượt bằng penalty sai phân bậc hai:

**Objective / Mục tiêu:**
$$\min_{k} \left[ \sum_m w_m \cdot (k_m - k_m^{raw})^2 + \gamma \cdot \sum_m (k_{m+2} - 2k_{m+1} + k_m)^2 \right]$$

**Subject to / Ràng buộc:**
$$0 \leq k_m \leq 1 \quad \forall m$$

**Parameters / Tham số:**
- $\gamma$ = smoothing strength (cường độ làm mượt), typically $10$
- $w_m$ = weight at MOB $m$ (trọng số tại MOB $m$), from WLS denominator

**Second-difference penalty / Penalty sai phân bậc hai:**
$$\Delta^2 k_m = k_{m+2} - 2k_{m+1} + k_m$$

This penalizes curvature, encouraging a smooth curve.
Điều này phạt độ cong, khuyến khích đường cong mượt.

**Solver / Bộ giải:**
- CVXPY with OSQP (if available / nếu có)
- scipy.optimize.minimize with L-BFGS-B (fallback / dự phòng)

### 5.4 Optional Monotonicity Constraint / Ràng buộc Đơn điệu (Tùy chọn)

$$k_{m+1} \geq k_m \quad \forall m$$

This ensures K is non-decreasing (useful if delinquency acceleration is expected to increase with MOB).
Điều này đảm bảo K không giảm (hữu ích nếu gia tốc nợ xấu dự kiến tăng theo MOB).

---

## 6. Alpha Scaling / Hệ số Alpha

### 6.1 Purpose / Mục đích

**English:**
Alpha provides a final global scaling to the entire K curve to optimize long-horizon forecast accuracy:

**Tiếng Việt:**
Alpha cung cấp một hệ số tỷ lệ toàn cục cuối cùng cho toàn bộ đường K để tối ưu độ chính xác dự báo dài hạn:

$$k_m^{final} = \text{clip}(\alpha \cdot k_m^{smooth}, 0, 1)$$

### 6.2 Grid Search Optimization / Tối ưu Tìm kiếm Lưới

**English:**
Alpha is selected by minimizing weighted MAE on a validation set at a target MOB:

**Tiếng Việt:**
Alpha được chọn bằng cách tối thiểu hóa MAE có trọng số trên tập validation tại MOB mục tiêu:

**Objective / Mục tiêu:**
$$\alpha^* = \arg\min_{\alpha} \sum_{v \in V_{val}} w_v \cdot |DEL30_{forecast}^{(v)}(MOB_{target}) - DEL30_{actual}^{(v)}(MOB_{target})|$$

**Grid / Lưới:**
$$\alpha \in \{0.50, 0.51, 0.52, ..., 1.49, 1.50\}$$

**Validation split / Phân chia Validation:**
- Training: 80% of vintages (oldest / cũ nhất)
- Validation: 20% of vintages (newest / mới nhất)

### 6.3 Interpretation / Giải thích

- $\alpha > 1$: Model was under-predicting → scale up (Model dự đoán thấp → tăng lên)
- $\alpha < 1$: Model was over-predicting → scale down (Model dự đoán cao → giảm xuống)
- $\alpha \approx 1$: K_smooth was already well-calibrated (K_smooth đã được hiệu chỉnh tốt)

---

## 7. Partial-Step Forecast / Dự báo Bước Từng phần

### 7.1 Core Formula / Công thức Cốt lõi

**English:**
Instead of using pure Markov ($v_{m+1} = v_m \cdot P_m$), we apply a partial step controlled by K:

**Tiếng Việt:**
Thay vì sử dụng Markov thuần túy ($v_{m+1} = v_m \cdot P_m$), chúng ta áp dụng bước từng phần được kiểm soát bởi K:

$$v_{m+1} = v_m + k_m \cdot (\hat{v}_{m+1} - v_m)$$

Where / Trong đó:
- $\hat{v}_{m+1} = v_m \cdot P_m$ (Markov forecast / Dự báo Markov)
- $k_m$ = calibration factor at MOB $m$ (hệ số hiệu chỉnh tại MOB $m$)

**Equivalent form / Dạng tương đương:**
$$v_{m+1} = (1 - k_m) \cdot v_m + k_m \cdot \hat{v}_{m+1}$$

### 7.2 Interpretation / Giải thích

| $k_m$ | Behavior / Hành vi |
|-------|-------------------|
| $k_m = 0$ | Stay at current state: $v_{m+1} = v_m$ (Giữ nguyên trạng thái hiện tại) |
| $k_m = 0.5$ | Move halfway: $v_{m+1} = 0.5 \cdot v_m + 0.5 \cdot \hat{v}_{m+1}$ (Di chuyển nửa đường) |
| $k_m = 1$ | Full Markov: $v_{m+1} = \hat{v}_{m+1}$ (Markov hoàn toàn) |

### 7.3 Multi-Step Forecast / Dự báo Nhiều bước

**English:**
For forecasting from $MOB_{start}$ to $MOB_{max}$:

**Tiếng Việt:**
Để dự báo từ $MOB_{start}$ đến $MOB_{max}$:

```
v[MOB_start] = initial_ead (normalized)

for m = MOB_start to MOB_max - 1:
    v_hat = v[m] @ P[m]
    k = k_final[m]
    v[m+1] = v[m] + k * (v_hat - v[m])
```

### 7.4 State Vector Normalization / Chuẩn hóa Vector Trạng thái

**English:**
After each step, ensure the state vector remains a valid probability distribution:

**Tiếng Việt:**
Sau mỗi bước, đảm bảo vector trạng thái vẫn là phân phối xác suất hợp lệ:

$$v_{m+1} = \frac{\max(0, v_{m+1})}{\sum_s \max(0, v_{m+1}^{(s)})}$$

This handles numerical precision issues and ensures:
Điều này xử lý vấn đề độ chính xác số học và đảm bảo:
- $v^{(s)} \geq 0$ for all states (cho tất cả trạng thái)
- $\sum_s v^{(s)} = 1$

---

## 8. Numerical Examples / Ví dụ Số học

### 8.1 Time Weighting Example / Ví dụ Trọng số Thời gian

**Given / Cho:**
- Current date: 2024-01
- Observation date: 2023-07
- $\lambda = 0.944$
- $ROLL\_WINDOW = 12$

**Calculation / Tính toán:**
$$age = 2024\text{-}01 - 2023\text{-}07 = 6 \text{ months}$$
$$w_{time} = 0.944^6 = 0.707$$

**Interpretation / Giải thích:**
An observation from 6 months ago has 70.7% of the weight of a current observation.
Một quan sát từ 6 tháng trước có 70.7% trọng số của quan sát hiện tại.

### 8.2 K Calibration Example / Ví dụ Hiệu chỉnh K

**Given data at MOB 5 / Dữ liệu cho tại MOB 5:**

| Cohort | $w$ | $a$ (Markov incr.) | $d$ (Actual incr.) |
|--------|-----|--------------------|--------------------|
| V1 | 1.0 | 0.02 | 0.015 |
| V2 | 1.0 | 0.03 | 0.020 |
| V3 | 1.0 | 0.025 | 0.022 |

**WLS Calculation / Tính WLS:**
$$\sum w \cdot a \cdot d = 1(0.02)(0.015) + 1(0.03)(0.020) + 1(0.025)(0.022)$$
$$= 0.0003 + 0.0006 + 0.00055 = 0.00145$$

$$\sum w \cdot a^2 = 1(0.02)^2 + 1(0.03)^2 + 1(0.025)^2$$
$$= 0.0004 + 0.0009 + 0.000625 = 0.001925$$

$$k_5^{raw} = \frac{0.00145}{0.001925} = 0.753$$

**With regularization / Với điều chuẩn ($\lambda_k = 0.0001$, $k_{prior} = 0$):**
$$k_5^{reg} = \frac{0.00145 + 0.0001 \times 0}{0.001925 + 0.0001} = \frac{0.00145}{0.002025} = 0.716$$

### 8.3 Partial-Step Forecast Example / Ví dụ Dự báo Bước Từng phần

**Given / Cho:**
- $v_5 = [DPD0: 0.85, DPD30+: 0.10, WRITEOFF: 0.05]$
- $\hat{v}_6 = v_5 \cdot P_5 = [DPD0: 0.80, DPD30+: 0.13, WRITEOFF: 0.07]$
- $k_5 = 0.75$

**Calculation / Tính toán:**
$$v_6 = v_5 + 0.75 \times (\hat{v}_6 - v_5)$$

For DPD0:
$$v_6^{DPD0} = 0.85 + 0.75 \times (0.80 - 0.85) = 0.85 - 0.0375 = 0.8125$$

For DPD30+:
$$v_6^{DPD30+} = 0.10 + 0.75 \times (0.13 - 0.10) = 0.10 + 0.0225 = 0.1225$$

For WRITEOFF:
$$v_6^{WRITEOFF} = 0.05 + 0.75 \times (0.07 - 0.05) = 0.05 + 0.015 = 0.065$$

**Result / Kết quả:**
$$v_6 = [DPD0: 0.8125, DPD30+: 0.1225, WRITEOFF: 0.065]$$

**DEL30 comparison / So sánh DEL30:**
- Pure Markov: $DEL30 = 0.13 + 0.07 = 0.20$
- Partial-step: $DEL30 = 0.1225 + 0.065 = 0.1875$
- Difference: $0.20 - 0.1875 = 0.0125$ (1.25% lower / thấp hơn)

---

## 9. Summary of Formulas / Tổng hợp Công thức

### 9.1 Weighting / Trọng số

| Formula | Description (EN) | Mô tả (VN) |
|---------|------------------|------------|
| $w_{time} = \lambda^{age}$ | Exponential time decay | Suy giảm thời gian theo hàm mũ |
| $w_{EAD} = EAD_n$ | EAD weighting | Trọng số theo dư nợ |
| $w_n = w_{time} \times w_{EAD}$ | Combined weight | Trọng số kết hợp |

### 9.2 Transition Matrix / Ma trận Chuyển đổi

| Formula | Description (EN) | Mô tả (VN) |
|---------|------------------|------------|
| $P_{ij} = \frac{\sum w_n \cdot \mathbf{1}_{(i \to j)}}{\sum w_n \cdot \mathbf{1}_{(i)}}$ | Weighted transition probability | Xác suất chuyển đổi có trọng số |
| $\sum_j P_{ij} = 1$ | Row-stochastic constraint | Ràng buộc tổng hàng = 1 |

### 9.3 K Calibration / Hiệu chỉnh K

| Formula | Description (EN) | Mô tả (VN) |
|---------|------------------|------------|
| $a = y_{hat} - y_{vm}$ | Markov increment | Gia tăng Markov |
| $d = y_{tar} - y_{vm}$ | Actual increment | Gia tăng thực tế |
| $k_m = \frac{\sum w \cdot a \cdot d}{\sum w \cdot a^2}$ | WLS solution | Nghiệm WLS |
| $k_m = \frac{\sum w \cdot a \cdot d + \lambda_k \cdot k_{prior}}{\sum w \cdot a^2 + \lambda_k}$ | Regularized WLS | WLS có điều chuẩn |

### 9.4 Smoothing / Làm mượt

| Formula | Description (EN) | Mô tả (VN) |
|---------|------------------|------------|
| $\min \sum w_m(k_m - k_m^{raw})^2 + \gamma \sum (\Delta^2 k_m)^2$ | Smoothing objective | Mục tiêu làm mượt |
| $\Delta^2 k_m = k_{m+2} - 2k_{m+1} + k_m$ | Second difference | Sai phân bậc hai |

### 9.5 Alpha Scaling / Hệ số Alpha

| Formula | Description (EN) | Mô tả (VN) |
|---------|------------------|------------|
| $k_m^{final} = \text{clip}(\alpha \cdot k_m^{smooth}, 0, 1)$ | Final K with alpha | K cuối cùng với alpha |
| $\alpha^* = \arg\min_\alpha MAE_{val}$ | Optimal alpha | Alpha tối ưu |

### 9.6 Partial-Step Forecast / Dự báo Bước Từng phần

| Formula | Description (EN) | Mô tả (VN) |
|---------|------------------|------------|
| $\hat{v}_{m+1} = v_m \cdot P_m$ | Markov forecast | Dự báo Markov |
| $v_{m+1} = v_m + k_m(\hat{v}_{m+1} - v_m)$ | Partial-step forecast | Dự báo bước từng phần |
| $v_{m+1} = (1-k_m)v_m + k_m \hat{v}_{m+1}$ | Equivalent form | Dạng tương đương |

---

## 10. Parameter Reference / Tham chiếu Tham số

| Parameter | Default | Range | Description (EN) | Mô tả (VN) |
|-----------|---------|-------|------------------|------------|
| `DECAY_LAMBDA` | 0.944 | (0, 1) | Time decay factor | Hệ số suy giảm thời gian |
| `ROLL_WINDOW` | 12 | [6, 24] | Historical window (months) | Cửa sổ lịch sử (tháng) |
| `lambda_k` | 1e-4 | [0, 1] | WLS regularization | Điều chuẩn WLS |
| `k_prior` | 0.0 | [0, 1] | Prior K value | Giá trị K prior |
| `gamma` | 10.0 | [1, 100] | Smoothing strength | Cường độ làm mượt |
| `alpha_grid` | [0.5, 1.5] | - | Alpha search range | Phạm vi tìm kiếm alpha |
| `val_frac` | 0.2 | (0, 0.5) | Validation fraction | Tỷ lệ validation |
| `MIN_OBS` | 100 | [10, 500] | Min observations for matrix | Số quan sát tối thiểu cho ma trận |
| `MIN_EAD` | 100 | [0, ∞) | Min EAD for matrix | EAD tối thiểu cho ma trận |

---

## 11. Code Reference / Tham chiếu Code

### Key Functions / Các Hàm Chính

| Function | File | Purpose (EN) | Mục đích (VN) |
|----------|------|--------------|---------------|
| `make_pairs()` | `transition.py` | Create state transition pairs | Tạo cặp chuyển đổi trạng thái |
| `compute_transition_by_mob()` | `transition.py` | Build P matrices by MOB | Xây dựng ma trận P theo MOB |
| `fit_k_raw()` | `calibration_kmob.py` | WLS regression for K | Hồi quy WLS cho K |
| `smooth_k()` | `calibration_kmob.py` | Smooth K curve | Làm mượt đường K |
| `fit_alpha()` | `calibration_kmob.py` | Grid search for alpha | Tìm kiếm lưới cho alpha |
| `forecast_segment_partial_step()` | `calibration_kmob.py` | Partial-step forecast | Dự báo bước từng phần |
| `add_del_metrics()` | `lifecycle.py` | Calculate DEL30/60/90 | Tính DEL30/60/90 |
| `aggregate_to_product()` | `lifecycle.py` | Aggregate to product level | Gộp lên cấp sản phẩm |

---

## 12. Appendix: Mathematical Derivations / Phụ lục: Chứng minh Toán học

### A. WLS Derivation / Chứng minh WLS

**Objective / Mục tiêu:**
$$L(k) = \sum_i w_i (k \cdot a_i - d_i)^2$$

**First-order condition / Điều kiện bậc nhất:**
$$\frac{\partial L}{\partial k} = 2 \sum_i w_i (k \cdot a_i - d_i) \cdot a_i = 0$$

$$\sum_i w_i a_i^2 \cdot k = \sum_i w_i a_i d_i$$

$$k^* = \frac{\sum_i w_i a_i d_i}{\sum_i w_i a_i^2}$$

### B. Regularized WLS Derivation / Chứng minh WLS có Điều chuẩn

**Objective / Mục tiêu:**
$$L(k) = \sum_i w_i (k \cdot a_i - d_i)^2 + \lambda (k - k_0)^2$$

**First-order condition / Điều kiện bậc nhất:**
$$\frac{\partial L}{\partial k} = 2 \sum_i w_i a_i (k \cdot a_i - d_i) + 2\lambda(k - k_0) = 0$$

$$k \left( \sum_i w_i a_i^2 + \lambda \right) = \sum_i w_i a_i d_i + \lambda k_0$$

$$k^* = \frac{\sum_i w_i a_i d_i + \lambda k_0}{\sum_i w_i a_i^2 + \lambda}$$

---

*Document created: 2026-01-20*
*Author: Roll Rate Model Team*
