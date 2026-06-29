# Luồng Model Final_Workflow (hiệu chỉnh K -> forecast)

Mã tham chiếu: src/rollrate/calibration_kmob.py, src/rollrate/transition.py, src/rollrate/forecast.py, export_cohort_details.py, update_final_workflow_wls_reg.py. Notebook Final_Workflow chạy với MAX_MOB=13 (vận hành ngắn hạn) nhưng có thể đổi.

## 1) Xây ma trận chuyển trạng thái
- Đầu vào df_raw gồm PRODUCT_TYPE, RISK_SCORE, MOB, STATE_MODEL, PRINCIPLE_OUTSTANDING, DISBURSAL_AMOUNT, CUTOFF_DATE.
- make_pairs() (transition.py) tạo cặp kề (state_t -> state_t1) với trọng số EAD*trọng số thời gian (DECAY_LAMBDA trong cfg, ROLL_WINDOW=12, WEIGHT_METHOD="exp").
- compute_transition_by_mob() tạo ma trận parent theo (product, score), sau đó ma trận theo MOB khi n_obs>=MIN_OBS (100) và total_ead>=MIN_EAD (1e2). Fallback: dùng parent matrix; ALPHA_SMOOTH=0.5 xử lý hàng zero; trạng thái hấp thụ cưỡng bức (DPD90+, WRITEOFF, PREPAY, SOLDOUT). Kết quả: matrices_by_mob + parent_fallback.

## 2) Actual và map giải ngân
- actual_results = get_actual_all_vintages_amount(df_raw) -> {(product, score, vintage): {mob: Series(EAD theo BUCKETS_CANON)}} chỉ dùng dòng actual.
- disb_total_by_vintage = df_raw.groupby([PRODUCT_TYPE, RISK_SCORE, DISBURSAL_DATE, AGREEMENT_ID])[DISBURSAL_AMOUNT].first().groupby(level=[0,1,2]).sum().to_dict(). Dùng để tính DEL trên DISB_TOTAL cố định mỗi cohort.

## 3) Fit k_raw theo MOB (wls_reg)
- Gọi trong Final_Workflow: k_raw_by_mob, weight_by_mob, _ = fit_k_raw(..., method="wls_reg", weight_mode="equal", denom_mode="disb", lambda_k=1e-4, k_prior=0.0, min_obs=5, fallback_k=1.0, fallback_weight=0.0, include_co=True, s30_states=BUCKETS_30P).
- Với từng cohort và từng cặp MOB liên tiếp m -> m+1:
  * v_m, v_m1: vector EAD theo state (reindex BUCKETS_CANON).
  * P_m lấy từ matrices_by_mob (đúng mob -> mob cuối -> parent fallback -> identity).
  * y_vm = tỷ trọng DEL30 tại mob m, y_hat = DEL30 Markov one-step v_m @ P_m, y_tar = DEL30 actual tại mob m+1. Với denom_mode="disb": tỷ trọng scale theo disb_total_by_vintage.
  * Gia số Markov a = y_hat - y_vm; gia số actual d = y_tar - y_vm; weight w = 1 (equal weight).
- Tổng hợp theo MOB:
  * tử số = sum(w * a * d), mẫu số = sum(w * a^2).
  * Nếu n_obs<min_obs hoặc mẫu+lambda_k < min_denom -> dùng fallback_k.
  * Công thức wls_reg: k_m = (tử + lambda_k * k_prior) / (mẫu + lambda_k); clip [0,1].
- k_raw_by_mob là global theo MOB (không tách product); weight_by_mob lưu tổng trọng số dùng.

## 4) Làm mượt đường k
- smooth_k(k_raw_by_mob, weight_by_mob, mob_min, mob_max, gamma=10.0, monotone=False) giải: min sum(w*(k-k_raw)^2) + gamma*sum(diff2^2) với ràng buộc 0<=k<=1. Dùng cvxpy nếu có, không thì scipy; trả k_smooth_by_mob cùng key MOB.

