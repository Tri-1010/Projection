from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.config import CFG
from src.rollrate.group_master_cache import (
    _apply_del90_blend,
    _apply_del90_portfolio_calibration,
    _attach_del90_calibration_drift,
    _build_del90_blend_curve,
    _build_metric_lifecycle,
    _merge_del90_metrics,
    get_default_settings,
    group_stage_dir,
    load_frame,
    recalibrate_group_pipeline_from_stage,
    run_group_pipeline,
)
from src.rollrate.lifecycle import get_actual_all_vintages_amount
from src.rollrate.transition import compute_transition_by_mob
from src.rollrate.allocation_v2_ultra_fast import recalibrate_existing_loan_forecast_del90
import src.rollrate.group_master_cache as group_master_cache


def build_synthetic_raw() -> pd.DataFrame:
    records = [
        ("L1", "PL", "A", "2024-01-01", 0, "2024-01-31", "DPD0", 100.0, 100.0),
        ("L1", "PL", "A", "2024-01-01", 1, "2024-02-29", "DPD30+", 100.0, 100.0),
        ("L1", "PL", "A", "2024-01-01", 2, "2024-03-31", "DPD90+", 100.0, 100.0),
        ("L2", "PL", "A", "2024-01-01", 0, "2024-01-31", "DPD0", 100.0, 100.0),
        ("L2", "PL", "A", "2024-01-01", 1, "2024-02-29", "DPD30+", 100.0, 100.0),
        ("L2", "PL", "A", "2024-01-01", 2, "2024-03-31", "DPD60+", 100.0, 100.0),
        ("L3", "PL", "A", "2024-02-01", 0, "2024-02-29", "DPD0", 100.0, 100.0),
        ("L3", "PL", "A", "2024-02-01", 1, "2024-03-31", "DPD1+", 100.0, 100.0),
        ("L3", "PL", "A", "2024-02-01", 2, "2024-04-30", "DPD30+", 100.0, 100.0),
        ("L4", "PL", "A", "2024-02-01", 0, "2024-02-29", "DPD0", 100.0, 100.0),
        ("L4", "PL", "A", "2024-02-01", 1, "2024-03-31", "DPD0", 100.0, 100.0),
        ("L4", "PL", "A", "2024-02-01", 2, "2024-04-30", "DPD0", 100.0, 100.0),
    ]
    df = pd.DataFrame(
        records,
        columns=[
            CFG["loan"],
            "PRODUCT_TYPE",
            "RISK_SCORE",
            CFG["orig_date"],
            CFG["mob"],
            CFG["cutoff"],
            CFG["state"],
            CFG["ead"],
            CFG["disb"],
        ],
    )
    df[CFG["orig_date"]] = pd.to_datetime(df[CFG["orig_date"]])
    df[CFG["cutoff"]] = pd.to_datetime(df[CFG["cutoff"]])
    return df


def build_disb_total_by_vintage(df_raw: pd.DataFrame) -> dict:
    loan_disb = df_raw.groupby(
        ["PRODUCT_TYPE", "RISK_SCORE", CFG["orig_date"], CFG["loan"]]
    )[CFG["disb"]].first()
    return loan_disb.groupby(level=[0, 1, 2]).sum().to_dict()


def build_blend_curve_raw() -> pd.DataFrame:
    records = []
    for idx, vintage in enumerate(
        pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]),
        start=1,
    ):
        records.append(
            (
                f"BLEND_{idx}",
                "PL",
                "A",
                vintage,
                12,
                vintage + pd.offsets.MonthEnd(12),
                "DPD90+",
                100.0,
                100.0,
            )
        )
    df = pd.DataFrame(
        records,
        columns=[
            CFG["loan"],
            "PRODUCT_TYPE",
            "RISK_SCORE",
            CFG["orig_date"],
            CFG["mob"],
            CFG["cutoff"],
            CFG["state"],
            CFG["ead"],
            CFG["disb"],
        ],
    )
    df[CFG["orig_date"]] = pd.to_datetime(df[CFG["orig_date"]])
    df[CFG["cutoff"]] = pd.to_datetime(df[CFG["cutoff"]])
    return df


