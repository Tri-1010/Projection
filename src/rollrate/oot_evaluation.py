from __future__ import annotations

from copy import deepcopy
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd

import src.config as project_config
import src.rollrate.transition as transition_module
from src.config import (
    BUCKETS_30P,
    BUCKETS_90P,
    BUCKETS_CANON,
    CFG,
    create_segment_columns,
    parse_date_column,
)
from src.rollrate.calibration_kmob import (
    fit_alpha,
    fit_k_raw,
    forecast_all_vintages_partial_step,
    smooth_k,
)
from src.rollrate.lifecycle import get_actual_all_vintages_amount
from src.rollrate.transition import compute_transition_by_mob


DEFAULT_METRICS = {
    "DEL30": BUCKETS_30P,
    "DEL90": BUCKETS_90P,
}


def snapshot_project_settings() -> Dict:
    return {
        "segment_cols": list(project_config.SEGMENT_COLS),
        "k_post_mature": project_config.K_POST_MATURE,
        "k_post_mature_del90": project_config.K_POST_MATURE_DEL90,
        "roll_window": project_config.CFG.get("ROLL_WINDOW"),
        "decay_lambda": project_config.CFG.get("DECAY_LAMBDA"),
        "weight_method": project_config.CFG.get(
            "WEIGHT_METHOD",
            getattr(project_config, "WEIGHT_METHOD", "exp"),
        ),
        "min_obs": transition_module.MIN_OBS,
        "min_ead": transition_module.MIN_EAD,
    }


def restore_project_settings(snapshot: Dict) -> None:
    project_config.SEGMENT_COLS = list(snapshot["segment_cols"])
    project_config.K_POST_MATURE = snapshot["k_post_mature"]
    project_config.K_POST_MATURE_DEL90 = snapshot["k_post_mature_del90"]
    project_config.CFG["ROLL_WINDOW"] = snapshot["roll_window"]
    project_config.CFG["DECAY_LAMBDA"] = snapshot["decay_lambda"]
    project_config.CFG["WEIGHT_METHOD"] = snapshot["weight_method"]
    project_config.CFG["MIN_OBS"] = snapshot["min_obs"]
    project_config.CFG["MIN_EAD"] = snapshot["min_ead"]
    transition_module.MIN_OBS = snapshot["min_obs"]
    transition_module.MIN_EAD = snapshot["min_ead"]


def apply_project_settings(overrides: Optional[Dict]) -> None:
    if not overrides:
        return
    if "segment_cols" in overrides and overrides["segment_cols"] is not None:
        project_config.SEGMENT_COLS = list(overrides["segment_cols"])
    if "k_post_mature" in overrides:
        project_config.K_POST_MATURE = overrides["k_post_mature"]
    if "k_post_mature_del90" in overrides:
        project_config.K_POST_MATURE_DEL90 = overrides["k_post_mature_del90"]
    if "roll_window" in overrides and overrides["roll_window"] is not None:
        project_config.CFG["ROLL_WINDOW"] = int(overrides["roll_window"])
    if "decay_lambda" in overrides and overrides["decay_lambda"] is not None:
        project_config.CFG["DECAY_LAMBDA"] = float(overrides["decay_lambda"])
    if "weight_method" in overrides:
        project_config.CFG["WEIGHT_METHOD"] = overrides["weight_method"]
    if "min_obs" in overrides and overrides["min_obs"] is not None:
        transition_module.MIN_OBS = int(overrides["min_obs"])
        project_config.CFG["MIN_OBS"] = int(overrides["min_obs"])
    if "min_ead" in overrides and overrides["min_ead"] is not None:
        transition_module.MIN_EAD = float(overrides["min_ead"])
        project_config.CFG["MIN_EAD"] = float(overrides["min_ead"])


