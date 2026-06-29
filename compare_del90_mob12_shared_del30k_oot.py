from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

import src.config as project_config
from src.config import BUCKETS_30P, BUCKETS_90P, BUCKETS_CANON, CFG, parse_date_column
from src.rollrate.oot_evaluation import (
    _asof_cutoff_for_vintage,
    build_disb_total_by_vintage,
    build_metric_compare_frame,
    fit_metric_curve,
    prepare_backtest_frame,
    restore_project_settings,
    snapshot_project_settings,
    summarize_weighted_compare,
)
from src.rollrate.lifecycle import get_actual_all_vintages_amount
from src.rollrate.transition import compute_transition_by_mob
from src.rollrate.calibration_kmob import forecast_all_vintages_partial_step


TARGET_MOB = 12
ANCHOR_CONFIG = {
    2: 1.0,
    4: 0.5,
    6: 0.5,
    8: 0.5,
}
CALIBRATION_N_VINTAGES = 6
CALIBRATION_MIN_VINTAGES = 4
CALIBRATION_HALF_LIFE_MONTHS = 3.0
CALIBRATION_RESIDUAL_CAP = 0.05
CALIBRATION_GUARDRAIL = True
K_SOURCE = "del30"
FIT_PARAMS = {
    "k_method": "wls_reg",
    "lambda_k": 1e-4,
    "k_prior": 0.0,
    "k_min_obs": 5,
    "fallback_k": 1.0,
    "fallback_weight": 0.0,
    "gamma": 10.0,
    "alpha_mob_target": TARGET_MOB,
    "k_weight_mode": "equal",
    "monotone": False,
}

INPUT_STAGE = Path("outputs/group_runs_production_calibrated/staging/POS/raw_filtered.parquet")
OUTPUT_DIR = Path("notebooks/outputs/oot_backtest_ntb/shared_del30k_baseline_vs_current_cal")


def _metric_run_key(metric_name: str, vintage: pd.Timestamp, lookback_months: int) -> tuple[str, pd.Timestamp, int]:
    return metric_name, pd.Timestamp(vintage), int(lookback_months)


def run_metric_asof_forecast(
    df_model: pd.DataFrame,
    *,
    vintage,
    target_mob: int,
    lookback_months: int,
    fit_params: dict,
    metric_name: str,
    fit_states: list[str],
    eval_states: list[str],
    post_mature_k,
    cache: dict,
) -> dict:
    cache_key = _metric_run_key(metric_name, pd.Timestamp(vintage), int(lookback_months))
    if cache_key in cache:
        return cache[cache_key]

    target_mob = int(target_mob)
    target_vintage = pd.Timestamp(vintage)
    target_cutoff, asof_cutoff = _asof_cutoff_for_vintage(
        df_model,
        vintage=target_vintage,
        target_mob=target_mob,
        lookback_months=lookback_months,
    )

    df_asof = df_model[df_model[CFG["cutoff"]] <= asof_cutoff].copy()
    df_target_actual = df_model[df_model["VINTAGE_DATE"] == target_vintage].copy()
    df_target_anchor = df_asof[df_asof["VINTAGE_DATE"] == target_vintage].copy()
    if df_asof.empty or df_target_anchor.empty:
        raise ValueError(
            f"As-of split is empty for vintage {target_vintage:%Y-%m-%d}, "
            f"asof={asof_cutoff:%Y-%m-%d}."
        )

    anchor_max_mob = int(pd.to_numeric(df_target_anchor[CFG["mob"]], errors="coerce").max())
    if anchor_max_mob >= target_mob:
        raise ValueError(
            f"Anchor MOB {anchor_max_mob} is not before target MOB {target_mob} "
            f"for vintage {target_vintage:%Y-%m-%d}."
        )

    matrices_by_mob, parent_fallback = compute_transition_by_mob(df_asof)
    actual_results_asof = get_actual_all_vintages_amount(df_asof)
    disb_total_asof = build_disb_total_by_vintage(df_asof)
    fit_output = fit_metric_curve(
        actual_results_train=actual_results_asof,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        disb_total_by_vintage_train=disb_total_asof,
        metric_states=fit_states,
        fit_params=fit_params,
        post_mature_k=post_mature_k,
        post_mature_start_mob=target_mob,
    )

    actual_results_target_full = get_actual_all_vintages_amount(df_target_actual)
    actual_results_target_anchor = get_actual_all_vintages_amount(df_target_anchor)
    disb_total_target = build_disb_total_by_vintage(df_target_actual)
    forecast_target = forecast_all_vintages_partial_step(
        actual_results=actual_results_target_anchor,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        max_mob=target_mob,
        k_by_mob=fit_output["k_final_by_mob"],
        states=BUCKETS_CANON,
    )
    compare_df = build_metric_compare_frame(
        actual_results_holdout=actual_results_target_full,
        forecast_results_holdout=forecast_target,
        disb_total_by_vintage_holdout=disb_total_target,
        metric_name=metric_name,
        metric_states=eval_states,
    )
    compare_df = compare_df[compare_df["MOB"] == target_mob].copy()
    if not compare_df.empty:
        compare_df["TARGET_VINTAGE"] = target_vintage
        compare_df["TARGET_MOB"] = target_mob
        compare_df["TARGET_CUTOFF"] = target_cutoff
        compare_df["AS_OF_CUTOFF"] = asof_cutoff
        compare_df["ANCHOR_MOB"] = anchor_max_mob

    result = {
        "target_vintage": target_vintage,
        "target_cutoff": target_cutoff,
        "asof_cutoff": asof_cutoff,
        "anchor_mob": anchor_max_mob,
        "compare_df": compare_df,
    }
    cache[cache_key] = result
    return result