def test_merge_helper():
    vintage = pd.Timestamp("2024-01-01")
    df_del30 = pd.DataFrame(
        [
            {
                "PRODUCT_TYPE": "PL",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                "MOB": 12,
                "IS_FORECAST": 1,
                "DPD0": 80.0,
                "DPD30+": 20.0,
                "DEL30_AMT": 20.0,
                "DEL30_PCT": 0.20,
                "DEL60_AMT": 0.0,
                "DEL60_PCT": 0.0,
                "DEL90_AMT": 1.0,
                "DEL90_PCT": 0.01,
            }
        ]
    )
    df_del90 = df_del30.copy()
    df_del90["DEL90_AMT"] = 7.0
    df_del90["DEL90_PCT"] = 0.07

    df_hybrid = _merge_del90_metrics(df_del30, df_del90)

    assert len(df_hybrid) == len(df_del30)
    assert float(df_hybrid.loc[0, "DEL30_PCT"]) == 0.20
    assert float(df_hybrid.loc[0, "DEL60_PCT"]) == 0.0
    assert float(df_hybrid.loc[0, "DEL90_PCT"]) == 0.07
    assert float(df_hybrid.loc[0, "DEL90_AMT"]) == 7.0
    assert int(df_hybrid.loc[0, "IS_FORECAST"]) == 1