def prepare_backtest_frame(
    df_raw: pd.DataFrame,
    product_filter: Optional[Iterable[str]] = None,
    risk_filter: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    df = df_raw.copy()
    if CFG["orig_date"] in df.columns:
        df[CFG["orig_date"]] = parse_date_column(df[CFG["orig_date"]])
    if CFG["cutoff"] in df.columns:
        df[CFG["cutoff"]] = parse_date_column(df[CFG["cutoff"]])
    df = create_segment_columns(df)
    df["VINTAGE_DATE"] = parse_date_column(df[CFG["orig_date"]])

    if product_filter:
        product_filter = {str(v) for v in product_filter}
        df = df[df["PRODUCT_TYPE"].astype(str).isin(product_filter)].copy()
    if risk_filter:
        risk_filter = {str(v) for v in risk_filter}
        df = df[df["RISK_SCORE"].astype(str).isin(risk_filter)].copy()

    if df.empty:
        raise ValueError("No data left after prepare_backtest_frame filters.")
    return df


def split_train_holdout_by_vintage(
    df_raw: pd.DataFrame,
    holdout_months: int = 6,
    min_train_vintages: int = 6,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    if holdout_months < 1:
        raise ValueError("holdout_months must be >= 1")
    vintages = sorted(pd.to_datetime(df_raw["VINTAGE_DATE"]).dropna().unique())
    if len(vintages) <= holdout_months:
        raise ValueError(
            f"Need more than {holdout_months} unique vintages for holdout; got {len(vintages)}."
        )

    cutoff_vintage = pd.Timestamp(vintages[-holdout_months])
    train_vintages = [pd.Timestamp(v) for v in vintages if pd.Timestamp(v) < cutoff_vintage]
    holdout_vintages = [pd.Timestamp(v) for v in vintages if pd.Timestamp(v) >= cutoff_vintage]
    if len(train_vintages) < min_train_vintages:
        raise ValueError(
            f"Need at least {min_train_vintages} train vintages; got {len(train_vintages)}."
        )

    df_train = df_raw[df_raw["VINTAGE_DATE"] < cutoff_vintage].copy()
    df_holdout = df_raw[df_raw["VINTAGE_DATE"] >= cutoff_vintage].copy()
    if df_train.empty or df_holdout.empty:
        raise ValueError("Train or holdout split is empty.")

    split_info = {
        "cutoff_vintage": cutoff_vintage,
        "train_vintages": train_vintages,
        "holdout_vintages": holdout_vintages,
        "n_train_vintages": len(train_vintages),
        "n_holdout_vintages": len(holdout_vintages),
        "train_rows": len(df_train),
        "holdout_rows": len(df_holdout),
        "train_loans": int(df_train[CFG["loan"]].nunique()),
        "holdout_loans": int(df_holdout[CFG["loan"]].nunique()),
    }
    return df_train, df_holdout, split_info


def build_disb_total_by_vintage(df_raw: pd.DataFrame) -> Dict:
    loan_disb = df_raw.groupby(
        ["PRODUCT_TYPE", "RISK_SCORE", CFG["orig_date"], CFG["loan"]]
    )[CFG["disb"]].first()
    return loan_disb.groupby(level=[0, 1, 2]).sum().to_dict()


def trim_actual_results_for_anchor(
    actual_results: Dict,
    anchor_mob: int | str = 0,
) -> Dict:
    trimmed = {}
    for key, mob_dict in actual_results.items():
        if not mob_dict:
            continue
        mobs = sorted(int(mob) for mob in mob_dict.keys())
        if anchor_mob == "min":
            start_mob = mobs[0]
        else:
            start_mob = int(anchor_mob)
            if start_mob not in mob_dict:
                continue
        trimmed[key] = {start_mob: mob_dict[start_mob]}
    return trimmed


def _metric_amount_and_rate(
    ead_by_state: pd.Series,
    metric_states: Iterable[str],
    disb_total: float,
) -> Tuple[float, float]:
    metric_states = [state for state in metric_states if state in ead_by_state.index]
    amount = float(ead_by_state.reindex(metric_states, fill_value=0.0).sum())
    if disb_total and disb_total > 0:
        rate = amount / float(disb_total)
    else:
        rate = np.nan
    return amount, rate


def fit_metric_curve(
    actual_results_train: Dict,
    matrices_by_mob: Dict,
    parent_fallback: Dict,
    disb_total_by_vintage_train: Dict,
    metric_states: Iterable[str],
    fit_params: Dict,
    post_mature_k=None,
    post_mature_start_mob: Optional[int] = None,
) -> Dict:
    metric_states = list(metric_states)
    k_raw_by_mob, weight_by_mob, detail_df = fit_k_raw(
        actual_results=actual_results_train,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        states=BUCKETS_CANON,
        s30_states=metric_states,
        include_co=True,
        denom_mode="disb",
        disb_total_by_vintage=disb_total_by_vintage_train,
        weight_mode=fit_params.get("k_weight_mode", "equal"),
        method=fit_params.get("k_method", "wls_reg"),
        lambda_k=float(fit_params.get("lambda_k", 1e-4)),
        k_prior=float(fit_params.get("k_prior", 0.0)),
        min_obs=int(fit_params.get("k_min_obs", 5)),
        fallback_k=float(fit_params.get("fallback_k", 1.0)),
        fallback_weight=float(fit_params.get("fallback_weight", 0.0)),
        return_detail=True,
    )
    if not k_raw_by_mob:
        raise ValueError("Empty k_raw_by_mob during fit_metric_curve.")

    mob_min = min(k_raw_by_mob)
    mob_max = max(k_raw_by_mob)
    k_smooth_by_mob, _, _ = smooth_k(
        k_raw_by_mob,
        weight_by_mob,
        mob_min,
        mob_max,
        gamma=float(fit_params.get("gamma", 10.0)),
        monotone=bool(fit_params.get("monotone", False)),
    )

    alpha_target = int(fit_params.get("alpha_mob_target", mob_max))
    alpha_target = min(alpha_target, mob_max)
    alpha, k_final_by_mob, alpha_score_df = fit_alpha(
        actual_results=actual_results_train,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        states=BUCKETS_CANON,
        s30_states=metric_states,
        k_smooth_by_mob=k_smooth_by_mob,
        mob_target=alpha_target,
        include_co=True,
        denom_mode="disb",
        disb_total_by_vintage=disb_total_by_vintage_train,
        weight_mode=fit_params.get("k_weight_mode", "equal"),
        post_mature_k=None,
    )

    if post_mature_k is not None and post_mature_start_mob is not None:
        for mob in range(int(post_mature_start_mob), max(k_final_by_mob.keys()) + 1):
            k_final_by_mob[mob] = float(post_mature_k)

    k_curve_df = pd.DataFrame(
        {
            "MOB": sorted(k_final_by_mob.keys()),
            "K_RAW": [k_raw_by_mob.get(mob, np.nan) for mob in sorted(k_final_by_mob.keys())],
            "K_WEIGHT": [weight_by_mob.get(mob, np.nan) for mob in sorted(k_final_by_mob.keys())],
            "K_SMOOTH": [k_smooth_by_mob.get(mob, np.nan) for mob in sorted(k_final_by_mob.keys())],
            "K_FINAL": [k_final_by_mob.get(mob, np.nan) for mob in sorted(k_final_by_mob.keys())],
        }
    )

    return {
        "metric_states": metric_states,
        "alpha": float(alpha),
        "alpha_target_mob": int(alpha_target),
        "k_raw_by_mob": k_raw_by_mob,
        "weight_by_mob": weight_by_mob,
        "k_smooth_by_mob": k_smooth_by_mob,
        "k_final_by_mob": k_final_by_mob,
        "k_detail_df": detail_df,
        "alpha_score_df": alpha_score_df,
        "k_curve_df": k_curve_df,
    }


def build_metric_compare_frame(
    actual_results_holdout: Dict,
    forecast_results_holdout: Dict,
    disb_total_by_vintage_holdout: Dict,
    metric_name: str,
    metric_states: Iterable[str],
) -> pd.DataFrame:
    rows = []
    metric_states = list(metric_states)
    for key, actual_mob_dict in actual_results_holdout.items():
        forecast_mob_dict = forecast_results_holdout.get(key)
        if not forecast_mob_dict:
            continue
        product, score, vintage = key
        start_mob = min(int(mob) for mob in forecast_mob_dict.keys())
        disb_total = float(disb_total_by_vintage_holdout.get(key, np.nan))
        for mob, actual_series in actual_mob_dict.items():
            mob = int(mob)
            if mob == start_mob or mob not in forecast_mob_dict:
                continue
            pred_series = forecast_mob_dict[mob]
            actual_amt, actual_pct = _metric_amount_and_rate(actual_series, metric_states, disb_total)
            pred_amt, pred_pct = _metric_amount_and_rate(pred_series, metric_states, disb_total)
            rows.append(
                {
                    "METRIC": metric_name,
                    "PRODUCT_TYPE": product,
                    "RISK_SCORE": score,
                    "VINTAGE_DATE": pd.Timestamp(vintage),
                    "MOB": mob,
                    "START_MOB": start_mob,
                    "DISB_TOTAL": disb_total,
                    "ACTUAL_AMT": actual_amt,
                    "PRED_AMT": pred_amt,
                    "ACTUAL_PCT": actual_pct,
                    "PRED_PCT": pred_pct,
                    "ERROR": pred_pct - actual_pct,
                    "ABS_ERROR": abs(pred_pct - actual_pct),
                    "SQ_ERROR": (pred_pct - actual_pct) ** 2,
                }
            )
    return pd.DataFrame(rows)


def summarize_path_metrics(compare_df: pd.DataFrame) -> Dict:
    if compare_df.empty:
        return {
            "N_OBS": 0,
            "N_COHORTS": 0,
            "MAE": np.nan,
            "RMSE": np.nan,
            "BRIER": np.nan,
            "WEIGHTED_MAE": np.nan,
            "WEIGHTED_RMSE": np.nan,
            "WEIGHTED_BRIER": np.nan,
            "BIAS": np.nan,
            "CORR": np.nan,
        }

    w = compare_df["DISB_TOTAL"].fillna(0.0).astype(float).values
    abs_err = compare_df["ABS_ERROR"].astype(float).values
    sq_err = compare_df["SQ_ERROR"].astype(float).values
    err = compare_df["ERROR"].astype(float).values
    actual = compare_df["ACTUAL_PCT"].astype(float).values
    pred = compare_df["PRED_PCT"].astype(float).values

    has_weight = np.any(w > 0)
    actual_std = float(np.std(actual))
    pred_std = float(np.std(pred))
    corr = (
        float(np.corrcoef(actual, pred)[0, 1])
        if len(compare_df) > 1 and actual_std > 0 and pred_std > 0
        else np.nan
    )

    return {
        "N_OBS": int(len(compare_df)),
        "N_COHORTS": int(compare_df[["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE"]].drop_duplicates().shape[0]),
        "MAE": float(np.mean(abs_err)),
        "RMSE": float(np.sqrt(np.mean(sq_err))),
        "BRIER": float(np.mean(sq_err)),
        "WEIGHTED_MAE": float(np.average(abs_err, weights=w)) if has_weight else np.nan,
        "WEIGHTED_RMSE": float(np.sqrt(np.average(sq_err, weights=w))) if has_weight else np.nan,
        "WEIGHTED_BRIER": float(np.average(sq_err, weights=w)) if has_weight else np.nan,
        "BIAS": float(np.mean(err)),
        "CORR": corr,
    }


def build_loan_level_brier_frame(
    df_holdout: pd.DataFrame,
    compare_df: pd.DataFrame,
    metric_states: Iterable[str],
    target_mob: int,
) -> pd.DataFrame:
    if compare_df.empty:
        return pd.DataFrame()

    metric_states = set(metric_states)
    loan_col = CFG["loan"]
    mob_col = CFG["mob"]
    state_col = CFG["state"]
    disb_col = CFG["disb"]

    df_base = (
        df_holdout.sort_values([loan_col, mob_col, CFG["cutoff"]])
        .drop_duplicates(subset=[loan_col], keep="first")
        [[loan_col, "PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", disb_col]]
        .rename(columns={disb_col: "DISBURSAL_AMOUNT"})
    )

    df_target = (
        df_holdout[df_holdout[mob_col] == int(target_mob)]
        .sort_values([loan_col, CFG["cutoff"]])
        .drop_duplicates(subset=[loan_col], keep="last")
        [[loan_col, state_col]]
        .rename(columns={state_col: "STATE_AT_TARGET"})
    )
    df_target["ACTUAL_EVENT"] = df_target["STATE_AT_TARGET"].isin(metric_states).astype(int)

    df_pred = (
        compare_df[compare_df["MOB"] == int(target_mob)]
        [["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "PRED_PCT"]]
        .drop_duplicates()
        .rename(columns={"PRED_PCT": "PRED_PROB"})
    )

    df_loan = df_base.merge(df_target, on=loan_col, how="inner")
    df_loan = df_loan.merge(
        df_pred,
        on=["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE"],
        how="inner",
        validate="many_to_one",
    )
    if df_loan.empty:
        return df_loan

    df_loan["TARGET_MOB"] = int(target_mob)
    df_loan["BRIER_COMPONENT"] = (df_loan["PRED_PROB"] - df_loan["ACTUAL_EVENT"]) ** 2
    df_loan["ABS_ERROR"] = (df_loan["PRED_PROB"] - df_loan["ACTUAL_EVENT"]).abs()
    return df_loan


def summarize_loan_brier(df_loan_brier: pd.DataFrame) -> Dict:
    if df_loan_brier.empty:
        return {
            "N_LOANS": 0,
            "ACTUAL_RATE": np.nan,
            "PRED_RATE": np.nan,
            "BRIER": np.nan,
            "WEIGHTED_BRIER": np.nan,
            "MAE": np.nan,
            "WEIGHTED_MAE": np.nan,
        }

    weights = df_loan_brier["DISBURSAL_AMOUNT"].fillna(0.0).astype(float).values
    has_weight = np.any(weights > 0)
    return {
        "N_LOANS": int(len(df_loan_brier)),
        "ACTUAL_RATE": float(df_loan_brier["ACTUAL_EVENT"].mean()),
        "PRED_RATE": float(df_loan_brier["PRED_PROB"].mean()),
        "BRIER": float(df_loan_brier["BRIER_COMPONENT"].mean()),
        "WEIGHTED_BRIER": float(np.average(df_loan_brier["BRIER_COMPONENT"], weights=weights))
        if has_weight
        else np.nan,
        "MAE": float(df_loan_brier["ABS_ERROR"].mean()),
        "WEIGHTED_MAE": float(np.average(df_loan_brier["ABS_ERROR"], weights=weights))
        if has_weight
        else np.nan,
    }


def _run_metric_backtest_from_prepared_split(
    *,
    df_holdout: pd.DataFrame,
    actual_results_train: Dict,
    actual_results_holdout: Dict,
    actual_results_holdout_anchor: Dict,
    matrices_by_mob: Dict,
    parent_fallback: Dict,
    disb_total_train: Dict,
    disb_total_holdout: Dict,
    metric_name: str,
    metric_states: Iterable[str],
    fit_params: Dict,
    max_mob_eval: int = 24,
    anchor_mob: int | str = 0,
    target_mobs: Optional[Iterable[int]] = None,
    post_mature_k=None,
    post_mature_start_mob: Optional[int] = None,
) -> Dict:
    metric_states = list(metric_states)

    fit_output = fit_metric_curve(
        actual_results_train=actual_results_train,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        disb_total_by_vintage_train=disb_total_train,
        metric_states=metric_states,
        fit_params=fit_params,
        post_mature_k=post_mature_k,
        post_mature_start_mob=post_mature_start_mob,
    )

    forecast_results_holdout = forecast_all_vintages_partial_step(
        actual_results=actual_results_holdout_anchor,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        max_mob=max_mob_eval,
        k_by_mob=fit_output["k_final_by_mob"],
        states=BUCKETS_CANON,
    )

    compare_df = build_metric_compare_frame(
        actual_results_holdout=actual_results_holdout,
        forecast_results_holdout=forecast_results_holdout,
        disb_total_by_vintage_holdout=disb_total_holdout,
        metric_name=metric_name,
        metric_states=metric_states,
    )

    summary = summarize_path_metrics(compare_df)
    loan_brier_frames = []
    loan_brier_summary_rows = []
    for target_mob in sorted({int(mob) for mob in (target_mobs or [])}):
        df_loan_brier = build_loan_level_brier_frame(
            df_holdout=df_holdout,
            compare_df=compare_df,
            metric_states=metric_states,
            target_mob=target_mob,
        )
        if df_loan_brier.empty:
            continue
        loan_brier_frames.append(df_loan_brier)
        loan_summary = summarize_loan_brier(df_loan_brier)
        loan_summary["METRIC"] = metric_name
        loan_summary["TARGET_MOB"] = target_mob
        loan_brier_summary_rows.append(loan_summary)

    loan_brier_df = (
        pd.concat(loan_brier_frames, ignore_index=True) if loan_brier_frames else pd.DataFrame()
    )
    loan_brier_summary_df = pd.DataFrame(loan_brier_summary_rows)

    summary_row = {"METRIC": metric_name}
    summary_row.update(summary)
    summary_df = pd.DataFrame([summary_row])

    return {
        "metric_name": metric_name,
        "metric_states": metric_states,
        "compare_df": compare_df,
        "summary_df": summary_df,
        "loan_brier_df": loan_brier_df,
        "loan_brier_summary_df": loan_brier_summary_df,
        "fit_output": fit_output,
        "matrices_by_mob": matrices_by_mob,
        "parent_fallback": parent_fallback,
        "actual_results_holdout": actual_results_holdout,
        "forecast_results_holdout": forecast_results_holdout,
        "disb_total_holdout": disb_total_holdout,
    }


def run_single_metric_oot_backtest(
    df_train: pd.DataFrame,
    df_holdout: pd.DataFrame,
    metric_name: str,
    metric_states: Iterable[str],
    fit_params: Dict,
    max_mob_eval: int = 24,
    anchor_mob: int | str = 0,
    target_mobs: Optional[Iterable[int]] = None,
    post_mature_k=None,
    post_mature_start_mob: Optional[int] = None,
) -> Dict:
    matrices_by_mob, parent_fallback = compute_transition_by_mob(df_train)
    actual_results_train = get_actual_all_vintages_amount(df_train)
    actual_results_holdout = get_actual_all_vintages_amount(df_holdout)
    actual_results_holdout_anchor = trim_actual_results_for_anchor(
        actual_results_holdout,
        anchor_mob=anchor_mob,
    )
    disb_total_train = build_disb_total_by_vintage(df_train)
    disb_total_holdout = build_disb_total_by_vintage(df_holdout)

    return _run_metric_backtest_from_prepared_split(
        df_holdout=df_holdout,
        actual_results_train=actual_results_train,
        actual_results_holdout=actual_results_holdout,
        actual_results_holdout_anchor=actual_results_holdout_anchor,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        disb_total_train=disb_total_train,
        disb_total_holdout=disb_total_holdout,
        metric_name=metric_name,
        metric_states=metric_states,
        fit_params=fit_params,
        max_mob_eval=max_mob_eval,
        anchor_mob=anchor_mob,
        target_mobs=target_mobs,
        post_mature_k=post_mature_k,
        post_mature_start_mob=post_mature_start_mob,
    )


def run_dual_metric_backtest_on_split(
    df_train: pd.DataFrame,
    df_holdout: pd.DataFrame,
    *,
    fit_params: Optional[Dict] = None,
    max_mob_eval: int = 24,
    anchor_mob: int | str = 0,
    target_mobs: Optional[Iterable[int]] = None,
) -> Dict:
    fit_params = deepcopy(fit_params or {})
    target_mobs = list(target_mobs or [])

    matrices_by_mob, parent_fallback = compute_transition_by_mob(df_train)
    actual_results_train = get_actual_all_vintages_amount(df_train)
    actual_results_holdout = get_actual_all_vintages_amount(df_holdout)
    actual_results_holdout_anchor = trim_actual_results_for_anchor(
        actual_results_holdout,
        anchor_mob=anchor_mob,
    )
    disb_total_train = build_disb_total_by_vintage(df_train)
    disb_total_holdout = build_disb_total_by_vintage(df_holdout)

    metric_results = {}
    for metric_name, metric_states in DEFAULT_METRICS.items():
        if metric_name == "DEL30":
            post_mature_k = project_config.K_POST_MATURE
        else:
            post_mature_k = project_config.K_POST_MATURE_DEL90

        metric_results[metric_name] = _run_metric_backtest_from_prepared_split(
            df_holdout=df_holdout,
            actual_results_train=actual_results_train,
            actual_results_holdout=actual_results_holdout,
            actual_results_holdout_anchor=actual_results_holdout_anchor,
            matrices_by_mob=matrices_by_mob,
            parent_fallback=parent_fallback,
            disb_total_train=disb_total_train,
            disb_total_holdout=disb_total_holdout,
            metric_name=metric_name,
            metric_states=metric_states,
            fit_params=fit_params,
            max_mob_eval=max_mob_eval,
            anchor_mob=anchor_mob,
            target_mobs=target_mobs,
            post_mature_k=post_mature_k,
            post_mature_start_mob=min(target_mobs) if target_mobs else None,
        )

    summary_df = pd.concat(
        [metric_results[name]["summary_df"] for name in metric_results],
        ignore_index=True,
    )
    loan_brier_summary_df = pd.concat(
        [
            metric_results[name]["loan_brier_summary_df"]
            for name in metric_results
            if not metric_results[name]["loan_brier_summary_df"].empty
        ],
        ignore_index=True,
    ) if any(
        not metric_results[name]["loan_brier_summary_df"].empty
        for name in metric_results
    ) else pd.DataFrame()

    return {
        "summary_df": summary_df,
        "loan_brier_summary_df": loan_brier_summary_df,
        "metric_results": metric_results,
        "matrices_by_mob": matrices_by_mob,
        "parent_fallback": parent_fallback,
        "actual_results_train": actual_results_train,
        "actual_results_holdout": actual_results_holdout,
        "actual_results_holdout_anchor": actual_results_holdout_anchor,
        "disb_total_train": disb_total_train,
        "disb_total_holdout": disb_total_holdout,
    }


def run_dual_metric_oot_backtest(
    df_raw: pd.DataFrame,
    *,
    holdout_months: int = 6,
    min_train_vintages: int = 6,
    max_mob_eval: int = 24,
    anchor_mob: int | str = 0,
    target_mobs: Optional[Iterable[int]] = None,
    product_filter: Optional[Iterable[str]] = None,
    risk_filter: Optional[Iterable[str]] = None,
    fit_params: Optional[Dict] = None,
    settings_overrides: Optional[Dict] = None,
) -> Dict:
    fit_params = deepcopy(fit_params or {})
    target_mobs = list(target_mobs or [])

    snapshot = snapshot_project_settings()
    try:
        apply_project_settings(settings_overrides)
        df_model = prepare_backtest_frame(
            df_raw,
            product_filter=product_filter,
            risk_filter=risk_filter,
        )
        df_train, df_holdout, split_info = split_train_holdout_by_vintage(
            df_model,
            holdout_months=holdout_months,
            min_train_vintages=min_train_vintages,
        )

        split_backtest = run_dual_metric_backtest_on_split(
            df_train=df_train,
            df_holdout=df_holdout,
            fit_params=fit_params,
            max_mob_eval=max_mob_eval,
            anchor_mob=anchor_mob,
            target_mobs=target_mobs,
        )
        metric_results = split_backtest["metric_results"]
        summary_df = split_backtest["summary_df"]
        loan_brier_summary_df = split_backtest["loan_brier_summary_df"]

        split_summary_df = pd.DataFrame(
            [
                {
                    "CUT_OFF_HOLDOUT_VINTAGE": split_info["cutoff_vintage"],
                    "N_TRAIN_VINTAGES": split_info["n_train_vintages"],
                    "N_HOLDOUT_VINTAGES": split_info["n_holdout_vintages"],
                    "TRAIN_ROWS": split_info["train_rows"],
                    "HOLDOUT_ROWS": split_info["holdout_rows"],
                    "TRAIN_LOANS": split_info["train_loans"],
                    "HOLDOUT_LOANS": split_info["holdout_loans"],
                    "TRAIN_DISB_TOTAL": float(df_train[CFG["disb"]].sum()),
                    "HOLDOUT_DISB_TOTAL": float(df_holdout[CFG["disb"]].sum()),
                }
            ]
        )

        return {
            "df_model": df_model,
            "df_train": df_train,
            "df_holdout": df_holdout,
            "split_info": split_info,
            "split_summary_df": split_summary_df,
            "summary_df": summary_df,
            "loan_brier_summary_df": loan_brier_summary_df,
            "metric_results": metric_results,
        }
    finally:
        restore_project_settings(snapshot)


def split_fixed_holdout_window(
    df_raw: pd.DataFrame,
    holdout_start_vintage,
    holdout_months: int = 6,
    min_train_vintages: int = 6,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    if holdout_months < 1:
        raise ValueError("holdout_months must be >= 1")
    vintages = sorted(pd.to_datetime(df_raw["VINTAGE_DATE"]).dropna().unique())
    holdout_start_vintage = pd.Timestamp(holdout_start_vintage)
    if holdout_start_vintage not in vintages:
        raise ValueError(f"holdout_start_vintage {holdout_start_vintage} not found in data.")

    start_idx = vintages.index(holdout_start_vintage)
    end_idx = start_idx + int(holdout_months)
    holdout_vintages = [pd.Timestamp(v) for v in vintages[start_idx:end_idx]]
    if len(holdout_vintages) < holdout_months:
        raise ValueError("Not enough vintages to complete requested fixed holdout window.")

    train_vintages = [pd.Timestamp(v) for v in vintages[:start_idx]]
    if len(train_vintages) < min_train_vintages:
        raise ValueError(
            f"Need at least {min_train_vintages} train vintages before {holdout_start_vintage}; "
            f"got {len(train_vintages)}."
        )

    holdout_end_vintage = holdout_vintages[-1]
    df_train = df_raw[df_raw["VINTAGE_DATE"] < holdout_start_vintage].copy()
    df_holdout = df_raw[
        (df_raw["VINTAGE_DATE"] >= holdout_start_vintage)
        & (df_raw["VINTAGE_DATE"] <= holdout_end_vintage)
    ].copy()
    if df_train.empty or df_holdout.empty:
        raise ValueError("Train or holdout split is empty for fixed holdout window.")

    split_info = {
        "cutoff_vintage": holdout_start_vintage,
        "holdout_start_vintage": holdout_start_vintage,
        "holdout_end_vintage": holdout_end_vintage,
        "train_vintages": train_vintages,
        "holdout_vintages": holdout_vintages,
        "n_train_vintages": len(train_vintages),
        "n_holdout_vintages": len(holdout_vintages),
        "train_rows": len(df_train),
        "holdout_rows": len(df_holdout),
        "train_loans": int(df_train[CFG["loan"]].nunique()),
        "holdout_loans": int(df_holdout[CFG["loan"]].nunique()),
    }
    return df_train, df_holdout, split_info


def find_mature_holdout_windows(
    df_model: pd.DataFrame,
    *,
    target_mob: int,
    holdout_months: int = 6,
    min_train_vintages: int = 12,
    max_windows: Optional[int] = None,
) -> pd.DataFrame:
    if holdout_months < 1:
        raise ValueError("holdout_months must be >= 1")
    target_mob = int(target_mob)

    vintage_max_mob = (
        df_model.groupby("VINTAGE_DATE")[CFG["mob"]]
        .max()
        .sort_index()
    )
    vintages = list(vintage_max_mob.index)
    windows = []
    start_idx = len(vintages) - holdout_months

    while start_idx >= min_train_vintages:
        holdout_vintages = vintages[start_idx:start_idx + holdout_months]
        if len(holdout_vintages) < holdout_months:
            start_idx -= 1
            continue
        holdout_max_mob = int(vintage_max_mob.loc[holdout_vintages].min())
        if holdout_max_mob >= target_mob:
            windows.append(
                {
                    "TARGET_MOB": target_mob,
                    "WINDOW_ID": f"MOB{target_mob}_{pd.Timestamp(holdout_vintages[0]).strftime('%Y%m')}_{pd.Timestamp(holdout_vintages[-1]).strftime('%Y%m')}",
                    "START_VINTAGE": pd.Timestamp(holdout_vintages[0]),
                    "END_VINTAGE": pd.Timestamp(holdout_vintages[-1]),
                    "N_HOLDOUT_VINTAGES": len(holdout_vintages),
                    "N_TRAIN_VINTAGES": start_idx,
                    "MIN_HOLDOUT_MAX_MOB": holdout_max_mob,
                }
            )
            start_idx -= holdout_months
        else:
            start_idx -= 1

    windows = list(reversed(windows))
    if max_windows is not None:
        windows = windows[-int(max_windows):]
    return pd.DataFrame(windows)


def run_rolling_mature_oot_backtest(
    df_raw: pd.DataFrame,
    *,
    mature_target_mobs: Iterable[int],
    holdout_months: int = 6,
    min_train_vintages: int = 12,
    max_windows_per_target: Optional[int] = 3,
    anchor_mob: int | str = 0,
    product_filter: Optional[Iterable[str]] = None,
    risk_filter: Optional[Iterable[str]] = None,
    fit_params: Optional[Dict] = None,
    settings_overrides: Optional[Dict] = None,
) -> Dict:
    fit_params = deepcopy(fit_params or {})
    mature_target_mobs = sorted({int(mob) for mob in mature_target_mobs})

    snapshot = snapshot_project_settings()
    try:
        apply_project_settings(settings_overrides)
        df_model = prepare_backtest_frame(
            df_raw,
            product_filter=product_filter,
            risk_filter=risk_filter,
        )

        windows_by_target = {}
        window_results = []
        compare_frames = []
        loan_brier_frames = []
        path_summary_rows = []
        loan_summary_rows = []

        for target_mob in mature_target_mobs:
            eligible_windows = find_mature_holdout_windows(
                df_model,
                target_mob=target_mob,
                holdout_months=holdout_months,
                min_train_vintages=min_train_vintages,
                max_windows=max_windows_per_target,
            )
            windows_by_target[target_mob] = eligible_windows
            if eligible_windows.empty:
                continue

            for _, window in eligible_windows.iterrows():
                df_train, df_holdout, split_info = split_fixed_holdout_window(
                    df_model,
                    holdout_start_vintage=window["START_VINTAGE"],
                    holdout_months=holdout_months,
                    min_train_vintages=min_train_vintages,
                )
                split_backtest = run_dual_metric_backtest_on_split(
                    df_train=df_train,
                    df_holdout=df_holdout,
                    fit_params=fit_params,
                    max_mob_eval=target_mob,
                    anchor_mob=anchor_mob,
                    target_mobs=[target_mob],
                )

                window_result = {
                    "TARGET_MOB": target_mob,
                    "WINDOW_ID": window["WINDOW_ID"],
                    "START_VINTAGE": pd.Timestamp(window["START_VINTAGE"]),
                    "END_VINTAGE": pd.Timestamp(window["END_VINTAGE"]),
                    "split_info": split_info,
                    "backtest": split_backtest,
                }
                window_results.append(window_result)

                for metric_name, metric_result in split_backtest["metric_results"].items():
                    compare_df = metric_result["compare_df"].copy()
                    if not compare_df.empty:
                        compare_df["WINDOW_ID"] = window["WINDOW_ID"]
                        compare_df["TARGET_MOB_WINDOW"] = target_mob
                        compare_df["WINDOW_START_VINTAGE"] = pd.Timestamp(window["START_VINTAGE"])
                        compare_df["WINDOW_END_VINTAGE"] = pd.Timestamp(window["END_VINTAGE"])
                        compare_frames.append(compare_df)

                    loan_brier_df = metric_result["loan_brier_df"].copy()
                    if not loan_brier_df.empty:
                        loan_brier_df["METRIC"] = metric_name
                        loan_brier_df["WINDOW_ID"] = window["WINDOW_ID"]
                        loan_brier_df["TARGET_MOB_WINDOW"] = target_mob
                        loan_brier_df["WINDOW_START_VINTAGE"] = pd.Timestamp(window["START_VINTAGE"])
                        loan_brier_df["WINDOW_END_VINTAGE"] = pd.Timestamp(window["END_VINTAGE"])
                        loan_brier_frames.append(loan_brier_df)

                    path_row = metric_result["summary_df"].iloc[0].to_dict()
                    path_row.update(
                        {
                            "TARGET_MOB_WINDOW": target_mob,
                            "WINDOW_ID": window["WINDOW_ID"],
                            "WINDOW_START_VINTAGE": pd.Timestamp(window["START_VINTAGE"]),
                            "WINDOW_END_VINTAGE": pd.Timestamp(window["END_VINTAGE"]),
                            "N_TRAIN_VINTAGES": split_info["n_train_vintages"],
                            "N_HOLDOUT_VINTAGES": split_info["n_holdout_vintages"],
                        }
                    )
                    path_summary_rows.append(path_row)

                    if not metric_result["loan_brier_summary_df"].empty:
                        for _, loan_row in metric_result["loan_brier_summary_df"].iterrows():
                            loan_row_dict = loan_row.to_dict()
                            loan_row_dict.update(
                                {
                                    "TARGET_MOB_WINDOW": target_mob,
                                    "WINDOW_ID": window["WINDOW_ID"],
                                    "WINDOW_START_VINTAGE": pd.Timestamp(window["START_VINTAGE"]),
                                    "WINDOW_END_VINTAGE": pd.Timestamp(window["END_VINTAGE"]),
                                    "N_TRAIN_VINTAGES": split_info["n_train_vintages"],
                                    "N_HOLDOUT_VINTAGES": split_info["n_holdout_vintages"],
                                }
                            )
                            loan_summary_rows.append(loan_row_dict)

        path_summary_by_window_df = pd.DataFrame(path_summary_rows)
        loan_brier_summary_by_window_df = pd.DataFrame(loan_summary_rows)
        mature_compare_df = pd.concat(compare_frames, ignore_index=True) if compare_frames else pd.DataFrame()
        mature_loan_brier_df = pd.concat(loan_brier_frames, ignore_index=True) if loan_brier_frames else pd.DataFrame()

        aggregate_rows = []
        aggregate_loan_rows = []
        for target_mob in mature_target_mobs:
            for metric_name in DEFAULT_METRICS:
                subset_compare = mature_compare_df[
                    (mature_compare_df.get("TARGET_MOB_WINDOW") == target_mob)
                    & (mature_compare_df.get("METRIC") == metric_name)
                ].copy() if not mature_compare_df.empty else pd.DataFrame()
                summary = summarize_path_metrics(subset_compare)
                summary["METRIC"] = metric_name
                summary["TARGET_MOB_WINDOW"] = target_mob
                summary["N_WINDOWS"] = int(
                    windows_by_target.get(target_mob, pd.DataFrame()).shape[0]
                )
                aggregate_rows.append(summary)

                subset_loan = mature_loan_brier_df[
                    (mature_loan_brier_df.get("TARGET_MOB_WINDOW") == target_mob)
                    & (mature_loan_brier_df.get("TARGET_MOB") == target_mob)
                    & (mature_loan_brier_df.get("METRIC") == metric_name)
                ].copy() if not mature_loan_brier_df.empty else pd.DataFrame()
                if not subset_loan.empty:
                    loan_summary = summarize_loan_brier(subset_loan)
                    loan_summary["METRIC"] = metric_name
                    loan_summary["TARGET_MOB_WINDOW"] = target_mob
                    loan_summary["N_WINDOWS"] = int(
                        windows_by_target.get(target_mob, pd.DataFrame()).shape[0]
                    )
                    aggregate_loan_rows.append(loan_summary)

        mature_path_summary_df = pd.DataFrame(aggregate_rows)
        mature_loan_brier_summary_df = pd.DataFrame(aggregate_loan_rows)

        windows_catalog_df = pd.concat(
            [
                df.assign(TARGET_MOB=target_mob)
                for target_mob, df in windows_by_target.items()
                if not df.empty
            ],
            ignore_index=True,
        ) if any(not df.empty for df in windows_by_target.values()) else pd.DataFrame()

        return {
            "df_model": df_model,
            "windows_by_target": windows_by_target,
            "windows_catalog_df": windows_catalog_df,
            "window_results": window_results,
            "path_summary_by_window_df": path_summary_by_window_df,
            "loan_brier_summary_by_window_df": loan_brier_summary_by_window_df,
            "mature_compare_df": mature_compare_df,
            "mature_loan_brier_df": mature_loan_brier_df,
            "mature_path_summary_df": mature_path_summary_df,
            "mature_loan_brier_summary_df": mature_loan_brier_summary_df,
        }
    finally:
        restore_project_settings(snapshot)


def blend_k_curves(
    primary_k_by_mob: Dict,
    secondary_k_by_mob: Dict,
    primary_weight: float = 0.5,
) -> Dict:
    primary_weight = float(primary_weight)
    if primary_weight < 0 or primary_weight > 1:
        raise ValueError("primary_weight must be between 0 and 1.")

    all_mobs = sorted({int(mob) for mob in primary_k_by_mob} | {int(mob) for mob in secondary_k_by_mob})
    blended = {}
    for mob in all_mobs:
        primary_value = primary_k_by_mob.get(mob)
        secondary_value = secondary_k_by_mob.get(mob)
        if primary_value is None:
            value = secondary_value
        elif secondary_value is None:
            value = primary_value
        else:
            value = primary_weight * float(primary_value) + (1.0 - primary_weight) * float(secondary_value)
        blended[mob] = float(np.clip(value, 0.0, 1.0))
    return blended


def _variant_name_for_blend(primary_weight: float) -> str:
    own_pct = int(round(float(primary_weight) * 100))
    shared_pct = int(round((1.0 - float(primary_weight)) * 100))
    return f"DEL90_BLEND_{own_pct}OWN_{shared_pct}DEL30"


def _summarize_variant_path(compare_df: pd.DataFrame) -> pd.DataFrame:
    if compare_df.empty:
        return pd.DataFrame()

    rows = []
    for variant, subset in compare_df.groupby("VARIANT"):
        row = summarize_path_metrics(subset)
        row["VARIANT"] = variant
        rows.append(row)
    return pd.DataFrame(rows)


def _summarize_variant_loans(loan_brier_df: pd.DataFrame) -> pd.DataFrame:
    if loan_brier_df.empty:
        return pd.DataFrame()

    rows = []
    for variant, subset in loan_brier_df.groupby("VARIANT"):
        row = summarize_loan_brier(subset)
        row["VARIANT"] = variant
        rows.append(row)
    return pd.DataFrame(rows)


def run_del90_k_variant_comparison(
    df_raw: pd.DataFrame,
    *,
    target_mob: int = 12,
    holdout_months: int = 6,
    min_train_vintages: int = 12,
    max_windows: Optional[int] = 2,
    anchor_mob: int | str = 0,
    blend_weights: Iterable[float] = (0.5,),
    product_filter: Optional[Iterable[str]] = None,
    risk_filter: Optional[Iterable[str]] = None,
    fit_params: Optional[Dict] = None,
    settings_overrides: Optional[Dict] = None,
) -> Dict:
    """Compare DEL90 forecasts under own, shared DEL30, and blended K curves.

    The comparison uses mature holdout windows and summarizes errors at the
    requested target MOB, so variants are measured on the business horizon
    rather than on the full path.
    """
    fit_params = deepcopy(fit_params or {})
    target_mob = int(target_mob)
    blend_weights = [float(weight) for weight in blend_weights]

    snapshot = snapshot_project_settings()
    try:
        apply_project_settings(settings_overrides)
        df_model = prepare_backtest_frame(
            df_raw,
            product_filter=product_filter,
            risk_filter=risk_filter,
        )

        windows_catalog_df = find_mature_holdout_windows(
            df_model,
            target_mob=target_mob,
            holdout_months=holdout_months,
            min_train_vintages=min_train_vintages,
            max_windows=max_windows,
        )
        if windows_catalog_df.empty:
            return {
                "df_model": df_model,
                "windows_catalog_df": windows_catalog_df,
                "window_results": [],
                "variant_compare_df": pd.DataFrame(),
                "variant_loan_brier_df": pd.DataFrame(),
                "variant_path_summary_by_window_df": pd.DataFrame(),
                "variant_loan_summary_by_window_df": pd.DataFrame(),
                "variant_path_summary_df": pd.DataFrame(),
                "variant_loan_summary_df": pd.DataFrame(),
                "variant_k_curve_df": pd.DataFrame(),
            }

        compare_frames = []
        loan_brier_frames = []
        path_summary_rows = []
        loan_summary_rows = []
        k_curve_frames = []
        window_results = []

        for _, window in windows_catalog_df.iterrows():
            df_train, df_holdout, split_info = split_fixed_holdout_window(
                df_model,
                holdout_start_vintage=window["START_VINTAGE"],
                holdout_months=holdout_months,
                min_train_vintages=min_train_vintages,
            )

            matrices_by_mob, parent_fallback = compute_transition_by_mob(df_train)
            actual_results_train = get_actual_all_vintages_amount(df_train)
            actual_results_holdout = get_actual_all_vintages_amount(df_holdout)
            actual_results_holdout_anchor = trim_actual_results_for_anchor(
                actual_results_holdout,
                anchor_mob=anchor_mob,
            )
            disb_total_train = build_disb_total_by_vintage(df_train)
            disb_total_holdout = build_disb_total_by_vintage(df_holdout)

            fit_del30 = fit_metric_curve(
                actual_results_train=actual_results_train,
                matrices_by_mob=matrices_by_mob,
                parent_fallback=parent_fallback,
                disb_total_by_vintage_train=disb_total_train,
                metric_states=BUCKETS_30P,
                fit_params=fit_params,
                post_mature_k=project_config.K_POST_MATURE,
                post_mature_start_mob=target_mob,
            )
            fit_del90 = fit_metric_curve(
                actual_results_train=actual_results_train,
                matrices_by_mob=matrices_by_mob,
                parent_fallback=parent_fallback,
                disb_total_by_vintage_train=disb_total_train,
                metric_states=BUCKETS_90P,
                fit_params=fit_params,
                post_mature_k=project_config.K_POST_MATURE_DEL90,
                post_mature_start_mob=target_mob,
            )

            variants = {
                "DEL90_OWN_K": fit_del90["k_final_by_mob"],
                "DEL90_SHARED_DEL30_K": fit_del30["k_final_by_mob"],
            }
            for weight in blend_weights:
                variants[_variant_name_for_blend(weight)] = blend_k_curves(
                    fit_del90["k_final_by_mob"],
                    fit_del30["k_final_by_mob"],
                    primary_weight=weight,
                )

            window_result = {
                "TARGET_MOB": target_mob,
                "WINDOW_ID": window["WINDOW_ID"],
                "START_VINTAGE": pd.Timestamp(window["START_VINTAGE"]),
                "END_VINTAGE": pd.Timestamp(window["END_VINTAGE"]),
                "split_info": split_info,
                "fit_del30": fit_del30,
                "fit_del90": fit_del90,
            }
            window_results.append(window_result)

            for variant, k_by_mob in variants.items():
                forecast_results_holdout = forecast_all_vintages_partial_step(
                    actual_results=actual_results_holdout_anchor,
                    matrices_by_mob=matrices_by_mob,
                    parent_fallback=parent_fallback,
                    max_mob=target_mob,
                    k_by_mob=k_by_mob,
                    states=BUCKETS_CANON,
                )
                compare_df = build_metric_compare_frame(
                    actual_results_holdout=actual_results_holdout,
                    forecast_results_holdout=forecast_results_holdout,
                    disb_total_by_vintage_holdout=disb_total_holdout,
                    metric_name="DEL90",
                    metric_states=BUCKETS_90P,
                )
                if compare_df.empty:
                    continue

                compare_df["VARIANT"] = variant
                compare_df["WINDOW_ID"] = window["WINDOW_ID"]
                compare_df["TARGET_MOB_WINDOW"] = target_mob
                compare_df["WINDOW_START_VINTAGE"] = pd.Timestamp(window["START_VINTAGE"])
                compare_df["WINDOW_END_VINTAGE"] = pd.Timestamp(window["END_VINTAGE"])
                compare_frames.append(compare_df)

                compare_target_df = compare_df[compare_df["MOB"] == target_mob].copy()
                path_summary = summarize_path_metrics(compare_target_df)
                path_summary.update(
                    {
                        "VARIANT": variant,
                        "METRIC": "DEL90",
                        "TARGET_MOB": target_mob,
                        "WINDOW_ID": window["WINDOW_ID"],
                        "WINDOW_START_VINTAGE": pd.Timestamp(window["START_VINTAGE"]),
                        "WINDOW_END_VINTAGE": pd.Timestamp(window["END_VINTAGE"]),
                        "N_TRAIN_VINTAGES": split_info["n_train_vintages"],
                        "N_HOLDOUT_VINTAGES": split_info["n_holdout_vintages"],
                    }
                )
                path_summary_rows.append(path_summary)

                loan_brier_df = build_loan_level_brier_frame(
                    df_holdout=df_holdout,
                    compare_df=compare_df,
                    metric_states=BUCKETS_90P,
                    target_mob=target_mob,
                )
                if not loan_brier_df.empty:
                    loan_brier_df["METRIC"] = "DEL90"
                    loan_brier_df["VARIANT"] = variant
                    loan_brier_df["WINDOW_ID"] = window["WINDOW_ID"]
                    loan_brier_df["TARGET_MOB_WINDOW"] = target_mob
                    loan_brier_df["WINDOW_START_VINTAGE"] = pd.Timestamp(window["START_VINTAGE"])
                    loan_brier_df["WINDOW_END_VINTAGE"] = pd.Timestamp(window["END_VINTAGE"])
                    loan_brier_frames.append(loan_brier_df)

                    loan_summary = summarize_loan_brier(loan_brier_df)
                    loan_summary.update(
                        {
                            "VARIANT": variant,
                            "METRIC": "DEL90",
                            "TARGET_MOB": target_mob,
                            "WINDOW_ID": window["WINDOW_ID"],
                            "WINDOW_START_VINTAGE": pd.Timestamp(window["START_VINTAGE"]),
                            "WINDOW_END_VINTAGE": pd.Timestamp(window["END_VINTAGE"]),
                            "N_TRAIN_VINTAGES": split_info["n_train_vintages"],
                            "N_HOLDOUT_VINTAGES": split_info["n_holdout_vintages"],
                        }
                    )
                    loan_summary_rows.append(loan_summary)

                k_curve_df = pd.DataFrame(
                    {
                        "MOB": sorted(k_by_mob.keys()),
                        "K_FINAL": [k_by_mob[mob] for mob in sorted(k_by_mob.keys())],
                    }
                )
                k_curve_df["VARIANT"] = variant
                k_curve_df["WINDOW_ID"] = window["WINDOW_ID"]
                k_curve_df["TARGET_MOB"] = target_mob
                k_curve_df["WINDOW_START_VINTAGE"] = pd.Timestamp(window["START_VINTAGE"])
                k_curve_df["WINDOW_END_VINTAGE"] = pd.Timestamp(window["END_VINTAGE"])
                k_curve_frames.append(k_curve_df)

        variant_compare_df = pd.concat(compare_frames, ignore_index=True) if compare_frames else pd.DataFrame()
        variant_loan_brier_df = pd.concat(loan_brier_frames, ignore_index=True) if loan_brier_frames else pd.DataFrame()
        variant_path_summary_by_window_df = pd.DataFrame(path_summary_rows)
        variant_loan_summary_by_window_df = pd.DataFrame(loan_summary_rows)
        variant_k_curve_df = pd.concat(k_curve_frames, ignore_index=True) if k_curve_frames else pd.DataFrame()

        compare_target_all_df = (
            variant_compare_df[variant_compare_df["MOB"] == target_mob].copy()
            if not variant_compare_df.empty
            else pd.DataFrame()
        )
        variant_path_summary_df = _summarize_variant_path(compare_target_all_df)
        if not variant_path_summary_df.empty:
            variant_path_summary_df["METRIC"] = "DEL90"
            variant_path_summary_df["TARGET_MOB"] = target_mob
            variant_path_summary_df["N_WINDOWS"] = int(windows_catalog_df.shape[0])

        variant_loan_summary_df = _summarize_variant_loans(variant_loan_brier_df)
        if not variant_loan_summary_df.empty:
            variant_loan_summary_df["METRIC"] = "DEL90"
            variant_loan_summary_df["TARGET_MOB"] = target_mob
            variant_loan_summary_df["N_WINDOWS"] = int(windows_catalog_df.shape[0])

        return {
            "df_model": df_model,
            "windows_catalog_df": windows_catalog_df,
            "window_results": window_results,
            "variant_compare_df": variant_compare_df,
            "variant_loan_brier_df": variant_loan_brier_df,
            "variant_path_summary_by_window_df": variant_path_summary_by_window_df,
            "variant_loan_summary_by_window_df": variant_loan_summary_by_window_df,
            "variant_path_summary_df": variant_path_summary_df,
            "variant_loan_summary_df": variant_loan_summary_df,
            "variant_k_curve_df": variant_k_curve_df,
        }
    finally:
        restore_project_settings(snapshot)


def _asof_cutoff_for_vintage(
    df_model: pd.DataFrame,
    vintage,
    target_mob: int,
    lookback_months: int,
) -> Tuple[pd.Timestamp, pd.Timestamp]:
    vintage = pd.Timestamp(vintage)
    target_rows = df_model[
        (df_model["VINTAGE_DATE"] == vintage)
        & (pd.to_numeric(df_model[CFG["mob"]], errors="coerce") == int(target_mob))
    ]
    if target_rows.empty:
        raise ValueError(f"No MOB{target_mob} rows for vintage {vintage:%Y-%m-%d}.")
    target_cutoff = pd.Timestamp(target_rows[CFG["cutoff"]].max())
    asof_cutoff = target_cutoff - pd.DateOffset(months=int(lookback_months))
    return target_cutoff, asof_cutoff


def _run_del90_asof_forecast_for_vintage(
    df_model: pd.DataFrame,
    *,
    vintage,
    target_mob: int,
    lookback_months: int,
    fit_params: Dict,
    k_source: str = "del30",
) -> Dict:
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

    k_source = str(k_source).lower()
    if k_source in {"del30", "shared_del30", "del90_shared_del30_k"}:
        fit_states = BUCKETS_30P
        post_mature_k = project_config.K_POST_MATURE
    elif k_source in {"del90", "own_del90", "del90_own_k"}:
        fit_states = BUCKETS_90P
        post_mature_k = project_config.K_POST_MATURE_DEL90
    else:
        raise ValueError(f"Unsupported k_source={k_source!r}. Use 'del30' or 'del90'.")

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
        metric_name="DEL90",
        metric_states=BUCKETS_90P,
    )
    compare_df = compare_df[compare_df["MOB"] == target_mob].copy()
    if not compare_df.empty:
        compare_df["TARGET_VINTAGE"] = target_vintage
        compare_df["TARGET_MOB"] = target_mob
        compare_df["TARGET_CUTOFF"] = target_cutoff
        compare_df["AS_OF_CUTOFF"] = asof_cutoff
        compare_df["ANCHOR_MOB"] = anchor_max_mob
        compare_df["K_SOURCE"] = k_source

    return {
        "target_vintage": target_vintage,
        "target_cutoff": target_cutoff,
        "asof_cutoff": asof_cutoff,
        "anchor_mob": anchor_max_mob,
        "df_asof": df_asof,
        "df_target_actual": df_target_actual,
        "df_target_anchor": df_target_anchor,
        "compare_df": compare_df,
        "fit_output": fit_output,
    }


def summarize_weighted_compare(
    compare_df: pd.DataFrame,
    pred_col: str = "PRED_PCT",
) -> Dict:
    if compare_df.empty:
        return {
            "N_OBS": 0,
            "DISB_TOTAL": np.nan,
            "ACTUAL_PCT": np.nan,
            "PRED_PCT": np.nan,
            "GAP": np.nan,
            "W_MAE": np.nan,
            "W_RMSE": np.nan,
        }

    w = compare_df["DISB_TOTAL"].fillna(0.0).astype(float)
    actual = compare_df["ACTUAL_PCT"].astype(float)
    pred = compare_df[pred_col].astype(float)
    err = pred - actual
    has_weight = bool((w > 0).any())
    return {
        "N_OBS": int(len(compare_df)),
        "DISB_TOTAL": float(w.sum()),
        "ACTUAL_PCT": float(np.average(actual, weights=w)) if has_weight else float(actual.mean()),
        "PRED_PCT": float(np.average(pred, weights=w)) if has_weight else float(pred.mean()),
        "GAP": float(np.average(err, weights=w)) if has_weight else float(err.mean()),
        "W_MAE": float(np.average(err.abs(), weights=w)) if has_weight else float(err.abs().mean()),
        "W_RMSE": float(np.sqrt(np.average(err ** 2, weights=w))) if has_weight else float(np.sqrt((err ** 2).mean())),
    }


def build_del90_asof_calibration_table(
    calibration_compare_df: pd.DataFrame,
    *,
    group_cols: Iterable[str] = ("PRODUCT_TYPE", "RISK_SCORE"),
    shrink: float = 0.25,
    residual_cap: Optional[float] = 0.10,
    min_calibration_disb: float = 0.0,
) -> pd.DataFrame:
    group_cols = list(group_cols)
    if calibration_compare_df.empty:
        return pd.DataFrame(columns=group_cols + ["RAW_ADJ", "ADJ", "CALIBRATION_DISB"])
    missing_cols = [col for col in group_cols if col not in calibration_compare_df.columns]
    if missing_cols:
        raise KeyError(
            "Calibration group columns are not available in the canonical cohort output: "
            f"{missing_cols}. Available columns: {list(calibration_compare_df.columns)}"
        )

    work = calibration_compare_df.copy()
    work["RESIDUAL"] = work["ACTUAL_PCT"].astype(float) - work["PRED_PCT"].astype(float)
    rows = []
    grouped = (
        work.groupby(group_cols, dropna=False)
        if group_cols
        else [((), work)]
    )
    for keys, subset in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        w = subset["DISB_TOTAL"].fillna(0.0).astype(float)
        if not bool((w > 0).any()):
            raw_adj = float(subset["RESIDUAL"].mean())
            disb = 0.0
        else:
            raw_adj = float(np.average(subset["RESIDUAL"].astype(float), weights=w))
            disb = float(w.sum())
        adj = raw_adj * float(shrink) if disb >= float(min_calibration_disb) else 0.0
        if residual_cap is not None:
            cap = abs(float(residual_cap))
            adj = float(np.clip(adj, -cap, cap))
        row = {col: val for col, val in zip(group_cols, keys)}
        row.update({"RAW_ADJ": raw_adj, "ADJ": adj, "CALIBRATION_DISB": disb})
        rows.append(row)
    return pd.DataFrame(rows)


def apply_del90_pct_calibration(
    compare_df: pd.DataFrame,
    calibration_table: pd.DataFrame,
    *,
    group_cols: Iterable[str] = ("PRODUCT_TYPE", "RISK_SCORE"),
    pred_col: str = "PRED_PCT",
    output_col: str = "PRED_PCT_CAL",
) -> pd.DataFrame:
    group_cols = list(group_cols)
    out = compare_df.copy()
    missing_cols = [col for col in group_cols if col not in out.columns]
    if missing_cols:
        raise KeyError(
            "Calibration group columns are not available in the target cohort output: "
            f"{missing_cols}. Available columns: {list(out.columns)}"
        )
    if calibration_table.empty:
        out[output_col] = out[pred_col].astype(float)
        out["CAL_ADJ"] = 0.0
        return out

    if group_cols:
        out = out.merge(
            calibration_table[group_cols + ["ADJ"]],
            on=group_cols,
            how="left",
            validate="many_to_one",
        )
    else:
        if len(calibration_table) != 1:
            raise ValueError(
                "Portfolio calibration requires exactly one global adjustment row; "
                f"got {len(calibration_table)}."
            )
        out["ADJ"] = float(calibration_table["ADJ"].iloc[0])
    out["CAL_ADJ"] = out["ADJ"].fillna(0.0).astype(float)
    out[output_col] = (out[pred_col].astype(float) + out["CAL_ADJ"]).clip(0.0, 1.0)
    out = out.drop(columns=["ADJ"])
    return out


def run_del90_asof_calibrated_backtest(
    df_raw: pd.DataFrame,
    *,
    target_vintage=None,
    target_mob: int = 12,
    lookback_months: int = 8,
    calibration_n_vintages: int = 1,
    calibration_group_cols: Iterable[str] = ("PRODUCT_TYPE", "RISK_SCORE"),
    calibration_shrink: float = 0.25,
    residual_cap: Optional[float] = 0.10,
    min_calibration_disb: float = 0.0,
    k_source: str = "del30",
    product_filter: Optional[Iterable[str]] = None,
    risk_filter: Optional[Iterable[str]] = None,
    fit_params: Optional[Dict] = None,
    settings_overrides: Optional[Dict] = None,
) -> Dict:
    fit_params = deepcopy(fit_params or {})
    target_mob = int(target_mob)

    snapshot = snapshot_project_settings()
    try:
        apply_project_settings(settings_overrides)
        df_model = prepare_backtest_frame(
            df_raw,
            product_filter=product_filter,
            risk_filter=risk_filter,
        )
        df_model[CFG["cutoff"]] = parse_date_column(df_model[CFG["cutoff"]])
        df_model[CFG["mob"]] = pd.to_numeric(df_model[CFG["mob"]], errors="coerce")

        target_candidates = (
            df_model[df_model[CFG["mob"]] == target_mob]
            .groupby("VINTAGE_DATE")[CFG["cutoff"]]
            .max()
            .sort_index()
        )
        if target_candidates.empty:
            raise ValueError(f"No vintages with observed MOB{target_mob}.")

        if target_vintage is None:
            target_vintage = pd.Timestamp(target_candidates.index.max())
        else:
            target_vintage = pd.Timestamp(target_vintage)
        if target_vintage not in target_candidates.index:
            raise ValueError(f"target_vintage {target_vintage:%Y-%m-%d} has no MOB{target_mob}.")

        target_cutoff, target_asof_cutoff = _asof_cutoff_for_vintage(
            df_model,
            vintage=target_vintage,
            target_mob=target_mob,
            lookback_months=lookback_months,
        )
        calibration_candidates = target_candidates[
            (target_candidates.index < target_vintage)
            & (target_candidates <= target_asof_cutoff)
        ].tail(int(calibration_n_vintages))

        target_result = _run_del90_asof_forecast_for_vintage(
            df_model,
            vintage=target_vintage,
            target_mob=target_mob,
            lookback_months=lookback_months,
            fit_params=fit_params,
            k_source=k_source,
        )

        calibration_results = []
        calibration_compare_frames = []
        for cal_vintage in calibration_candidates.index:
            cal_result = _run_del90_asof_forecast_for_vintage(
                df_model,
                vintage=cal_vintage,
                target_mob=target_mob,
                lookback_months=lookback_months,
                fit_params=fit_params,
                k_source=k_source,
            )
            cal_compare = cal_result["compare_df"].copy()
            if not cal_compare.empty:
                calibration_compare_frames.append(cal_compare)
            calibration_results.append(cal_result)

        calibration_compare_df = (
            pd.concat(calibration_compare_frames, ignore_index=True)
            if calibration_compare_frames
            else pd.DataFrame()
        )
        calibration_table = build_del90_asof_calibration_table(
            calibration_compare_df,
            group_cols=calibration_group_cols,
            shrink=calibration_shrink,
            residual_cap=residual_cap,
            min_calibration_disb=min_calibration_disb,
        )
        target_compare_df = target_result["compare_df"].copy()
        calibrated_compare_df = apply_del90_pct_calibration(
            target_compare_df,
            calibration_table,
            group_cols=calibration_group_cols,
            pred_col="PRED_PCT",
            output_col="PRED_PCT_CAL",
        )

        base_summary = summarize_weighted_compare(target_compare_df, pred_col="PRED_PCT")
        calibrated_summary = summarize_weighted_compare(calibrated_compare_df, pred_col="PRED_PCT_CAL")
        calibration_summary = summarize_weighted_compare(calibration_compare_df, pred_col="PRED_PCT")

        summary_df = pd.DataFrame(
            [
                {"VIEW": "BASE_TARGET", **base_summary},
                {"VIEW": "CALIBRATED_TARGET", **calibrated_summary},
                {"VIEW": "CALIBRATION_SOURCE", **calibration_summary},
            ]
        )
        metadata = {
            "TARGET_VINTAGE": target_vintage,
            "TARGET_MOB": target_mob,
            "LOOKBACK_MONTHS": int(lookback_months),
            "TARGET_CUTOFF": target_cutoff,
            "TARGET_AS_OF_CUTOFF": target_asof_cutoff,
            "TARGET_ANCHOR_MOB": target_result["anchor_mob"],
            "K_SOURCE": k_source,
            "CALIBRATION_GROUP_COLS": list(calibration_group_cols),
            "CALIBRATION_SHRINK": float(calibration_shrink),
            "RESIDUAL_CAP": residual_cap,
            "MIN_CALIBRATION_DISB": float(min_calibration_disb),
            "CALIBRATION_VINTAGES": [pd.Timestamp(v) for v in calibration_candidates.index],
        }

        return {
            "df_model": df_model,
            "metadata": metadata,
            "target_result": target_result,
            "calibration_results": calibration_results,
            "calibration_compare_df": calibration_compare_df,
            "calibration_table_df": calibration_table,
            "target_compare_df": target_compare_df,
            "calibrated_compare_df": calibrated_compare_df,
            "summary_df": summary_df,
        }
    finally:
        restore_project_settings(snapshot)


def run_del90_portfolio_asof_grid(
    df_raw: pd.DataFrame,
    *,
    target_mob: int = 12,
    anchor_mobs: Iterable[int] = (2, 4, 6, 8),
    target_vintages: Optional[Iterable] = None,
    target_n_vintages: int = 4,
    calibration_n_vintages: int = 3,
    calibration_shrink: float = 1.0,
    residual_cap: Optional[float] = 0.10,
    k_source: str = "del30",
    product_filter: Optional[Iterable[str]] = None,
    risk_filter: Optional[Iterable[str]] = None,
    fit_params: Optional[Dict] = None,
    settings_overrides: Optional[Dict] = None,
) -> Dict:
    """Rolling true-as-of DEL90 backtest with one portfolio-level adjustment."""
    fit_params = deepcopy(fit_params or {})
    target_mob = int(target_mob)
    requested_anchor_mobs = sorted({int(mob) for mob in anchor_mobs})
    invalid_anchor_mobs = [
        mob for mob in requested_anchor_mobs if mob < 0 or mob >= target_mob
    ]
    if invalid_anchor_mobs:
        raise ValueError(
            f"anchor_mobs must be in [0, {target_mob - 1}]; got {invalid_anchor_mobs}."
        )

    snapshot = snapshot_project_settings()
    try:
        apply_project_settings(settings_overrides)
        df_model = prepare_backtest_frame(
            df_raw,
            product_filter=product_filter,
            risk_filter=risk_filter,
        )
        df_model[CFG["cutoff"]] = parse_date_column(df_model[CFG["cutoff"]])
        df_model[CFG["mob"]] = pd.to_numeric(df_model[CFG["mob"]], errors="coerce")

        target_candidates = (
            df_model[df_model[CFG["mob"]] == target_mob]
            .groupby("VINTAGE_DATE")[CFG["cutoff"]]
            .max()
            .sort_index()
        )
        if target_candidates.empty:
            raise ValueError(f"No vintages with observed MOB{target_mob}.")

        if target_vintages is None:
            selected_target_vintages = [
                pd.Timestamp(v)
                for v in target_candidates.tail(int(target_n_vintages)).index
            ]
        else:
            selected_target_vintages = [pd.Timestamp(v) for v in target_vintages]
            missing_vintages = [
                v for v in selected_target_vintages if v not in target_candidates.index
            ]
            if missing_vintages:
                raise ValueError(
                    f"Target vintages without observed MOB{target_mob}: {missing_vintages}"
                )

        compact_cache = {}

        def get_compact_forecast(vintage, lookback_months):
            cache_key = (pd.Timestamp(vintage), int(lookback_months))
            if cache_key not in compact_cache:
                result = _run_del90_asof_forecast_for_vintage(
                    df_model,
                    vintage=cache_key[0],
                    target_mob=target_mob,
                    lookback_months=cache_key[1],
                    fit_params=fit_params,
                    k_source=k_source,
                )
                compact_cache[cache_key] = {
                    "target_vintage": result["target_vintage"],
                    "target_cutoff": result["target_cutoff"],
                    "asof_cutoff": result["asof_cutoff"],
                    "anchor_mob": result["anchor_mob"],
                    "compare_df": result["compare_df"].copy(),
                }
            return compact_cache[cache_key]

        summary_rows = []
        detail_frames = []
        calibration_frames = []
        for requested_anchor_mob in requested_anchor_mobs:
            lookback_months = target_mob - requested_anchor_mob
            for target_vintage in selected_target_vintages:
                target_result = get_compact_forecast(
                    target_vintage,
                    lookback_months,
                )
                target_asof_cutoff = target_result["asof_cutoff"]
                calibration_candidates = target_candidates[
                    (target_candidates.index < target_vintage)
                    & (target_candidates <= target_asof_cutoff)
                ].tail(int(calibration_n_vintages))

                calibration_compare_frames = []
                for calibration_vintage in calibration_candidates.index:
                    calibration_result = get_compact_forecast(
                        calibration_vintage,
                        lookback_months,
                    )
                    calibration_compare = calibration_result["compare_df"].copy()
                    calibration_compare["EVAL_TARGET_VINTAGE"] = target_vintage
                    calibration_compare["REQUESTED_ANCHOR_MOB"] = requested_anchor_mob
                    calibration_compare_frames.append(calibration_compare)

                calibration_compare_df = (
                    pd.concat(calibration_compare_frames, ignore_index=True)
                    if calibration_compare_frames
                    else pd.DataFrame()
                )
                calibration_table = build_del90_asof_calibration_table(
                    calibration_compare_df,
                    group_cols=[],
                    shrink=calibration_shrink,
                    residual_cap=residual_cap,
                )
                target_compare = target_result["compare_df"].copy()
                calibrated_compare = apply_del90_pct_calibration(
                    target_compare,
                    calibration_table,
                    group_cols=[],
                    pred_col="PRED_PCT",
                    output_col="PRED_PCT_CAL",
                )
                calibrated_compare["REQUESTED_ANCHOR_MOB"] = requested_anchor_mob
                calibrated_compare["LOOKBACK_MONTHS"] = lookback_months
                calibrated_compare["CALIBRATION_N_VINTAGES"] = len(
                    calibration_candidates
                )
                calibrated_compare["CALIBRATION_VINTAGES"] = ",".join(
                    pd.Timestamp(v).strftime("%Y-%m-%d")
                    for v in calibration_candidates.index
                )
                detail_frames.append(calibrated_compare)
                if not calibration_compare_df.empty:
                    calibration_frames.append(calibration_compare_df)

                base_summary = summarize_weighted_compare(
                    calibrated_compare,
                    pred_col="PRED_PCT",
                )
                calibrated_summary = summarize_weighted_compare(
                    calibrated_compare,
                    pred_col="PRED_PCT_CAL",
                )
                summary_rows.append(
                    {
                        "TARGET_VINTAGE": target_vintage,
                        "TARGET_MOB": target_mob,
                        "REQUESTED_ANCHOR_MOB": requested_anchor_mob,
                        "ACTUAL_ANCHOR_MOB": target_result["anchor_mob"],
                        "LOOKBACK_MONTHS": lookback_months,
                        "AS_OF_CUTOFF": target_asof_cutoff,
                        "CALIBRATION_N_VINTAGES": len(calibration_candidates),
                        "CALIBRATION_VINTAGES": ",".join(
                            pd.Timestamp(v).strftime("%Y-%m-%d")
                            for v in calibration_candidates.index
                        ),
                        "CAL_ADJ": (
                            float(calibration_table["ADJ"].iloc[0])
                            if not calibration_table.empty
                            else 0.0
                        ),
                        "ACTUAL_PCT": base_summary["ACTUAL_PCT"],
                        "BASE_PRED_PCT": base_summary["PRED_PCT"],
                        "BASE_GAP": base_summary["GAP"],
                        "BASE_W_MAE": base_summary["W_MAE"],
                        "BASE_W_RMSE": base_summary["W_RMSE"],
                        "CAL_PRED_PCT": calibrated_summary["PRED_PCT"],
                        "CAL_GAP": calibrated_summary["GAP"],
                        "CAL_W_MAE": calibrated_summary["W_MAE"],
                        "CAL_W_RMSE": calibrated_summary["W_RMSE"],
                        "DISB_TOTAL": base_summary["DISB_TOTAL"],
                    }
                )

        summary_df = pd.DataFrame(summary_rows)
        detail_df = (
            pd.concat(detail_frames, ignore_index=True)
            if detail_frames
            else pd.DataFrame()
        )
        calibration_detail_df = (
            pd.concat(calibration_frames, ignore_index=True)
            if calibration_frames
            else pd.DataFrame()
        )

        anchor_summary_rows = []
        for anchor_mob, subset in summary_df.groupby("REQUESTED_ANCHOR_MOB"):
            weights = subset["DISB_TOTAL"].fillna(0.0).astype(float)
            has_weight = bool((weights > 0).any())

            def weighted_average(values):
                values = pd.Series(values, index=subset.index).astype(float)
                return (
                    float(np.average(values, weights=weights))
                    if has_weight
                    else float(values.mean())
                )

            anchor_summary_rows.append(
                {
                    "REQUESTED_ANCHOR_MOB": int(anchor_mob),
                    "N_TARGET_VINTAGES": int(len(subset)),
                    "ACTUAL_PCT": weighted_average(subset["ACTUAL_PCT"]),
                    "BASE_PRED_PCT": weighted_average(subset["BASE_PRED_PCT"]),
                    "BASE_BIAS": weighted_average(subset["BASE_GAP"]),
                    "BASE_MAE_BY_VINTAGE": weighted_average(
                        subset["BASE_GAP"].abs()
                    ),
                    "CAL_PRED_PCT": weighted_average(subset["CAL_PRED_PCT"]),
                    "CAL_BIAS": weighted_average(subset["CAL_GAP"]),
                    "CAL_MAE_BY_VINTAGE": weighted_average(
                        subset["CAL_GAP"].abs()
                    ),
                    "MEAN_CAL_ADJ": weighted_average(subset["CAL_ADJ"]),
                }
            )

        return {
            "summary_df": summary_df,
            "anchor_summary_df": pd.DataFrame(anchor_summary_rows),
            "detail_df": detail_df,
            "calibration_detail_df": calibration_detail_df,
            "selected_target_vintages": selected_target_vintages,
            "forecast_cache_size": len(compact_cache),
        }
    finally:
        restore_project_settings(snapshot)