## 5) Alpha scaling (fit dài hạn)
- mob_target = min(MAX_MOB, mob_max) (Final_Workflow dùng MAX_MOB=13). Vintages validation = 20% cohort mới nhất.
- Quét alpha [0.5, 1.5] (bước 0.01). Với mỗi alpha: k_candidate[m] = clip(alpha * k_smooth_by_mob[m], 0, 1).
- Với từng cohort validation: start_mob = mob nhỏ nhất quan sát; chạy forecast_segment_partial_step(..., k_by_mob=k_candidate, max_mob=mob_target, denom_mode="ead", weight_mode="ead"); so sánh DEL30 tại mob_target với actual; MAE có trọng số chọn alpha tốt nhất (fallback 1.0 nếu thiếu dữ liệu).
- Kết quả: alpha vô hướng và k_final_by_mob (theo MOB) dùng downstream. alpha_by_mob trong export là view per-MOB của cùng alpha này.

## 6) Forecast với partial-step k
- Engine: forecast_all_vintages_partial_step(actual_results, matrices_by_mob, parent_fallback, max_mob=MAX_MOB, k_by_mob=k_final_by_mob, states=BUCKETS_CANON).
- Với từng cohort: start_mob = mob actual lớn nhất; initial_ead = vector EAD actual tại start_mob. Vòng lặp mob=start_mob..MAX_MOB-1:
  * Chọn P_m (đúng mob -> mob cuối -> parent fallback -> identity).
  * v_hat = current @ P_m.
-  * k_m = k_final_by_mob.get(mob, 1.0); cập nhật partial-step: current_new = current + k_m * (v_hat - current) = (1-k_m)*current + k_m*v_hat. Đây là “nhân một phần độ lệch”, không nhân trực tiếp v_hat. Ví dụ k_m=0.4: nếu DPD0/30+/WO đang [900,80,20], v_hat=[850,110,40], thì bước mới = [880,92,28] (đi 40% quãng đường tới Markov). Lưu current_new tại mob+1.
- Gộp actual + forecast về long-format (lifecycle_to_long_df_amount), gắn IS_FORECAST, thêm DEL30/60/90 + DISB_TOTAL qua add_del_metrics. Tổng hợp lên product/portfolio với aggregate_to_product và aggregate_products_to_portfolio.

### Vi du so: k_raw -> k_smooth -> k_final -> partial-step
- Dau vao (DEL30 tren DISB, w=1) tai MOB 5:
  - Cohort A: a=+0.030, d=+0.024
  - Cohort B: a=+0.020, d=+0.012
  - Cohort C: a=+0.015, d=+0.018
- WLS_reg:
  - Tu so = 0.030*0.024 + 0.020*0.012 + 0.015*0.018 = 0.00123
  - Mau so = 0.030^2 + 0.020^2 + 0.015^2 = 0.001525
  - k_raw(5) = (0.00123 + 1e-4*0)/(0.001525 + 1e-4) ≈ 0.757 (clip 0–1)
- Gia su k_raw cac MOB: 5:0.76, 6:0.60, 7:0.95, 8:0.50
- Smooth (gamma=10) lam mem: 5:0.74, 6:0.68, 7:0.78, 8:0.65
- Alpha (vd alpha*=1.05) -> k_final = clip(alpha*k_smooth): 5:0.78, 6:0.71, 7:0.82, 8:0.68
- Partial-step MOB5->6:
  - current: [DPD0=900, DPD30+=80, WO=20], v_hat: [850,110,40], k_m=0.78
  - current_new = current + 0.78*(v_hat - current) = [861, 103.4, 35.6] (tong giu 1000). Lap den MAX_MOB.

## 7) Export
- Lifecycle Excel kèm metadata config: export_lifecycle_with_config_info(df_del_all, actual_info_all, df_raw, config_params, path) trong lifecycle_export_enhanced.py.
- Excel chi tiết cohort: export_cohort_forecast_details(cohorts, df_raw, matrices_by_mob, k_raw_by_mob, k_smooth_by_mob, alpha_by_mob, target_mob) tạo sheet Summary/TM/K-values/Actual/Forecast_Steps.
- Allocation loan-level (nếu chạy): allocate_multi_mob_fast dùng df_lifecycle_final + matrices_by_mob và TARGET_MOBS để tạo Excel forecast loan.