def test_del90_flow_differs_from_del30_flow():
    df_raw = build_synthetic_raw()
    matrices_by_mob, parent_fallback = compute_transition_by_mob(df_raw)
    actual_results = get_actual_all_vintages_amount(df_raw)
    disb_total_by_vintage = build_disb_total_by_vintage(df_raw)
    run_cfg = {
        "name": "SYNTH",
        "data_path": "synthetic.parquet",
        "max_mob": 4,
        "target_mobs": [3],
        "k_method": "wls_reg",
        "k_min_obs": 1,
        "fallback_k": 0.0,
        "fallback_weight": 0.0,
        "lambda_k": 1e-4,
        "k_prior": 0.0,
        "gamma": 1.0,
        "alpha_mob_target": 2,
        "k_weight_mode": "equal",
        "monotone": False,
    }

    df_flow_del30 = _build_metric_lifecycle(
        df_raw=df_raw,
        run_cfg=run_cfg,
        actual_results=actual_results,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        disb_total_by_vintage=disb_total_by_vintage,
        metric_name="DEL30",
        metric_states=["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"],
        post_mature_k=0.03,
    )
    df_flow_del90 = _build_metric_lifecycle(
        df_raw=df_raw,
        run_cfg=run_cfg,
        actual_results=actual_results,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        disb_total_by_vintage=disb_total_by_vintage,
        metric_name="DEL90",
        metric_states=["DPD90+", "DPD120+", "DPD180+", "WRITEOFF"],
        post_mature_k=None,
    )

    merged = df_flow_del30.merge(
        df_flow_del90[["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "MOB", "DEL90_PCT"]],
        on=["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "MOB"],
        suffixes=("_DEL30_FLOW", "_DEL90_FLOW"),
        how="inner",
    )
    forecast_rows = merged[merged["IS_FORECAST"] == 1].copy()
    diff = (
        forecast_rows["DEL90_PCT_DEL30_FLOW"] - forecast_rows["DEL90_PCT_DEL90_FLOW"]
    ).abs()
    assert not forecast_rows.empty
    assert (diff > 1e-12).any(), diff.tolist()


def test_portfolio_calibration_changes_forecast_only():
    vintage = pd.Timestamp("2024-01-01")
    lifecycle = pd.DataFrame(
        [
            {
                "PRODUCT_TYPE": "PL",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                "MOB": 2,
                "IS_FORECAST": 0,
                "DISB_TOTAL": 100.0,
                "DEL30_PCT": 0.30,
                "DEL90_PCT": 0.10,
                "DEL90_AMT": 10.0,
            },
            {
                "PRODUCT_TYPE": "PL",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                "MOB": 4,
                "IS_FORECAST": 1,
                "DISB_TOTAL": 100.0,
                "DEL30_PCT": 0.30,
                "DEL90_PCT": 0.10,
                "DEL90_AMT": 10.0,
            },
        ]
    )
    actual_results = {
        ("PL", "A", vintage): {
            0: pd.Series(dtype=float),
            1: pd.Series(dtype=float),
            2: pd.Series(dtype=float),
        }
    }
    curve = pd.DataFrame(
        [
            {
                "TARGET_MOB": 4,
                "ANCHOR_MOB": 2,
                "ADJ": 0.25,
                "N_CALIBRATION_VINTAGES": 3,
            }
        ]
    )

    result = _apply_del90_portfolio_calibration(
        lifecycle,
        actual_results,
        curve,
        enforce_del30_cap=True,
    )

    actual_row = result[result["MOB"] == 2].iloc[0]
    forecast_row = result[result["MOB"] == 4].iloc[0]
    assert float(actual_row["DEL90_PCT"]) == 0.10
    assert int(actual_row["DEL90_CAL_APPLIED"]) == 0
    assert float(forecast_row["DEL90_PCT_BASE"]) == 0.10
    assert float(forecast_row["DEL90_PCT"]) == 0.30
    assert float(forecast_row["DEL90_AMT"]) == 30.0
    assert int(forecast_row["DEL90_CAL_APPLIED"]) == 1


def test_calibration_drift_warning():
    current = pd.DataFrame(
        [{"TARGET_MOB": 12, "ANCHOR_MOB": 6, "ADJ": 0.03}]
    )
    previous = pd.DataFrame(
        [{"TARGET_MOB": 12, "ANCHOR_MOB": 6, "ADJ": 0.01}]
    )
    result = _attach_del90_calibration_drift(
        current,
        previous,
        warning_threshold=0.01,
    )
    assert abs(float(result.loc[0, "ADJ_CHANGE"]) - 0.02) < 1e-12
    assert bool(result.loc[0, "DRIFT_WARNING"])


def test_apply_del90_blend_convex_combination():
    vintage = pd.Timestamp("2024-01-01")
    df_del30 = pd.DataFrame(
        [
            {
                "PRODUCT_TYPE": "PL",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                "MOB": 12,
                "IS_FORECAST": 1,
                "DISB_TOTAL": 100.0,
                "DEL90_PCT": 0.10,
                "DEL90_AMT": 10.0,
            }
        ]
    )
    df_del90 = df_del30.copy()
    df_del90["DEL90_PCT"] = 0.30
    df_del90["DEL90_AMT"] = 30.0
    actual_results = {
        ("PL", "A", vintage): {
            0: pd.Series(dtype=float),
            6: pd.Series(dtype=float),
        }
    }
    blend_curve = pd.DataFrame(
        [
            {
                "TARGET_MOB": 12,
                "ANCHOR_MOB": 6,
                "WEIGHT_DEL30K": 0.75,
                "WEIGHT_DEL90K": 0.25,
                "N_CALIBRATION_VINTAGES": 4,
            }
        ]
    )

    result = _apply_del90_blend(
        df_del30,
        df_del90,
        actual_results,
        blend_curve,
        fallback_weight=1.0,
    )

    row = result.iloc[0]
    assert abs(float(row["DEL90_PCT"]) - 0.15) < 1e-12
    assert abs(float(row["DEL90_AMT"]) - 15.0) < 1e-12
    assert abs(float(row["DEL90_BLEND_WEIGHT_DEL30K"]) - 0.75) < 1e-12
    assert abs(float(row["DEL90_BLEND_WEIGHT_DEL90K"]) - 0.25) < 1e-12
    assert int(row["DEL90_BLEND_APPLIED"]) == 1


def test_build_del90_blend_curve_prefers_del30_early_and_allows_del90_later():
    df_raw = build_blend_curve_raw()
    run_cfg = {
        "name": "BLEND_TEST",
        "data_path": "synthetic.parquet",
        "max_mob": 12,
        "target_mobs": [12],
        "del90_k_source": "blend",
        "del90_blend_anchor_mobs": [2, 6],
        "del90_blend_weight_grid": [0.0, 0.5, 1.0],
        "del90_blend_n_vintages": 4,
        "del90_blend_min_vintages": 4,
        "del90_blend_half_life_months": 3.0,
        "del90_blend_fallback_weight": 1.0,
        "del90_blend_epsilon": 1e-6,
        "del90_blend_objective": "portfolio_mae",
        "k_method": "wls_reg",
        "k_min_obs": 1,
        "fallback_k": 1.0,
        "fallback_weight": 0.0,
        "lambda_k": 1e-4,
        "k_prior": 0.0,
        "gamma": 1.0,
        "alpha_mob_target": 12,
        "k_weight_mode": "equal",
        "monotone": False,
    }

    def fake_run(df_model, *, vintage, target_mob, lookback_months, fit_params, k_source):
        anchor_mob = int(target_mob) - int(lookback_months)
        actual_pct = 0.12 if anchor_mob == 2 else 0.13
        if anchor_mob == 2:
            pred_pct = 0.11 if k_source == "del30" else 0.18
        else:
            pred_pct = 0.10 if k_source == "del30" else 0.13
        vintage = pd.Timestamp(vintage)
        compare_df = pd.DataFrame(
            [
                {
                    "PRODUCT_TYPE": "PL",
                    "RISK_SCORE": "A",
                    "VINTAGE_DATE": vintage,
                    "MOB": int(target_mob),
                    "START_MOB": anchor_mob,
                    "DISB_TOTAL": 100.0,
                    "ACTUAL_AMT": actual_pct * 100.0,
                    "PRED_AMT": pred_pct * 100.0,
                    "ACTUAL_PCT": actual_pct,
                    "PRED_PCT": pred_pct,
                    "ERROR": pred_pct - actual_pct,
                    "ABS_ERROR": abs(pred_pct - actual_pct),
                    "SQ_ERROR": (pred_pct - actual_pct) ** 2,
                    "TARGET_VINTAGE": vintage,
                    "TARGET_MOB": int(target_mob),
                    "TARGET_CUTOFF": vintage + pd.offsets.MonthEnd(int(target_mob)),
                    "AS_OF_CUTOFF": vintage + pd.offsets.MonthEnd(anchor_mob),
                    "ANCHOR_MOB": anchor_mob,
                }
            ]
        )
        return {
            "target_vintage": vintage,
            "target_cutoff": vintage + pd.offsets.MonthEnd(int(target_mob)),
            "asof_cutoff": vintage + pd.offsets.MonthEnd(anchor_mob),
            "anchor_mob": anchor_mob,
            "compare_df": compare_df,
        }

    original_runner = group_master_cache._run_del90_asof_forecast_for_vintage
    group_master_cache._run_del90_asof_forecast_for_vintage = fake_run
    try:
        curve = _build_del90_blend_curve(df_raw, run_cfg)
    finally:
        group_master_cache._run_del90_asof_forecast_for_vintage = original_runner

    early = curve[curve["ANCHOR_MOB"] == 2].iloc[0]
    late = curve[curve["ANCHOR_MOB"] == 6].iloc[0]

    assert float(early["WEIGHT_DEL30K"]) == 1.0
    assert str(early["STATUS"]) == "no_improvement_fallback"
    assert float(late["WEIGHT_DEL30K"]) < 1.0
    assert str(late["STATUS"]) == "applied"


def test_run_group_pipeline_hybrid_schema():
    df_raw = build_synthetic_raw()
    raw_cfg = {
        "name": "TEST_DUALK",
        "data_path": "synthetic.parquet",
        "max_mob": 4,
        "target_mobs": [3],
        "run_allocation": False,
        "export_group_workbook": False,
        "export_loan_forecast": False,
        "k_method": "wls_reg",
        "k_min_obs": 1,
        "fallback_k": 0.0,
        "fallback_weight": 0.0,
        "lambda_k": 1e-4,
        "k_prior": 0.0,
        "gamma": 1.0,
        "alpha_mob_target": 2,
        "k_weight_mode": "equal",
        "monotone": False,
        "min_obs": 1,
        "min_ead": 0.0,
        "k_post_mature": 0.03,
        "k_post_mature_del90": None,
    }

    original_load_data = group_master_cache.load_data
    group_master_cache.load_data = lambda _path: df_raw.copy()
    try:
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            summary = run_group_pipeline(
                raw_cfg=raw_cfg,
                output_root=tmp_path / "outputs",
                staging_root=tmp_path / "staging",
                save_full_cache=True,
                defaults=get_default_settings(),
            )
            assert summary["STATUS"] == "ran"

            stage_dir = group_stage_dir(tmp_path / "staging", raw_cfg["name"])
            df_lifecycle_final = load_frame(stage_dir / "lifecycle_final")
            k_curve = load_frame(stage_dir / "k_curve")

            required_cols = [
                "DEL30_PCT",
                "DEL60_PCT",
                "DEL90_PCT",
                "IS_FORECAST",
                "DPD0",
                "DPD30+",
                "DPD90+",
            ]
            for col in required_cols:
                assert col in df_lifecycle_final.columns, col

            assert not df_lifecycle_final.empty
            assert not df_lifecycle_final["DEL90_PCT"].isna().any()
            assert set(k_curve["METRIC"]) == {"DEL30", "DEL90"}
            assert {"K_RAW", "K_SMOOTH", "K_FINAL", "ALPHA"}.issubset(k_curve.columns)
    finally:
        group_master_cache.load_data = original_load_data


def test_recalibrate_existing_loan_forecast_del90_matches_target():
    vintage = pd.Timestamp("2024-01-01")
    loans = pd.DataFrame(
        [
            {
                "AGREEMENT_ID": "L1",
                "PRODUCT_TYPE": "PL",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                "DISBURSAL_AMOUNT": 100.0,
                "STATE_CURRENT": "DPD0",
                "PROB_DEL90_RAW_MOB12": 0.10,
                "PROB_DEL90_MOB12": 0.10,
                "DEL90_FLAG_MOB12": 0,
            },
            {
                "AGREEMENT_ID": "L2",
                "PRODUCT_TYPE": "PL",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                "DISBURSAL_AMOUNT": 100.0,
                "STATE_CURRENT": "WRITEOFF",
                "PROB_DEL90_RAW_MOB12": 0.40,
                "PROB_DEL90_MOB12": 0.40,
                "DEL90_FLAG_MOB12": 0,
            },
        ]
    )
    lifecycle = pd.DataFrame(
        [
            {
                "PRODUCT_TYPE": "PL",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                "MOB": 12,
                "DEL90_PCT": 0.70,
            }
        ]
    )

    result = recalibrate_existing_loan_forecast_del90(
        df_loan_forecast=loans,
        df_lifecycle_final=lifecycle,
        target_mobs=[12],
    )
    target_total = 0.70 * result["DISBURSAL_AMOUNT"].sum()
    actual_total = result["EAD_DEL90_MOB12"].sum()
    assert abs(actual_total - target_total) < 1e-6
    assert float(result.loc[result["AGREEMENT_ID"] == "L2", "PROB_DEL90_MOB12"].iloc[0]) == 1.0


def test_recalibrate_group_pipeline_from_stage_updates_del90_only():
    df_raw = build_synthetic_raw()
    raw_cfg = {
        "name": "TEST_FAST_RECAL",
        "data_path": "synthetic.parquet",
        "max_mob": 4,
        "target_mobs": [3],
        "run_allocation": True,
        "export_group_workbook": False,
        "export_loan_forecast": False,
        "k_method": "wls_reg",
        "k_min_obs": 1,
        "fallback_k": 0.0,
        "fallback_weight": 0.0,
        "lambda_k": 1e-4,
        "k_prior": 0.0,
        "gamma": 1.0,
        "alpha_mob_target": 2,
        "k_weight_mode": "equal",
        "monotone": False,
        "min_obs": 1,
        "min_ead": 0.0,
        "k_post_mature": 0.03,
        "k_post_mature_del90": None,
        "del90_k_source": "del90",
        "del90_portfolio_calibration_enabled": True,
        "del90_calibration_anchor_mobs": [2],
        "del90_calibration_n_vintages": 2,
        "del90_calibration_min_vintages": 1,
        "del90_calibration_half_life_months": 3.0,
        "del90_calibration_min_disb": 0.0,
        "del90_calibration_shrink": 0.0,
        "del90_calibration_residual_cap": 0.5,
        "del90_calibration_enforce_del30_cap": True,
        "del90_calibration_mae_guardrail": False,
        "del90_calibration_drift_warning": 0.01,
        "loan_base_mode": "latest_cutoff",
    }

    original_load_data = group_master_cache.load_data
    group_master_cache.load_data = lambda _path: df_raw.copy()
    try:
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            run_group_pipeline(
                raw_cfg=raw_cfg,
                output_root=tmp_path / "outputs",
                staging_root=tmp_path / "staging",
                save_full_cache=True,
                defaults=get_default_settings(),
            )

            stage_dir = group_stage_dir(tmp_path / "staging", raw_cfg["name"])
            before = load_frame(stage_dir / "lifecycle_final")

            recal_cfg = dict(raw_cfg)
            recal_cfg["del90_calibration_shrink"] = 1.0
            original_build_curve = group_master_cache._build_del90_portfolio_calibration_curve
            group_master_cache._build_del90_portfolio_calibration_curve = (
                lambda df_raw_unsegmented, run_cfg, blend_curve=None: pd.DataFrame(
                    [
                        {
                            "TARGET_MOB": 3,
                            "ANCHOR_MOB": 2,
                            "LOOKBACK_MONTHS": 1,
                            "RAW_ADJ": 0.15,
                            "SHRINK": 1.0,
                            "ADJ": 0.15,
                            "CALIBRATION_DISB": 200.0,
                            "EFFECTIVE_WEIGHT": 200.0,
                            "N_CALIBRATION_VINTAGES": 2,
                            "CALIBRATION_VINTAGES": "2024-01-01,2024-02-01",
                            "BASE_MAE": 0.15,
                            "CALIBRATED_MAE": 0.0,
                            "MAE_GUARDRAIL_PASSED": True,
                            "STATUS": "applied",
                            "K_SOURCE": "del90",
                        }
                    ]
                )
            )
            try:
                summary = recalibrate_group_pipeline_from_stage(
                    raw_cfg=recal_cfg,
                    output_root=tmp_path / "outputs",
                    staging_root=tmp_path / "staging",
                    defaults=get_default_settings(),
                )
            finally:
                group_master_cache._build_del90_portfolio_calibration_curve = original_build_curve
            after = load_frame(stage_dir / "lifecycle_final")
            assert summary["STATUS"] == "recalibrated_from_stage"

            key_cols = ["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "MOB", "IS_FORECAST"]
            merged = before.merge(
                after,
                on=key_cols,
                suffixes=("_before", "_after"),
                how="inner",
            )
            assert (merged["DEL30_PCT_before"] == merged["DEL30_PCT_after"]).all()
            assert (
                merged["DEL90_PCT_before"]
                .sub(merged["DEL90_PCT_after"])
                .abs()
                .max()
                > 1e-12
            )
    finally:
        group_master_cache.load_data = original_load_data


def main():
    test_merge_helper()
    test_del90_flow_differs_from_del30_flow()
    test_portfolio_calibration_changes_forecast_only()
    test_calibration_drift_warning()
    test_apply_del90_blend_convex_combination()
    test_build_del90_blend_curve_prefers_del30_early_and_allows_del90_later()
    test_run_group_pipeline_hybrid_schema()
    test_recalibrate_existing_loan_forecast_del90_matches_target()
    test_recalibrate_group_pipeline_from_stage_updates_del90_only()
    print("PASS")


if __name__ == "__main__":
    main()