def build_portfolio_calibration_for_target(
    df_model: pd.DataFrame,
    *,
    target_vintage: pd.Timestamp,
    anchor_mob: int,
    fit_params: dict,
    forecast_cache: dict,
) -> dict | None:
    lookback_months = TARGET_MOB - int(anchor_mob)
    target_candidates = (
        df_model[pd.to_numeric(df_model[CFG["mob"]], errors="coerce") == TARGET_MOB]
        .groupby("VINTAGE_DATE")[CFG["cutoff"]]
        .max()
        .sort_index()
    )
    target_run = run_metric_asof_forecast(
        df_model,
        vintage=target_vintage,
        target_mob=TARGET_MOB,
        lookback_months=lookback_months,
        fit_params=fit_params,
        metric_name="DEL90",
        fit_states=BUCKETS_30P,
        eval_states=BUCKETS_90P,
        post_mature_k=project_config.K_POST_MATURE,
        cache=forecast_cache,
    )
    calibration_candidates = target_candidates[
        (target_candidates.index < target_vintage)
        & (target_candidates <= target_run["asof_cutoff"])
    ].tail(CALIBRATION_N_VINTAGES)

    if len(calibration_candidates) < CALIBRATION_MIN_VINTAGES:
        return None

    compare_frames = []
    used_vintages = []
    for calibration_vintage in calibration_candidates.index:
        result = run_metric_asof_forecast(
            df_model,
            vintage=calibration_vintage,
            target_mob=TARGET_MOB,
            lookback_months=lookback_months,
            fit_params=fit_params,
            metric_name="DEL90",
            fit_states=BUCKETS_30P,
            eval_states=BUCKETS_90P,
            post_mature_k=project_config.K_POST_MATURE,
            cache=forecast_cache,
        )
        compare_df = result["compare_df"].copy()
        if compare_df.empty:
            continue
        compare_df["CALIBRATION_VINTAGE"] = pd.Timestamp(calibration_vintage)
        compare_frames.append(compare_df)
        used_vintages.append(pd.Timestamp(calibration_vintage))

    if len(used_vintages) < CALIBRATION_MIN_VINTAGES:
        return None

    compare_df = pd.concat(compare_frames, ignore_index=True)
    newest_vintage = max(used_vintages)
    compare_df["VINTAGE_AGE_MONTHS"] = (
        (newest_vintage.year - compare_df["CALIBRATION_VINTAGE"].dt.year) * 12
        + newest_vintage.month
        - compare_df["CALIBRATION_VINTAGE"].dt.month
    ).astype(float)
    compare_df["RECENCY_WEIGHT"] = np.power(
        0.5,
        compare_df["VINTAGE_AGE_MONTHS"] / CALIBRATION_HALF_LIFE_MONTHS,
    )
    compare_df["CALIBRATION_WEIGHT"] = (
        compare_df["DISB_TOTAL"].fillna(0.0).astype(float)
        * compare_df["RECENCY_WEIGHT"]
    )
    residual = compare_df["ACTUAL_PCT"].astype(float) - compare_df["PRED_PCT"].astype(float)
    weights = compare_df["CALIBRATION_WEIGHT"].to_numpy(dtype=float)
    if not bool((weights > 0).any()):
        return None

    raw_adj = float(np.average(residual, weights=weights))
    shrink = float(ANCHOR_CONFIG[int(anchor_mob)])
    adj = raw_adj * shrink
    if CALIBRATION_RESIDUAL_CAP is not None:
        cap = abs(float(CALIBRATION_RESIDUAL_CAP))
        adj = float(np.clip(adj, -cap, cap))

    vintage_summary_rows = []
    for calibration_vintage, vintage_df in compare_df.groupby("CALIBRATION_VINTAGE"):
        vintage_weights = vintage_df["DISB_TOTAL"].fillna(0.0).astype(float)
        if not bool((vintage_weights > 0).any()):
            continue
        actual = float(np.average(vintage_df["ACTUAL_PCT"], weights=vintage_weights))
        predicted = float(np.average(vintage_df["PRED_PCT"], weights=vintage_weights))
        age_months = float(vintage_df["VINTAGE_AGE_MONTHS"].iloc[0])
        recency_weight = float(np.power(0.5, age_months / CALIBRATION_HALF_LIFE_MONTHS))
        vintage_summary_rows.append(
            {
                "ACTUAL": actual,
                "PREDICTED": predicted,
                "WEIGHT": float(vintage_weights.sum()) * recency_weight,
            }
        )
    vintage_summary = pd.DataFrame(vintage_summary_rows)
    base_errors = (vintage_summary["PREDICTED"] - vintage_summary["ACTUAL"]).abs()
    calibrated_errors = (vintage_summary["PREDICTED"] + adj - vintage_summary["ACTUAL"]).abs()
    base_mae = float(np.average(base_errors, weights=vintage_summary["WEIGHT"]))
    calibrated_mae = float(np.average(calibrated_errors, weights=vintage_summary["WEIGHT"]))
    guardrail_passed = (not CALIBRATION_GUARDRAIL) or calibrated_mae <= base_mae + 1e-12
    if not guardrail_passed:
        adj = 0.0
        calibrated_mae = base_mae

    return {
        "target_run": target_run,
        "calibration_candidates": [pd.Timestamp(v) for v in calibration_candidates.index],
        "used_vintages": used_vintages,
        "raw_adj": raw_adj,
        "shrink": shrink,
        "adj": adj,
        "base_mae": base_mae,
        "calibrated_mae": calibrated_mae,
        "guardrail_passed": bool(guardrail_passed),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = snapshot_project_settings()
    try:
        project_config.SEGMENT_COLS = ["PRODUCT_TYPE", "RISK_SCORE"]

        df_raw = pd.read_parquet(INPUT_STAGE)
        df_model = prepare_backtest_frame(df_raw)
        df_model[CFG["cutoff"]] = parse_date_column(df_model[CFG["cutoff"]])
        df_model[CFG["mob"]] = pd.to_numeric(df_model[CFG["mob"]], errors="coerce")

        target_candidates = (
            df_model[df_model[CFG["mob"]] == TARGET_MOB]
            .groupby("VINTAGE_DATE")[CFG["cutoff"]]
            .max()
            .sort_index()
        )
        target_vintages = [pd.Timestamp(v) for v in target_candidates.index]

        forecast_cache: dict = {}
        detail_rows = []
        for anchor_mob in sorted(ANCHOR_CONFIG):
            lookback_months = TARGET_MOB - int(anchor_mob)
            for target_vintage in target_vintages:
                calibration_result = build_portfolio_calibration_for_target(
                    df_model,
                    target_vintage=target_vintage,
                    anchor_mob=anchor_mob,
                    fit_params=FIT_PARAMS,
                    forecast_cache=forecast_cache,
                )
                if calibration_result is None:
                    continue

                del90_target = calibration_result["target_run"]["compare_df"].copy()
                if del90_target.empty:
                    continue
                del30_target = run_metric_asof_forecast(
                    df_model,
                    vintage=target_vintage,
                    target_mob=TARGET_MOB,
                    lookback_months=lookback_months,
                    fit_params=FIT_PARAMS,
                    metric_name="DEL30",
                    fit_states=BUCKETS_30P,
                    eval_states=BUCKETS_30P,
                    post_mature_k=project_config.K_POST_MATURE,
                    cache=forecast_cache,
                )["compare_df"].copy()

                if del30_target.empty:
                    continue

                del30_pred = del30_target[
                    ["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "MOB", "PRED_PCT"]
                ].rename(columns={"PRED_PCT": "DEL30_PRED_PCT"})
                calibrated_target = del90_target.merge(
                    del30_pred,
                    on=["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "MOB"],
                    how="left",
                    validate="one_to_one",
                )
                calibrated_target["PRED_PCT_CAL_UNCAPPED"] = (
                    calibrated_target["PRED_PCT"].astype(float) + float(calibration_result["adj"])
                ).clip(0.0, 1.0)
                calibrated_target["PRED_PCT_CAL"] = np.minimum(
                    calibrated_target["PRED_PCT_CAL_UNCAPPED"].astype(float),
                    calibrated_target["DEL30_PRED_PCT"].astype(float).clip(0.0, 1.0),
                )
                calibrated_target["CAL_ADJ_APPLIED"] = (
                    calibrated_target["PRED_PCT_CAL"] - calibrated_target["PRED_PCT"]
                )

                base_summary = summarize_weighted_compare(del90_target, pred_col="PRED_PCT")
                calibrated_summary = summarize_weighted_compare(
                    calibrated_target, pred_col="PRED_PCT_CAL"
                )
                detail_rows.append(
                    {
                        "TARGET_VINTAGE": pd.Timestamp(target_vintage),
                        "ANCHOR_MOB": int(anchor_mob),
                        "LOOKBACK_MONTHS": lookback_months,
                        "AS_OF_CUTOFF": calibration_result["target_run"]["asof_cutoff"],
                        "CALIBRATION_N_VINTAGES": len(calibration_result["used_vintages"]),
                        "CALIBRATION_VINTAGES": ",".join(
                            pd.Timestamp(v).strftime("%Y-%m-%d")
                            for v in calibration_result["used_vintages"]
                        ),
                        "RAW_ADJ": float(calibration_result["raw_adj"]),
                        "SHRINK": float(calibration_result["shrink"]),
                        "ADJ": float(calibration_result["adj"]),
                        "BASE_ACTUAL_PCT": float(base_summary["ACTUAL_PCT"]),
                        "BASE_PRED_PCT": float(base_summary["PRED_PCT"]),
                        "BASE_GAP": float(base_summary["GAP"]),
                        "BASE_W_MAE": float(base_summary["W_MAE"]),
                        "BASE_W_RMSE": float(base_summary["W_RMSE"]),
                        "CAL_PRED_PCT": float(calibrated_summary["PRED_PCT"]),
                        "CAL_GAP": float(calibrated_summary["GAP"]),
                        "CAL_W_MAE": float(calibrated_summary["W_MAE"]),
                        "CAL_W_RMSE": float(calibrated_summary["W_RMSE"]),
                        "DISB_TOTAL": float(base_summary["DISB_TOTAL"]),
                        "GUARDRAIL_PASSED": bool(calibration_result["guardrail_passed"]),
                    }
                )

        detail_df = pd.DataFrame(detail_rows).sort_values(["ANCHOR_MOB", "TARGET_VINTAGE"])
        if detail_df.empty:
            raise ValueError("No valid OOT rows were produced for the requested anchors.")

        def weighted_avg(df: pd.DataFrame, col: str) -> float:
            w = df["DISB_TOTAL"].fillna(0.0).astype(float)
            x = df[col].astype(float)
            return float(np.average(x, weights=w)) if bool((w > 0).any()) else float(x.mean())

        anchor_rows = []
        for anchor_mob, subset in detail_df.groupby("ANCHOR_MOB"):
            anchor_rows.append(
                {
                    "ANCHOR_MOB": int(anchor_mob),
                    "N_TARGET_VINTAGES": int(len(subset)),
                    "BASE_ACTUAL_PCT": weighted_avg(subset, "BASE_ACTUAL_PCT"),
                    "BASE_PRED_PCT": weighted_avg(subset, "BASE_PRED_PCT"),
                    "BASE_BIAS": weighted_avg(subset, "BASE_GAP"),
                    "BASE_W_MAE_BY_VINTAGE": weighted_avg(subset, "BASE_W_MAE"),
                    "BASE_W_RMSE_BY_VINTAGE": weighted_avg(subset, "BASE_W_RMSE"),
                    "CAL_PRED_PCT": weighted_avg(subset, "CAL_PRED_PCT"),
                    "CAL_BIAS": weighted_avg(subset, "CAL_GAP"),
                    "CAL_W_MAE_BY_VINTAGE": weighted_avg(subset, "CAL_W_MAE"),
                    "CAL_W_RMSE_BY_VINTAGE": weighted_avg(subset, "CAL_W_RMSE"),
                    "MEAN_ADJ": weighted_avg(subset, "ADJ"),
                }
            )
        anchor_summary_df = pd.DataFrame(anchor_rows).sort_values("ANCHOR_MOB")

        overall_summary_df = pd.DataFrame(
            [
                {
                    "VIEW": "BASELINE_SHARED_DEL30_K",
                    "N_ROWS": int(len(detail_df)),
                    "N_TARGET_VINTAGES": int(detail_df["TARGET_VINTAGE"].nunique()),
                    "ACTUAL_PCT": weighted_avg(detail_df, "BASE_ACTUAL_PCT"),
                    "PRED_PCT": weighted_avg(detail_df, "BASE_PRED_PCT"),
                    "BIAS": weighted_avg(detail_df, "BASE_GAP"),
                    "W_MAE_BY_VINTAGE": weighted_avg(detail_df, "BASE_W_MAE"),
                    "W_RMSE_BY_VINTAGE": weighted_avg(detail_df, "BASE_W_RMSE"),
                },
                {
                    "VIEW": "CURRENT_CALIBRATED_SHARED_DEL30_K",
                    "N_ROWS": int(len(detail_df)),
                    "N_TARGET_VINTAGES": int(detail_df["TARGET_VINTAGE"].nunique()),
                    "ACTUAL_PCT": weighted_avg(detail_df, "BASE_ACTUAL_PCT"),
                    "PRED_PCT": weighted_avg(detail_df, "CAL_PRED_PCT"),
                    "BIAS": weighted_avg(detail_df, "CAL_GAP"),
                    "W_MAE_BY_VINTAGE": weighted_avg(detail_df, "CAL_W_MAE"),
                    "W_RMSE_BY_VINTAGE": weighted_avg(detail_df, "CAL_W_RMSE"),
                },
            ]
        )

        detail_df.to_csv(OUTPUT_DIR / "detail_df.csv", index=False, encoding="utf-8-sig")
        anchor_summary_df.to_csv(
            OUTPUT_DIR / "anchor_summary_df.csv", index=False, encoding="utf-8-sig"
        )
        overall_summary_df.to_csv(
            OUTPUT_DIR / "overall_summary_df.csv", index=False, encoding="utf-8-sig"
        )

        print("Output dir:", OUTPUT_DIR)
        print("\nOverall summary:")
        print(overall_summary_df.to_string(index=False))
        print("\nAnchor summary:")
        print(anchor_summary_df.to_string(index=False))
    finally:
        restore_project_settings(snapshot)


if __name__ == "__main__":
    main()
