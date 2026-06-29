from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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
    export_loan_forecast_excel,
    parse_date_column,
)
from src.data_loader import load_data
from src.rollrate.allocation_v2_ultra_fast import (
    allocate_multi_mob_ultra_fast,
    recalibrate_existing_loan_forecast_del90,
)
from src.rollrate.calibration_kmob import (
    fit_alpha,
    fit_k_raw,
    forecast_all_vintages_partial_step,
    smooth_k,
)
from src.rollrate.lifecycle import (
    add_del_metrics,
    aggregate_products_to_portfolio,
    aggregate_to_product,
    combine_all_lifecycle_amount,
    export_lifecycle_all_products_one_file,
    extend_actual_info_with_portfolio,
    get_actual_all_vintages_amount,
    lifecycle_to_long_df_amount,
    tag_forecast_rows_amount,
)
from src.rollrate.lifecycle_export_enhanced import export_lifecycle_with_config_info
from src.rollrate.oot_evaluation import (
    _run_del90_asof_forecast_for_vintage,
    prepare_backtest_frame,
)
from src.rollrate.transition import compute_transition_by_mob


CACHE_FORMAT_VERSION = 6

LIFECYCLE_MERGE_KEYS = ["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "MOB"]
DEL90_METRIC_COLS = ["DEL90_AMT", "DEL90_PCT"]
FAST_RECAL_STAGE_REQUIRED_FILES = (
    "raw_filtered",
    "lifecycle_final",
)

DEFAULT_DEL90_BLEND_WEIGHT_GRID = [round(step * 0.05, 2) for step in range(21)]


def get_default_settings() -> Dict:
    return {
        "segment_cols": list(project_config.SEGMENT_COLS),
        "k_post_mature": project_config.K_POST_MATURE,
        "k_post_mature_del90": project_config.K_POST_MATURE_DEL90,
        "roll_window": project_config.CFG.get("ROLL_WINDOW"),
        "decay_lambda": project_config.CFG.get("DECAY_LAMBDA"),
        "weight_method": project_config.CFG.get("WEIGHT_METHOD"),
        "min_obs": transition_module.MIN_OBS,
        "min_ead": transition_module.MIN_EAD,
    }


def json_default(obj):
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(type(obj).__name__)


def normalize_run_cfg(cfg: Dict) -> Dict:
    run_cfg = deepcopy(cfg)
    if "name" not in run_cfg or "data_path" not in run_cfg:
        raise KeyError("Each run config must include at least: name, data_path")

    run_cfg["name"] = str(run_cfg["name"]).strip()
    run_cfg["data_path"] = str(run_cfg["data_path"]).strip()
    run_cfg["max_mob"] = int(run_cfg.get("max_mob", 24))
    run_cfg["target_mobs"] = sorted(
        {int(mob) for mob in (run_cfg.get("target_mobs", []) or [])}
    )
    run_cfg["group_portfolio_name"] = str(
        run_cfg.get("group_portfolio_name", f"TOTAL_{run_cfg['name']}")
    )
    run_cfg["run_allocation"] = bool(
        run_cfg.get("run_allocation", bool(run_cfg["target_mobs"]))
    )
    run_cfg["export_group_workbook"] = bool(
        run_cfg.get("export_group_workbook", True)
    )
    run_cfg["export_loan_forecast"] = bool(
        run_cfg.get(
            "export_loan_forecast",
            run_cfg["run_allocation"] and bool(run_cfg["target_mobs"]),
        )
    )
    run_cfg["product_filter"] = list(run_cfg.get("product_filter", []) or []) or None
    run_cfg["risk_filter"] = list(run_cfg.get("risk_filter", []) or []) or None
    raw_segment_cols = list(run_cfg.get("segment_cols", []) or [])
    normalized_segment_cols = []
    for col in raw_segment_cols:
        for part in str(col).split(","):
            part = part.strip()
            if part:
                normalized_segment_cols.append(part)
    run_cfg["segment_cols"] = normalized_segment_cols or None
    run_cfg["loan_base_mode"] = str(
        run_cfg.get("loan_base_mode", "latest_cutoff")
    ).strip().lower()
    loan_min_vintage = run_cfg.get("loan_min_vintage")
    run_cfg["loan_min_vintage"] = (
        str(loan_min_vintage).strip() if loan_min_vintage not in (None, "") else None
    )
    run_cfg["del90_k_source"] = str(
        run_cfg.get("del90_k_source", "del90")
    ).strip().lower()
    if run_cfg["del90_k_source"] not in {"del30", "del90", "blend"}:
        raise ValueError("del90_k_source must be 'del30', 'del90', or 'blend'")

    run_cfg["del90_portfolio_calibration_enabled"] = bool(
        run_cfg.get("del90_portfolio_calibration_enabled", False)
    )
    run_cfg["del90_calibration_anchor_mobs"] = sorted(
        {
            int(mob)
            for mob in (
                run_cfg.get(
                    "del90_calibration_anchor_mobs",
                    list(range(12)),
                )
                or []
            )
        }
    )
    run_cfg["del90_calibration_n_vintages"] = int(
        run_cfg.get("del90_calibration_n_vintages", 6)
    )
    run_cfg["del90_calibration_min_vintages"] = int(
        run_cfg.get("del90_calibration_min_vintages", 4)
    )
    run_cfg["del90_calibration_half_life_months"] = float(
        run_cfg.get("del90_calibration_half_life_months", 3.0)
    )
    run_cfg["del90_calibration_min_disb"] = float(
        run_cfg.get("del90_calibration_min_disb", 0.0)
    )
    run_cfg["del90_calibration_shrink"] = float(
        run_cfg.get("del90_calibration_shrink", 0.5)
    )
    raw_shrink_by_anchor = run_cfg.get("del90_calibration_shrink_by_anchor", {}) or {}
    run_cfg["del90_calibration_shrink_by_anchor"] = {
        int(anchor): float(shrink)
        for anchor, shrink in raw_shrink_by_anchor.items()
    }
    residual_cap = run_cfg.get("del90_calibration_residual_cap", 0.05)
    run_cfg["del90_calibration_residual_cap"] = (
        None if residual_cap is None else float(residual_cap)
    )
    run_cfg["del90_calibration_enforce_del30_cap"] = bool(
        run_cfg.get("del90_calibration_enforce_del30_cap", True)
    )
    run_cfg["del90_calibration_mae_guardrail"] = bool(
        run_cfg.get("del90_calibration_mae_guardrail", True)
    )
    run_cfg["del90_calibration_drift_warning"] = float(
        run_cfg.get("del90_calibration_drift_warning", 0.01)
    )
    run_cfg["del90_blend_anchor_mobs"] = sorted(
        {
            int(mob)
            for mob in (
                run_cfg.get(
                    "del90_blend_anchor_mobs",
                    [2, 4, 6, 8],
                )
                or []
            )
        }
    )
    raw_blend_weight_grid = (
        list(run_cfg.get("del90_blend_weight_grid", DEFAULT_DEL90_BLEND_WEIGHT_GRID) or [])
        or list(DEFAULT_DEL90_BLEND_WEIGHT_GRID)
    )
    blend_weight_grid = []
    for weight in raw_blend_weight_grid:
        weight = float(weight)
        if not np.isfinite(weight):
            continue
        blend_weight_grid.append(min(max(weight, 0.0), 1.0))
    if not blend_weight_grid:
        blend_weight_grid = list(DEFAULT_DEL90_BLEND_WEIGHT_GRID)
    blend_weight_grid = sorted({round(weight, 6) for weight in blend_weight_grid})
    if 1.0 not in blend_weight_grid:
        blend_weight_grid.append(1.0)
        blend_weight_grid = sorted(blend_weight_grid)
    run_cfg["del90_blend_weight_grid"] = blend_weight_grid
    run_cfg["del90_blend_n_vintages"] = int(
        run_cfg.get("del90_blend_n_vintages", 6)
    )
    run_cfg["del90_blend_min_vintages"] = int(
        run_cfg.get("del90_blend_min_vintages", 4)
    )
    run_cfg["del90_blend_half_life_months"] = float(
        run_cfg.get("del90_blend_half_life_months", 3.0)
    )
    run_cfg["del90_blend_objective"] = "portfolio_mae"
    run_cfg["del90_blend_fallback_weight"] = float(
        run_cfg.get("del90_blend_fallback_weight", 1.0)
    )
    if not 0.0 <= run_cfg["del90_blend_fallback_weight"] <= 1.0:
        raise ValueError("del90_blend_fallback_weight must be between 0 and 1")
    run_cfg["del90_blend_epsilon"] = float(
        run_cfg.get("del90_blend_epsilon", 1e-6)
    )
    run_cfg["notes"] = str(run_cfg.get("notes", ""))
    return run_cfg


def _resolve_effective_settings(run_cfg: Dict, defaults: Dict) -> Dict:
    return {
        "segment_cols": (
            list(run_cfg["segment_cols"])
            if run_cfg.get("segment_cols")
            else list(defaults["segment_cols"])
        ),
        "k_post_mature": (
            run_cfg["k_post_mature"]
            if "k_post_mature" in run_cfg
            else defaults["k_post_mature"]
        ),
        "k_post_mature_del90": (
            run_cfg["k_post_mature_del90"]
            if "k_post_mature_del90" in run_cfg
            else defaults["k_post_mature_del90"]
        ),
        "roll_window": (
            int(run_cfg["roll_window"])
            if "roll_window" in run_cfg and run_cfg["roll_window"] is not None
            else defaults["roll_window"]
        ),
        "decay_lambda": (
            float(run_cfg["decay_lambda"])
            if "decay_lambda" in run_cfg and run_cfg["decay_lambda"] is not None
            else defaults["decay_lambda"]
        ),
        "weight_method": (
            str(run_cfg["weight_method"])
            if "weight_method" in run_cfg and run_cfg["weight_method"] is not None
            else defaults["weight_method"]
        ),
        "min_obs": (
            int(run_cfg["min_obs"])
            if "min_obs" in run_cfg and run_cfg["min_obs"] is not None
            else defaults["min_obs"]
        ),
        "min_ead": (
            float(run_cfg["min_ead"])
            if "min_ead" in run_cfg and run_cfg["min_ead"] is not None
            else defaults["min_ead"]
        ),
    }


def _build_cache_signature_payload(raw_cfg: Dict, defaults: Dict) -> Dict:
    run_cfg = normalize_run_cfg(raw_cfg)
    non_logic_keys = {
        "run_allocation",
        "export_group_workbook",
        "export_loan_forecast",
        "notes",
    }
    logic_run_cfg = {k: v for k, v in run_cfg.items() if k not in non_logic_keys}
    return {
        "cache_format_version": CACHE_FORMAT_VERSION,
        "logic_run_cfg": logic_run_cfg,
        "effective_settings": _resolve_effective_settings(run_cfg, defaults),
    }


def build_stage_signature(raw_cfg: Dict, defaults: Dict) -> str:
    payload = _build_cache_signature_payload(raw_cfg, defaults)
    payload_text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=json_default,
    )
    return hashlib.sha256(payload_text.encode("utf-8")).hexdigest()


def restore_project_settings(defaults: Dict) -> None:
    project_config.SEGMENT_COLS = list(defaults["segment_cols"])
    project_config.K_POST_MATURE = defaults["k_post_mature"]
    project_config.K_POST_MATURE_DEL90 = defaults["k_post_mature_del90"]
    project_config.CFG["ROLL_WINDOW"] = defaults["roll_window"]
    project_config.CFG["DECAY_LAMBDA"] = defaults["decay_lambda"]
    project_config.CFG["WEIGHT_METHOD"] = defaults["weight_method"]
    project_config.CFG["MIN_OBS"] = defaults["min_obs"]
    project_config.CFG["MIN_EAD"] = defaults["min_ead"]
    transition_module.MIN_OBS = defaults["min_obs"]
    transition_module.MIN_EAD = defaults["min_ead"]


def apply_run_overrides(run_cfg: Dict, defaults: Dict) -> None:
    restore_project_settings(defaults)

    if run_cfg.get("segment_cols"):
        project_config.SEGMENT_COLS = list(run_cfg["segment_cols"])

    if "k_post_mature" in run_cfg:
        project_config.K_POST_MATURE = run_cfg.get("k_post_mature")
    if "k_post_mature_del90" in run_cfg:
        project_config.K_POST_MATURE_DEL90 = run_cfg.get("k_post_mature_del90")

    if "roll_window" in run_cfg:
        project_config.CFG["ROLL_WINDOW"] = int(run_cfg["roll_window"])
    if "decay_lambda" in run_cfg:
        project_config.CFG["DECAY_LAMBDA"] = float(run_cfg["decay_lambda"])
    if "weight_method" in run_cfg:
        project_config.CFG["WEIGHT_METHOD"] = str(run_cfg["weight_method"])
    if "min_obs" in run_cfg:
        transition_module.MIN_OBS = int(run_cfg["min_obs"])
        project_config.CFG["MIN_OBS"] = int(run_cfg["min_obs"])
    if "min_ead" in run_cfg:
        transition_module.MIN_EAD = float(run_cfg["min_ead"])
        project_config.CFG["MIN_EAD"] = float(run_cfg["min_ead"])


def save_frame(df: pd.DataFrame, path_stem: Path) -> Path:
    path_stem = Path(path_stem)
    parquet_path = path_stem.with_suffix(".parquet")
    pickle_path = path_stem.with_suffix(".pkl")
    try:
        df.to_parquet(parquet_path, index=False)
        return parquet_path
    except Exception:
        df.to_pickle(pickle_path)
        return pickle_path


def load_frame(path_stem: Path) -> pd.DataFrame:
    path_stem = Path(path_stem)
    parquet_path = path_stem.with_suffix(".parquet")
    pickle_path = path_stem.with_suffix(".pkl")
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    if pickle_path.exists():
        return pd.read_pickle(pickle_path)
    raise FileNotFoundError(path_stem)


def actual_info_to_frame(actual_info: Dict) -> pd.DataFrame:
    rows = [
        {
            "PRODUCT_TYPE": str(product),
            "VINTAGE_DATE": pd.to_datetime(vintage),
            "ACTUAL_MAX_MOB": int(max_mob),
        }
        for (product, vintage), max_mob in actual_info.items()
    ]
    return pd.DataFrame(
        rows, columns=["PRODUCT_TYPE", "VINTAGE_DATE", "ACTUAL_MAX_MOB"]
    )


def frame_to_actual_info(df_actual_info: pd.DataFrame) -> Dict:
    if df_actual_info is None or df_actual_info.empty:
        return {}
    work = df_actual_info.copy()
    work["VINTAGE_DATE"] = pd.to_datetime(work["VINTAGE_DATE"])
    return {
        (str(row["PRODUCT_TYPE"]), row["VINTAGE_DATE"]): int(row["ACTUAL_MAX_MOB"])
        for _, row in work.iterrows()
    }


def group_stage_dir(staging_root: Path, group_name: str) -> Path:
    return Path(staging_root) / str(group_name)


def manifest_path(staging_root: Path, group_name: str) -> Path:
    return group_stage_dir(staging_root, group_name) / "manifest.json"


def _frame_exists(stage_dir: Path, frame_stem: str) -> bool:
    return stage_dir.joinpath(f"{frame_stem}.parquet").exists() or stage_dir.joinpath(
        f"{frame_stem}.pkl"
    ).exists()


def _required_stage_files_exist(stage_dir: Path) -> bool:
    return _frame_exists(stage_dir, "group_total_master") and _frame_exists(
        stage_dir, "group_actual_info"
    )


def stage_exists(staging_root: Path, group_name: str) -> bool:
    stage_dir = group_stage_dir(staging_root, group_name)
    return _required_stage_files_exist(stage_dir)


def list_staged_groups(staging_root: Path) -> List[str]:
    root = Path(staging_root)
    if not root.exists():
        return []
    groups = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if stage_exists(root, child.name):
            groups.append(child.name)
    return sorted(groups)


def load_stage_manifest(staging_root: Path, group_name: str) -> Dict:
    path = manifest_path(staging_root, group_name)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def is_stage_compatible(
    staging_root: Path,
    raw_cfg: Dict,
    defaults: Optional[Dict] = None,
) -> tuple[bool, str]:
    run_cfg = normalize_run_cfg(raw_cfg)
    defaults = defaults or get_default_settings()

    stage_dir = group_stage_dir(staging_root, run_cfg["name"])
    if not _required_stage_files_exist(stage_dir):
        return False, "missing_required_stage_files"

    manifest = load_stage_manifest(staging_root, run_cfg["name"])
    if not manifest:
        return False, "missing_manifest"

    cached_signature = manifest.get("cache_signature")
    if not cached_signature:
        legacy_cfg = manifest.get("config")
        if legacy_cfg is None:
            return False, "legacy_stage_without_signature"
        try:
            legacy_cfg_norm = normalize_run_cfg(legacy_cfg)
        except Exception:
            return False, "legacy_config_unreadable"
        if legacy_cfg_norm == run_cfg:
            return True, "legacy_config_match"
        return False, "legacy_config_mismatch"

    expected_signature = build_stage_signature(run_cfg, defaults)
    if cached_signature != expected_signature:
        return False, "signature_mismatch"
    return True, "signature_match"


def build_group_master_payload(
    df_portfolio: pd.DataFrame,
    actual_info_all: Dict,
    group_portfolio_name: str,
    group_name: str,
) -> tuple[pd.DataFrame, Dict]:
    df_group_total = df_portfolio.copy()
    df_group_total["PRODUCT_TYPE"] = group_name
    actual_info_group = {
        (group_name, pd.to_datetime(vintage)): max_mob
        for (product, vintage), max_mob in actual_info_all.items()
        if product == group_portfolio_name
    }
    return df_group_total, actual_info_group


def _build_metric_lifecycle(
    df_raw: pd.DataFrame,
    run_cfg: Dict,
    actual_results: Dict,
    matrices_by_mob: Dict,
    parent_fallback: Dict,
    disb_total_by_vintage: Dict,
    metric_name: str,
    metric_states: List[str],
    post_mature_k,
    fit_states: Optional[List[str]] = None,
    return_diagnostics: bool = False,
):
    fit_states = list(fit_states or metric_states)
    k_raw_by_mob, weight_by_mob, _ = fit_k_raw(
        actual_results=actual_results,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        states=BUCKETS_CANON,
        s30_states=fit_states,
        include_co=True,
        denom_mode="disb",
        disb_total_by_vintage=disb_total_by_vintage,
        weight_mode=run_cfg.get("k_weight_mode", "equal"),
        method=run_cfg.get("k_method", "wls_reg"),
        lambda_k=float(run_cfg.get("lambda_k", 1e-4)),
        k_prior=float(run_cfg.get("k_prior", 0.0)),
        min_obs=int(run_cfg.get("k_min_obs", 5)),
        fallback_k=float(run_cfg.get("fallback_k", 1.0)),
        fallback_weight=float(run_cfg.get("fallback_weight", 0.0)),
        return_detail=True,
    )

    if not k_raw_by_mob:
        raise ValueError(f"{run_cfg['name']}[{metric_name}]: empty k_raw_by_mob")

    mob_min = min(k_raw_by_mob)
    mob_max = max(k_raw_by_mob)
    k_smooth_by_mob, _, _ = smooth_k(
        k_raw_by_mob,
        weight_by_mob,
        mob_min,
        mob_max,
        gamma=float(run_cfg.get("gamma", 10.0)),
        monotone=bool(run_cfg.get("monotone", False)),
    )

    alpha_target = int(run_cfg.get("alpha_mob_target", min(run_cfg["max_mob"], mob_max)))
    alpha, k_final_by_mob, _ = fit_alpha(
        actual_results=actual_results,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        states=BUCKETS_CANON,
        s30_states=fit_states,
        k_smooth_by_mob=k_smooth_by_mob,
        mob_target=alpha_target,
        include_co=True,
        post_mature_k=None,
    )

    if post_mature_k is not None and run_cfg["target_mobs"]:
        for mob in range(run_cfg["target_mobs"][0], run_cfg["max_mob"] + 1):
            k_final_by_mob[mob] = float(post_mature_k)

    forecast_calibrated = forecast_all_vintages_partial_step(
        actual_results=actual_results,
        matrices_by_mob=matrices_by_mob,
        parent_fallback=parent_fallback,
        max_mob=run_cfg["max_mob"],
        k_by_mob=k_final_by_mob,
        states=BUCKETS_CANON,
    )

    lifecycle_combined = combine_all_lifecycle_amount(actual_results, forecast_calibrated)
    df_lifecycle_metric = lifecycle_to_long_df_amount(lifecycle_combined)
    df_lifecycle_metric = tag_forecast_rows_amount(df_lifecycle_metric, df_raw)
    df_lifecycle_metric = add_del_metrics(df_lifecycle_metric, df_raw)
    if not return_diagnostics:
        return df_lifecycle_metric

    all_mobs = sorted(
        set(k_raw_by_mob)
        | set(weight_by_mob)
        | set(k_smooth_by_mob)
        | set(k_final_by_mob)
    )
    diagnostics = pd.DataFrame(
        {
            "METRIC": metric_name,
            "FIT_STATES": ",".join(fit_states),
            "MOB": all_mobs,
            "K_RAW": [k_raw_by_mob.get(mob, np.nan) for mob in all_mobs],
            "K_WEIGHT": [weight_by_mob.get(mob, np.nan) for mob in all_mobs],
            "K_SMOOTH": [k_smooth_by_mob.get(mob, np.nan) for mob in all_mobs],
            "K_FINAL": [k_final_by_mob.get(mob, np.nan) for mob in all_mobs],
            "ALPHA": float(alpha),
            "ALPHA_TARGET_MOB": alpha_target,
        }
    )
    return df_lifecycle_metric, diagnostics


def _resolve_del90_variant_settings(k_source: str) -> Dict:
    k_source = str(k_source).strip().lower()
    if k_source == "del30":
        return {
            "fit_states": BUCKETS_30P,
            "post_mature_k": project_config.K_POST_MATURE,
            "variant": "DEL30K",
        }
    if k_source == "del90":
        return {
            "fit_states": BUCKETS_90P,
            "post_mature_k": project_config.K_POST_MATURE_DEL90,
            "variant": "DEL90K",
        }
    raise ValueError(f"Unsupported DEL90 k source: {k_source!r}")


def _build_actual_max_mob_lookup(actual_results: Dict) -> Dict:
    return {
        (str(product), str(score), pd.Timestamp(vintage)): int(max(mob_dict))
        for (product, score, vintage), mob_dict in actual_results.items()
        if mob_dict
    }


def _merge_del90_compare_variants(
    compare_del30: pd.DataFrame,
    compare_del90: pd.DataFrame,
) -> pd.DataFrame:
    key_cols = ["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "MOB"]
    if compare_del30.empty or compare_del90.empty:
        return pd.DataFrame()

    left = compare_del30[
        key_cols
        + [
            "DISB_TOTAL",
            "ACTUAL_PCT",
            "AS_OF_CUTOFF",
            "TARGET_CUTOFF",
            "TARGET_VINTAGE",
            "TARGET_MOB",
            "ANCHOR_MOB",
        ]
    ].copy()
    left["PRED_PCT_DEL30K"] = compare_del30["PRED_PCT"].astype(float)

    right = compare_del90[key_cols].copy()
    right["PRED_PCT_DEL90K"] = compare_del90["PRED_PCT"].astype(float)

    merged = left.merge(
        right,
        on=key_cols,
        how="inner",
        validate="one_to_one",
    )
    return merged


def _interp_blend_weight_for_anchor(
    blend_curve: pd.DataFrame,
    *,
    target_mob: int,
    anchor_mob: int,
    fallback_weight: float,
) -> Dict:
    if blend_curve.empty:
        return {
            "weight_del30k": float(fallback_weight),
            "weight_del90k": float(1.0 - fallback_weight),
            "anchor_used": float(anchor_mob),
            "source_n": 0,
        }

    curve = blend_curve[blend_curve["TARGET_MOB"].astype(int) == int(target_mob)].copy()
    if curve.empty:
        return {
            "weight_del30k": float(fallback_weight),
            "weight_del90k": float(1.0 - fallback_weight),
            "anchor_used": float(anchor_mob),
            "source_n": 0,
        }

    curve = curve.sort_values("ANCHOR_MOB")
    anchors = curve["ANCHOR_MOB"].to_numpy(dtype=float)
    weights = curve["WEIGHT_DEL30K"].to_numpy(dtype=float)
    source_counts = curve["N_CALIBRATION_VINTAGES"].to_numpy(dtype=float)
    clipped_anchor = float(np.clip(float(anchor_mob), anchors.min(), anchors.max()))
    weight_del30k = float(np.interp(clipped_anchor, anchors, weights))
    nearest_idx = int(np.abs(anchors - clipped_anchor).argmin())
    source_n = int(source_counts[nearest_idx]) if len(source_counts) else 0
    return {
        "weight_del30k": weight_del30k,
        "weight_del90k": float(1.0 - weight_del30k),
        "anchor_used": clipped_anchor,
        "source_n": source_n,
    }


def _run_del90_blend_asof_forecast_for_vintage(
    df_model: pd.DataFrame,
    *,
    vintage,
    target_mob: int,
    lookback_months: int,
    fit_params: Dict,
    blend_curve: pd.DataFrame,
    fallback_weight: float,
) -> Dict:
    result_del30 = _run_del90_asof_forecast_for_vintage(
        df_model,
        vintage=vintage,
        target_mob=target_mob,
        lookback_months=lookback_months,
        fit_params=fit_params,
        k_source="del30",
    )
    result_del90 = _run_del90_asof_forecast_for_vintage(
        df_model,
        vintage=vintage,
        target_mob=target_mob,
        lookback_months=lookback_months,
        fit_params=fit_params,
        k_source="del90",
    )
    compare_df = _merge_del90_compare_variants(
        result_del30["compare_df"],
        result_del90["compare_df"],
    )
    if compare_df.empty:
        result = dict(result_del30)
        result["compare_df"] = pd.DataFrame()
        return result

    blend_meta = _interp_blend_weight_for_anchor(
        blend_curve,
        target_mob=int(target_mob),
        anchor_mob=int(result_del30["anchor_mob"]),
        fallback_weight=float(fallback_weight),
    )
    compare_df["PRED_PCT"] = (
        blend_meta["weight_del30k"] * compare_df["PRED_PCT_DEL30K"].astype(float)
        + blend_meta["weight_del90k"] * compare_df["PRED_PCT_DEL90K"].astype(float)
    )
    compare_df["BLEND_WEIGHT_DEL30K"] = blend_meta["weight_del30k"]
    compare_df["BLEND_WEIGHT_DEL90K"] = blend_meta["weight_del90k"]
    compare_df["BLEND_ANCHOR_MOB"] = blend_meta["anchor_used"]
    compare_df["BLEND_SOURCE_N"] = blend_meta["source_n"]
    compare_df["PRED_AMT"] = compare_df["PRED_PCT"] * compare_df["DISB_TOTAL"].astype(float)
    compare_df["ERROR"] = compare_df["PRED_PCT"] - compare_df["ACTUAL_PCT"].astype(float)
    compare_df["ABS_ERROR"] = compare_df["ERROR"].abs()
    compare_df["SQ_ERROR"] = compare_df["ERROR"] ** 2

    result = dict(result_del30)
    result["compare_df"] = compare_df
    return result


def _build_del90_blend_curve(
    df_raw_unsegmented: pd.DataFrame,
    run_cfg: Dict,
) -> pd.DataFrame:
    columns = [
        "TARGET_MOB",
        "ANCHOR_MOB",
        "LOOKBACK_MONTHS",
        "WEIGHT_DEL30K",
        "WEIGHT_DEL90K",
        "N_CALIBRATION_VINTAGES",
        "CALIBRATION_VINTAGES",
        "CALIBRATION_DISB",
        "EFFECTIVE_WEIGHT",
        "BASELINE_MAE",
        "BLENDED_MAE",
        "BASELINE_SOURCE",
        "OBJECTIVE",
        "STATUS",
        "FALLBACK_WEIGHT",
        "ASOF_CUTOFF_MIN",
        "ASOF_CUTOFF_MAX",
    ]
    if run_cfg.get("del90_k_source") != "blend":
        return pd.DataFrame(columns=columns)

    df_model = prepare_backtest_frame(
        df_raw_unsegmented,
        product_filter=run_cfg.get("product_filter"),
        risk_filter=run_cfg.get("risk_filter"),
    )
    df_model[CFG["cutoff"]] = parse_date_column(df_model[CFG["cutoff"]])
    df_model[CFG["mob"]] = pd.to_numeric(df_model[CFG["mob"]], errors="coerce")

    fit_params = {
        "k_method": run_cfg.get("k_method", "wls_reg"),
        "lambda_k": float(run_cfg.get("lambda_k", 1e-4)),
        "k_prior": float(run_cfg.get("k_prior", 0.0)),
        "k_min_obs": int(run_cfg.get("k_min_obs", 5)),
        "fallback_k": float(run_cfg.get("fallback_k", 1.0)),
        "fallback_weight": float(run_cfg.get("fallback_weight", 0.0)),
        "gamma": float(run_cfg.get("gamma", 10.0)),
        "alpha_mob_target": int(
            run_cfg.get("alpha_mob_target", max(run_cfg["target_mobs"]))
        ),
        "k_weight_mode": run_cfg.get("k_weight_mode", "equal"),
        "monotone": bool(run_cfg.get("monotone", False)),
    }
    half_life = float(run_cfg["del90_blend_half_life_months"])
    min_vintages = int(run_cfg["del90_blend_min_vintages"])
    fallback_weight = float(run_cfg["del90_blend_fallback_weight"])
    epsilon = float(run_cfg["del90_blend_epsilon"])
    weight_grid = sorted(
        {float(weight) for weight in run_cfg["del90_blend_weight_grid"]},
        reverse=True,
    )
    rows = []

    for target_mob in run_cfg["target_mobs"]:
        target_candidates = (
            df_model[df_model[CFG["mob"]] == int(target_mob)]
            .groupby("VINTAGE_DATE")[CFG["cutoff"]]
            .max()
            .sort_index()
        )
        if target_candidates.empty:
            continue

        valid_anchor_mobs = [
            mob
            for mob in run_cfg["del90_blend_anchor_mobs"]
            if 0 <= int(mob) < int(target_mob)
        ]
        for anchor_mob in valid_anchor_mobs:
            lookback_months = int(target_mob) - int(anchor_mob)
            calibration_vintages = target_candidates.tail(
                run_cfg["del90_blend_n_vintages"]
            ).index
            compare_frames = []
            used_vintages = []
            for vintage in calibration_vintages:
                try:
                    result_del30 = _run_del90_asof_forecast_for_vintage(
                        df_model,
                        vintage=vintage,
                        target_mob=int(target_mob),
                        lookback_months=lookback_months,
                        fit_params=fit_params,
                        k_source="del30",
                    )
                    result_del90 = _run_del90_asof_forecast_for_vintage(
                        df_model,
                        vintage=vintage,
                        target_mob=int(target_mob),
                        lookback_months=lookback_months,
                        fit_params=fit_params,
                        k_source="del90",
                    )
                except ValueError as exc:
                    print(
                        f"[WARN] Skip DEL90 blend vintage {pd.Timestamp(vintage):%Y-%m-%d} "
                        f"at anchor MOB{anchor_mob}: {exc}"
                    )
                    continue

                compare = _merge_del90_compare_variants(
                    result_del30["compare_df"],
                    result_del90["compare_df"],
                )
                if compare.empty:
                    continue
                compare["CALIBRATION_VINTAGE"] = pd.Timestamp(vintage)
                compare_frames.append(compare)
                used_vintages.append(pd.Timestamp(vintage))

            status = "applied"
            if len(used_vintages) < min_vintages:
                status = "insufficient_vintages_fallback"
                rows.append(
                    {
                        "TARGET_MOB": int(target_mob),
                        "ANCHOR_MOB": int(anchor_mob),
                        "LOOKBACK_MONTHS": lookback_months,
                        "WEIGHT_DEL30K": fallback_weight,
                        "WEIGHT_DEL90K": float(1.0 - fallback_weight),
                        "N_CALIBRATION_VINTAGES": len(used_vintages),
                        "CALIBRATION_VINTAGES": ",".join(
                            pd.Timestamp(vintage).strftime("%Y-%m-%d")
                            for vintage in used_vintages
                        ),
                        "CALIBRATION_DISB": np.nan,
                        "EFFECTIVE_WEIGHT": np.nan,
                        "BASELINE_MAE": np.nan,
                        "BLENDED_MAE": np.nan,
                        "BASELINE_SOURCE": "DEL30K",
                        "OBJECTIVE": run_cfg["del90_blend_objective"],
                        "STATUS": status,
                        "FALLBACK_WEIGHT": fallback_weight,
                        "ASOF_CUTOFF_MIN": pd.NaT,
                        "ASOF_CUTOFF_MAX": pd.NaT,
                    }
                )
                continue

            compare_df = pd.concat(compare_frames, ignore_index=True)
            newest_vintage = max(used_vintages)
            compare_df["VINTAGE_AGE_MONTHS"] = (
                (newest_vintage.year - compare_df["CALIBRATION_VINTAGE"].dt.year) * 12
                + newest_vintage.month
                - compare_df["CALIBRATION_VINTAGE"].dt.month
            ).astype(float)
            if half_life > 0:
                compare_df["RECENCY_WEIGHT"] = np.power(
                    0.5,
                    compare_df["VINTAGE_AGE_MONTHS"] / half_life,
                )
            else:
                compare_df["RECENCY_WEIGHT"] = 1.0

            vintage_summary_rows = []
            for vintage, vintage_df in compare_df.groupby("CALIBRATION_VINTAGE"):
                vintage_weights = vintage_df["DISB_TOTAL"].fillna(0.0).astype(float)
                disb_total = float(vintage_weights.sum())
                if disb_total <= 0:
                    continue
                age_months = float(vintage_df["VINTAGE_AGE_MONTHS"].iloc[0])
                recency_weight = (
                    float(np.power(0.5, age_months / half_life))
                    if half_life > 0
                    else 1.0
                )
                vintage_summary_rows.append(
                    {
                        "CALIBRATION_VINTAGE": pd.Timestamp(vintage),
                        "ACTUAL": float(
                            np.average(vintage_df["ACTUAL_PCT"], weights=vintage_weights)
                        ),
                        "PRED_DEL30K": float(
                            np.average(vintage_df["PRED_PCT_DEL30K"], weights=vintage_weights)
                        ),
                        "PRED_DEL90K": float(
                            np.average(vintage_df["PRED_PCT_DEL90K"], weights=vintage_weights)
                        ),
                        "WEIGHT": disb_total * recency_weight,
                        "DISB_TOTAL": disb_total,
                        "ASOF_CUTOFF": pd.to_datetime(vintage_df["AS_OF_CUTOFF"].iloc[0]),
                    }
                )

            vintage_summary = pd.DataFrame(vintage_summary_rows)
            if vintage_summary.empty or not bool((vintage_summary["WEIGHT"] > 0).any()):
                status = "no_effective_weight_fallback"
                rows.append(
                    {
                        "TARGET_MOB": int(target_mob),
                        "ANCHOR_MOB": int(anchor_mob),
                        "LOOKBACK_MONTHS": lookback_months,
                        "WEIGHT_DEL30K": fallback_weight,
                        "WEIGHT_DEL90K": float(1.0 - fallback_weight),
                        "N_CALIBRATION_VINTAGES": len(used_vintages),
                        "CALIBRATION_VINTAGES": ",".join(
                            pd.Timestamp(vintage).strftime("%Y-%m-%d")
                            for vintage in used_vintages
                        ),
                        "CALIBRATION_DISB": float(compare_df["DISB_TOTAL"].fillna(0.0).sum()),
                        "EFFECTIVE_WEIGHT": float(compare_df["DISB_TOTAL"].fillna(0.0).sum()),
                        "BASELINE_MAE": np.nan,
                        "BLENDED_MAE": np.nan,
                        "BASELINE_SOURCE": "DEL30K",
                        "OBJECTIVE": run_cfg["del90_blend_objective"],
                        "STATUS": status,
                        "FALLBACK_WEIGHT": fallback_weight,
                        "ASOF_CUTOFF_MIN": pd.to_datetime(compare_df["AS_OF_CUTOFF"]).min(),
                        "ASOF_CUTOFF_MAX": pd.to_datetime(compare_df["AS_OF_CUTOFF"]).max(),
                    }
                )
                continue

            weights = vintage_summary["WEIGHT"].astype(float).to_numpy()
            actual = vintage_summary["ACTUAL"].astype(float).to_numpy()
            pred_del30 = vintage_summary["PRED_DEL30K"].astype(float).to_numpy()
            pred_del90 = vintage_summary["PRED_DEL90K"].astype(float).to_numpy()

            baseline_mae = float(np.average(np.abs(pred_del30 - actual), weights=weights))
            best_weight = fallback_weight
            best_mae = baseline_mae
            for weight_del30k in weight_grid:
                blended_pred = (
                    float(weight_del30k) * pred_del30
                    + float(1.0 - weight_del30k) * pred_del90
                )
                blended_mae = float(
                    np.average(np.abs(blended_pred - actual), weights=weights)
                )
                if blended_mae < best_mae - 1e-12:
                    best_mae = blended_mae
                    best_weight = float(weight_del30k)

            if best_mae + epsilon >= baseline_mae:
                status = "no_improvement_fallback"
                best_weight = fallback_weight
                best_mae = baseline_mae

            rows.append(
                {
                    "TARGET_MOB": int(target_mob),
                    "ANCHOR_MOB": int(anchor_mob),
                    "LOOKBACK_MONTHS": lookback_months,
                    "WEIGHT_DEL30K": float(best_weight),
                    "WEIGHT_DEL90K": float(1.0 - best_weight),
                    "N_CALIBRATION_VINTAGES": int(len(vintage_summary)),
                    "CALIBRATION_VINTAGES": ",".join(
                        vintage_summary["CALIBRATION_VINTAGE"].dt.strftime("%Y-%m-%d").tolist()
                    ),
                    "CALIBRATION_DISB": float(vintage_summary["DISB_TOTAL"].sum()),
                    "EFFECTIVE_WEIGHT": float(vintage_summary["WEIGHT"].sum()),
                    "BASELINE_MAE": baseline_mae,
                    "BLENDED_MAE": best_mae,
                    "BASELINE_SOURCE": "DEL30K",
                    "OBJECTIVE": run_cfg["del90_blend_objective"],
                    "STATUS": status,
                    "FALLBACK_WEIGHT": fallback_weight,
                    "ASOF_CUTOFF_MIN": vintage_summary["ASOF_CUTOFF"].min(),
                    "ASOF_CUTOFF_MAX": vintage_summary["ASOF_CUTOFF"].max(),
                }
            )

    return pd.DataFrame(rows, columns=columns)


def _apply_del90_blend(
    df_lifecycle_del30k: pd.DataFrame,
    df_lifecycle_del90k: pd.DataFrame,
    actual_results: Dict,
    blend_curve: pd.DataFrame,
    fallback_weight: float = 1.0,
) -> pd.DataFrame:
    missing_cols = [col for col in DEL90_METRIC_COLS if col not in df_lifecycle_del90k.columns]
    if missing_cols:
        raise KeyError(f"DEL90 lifecycle missing columns for blend: {missing_cols}")

    out = df_lifecycle_del30k.copy()
    out["DEL90_BLEND_WEIGHT_DEL30K"] = float(fallback_weight)
    out["DEL90_BLEND_WEIGHT_DEL90K"] = float(1.0 - fallback_weight)
    out["DEL90_BLEND_ANCHOR_MOB"] = np.nan
    out["DEL90_BLEND_SOURCE_N"] = 0
    out["DEL90_BLEND_APPLIED"] = 0

    variant = df_lifecycle_del90k[LIFECYCLE_MERGE_KEYS + DEL90_METRIC_COLS].rename(
        columns={
            "DEL90_AMT": "DEL90_AMT_DEL90K_BASE",
            "DEL90_PCT": "DEL90_PCT_DEL90K_BASE",
        }
    )
    out = out.merge(
        variant,
        on=LIFECYCLE_MERGE_KEYS,
        how="left",
        validate="one_to_one",
    )
    if out["DEL90_PCT_DEL90K_BASE"].isna().any():
        raise ValueError("DEL90 blend merge produced missing DEL90K base values")

    out["DEL90_PCT_DEL30K_BASE"] = out["DEL90_PCT"].astype(float)
    out["DEL90_AMT_DEL30K_BASE"] = out["DEL90_AMT"].astype(float)
    if blend_curve.empty:
        return out.drop(
            columns=[
                "DEL90_PCT_DEL30K_BASE",
                "DEL90_AMT_DEL30K_BASE",
                "DEL90_PCT_DEL90K_BASE",
                "DEL90_AMT_DEL90K_BASE",
            ]
        )

    actual_max_mob = _build_actual_max_mob_lookup(actual_results)
    out["_ACTUAL_MAX_MOB"] = [
        actual_max_mob.get(
            (str(product), str(score), pd.Timestamp(vintage)),
            -1,
        )
        for product, score, vintage in zip(
            out["PRODUCT_TYPE"],
            out["RISK_SCORE"],
            out["VINTAGE_DATE"],
        )
    ]

    for target_mob, curve in blend_curve.groupby("TARGET_MOB"):
        curve = curve.sort_values("ANCHOR_MOB")
        anchors = curve["ANCHOR_MOB"].to_numpy(dtype=float)
        weights_del30 = curve["WEIGHT_DEL30K"].to_numpy(dtype=float)
        source_counts = curve["N_CALIBRATION_VINTAGES"].to_numpy(dtype=float)
        mask = (
            (out["MOB"] == int(target_mob))
            & (out["IS_FORECAST"].astype(int) == 1)
            & (out["_ACTUAL_MAX_MOB"] < int(target_mob))
        )
        if not mask.any():
            continue

        actual_anchors = out.loc[mask, "_ACTUAL_MAX_MOB"].clip(
            lower=anchors.min(),
            upper=anchors.max(),
        )
        interpolated_w_del30 = np.interp(actual_anchors, anchors, weights_del30)
        interpolated_w_del90 = 1.0 - interpolated_w_del30
        nearest_idx = np.abs(
            actual_anchors.to_numpy(dtype=float)[:, None] - anchors[None, :]
        ).argmin(axis=1)

        blended_pct = (
            interpolated_w_del30 * out.loc[mask, "DEL90_PCT_DEL30K_BASE"].astype(float).to_numpy()
            + interpolated_w_del90 * out.loc[mask, "DEL90_PCT_DEL90K_BASE"].astype(float).to_numpy()
        )
        out.loc[mask, "DEL90_PCT"] = np.clip(blended_pct, 0.0, 1.0)
        out.loc[mask, "DEL90_AMT"] = (
            out.loc[mask, "DEL90_PCT"].astype(float)
            * out.loc[mask, "DISB_TOTAL"].astype(float)
        )
        out.loc[mask, "DEL90_BLEND_WEIGHT_DEL30K"] = interpolated_w_del30
        out.loc[mask, "DEL90_BLEND_WEIGHT_DEL90K"] = interpolated_w_del90
        out.loc[mask, "DEL90_BLEND_ANCHOR_MOB"] = actual_anchors
        out.loc[mask, "DEL90_BLEND_SOURCE_N"] = source_counts[nearest_idx].astype(int)
        out.loc[mask, "DEL90_BLEND_APPLIED"] = 1

    out = out.drop(
        columns=[
            "_ACTUAL_MAX_MOB",
            "DEL90_PCT_DEL30K_BASE",
            "DEL90_AMT_DEL30K_BASE",
            "DEL90_PCT_DEL90K_BASE",
            "DEL90_AMT_DEL90K_BASE",
        ]
    )
    return out


def _build_del90_portfolio_calibration_curve(
    df_raw_unsegmented: pd.DataFrame,
    run_cfg: Dict,
    blend_curve: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    columns = [
        "TARGET_MOB",
        "ANCHOR_MOB",
        "LOOKBACK_MONTHS",
        "RAW_ADJ",
        "SHRINK",
        "ADJ",
        "CALIBRATION_DISB",
        "EFFECTIVE_WEIGHT",
        "N_CALIBRATION_VINTAGES",
        "CALIBRATION_VINTAGES",
        "BASE_MAE",
        "CALIBRATED_MAE",
        "MAE_GUARDRAIL_PASSED",
        "STATUS",
        "K_SOURCE",
    ]
    if not run_cfg.get("del90_portfolio_calibration_enabled", False):
        return pd.DataFrame(columns=columns)

    df_model = prepare_backtest_frame(
        df_raw_unsegmented,
        product_filter=run_cfg.get("product_filter"),
        risk_filter=run_cfg.get("risk_filter"),
    )
    df_model[CFG["cutoff"]] = parse_date_column(df_model[CFG["cutoff"]])
    df_model[CFG["mob"]] = pd.to_numeric(df_model[CFG["mob"]], errors="coerce")

    fit_params = {
        "k_method": run_cfg.get("k_method", "wls_reg"),
        "lambda_k": float(run_cfg.get("lambda_k", 1e-4)),
        "k_prior": float(run_cfg.get("k_prior", 0.0)),
        "k_min_obs": int(run_cfg.get("k_min_obs", 5)),
        "fallback_k": float(run_cfg.get("fallback_k", 1.0)),
        "fallback_weight": float(run_cfg.get("fallback_weight", 0.0)),
        "gamma": float(run_cfg.get("gamma", 10.0)),
        "alpha_mob_target": int(
            run_cfg.get("alpha_mob_target", max(run_cfg["target_mobs"]))
        ),
        "k_weight_mode": run_cfg.get("k_weight_mode", "equal"),
        "monotone": bool(run_cfg.get("monotone", False)),
    }
    k_source = run_cfg["del90_k_source"]
    shrink_by_anchor = run_cfg["del90_calibration_shrink_by_anchor"]
    default_shrink = run_cfg["del90_calibration_shrink"]
    half_life = run_cfg["del90_calibration_half_life_months"]
    min_vintages = run_cfg["del90_calibration_min_vintages"]
    min_disb = run_cfg["del90_calibration_min_disb"]
    rows = []

    for target_mob in run_cfg["target_mobs"]:
        target_candidates = (
            df_model[df_model[CFG["mob"]] == int(target_mob)]
            .groupby("VINTAGE_DATE")[CFG["cutoff"]]
            .max()
            .sort_index()
        )
        if target_candidates.empty:
            print(f"[WARN] No mature vintages found for DEL90 MOB{target_mob} calibration.")
            continue

        valid_anchor_mobs = [
            mob
            for mob in run_cfg["del90_calibration_anchor_mobs"]
            if 0 <= int(mob) < int(target_mob)
        ]
        for anchor_mob in valid_anchor_mobs:
            lookback_months = int(target_mob) - int(anchor_mob)
            calibration_vintages = target_candidates.tail(
                run_cfg["del90_calibration_n_vintages"]
            ).index
            compare_frames = []
            used_vintages = []
            for vintage in calibration_vintages:
                try:
                    if k_source == "blend":
                        result = _run_del90_blend_asof_forecast_for_vintage(
                            df_model,
                            vintage=vintage,
                            target_mob=int(target_mob),
                            lookback_months=lookback_months,
                            fit_params=fit_params,
                            blend_curve=blend_curve if blend_curve is not None else pd.DataFrame(),
                            fallback_weight=run_cfg["del90_blend_fallback_weight"],
                        )
                    else:
                        result = _run_del90_asof_forecast_for_vintage(
                            df_model,
                            vintage=vintage,
                            target_mob=int(target_mob),
                            lookback_months=lookback_months,
                            fit_params=fit_params,
                            k_source=k_source,
                        )
                except ValueError as exc:
                    print(
                        f"[WARN] Skip DEL90 calibration vintage {pd.Timestamp(vintage):%Y-%m-%d} "
                        f"at anchor MOB{anchor_mob}: {exc}"
                    )
                    continue
                if not result["compare_df"].empty:
                    compare = result["compare_df"].copy()
                    compare["CALIBRATION_VINTAGE"] = pd.Timestamp(vintage)
                    compare_frames.append(compare)
                    used_vintages.append(pd.Timestamp(vintage))

            if len(used_vintages) < min_vintages:
                print(
                    f"[WARN] DEL90 calibration MOB{target_mob}/anchor{anchor_mob}: "
                    f"only {len(used_vintages)} vintages, require {min_vintages}."
                )
                continue
            compare_df = pd.concat(compare_frames, ignore_index=True)
            newest_vintage = max(used_vintages)
            compare_df["VINTAGE_AGE_MONTHS"] = (
                (newest_vintage.year - compare_df["CALIBRATION_VINTAGE"].dt.year) * 12
                + newest_vintage.month
                - compare_df["CALIBRATION_VINTAGE"].dt.month
            ).astype(float)
            if half_life > 0:
                compare_df["RECENCY_WEIGHT"] = np.power(
                    0.5,
                    compare_df["VINTAGE_AGE_MONTHS"] / half_life,
                )
            else:
                compare_df["RECENCY_WEIGHT"] = 1.0
            compare_df["CALIBRATION_WEIGHT"] = (
                compare_df["DISB_TOTAL"].fillna(0.0).astype(float)
                * compare_df["RECENCY_WEIGHT"]
            )
            calibration_disb = float(compare_df["DISB_TOTAL"].fillna(0.0).sum())
            if calibration_disb < min_disb:
                print(
                    f"[WARN] DEL90 calibration MOB{target_mob}/anchor{anchor_mob}: "
                    f"disb {calibration_disb:,.4f} below minimum {min_disb:,.4f}."
                )
                continue

            residual = (
                compare_df["ACTUAL_PCT"].astype(float)
                - compare_df["PRED_PCT"].astype(float)
            )
            weights = compare_df["CALIBRATION_WEIGHT"].to_numpy(dtype=float)
            if not bool((weights > 0).any()):
                continue
            raw_adj = float(np.average(residual, weights=weights))
            shrink = float(shrink_by_anchor.get(anchor_mob, default_shrink))
            adj = raw_adj * shrink
            residual_cap = run_cfg["del90_calibration_residual_cap"]
            if residual_cap is not None:
                adj = float(np.clip(adj, -abs(residual_cap), abs(residual_cap)))

            vintage_summary_rows = []
            for vintage, vintage_df in compare_df.groupby("CALIBRATION_VINTAGE"):
                vintage_weights = vintage_df["DISB_TOTAL"].fillna(0.0).astype(float)
                if not bool((vintage_weights > 0).any()):
                    continue
                actual = float(
                    np.average(vintage_df["ACTUAL_PCT"], weights=vintage_weights)
                )
                predicted = float(
                    np.average(vintage_df["PRED_PCT"], weights=vintage_weights)
                )
                age_months = float(vintage_df["VINTAGE_AGE_MONTHS"].iloc[0])
                recency_weight = (
                    float(np.power(0.5, age_months / half_life))
                    if half_life > 0
                    else 1.0
                )
                vintage_summary_rows.append(
                    {
                        "ACTUAL": actual,
                        "PREDICTED": predicted,
                        "WEIGHT": float(vintage_weights.sum()) * recency_weight,
                    }
                )
            vintage_summary = pd.DataFrame(vintage_summary_rows)
            base_errors = (
                vintage_summary["PREDICTED"] - vintage_summary["ACTUAL"]
            ).abs()
            calibrated_errors = (
                vintage_summary["PREDICTED"] + adj - vintage_summary["ACTUAL"]
            ).abs()
            base_mae = float(
                np.average(base_errors, weights=vintage_summary["WEIGHT"])
            )
            calibrated_mae = float(
                np.average(calibrated_errors, weights=vintage_summary["WEIGHT"])
            )
            guardrail_passed = (
                not run_cfg["del90_calibration_mae_guardrail"]
                or calibrated_mae <= base_mae + 1e-12
            )
            status = "applied"
            if not guardrail_passed:
                adj = 0.0
                calibrated_mae = base_mae
                status = "guardrail_rejected"

            rows.append(
                {
                    "TARGET_MOB": int(target_mob),
                    "ANCHOR_MOB": int(anchor_mob),
                    "LOOKBACK_MONTHS": lookback_months,
                    "RAW_ADJ": raw_adj,
                    "SHRINK": shrink,
                    "ADJ": adj,
                    "CALIBRATION_DISB": calibration_disb,
                    "EFFECTIVE_WEIGHT": float(weights.sum()),
                    "N_CALIBRATION_VINTAGES": len(used_vintages),
                    "CALIBRATION_VINTAGES": ",".join(
                        vintage.strftime("%Y-%m-%d") for vintage in used_vintages
                    ),
                    "BASE_MAE": base_mae,
                    "CALIBRATED_MAE": calibrated_mae,
                    "MAE_GUARDRAIL_PASSED": bool(guardrail_passed),
                    "STATUS": status,
                    "K_SOURCE": k_source,
                }
            )

    return pd.DataFrame(rows, columns=columns)


def _attach_del90_calibration_drift(
    calibration_curve: pd.DataFrame,
    previous_curve: Optional[pd.DataFrame],
    warning_threshold: float,
) -> pd.DataFrame:
    out = calibration_curve.copy()
    out["PREVIOUS_ADJ"] = np.nan
    out["ADJ_CHANGE"] = np.nan
    out["DRIFT_WARNING"] = False
    if out.empty or previous_curve is None or previous_curve.empty:
        return out
    required = {"TARGET_MOB", "ANCHOR_MOB", "ADJ"}
    if not required.issubset(previous_curve.columns):
        return out

    previous = previous_curve[
        ["TARGET_MOB", "ANCHOR_MOB", "ADJ"]
    ].rename(columns={"ADJ": "PREVIOUS_ADJ"})
    out = out.drop(columns=["PREVIOUS_ADJ"]).merge(
        previous,
        on=["TARGET_MOB", "ANCHOR_MOB"],
        how="left",
        validate="one_to_one",
    )
    out["ADJ_CHANGE"] = out["ADJ"] - out["PREVIOUS_ADJ"]
    out["DRIFT_WARNING"] = (
        out["ADJ_CHANGE"].abs() > abs(float(warning_threshold))
    ).fillna(False)
    for row in out[out["DRIFT_WARNING"]].itertuples(index=False):
        print(
            f"[WARN] DEL90 calibration drift MOB{row.TARGET_MOB}/anchor"
            f"{row.ANCHOR_MOB}: {row.PREVIOUS_ADJ:.4f} -> {row.ADJ:.4f} "
            f"(change {row.ADJ_CHANGE:+.4f})."
        )
    return out


def _apply_del90_portfolio_calibration(
    df_lifecycle: pd.DataFrame,
    actual_results: Dict,
    calibration_curve: pd.DataFrame,
    enforce_del30_cap: bool = True,
) -> pd.DataFrame:
    out = df_lifecycle.copy()
    out["DEL90_PCT_BASE"] = out["DEL90_PCT"].astype(float)
    out["DEL90_CAL_ADJ"] = 0.0
    out["DEL90_CAL_ANCHOR_MOB"] = np.nan
    out["DEL90_CAL_SOURCE_N"] = 0
    out["DEL90_CAL_APPLIED"] = 0

    if calibration_curve.empty:
        return out

    actual_max_mob = {
        (str(product), str(score), pd.Timestamp(vintage)): int(max(mob_dict))
        for (product, score, vintage), mob_dict in actual_results.items()
        if mob_dict
    }
    out["_ACTUAL_MAX_MOB"] = [
        actual_max_mob.get(
            (str(product), str(score), pd.Timestamp(vintage)),
            -1,
        )
        for product, score, vintage in zip(
            out["PRODUCT_TYPE"],
            out["RISK_SCORE"],
            out["VINTAGE_DATE"],
        )
    ]

    for target_mob, curve in calibration_curve.groupby("TARGET_MOB"):
        curve = curve.sort_values("ANCHOR_MOB")
        anchors = curve["ANCHOR_MOB"].to_numpy(dtype=float)
        adjustments = curve["ADJ"].to_numpy(dtype=float)
        source_counts = curve["N_CALIBRATION_VINTAGES"].to_numpy(dtype=float)
        mask = (
            (out["MOB"] == int(target_mob))
            & (out["IS_FORECAST"].astype(int) == 1)
            & (out["_ACTUAL_MAX_MOB"] < int(target_mob))
        )
        if not mask.any():
            continue

        actual_anchors = out.loc[mask, "_ACTUAL_MAX_MOB"].clip(
            lower=anchors.min(),
            upper=anchors.max(),
        )
        interpolated_adj = np.interp(actual_anchors, anchors, adjustments)
        nearest_idx = np.abs(
            actual_anchors.to_numpy(dtype=float)[:, None] - anchors[None, :]
        ).argmin(axis=1)
        out.loc[mask, "DEL90_CAL_ADJ"] = interpolated_adj
        out.loc[mask, "DEL90_CAL_ANCHOR_MOB"] = actual_anchors
        out.loc[mask, "DEL90_CAL_SOURCE_N"] = source_counts[nearest_idx].astype(int)
        out.loc[mask, "DEL90_CAL_APPLIED"] = 1

    calibrated = (
        out["DEL90_PCT_BASE"].astype(float)
        + out["DEL90_CAL_ADJ"].astype(float)
    ).clip(0.0, 1.0)
    if enforce_del30_cap and "DEL30_PCT" in out.columns:
        calibrated = np.minimum(calibrated, out["DEL30_PCT"].astype(float).clip(0.0, 1.0))
    out["DEL90_PCT"] = calibrated
    out["DEL90_AMT"] = out["DEL90_PCT"] * out["DISB_TOTAL"]
    out = out.drop(columns=["_ACTUAL_MAX_MOB"])
    return out


def _merge_del90_metrics(
    df_lifecycle_del30: pd.DataFrame,
    df_lifecycle_del90: pd.DataFrame,
) -> pd.DataFrame:
    missing_cols = [col for col in DEL90_METRIC_COLS if col not in df_lifecycle_del90.columns]
    if missing_cols:
        raise KeyError(f"DEL90 lifecycle missing columns: {missing_cols}")

    df_del90_only = df_lifecycle_del90[LIFECYCLE_MERGE_KEYS + DEL90_METRIC_COLS].copy()
    df_merged = df_lifecycle_del30.merge(
        df_del90_only,
        on=LIFECYCLE_MERGE_KEYS,
        how="left",
        suffixes=("", "_DEL90_FLOW"),
        validate="one_to_one",
    )

    for col in DEL90_METRIC_COLS:
        flow_col = f"{col}_DEL90_FLOW"
        if flow_col not in df_merged.columns:
            raise KeyError(f"Missing merged DEL90 column: {flow_col}")
        if df_merged[flow_col].isna().any():
            raise ValueError(f"DEL90 merge produced missing values for {col}")
        df_merged[col] = df_merged[flow_col]
        df_merged = df_merged.drop(columns=[flow_col])

    return df_merged


def _build_config_params(run_cfg: Dict) -> Dict:
    return {
        "DATA_PATH": run_cfg["data_path"],
        "MAX_MOB": run_cfg["max_mob"],
        "TARGET_MOBS": run_cfg["target_mobs"],
        "LOAN_BASE_MODE": run_cfg.get("loan_base_mode", "latest_cutoff"),
        "LOAN_MIN_VINTAGE": run_cfg.get("loan_min_vintage") or "-",
        "SEGMENT_COLS": list(project_config.SEGMENT_COLS),
        "MIN_OBS": transition_module.MIN_OBS,
        "MIN_EAD": transition_module.MIN_EAD,
        "WEIGHT_METHOD": project_config.CFG.get("WEIGHT_METHOD", "exp"),
        "ROLL_WINDOW": project_config.CFG.get("ROLL_WINDOW"),
        "DECAY_LAMBDA": project_config.CFG.get("DECAY_LAMBDA"),
        "K_POST_MATURE": project_config.K_POST_MATURE,
        "K_POST_MATURE_DEL90": project_config.K_POST_MATURE_DEL90,
        "DEL90_K_SOURCE": run_cfg["del90_k_source"],
        "DEL90_PORTFOLIO_CALIBRATION_ENABLED": run_cfg[
            "del90_portfolio_calibration_enabled"
        ],
        "DEL90_CALIBRATION_ANCHOR_MOBS": run_cfg[
            "del90_calibration_anchor_mobs"
        ],
        "DEL90_CALIBRATION_N_VINTAGES": run_cfg[
            "del90_calibration_n_vintages"
        ],
        "DEL90_CALIBRATION_MIN_VINTAGES": run_cfg[
            "del90_calibration_min_vintages"
        ],
        "DEL90_CALIBRATION_HALF_LIFE_MONTHS": run_cfg[
            "del90_calibration_half_life_months"
        ],
        "DEL90_CALIBRATION_MIN_DISB": run_cfg["del90_calibration_min_disb"],
        "DEL90_CALIBRATION_SHRINK": run_cfg["del90_calibration_shrink"],
        "DEL90_CALIBRATION_SHRINK_BY_ANCHOR": run_cfg[
            "del90_calibration_shrink_by_anchor"
        ],
        "DEL90_CALIBRATION_RESIDUAL_CAP": run_cfg[
            "del90_calibration_residual_cap"
        ],
        "DEL90_CALIBRATION_MAE_GUARDRAIL": run_cfg[
            "del90_calibration_mae_guardrail"
        ],
        "DEL90_CALIBRATION_DRIFT_WARNING": run_cfg[
            "del90_calibration_drift_warning"
        ],
        "DEL90_BLEND_ANCHOR_MOBS": run_cfg["del90_blend_anchor_mobs"],
        "DEL90_BLEND_WEIGHT_GRID": run_cfg["del90_blend_weight_grid"],
        "DEL90_BLEND_N_VINTAGES": run_cfg["del90_blend_n_vintages"],
        "DEL90_BLEND_MIN_VINTAGES": run_cfg["del90_blend_min_vintages"],
        "DEL90_BLEND_HALF_LIFE_MONTHS": run_cfg["del90_blend_half_life_months"],
        "DEL90_BLEND_OBJECTIVE": run_cfg["del90_blend_objective"],
        "DEL90_BLEND_FALLBACK_WEIGHT": run_cfg["del90_blend_fallback_weight"],
    }


def _reset_del90_to_base(df_lifecycle: pd.DataFrame) -> pd.DataFrame:
    if "DEL90_PCT_BASE" not in df_lifecycle.columns:
        raise KeyError(
            "Staged lifecycle is missing DEL90_PCT_BASE; full rerun is required."
        )
    if "DISB_TOTAL" not in df_lifecycle.columns:
        raise KeyError("Staged lifecycle is missing DISB_TOTAL; full rerun is required.")

    out = df_lifecycle.copy()
    out["DEL90_PCT"] = out["DEL90_PCT_BASE"].astype(float).clip(0.0, 1.0)
    out["DEL90_AMT"] = out["DEL90_PCT"] * out["DISB_TOTAL"].astype(float)
    out["DEL90_CAL_ADJ"] = 0.0
    out["DEL90_CAL_ANCHOR_MOB"] = np.nan
    out["DEL90_CAL_SOURCE_N"] = 0
    out["DEL90_CAL_APPLIED"] = 0
    return out


def _validate_fast_recalibration_stage(
    stage_manifest: Dict,
    run_cfg: Dict,
) -> None:
    staged_cfg = normalize_run_cfg(stage_manifest.get("config", {}))
    keys_to_match = [
        "name",
        "data_path",
        "max_mob",
        "target_mobs",
        "group_portfolio_name",
        "segment_cols",
        "product_filter",
        "risk_filter",
        "loan_base_mode",
        "del90_k_source",
        "del90_blend_anchor_mobs",
        "del90_blend_weight_grid",
        "del90_blend_n_vintages",
        "del90_blend_min_vintages",
        "del90_blend_half_life_months",
        "del90_blend_objective",
        "del90_blend_fallback_weight",
        "del90_blend_epsilon",
    ]
    mismatches = [
        key
        for key in keys_to_match
        if staged_cfg.get(key) != run_cfg.get(key)
    ]
    if mismatches:
        raise ValueError(
            "Fast recalibration only supports calibration-only changes. "
            f"Full rerun required because staged config differs in: {', '.join(mismatches)}."
        )


def recalibrate_group_pipeline_from_stage(
    raw_cfg: Dict,
    output_root: Path,
    staging_root: Path,
    defaults: Optional[Dict] = None,
) -> Dict:
    run_cfg = normalize_run_cfg(raw_cfg)
    defaults = defaults or get_default_settings()
    cache_signature_payload = _build_cache_signature_payload(run_cfg, defaults)
    cache_signature = build_stage_signature(run_cfg, defaults)

    output_root = Path(output_root)
    staging_root = Path(staging_root)
    stage_dir = group_stage_dir(staging_root, run_cfg["name"])
    group_output_dir = output_root / run_cfg["name"]
    group_output_dir.mkdir(parents=True, exist_ok=True)

    if not stage_dir.exists():
        raise FileNotFoundError(
            f"Stage not found for {run_cfg['name']}: {stage_dir}. Full rerun is required."
        )

    manifest = load_stage_manifest(staging_root, run_cfg["name"])
    if not manifest:
        raise FileNotFoundError(
            f"Manifest not found for staged group {run_cfg['name']}. Full rerun is required."
        )
    _validate_fast_recalibration_stage(manifest, run_cfg)

    missing_stage_files = [
        stem for stem in FAST_RECAL_STAGE_REQUIRED_FILES if not _frame_exists(stage_dir, stem)
    ]
    if missing_stage_files:
        raise FileNotFoundError(
            f"Stage for {run_cfg['name']} is missing required full-cache frames: "
            f"{', '.join(missing_stage_files)}. Rerun once with SAVE_FULL_GROUP_CACHE=True."
        )

    print("\n" + "=" * 100)
    print(f"FAST RECALIBRATE GROUP: {run_cfg['name']}")
    print("=" * 100)
    print(json.dumps(run_cfg, ensure_ascii=False, indent=2, default=json_default))

    restore_project_settings(defaults)
    apply_run_overrides(run_cfg, defaults)

    try:
        df_raw = load_frame(stage_dir / "raw_filtered")
        df_lifecycle_stage = load_frame(stage_dir / "lifecycle_final")
        try:
            previous_del90_calibration_curve = load_frame(stage_dir / "del90_calibration_curve")
        except FileNotFoundError:
            previous_del90_calibration_curve = pd.DataFrame()
        try:
            del90_blend_curve = load_frame(stage_dir / "del90_blend_curve")
        except FileNotFoundError:
            del90_blend_curve = pd.DataFrame()

        if CFG["orig_date"] in df_raw.columns:
            df_raw[CFG["orig_date"]] = parse_date_column(df_raw[CFG["orig_date"]])
        if CFG["cutoff"] in df_raw.columns:
            df_raw[CFG["cutoff"]] = parse_date_column(df_raw[CFG["cutoff"]])

        df_lifecycle_base = _reset_del90_to_base(df_lifecycle_stage)
        actual_results = get_actual_all_vintages_amount(df_raw)

        del90_calibration_curve = _build_del90_portfolio_calibration_curve(
            df_raw_unsegmented=df_raw,
            run_cfg=run_cfg,
            blend_curve=del90_blend_curve,
        )
        del90_calibration_curve = _attach_del90_calibration_drift(
            calibration_curve=del90_calibration_curve,
            previous_curve=previous_del90_calibration_curve,
            warning_threshold=run_cfg["del90_calibration_drift_warning"],
        )
        df_lifecycle_final = _apply_del90_portfolio_calibration(
            df_lifecycle=df_lifecycle_base,
            actual_results=actual_results,
            calibration_curve=del90_calibration_curve,
            enforce_del30_cap=run_cfg["del90_calibration_enforce_del30_cap"],
        )

        df_product = aggregate_to_product(df_lifecycle_final)
        df_portfolio = aggregate_products_to_portfolio(
            df_product, portfolio_name=run_cfg["group_portfolio_name"]
        )
        df_del_all = pd.concat([df_product, df_portfolio], ignore_index=True)

        actual_info_prod = {
            (str(product), pd.to_datetime(vintage)): int(max(mob_dict.keys()))
            for (product, _score, vintage), mob_dict in actual_results.items()
        }
        actual_info_all = extend_actual_info_with_portfolio(
            actual_info_prod, portfolio_name=run_cfg["group_portfolio_name"]
        )
        df_group_total_master, actual_info_group = build_group_master_payload(
            df_portfolio,
            actual_info_all,
            run_cfg["group_portfolio_name"],
            run_cfg["name"],
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        calibration_curve_file = None
        blend_curve_file = None
        if not del90_blend_curve.empty:
            blend_curve_file = (
                group_output_dir / f"{run_cfg['name']}_DEL90_Blend_{timestamp}.csv"
            )
            del90_blend_curve.to_csv(
                blend_curve_file,
                index=False,
                encoding="utf-8-sig",
            )
        if not del90_calibration_curve.empty:
            calibration_curve_file = (
                group_output_dir / f"{run_cfg['name']}_DEL90_Calibration_{timestamp}.csv"
            )
            del90_calibration_curve.to_csv(
                calibration_curve_file,
                index=False,
                encoding="utf-8-sig",
            )

        group_workbook = None
        if run_cfg["export_group_workbook"]:
            group_workbook = group_output_dir / f"{run_cfg['name']}_Lifecycle_{timestamp}.xlsx"
            export_lifecycle_with_config_info(
                df_del_all,
                actual_info_all,
                df_raw,
                _build_config_params(run_cfg),
                str(group_workbook),
            )

        loan_workbook = None
        allocated_loans = 0
        df_loan_forecast = None
        if run_cfg["run_allocation"] and run_cfg["target_mobs"]:
            if _frame_exists(stage_dir, "loan_forecast"):
                df_loan_forecast_stage = load_frame(stage_dir / "loan_forecast")
                df_loan_forecast = recalibrate_existing_loan_forecast_del90(
                    df_loan_forecast=df_loan_forecast_stage,
                    df_lifecycle_final=df_lifecycle_final,
                    target_mobs=run_cfg["target_mobs"],
                )
                allocated_loans = len(df_loan_forecast)
                if run_cfg["export_loan_forecast"]:
                    loan_workbook = (
                        group_output_dir / f"{run_cfg['name']}_Loan_Forecast_{timestamp}.xlsx"
                    )
                    export_loan_forecast_excel(
                        df_loan_forecast,
                        loan_workbook,
                        target_mobs=run_cfg["target_mobs"],
                        include_del_sheets=True,
                    )
            else:
                print(
                    f"[WARN] No staged loan_forecast for {run_cfg['name']}; "
                    "skip loan workbook in fast recalibration mode."
                )

        stage_files = dict(manifest.get("stage_files", {}))
        stage_files.update(
            {
                "product_level": str(save_frame(df_product, stage_dir / "product_level")),
                "portfolio_total_native": str(
                    save_frame(df_portfolio, stage_dir / "portfolio_total_native")
                ),
                "group_total_master": str(
                    save_frame(df_group_total_master, stage_dir / "group_total_master")
                ),
                "group_actual_info": str(
                    save_frame(actual_info_to_frame(actual_info_group), stage_dir / "group_actual_info")
                ),
                "del90_calibration_curve": str(
                    save_frame(del90_calibration_curve, stage_dir / "del90_calibration_curve")
                ),
                "del90_blend_curve": str(
                    save_frame(del90_blend_curve, stage_dir / "del90_blend_curve")
                ),
                "lifecycle_final": str(save_frame(df_lifecycle_final, stage_dir / "lifecycle_final")),
                "del_all": str(save_frame(df_del_all, stage_dir / "del_all")),
            }
        )
        if df_loan_forecast is not None:
            stage_files["loan_forecast"] = str(
                save_frame(df_loan_forecast, stage_dir / "loan_forecast")
            )

        summary = {
            "GROUP": run_cfg["name"],
            "MAX_MOB": run_cfg["max_mob"],
            "TARGET_MOBS": ", ".join(map(str, run_cfg["target_mobs"])) or "-",
            "ROWS_RAW": len(df_raw),
            "ROWS_GROUP_TOTAL": len(df_group_total_master),
            "ALLOCATED_LOANS": allocated_loans,
            "DEL90_K_SOURCE": run_cfg["del90_k_source"],
            "DEL90_BLEND_ROWS": len(del90_blend_curve),
            "DEL90_BLEND_FILE": str(blend_curve_file) if blend_curve_file else "-",
            "DEL90_CALIBRATION": (
                "enabled" if run_cfg["del90_portfolio_calibration_enabled"] else "disabled"
            ),
            "DEL90_CALIBRATION_ROWS": len(del90_calibration_curve),
            "DEL90_CALIBRATION_GUARDRAIL_REJECTED": int(
                (
                    del90_calibration_curve.get("STATUS", pd.Series(dtype=str))
                    == "guardrail_rejected"
                ).sum()
            ),
            "DEL90_CALIBRATION_DRIFT_WARNINGS": int(
                del90_calibration_curve.get("DRIFT_WARNING", pd.Series(dtype=bool)).sum()
            ),
            "DEL90_CALIBRATION_FILE": (
                str(calibration_curve_file) if calibration_curve_file else "-"
            ),
            "GROUP_WORKBOOK": str(group_workbook) if group_workbook else "-",
            "LOAN_WORKBOOK": str(loan_workbook) if loan_workbook else "-",
            "STAGING_DIR": str(stage_dir),
            "STATUS": "recalibrated_from_stage",
        }

        _write_stage_manifest(
            stage_dir,
            run_cfg,
            stage_files,
            group_workbook,
            loan_workbook,
            summary,
            cache_signature,
            cache_signature_payload,
        )
        return summary
    finally:
        restore_project_settings(defaults)


def _select_loan_export_base(df_raw: pd.DataFrame, run_cfg: Dict) -> pd.DataFrame:
    loan_col = CFG["loan"]
    mob_col = CFG["mob"]
    cutoff_col = CFG["cutoff"]
    orig_col = CFG["orig_date"]

    mode = str(run_cfg.get("loan_base_mode", "latest_cutoff")).strip().lower()

    df_base = df_raw.copy()
    df_base["VINTAGE_DATE"] = parse_date_column(df_base[orig_col])

    if mode == "latest_cutoff":
        latest_cutoff = df_base[cutoff_col].max()
        df_selected = df_base[df_base[cutoff_col] == latest_cutoff].copy()
        latest_cutoff_ts = parse_date_column(pd.Series([latest_cutoff])).iloc[0]
        print(f"📌 Loan export base: latest_cutoff = {latest_cutoff_ts:%Y-%m-%d}")
    elif mode == "latest_per_loan":
        df_base["_cutoff_ts"] = parse_date_column(df_base[cutoff_col])
        df_base["_mob_num"] = pd.to_numeric(df_base[mob_col], errors="coerce")
        df_base = df_base.sort_values([loan_col, "_cutoff_ts", "_mob_num"])
        df_selected = df_base.drop_duplicates(subset=[loan_col], keep="last").copy()
        cutoff_min = df_selected["_cutoff_ts"].min()
        cutoff_max = df_selected["_cutoff_ts"].max()
        print(
            "📌 Loan export base: latest row per loan "
            f"(cutoff range {cutoff_min:%Y-%m-%d} -> {cutoff_max:%Y-%m-%d})"
        )
        df_selected = df_selected.drop(columns=["_cutoff_ts", "_mob_num"], errors="ignore")
    else:
        raise ValueError(
            f"{run_cfg['name']}: unsupported loan_base_mode={mode!r}. "
            "Use 'latest_cutoff' or 'latest_per_loan'."
        )

    min_vintage = run_cfg.get("loan_min_vintage")
    if min_vintage:
        min_vintage_ts = pd.Timestamp(min_vintage)
        before = len(df_selected)
        df_selected = df_selected[df_selected["VINTAGE_DATE"] >= min_vintage_ts].copy()
        print(
            f"   Filter VINTAGE_DATE >= {min_vintage_ts:%Y-%m-%d}: "
            f"{before:,} -> {len(df_selected):,} loans"
        )

    if df_selected.empty:
        raise ValueError(f"{run_cfg['name']}: no loans left for loan export after base selection")

    vintage_min = df_selected["VINTAGE_DATE"].min()
    vintage_max = df_selected["VINTAGE_DATE"].max()
    print(f"   Loan export vintage range: {vintage_min:%Y-%m-%d} -> {vintage_max:%Y-%m-%d}")

    return df_selected


def _write_stage_manifest(
    stage_dir: Path,
    run_cfg: Dict,
    stage_files: Dict,
    group_workbook: Optional[Path],
    loan_workbook: Optional[Path],
    summary: Dict,
    cache_signature: str,
    cache_signature_payload: Dict,
) -> None:
    manifest = {
        "run_name": run_cfg["name"],
        "run_time": datetime.now().isoformat(),
        "cache_format_version": CACHE_FORMAT_VERSION,
        "cache_signature": cache_signature,
        "cache_signature_payload": cache_signature_payload,
        "config": run_cfg,
        "stage_files": stage_files,
        "group_workbook": str(group_workbook) if group_workbook else None,
        "loan_workbook": str(loan_workbook) if loan_workbook else None,
        "summary": summary,
    }
    manifest_path(stage_dir.parent, run_cfg["name"]).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )


def run_group_pipeline(
    raw_cfg: Dict,
    output_root: Path,
    staging_root: Path,
    save_full_cache: bool = False,
    defaults: Optional[Dict] = None,
) -> Dict:
    run_cfg = normalize_run_cfg(raw_cfg)
    defaults = defaults or get_default_settings()
    cache_signature_payload = _build_cache_signature_payload(run_cfg, defaults)
    cache_signature = build_stage_signature(run_cfg, defaults)

    output_root = Path(output_root)
    staging_root = Path(staging_root)
    stage_dir = group_stage_dir(staging_root, run_cfg["name"])
    group_output_dir = output_root / run_cfg["name"]
    stage_dir.mkdir(parents=True, exist_ok=True)
    group_output_dir.mkdir(parents=True, exist_ok=True)
    try:
        previous_del90_calibration_curve = load_frame(
            stage_dir / "del90_calibration_curve"
        )
    except FileNotFoundError:
        previous_del90_calibration_curve = pd.DataFrame()

    print("\n" + "=" * 100)
    print(f"RUN GROUP: {run_cfg['name']}")
    print("=" * 100)
    print(json.dumps(run_cfg, ensure_ascii=False, indent=2, default=json_default))

    restore_project_settings(defaults)
    apply_run_overrides(run_cfg, defaults)

    try:
        df_raw_source = load_data(run_cfg["data_path"])
        if CFG["orig_date"] in df_raw_source.columns:
            df_raw_source[CFG["orig_date"]] = parse_date_column(
                df_raw_source[CFG["orig_date"]]
            )
        df_raw = create_segment_columns(df_raw_source)

        if run_cfg["product_filter"] is not None:
            df_raw = df_raw[df_raw["PRODUCT_TYPE"].isin(run_cfg["product_filter"])].copy()
        if run_cfg["risk_filter"] is not None:
            df_raw = df_raw[df_raw["RISK_SCORE"].isin(run_cfg["risk_filter"])].copy()

        if df_raw.empty:
            raise ValueError(f"{run_cfg['name']}: no data left after filters")

        print(
            f"📊 Data: {len(df_raw):,} rows | "
            f"{df_raw[CFG['loan']].nunique():,} loans"
        )
        print(f"   SEGMENT_COLS: {list(project_config.SEGMENT_COLS)}")

        matrices_by_mob, parent_fallback = compute_transition_by_mob(df_raw)
        actual_results = get_actual_all_vintages_amount(df_raw)

        loan_disb = df_raw.groupby(
            ["PRODUCT_TYPE", "RISK_SCORE", CFG["orig_date"], CFG["loan"]]
        )[CFG["disb"]].first()
        disb_total_by_vintage = loan_disb.groupby(level=[0, 1, 2]).sum().to_dict()

        df_lifecycle_del30, k_curve_del30 = _build_metric_lifecycle(
            df_raw=df_raw,
            run_cfg=run_cfg,
            actual_results=actual_results,
            matrices_by_mob=matrices_by_mob,
            parent_fallback=parent_fallback,
            disb_total_by_vintage=disb_total_by_vintage,
            metric_name="DEL30",
            metric_states=BUCKETS_30P,
            post_mature_k=project_config.K_POST_MATURE,
            return_diagnostics=True,
        )
        k_curve_del30["K_SOURCE_VARIANT"] = "DEL30"
        del90_variant_frames = {}
        del90_variant_curves = []
        variant_sources = (
            ["del30", "del90"]
            if run_cfg["del90_k_source"] == "blend"
            else [run_cfg["del90_k_source"]]
        )
        for variant_source in variant_sources:
            variant_cfg = _resolve_del90_variant_settings(variant_source)
            df_variant, k_curve_variant = _build_metric_lifecycle(
                df_raw=df_raw,
                run_cfg=run_cfg,
                actual_results=actual_results,
                matrices_by_mob=matrices_by_mob,
                parent_fallback=parent_fallback,
                disb_total_by_vintage=disb_total_by_vintage,
                metric_name="DEL90",
                metric_states=BUCKETS_90P,
                post_mature_k=variant_cfg["post_mature_k"],
                fit_states=variant_cfg["fit_states"],
                return_diagnostics=True,
            )
            k_curve_variant["K_SOURCE_VARIANT"] = variant_cfg["variant"]
            del90_variant_frames[variant_source] = df_variant
            del90_variant_curves.append(k_curve_variant)

        k_curve_df = pd.concat(
            [k_curve_del30] + del90_variant_curves,
            ignore_index=True,
        )
        del90_blend_curve = _build_del90_blend_curve(
            df_raw_unsegmented=df_raw_source,
            run_cfg=run_cfg,
        )
        if run_cfg["del90_k_source"] == "blend":
            df_lifecycle_final = _apply_del90_blend(
                df_lifecycle_del30k=del90_variant_frames["del30"],
                df_lifecycle_del90k=del90_variant_frames["del90"],
                actual_results=actual_results,
                blend_curve=del90_blend_curve,
                fallback_weight=run_cfg["del90_blend_fallback_weight"],
            )
        else:
            df_lifecycle_final = _merge_del90_metrics(
                df_lifecycle_del30,
                del90_variant_frames[run_cfg["del90_k_source"]],
            )
        del90_calibration_curve = _build_del90_portfolio_calibration_curve(
            df_raw_unsegmented=df_raw_source,
            run_cfg=run_cfg,
            blend_curve=del90_blend_curve,
        )
        del90_calibration_curve = _attach_del90_calibration_drift(
            calibration_curve=del90_calibration_curve,
            previous_curve=previous_del90_calibration_curve,
            warning_threshold=run_cfg["del90_calibration_drift_warning"],
        )
        df_lifecycle_final = _apply_del90_portfolio_calibration(
            df_lifecycle=df_lifecycle_final,
            actual_results=actual_results,
            calibration_curve=del90_calibration_curve,
            enforce_del30_cap=run_cfg["del90_calibration_enforce_del30_cap"],
        )

        df_product = aggregate_to_product(df_lifecycle_final)
        df_portfolio = aggregate_products_to_portfolio(
            df_product, portfolio_name=run_cfg["group_portfolio_name"]
        )
        df_del_all = pd.concat([df_product, df_portfolio], ignore_index=True)

        actual_info_prod = {
            (str(product), pd.to_datetime(vintage)): int(max(mob_dict.keys()))
            for (product, _score, vintage), mob_dict in actual_results.items()
        }
        actual_info_all = extend_actual_info_with_portfolio(
            actual_info_prod, portfolio_name=run_cfg["group_portfolio_name"]
        )

        df_group_total_master, actual_info_group = build_group_master_payload(
            df_portfolio,
            actual_info_all,
            run_cfg["group_portfolio_name"],
            run_cfg["name"],
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        calibration_curve_file = None
        blend_curve_file = None
        if not del90_blend_curve.empty:
            blend_curve_file = (
                group_output_dir
                / f"{run_cfg['name']}_DEL90_Blend_{timestamp}.csv"
            )
            del90_blend_curve.to_csv(
                blend_curve_file,
                index=False,
                encoding="utf-8-sig",
            )
        if not del90_calibration_curve.empty:
            calibration_curve_file = (
                group_output_dir
                / f"{run_cfg['name']}_DEL90_Calibration_{timestamp}.csv"
            )
            del90_calibration_curve.to_csv(
                calibration_curve_file,
                index=False,
                encoding="utf-8-sig",
            )
        k_curve_file = group_output_dir / f"{run_cfg['name']}_K_Curves_{timestamp}.csv"
        k_curve_df.to_csv(k_curve_file, index=False, encoding="utf-8-sig")
        group_workbook = None
        if run_cfg["export_group_workbook"]:
            group_workbook = group_output_dir / f"{run_cfg['name']}_Lifecycle_{timestamp}.xlsx"
            export_lifecycle_with_config_info(
                df_del_all,
                actual_info_all,
                df_raw,
                _build_config_params(run_cfg),
                str(group_workbook),
            )

        loan_workbook = None
        df_loan_forecast = None
        allocated_loans = 0
        if run_cfg["run_allocation"] and run_cfg["target_mobs"]:
            df_loans_latest = _select_loan_export_base(df_raw, run_cfg)
            df_loan_forecast = allocate_multi_mob_ultra_fast(
                df_raw=df_raw,
                df_loans_latest=df_loans_latest,
                df_lifecycle_final=df_lifecycle_final,
                matrices_by_mob=matrices_by_mob,
                target_mobs=run_cfg["target_mobs"],
                parent_fallback=parent_fallback,
                include_del30=False,
                include_del90=True,
                seed=int(run_cfg.get("seed", 42)),
            )
            allocated_loans = len(df_loan_forecast)
            if run_cfg["export_loan_forecast"]:
                loan_workbook = (
                    group_output_dir / f"{run_cfg['name']}_Loan_Forecast_{timestamp}.xlsx"
                )
                export_loan_forecast_excel(
                    df_loan_forecast,
                    loan_workbook,
                    target_mobs=run_cfg["target_mobs"],
                    include_del_sheets=True,
                )

        stage_files = {
            "product_level": str(save_frame(df_product, stage_dir / "product_level")),
            "portfolio_total_native": str(
                save_frame(df_portfolio, stage_dir / "portfolio_total_native")
            ),
            "group_total_master": str(
                save_frame(df_group_total_master, stage_dir / "group_total_master")
            ),
            "group_actual_info": str(
                save_frame(actual_info_to_frame(actual_info_group), stage_dir / "group_actual_info")
            ),
            "del90_calibration_curve": str(
                save_frame(del90_calibration_curve, stage_dir / "del90_calibration_curve")
            ),
            "del90_blend_curve": str(
                save_frame(del90_blend_curve, stage_dir / "del90_blend_curve")
            ),
            "k_curve": str(save_frame(k_curve_df, stage_dir / "k_curve")),
        }

        if save_full_cache:
            stage_files["raw_filtered"] = str(save_frame(df_raw, stage_dir / "raw_filtered"))
            stage_files["lifecycle_final"] = str(
                save_frame(df_lifecycle_final, stage_dir / "lifecycle_final")
            )
            stage_files["del_all"] = str(save_frame(df_del_all, stage_dir / "del_all"))
            if df_loan_forecast is not None:
                stage_files["loan_forecast"] = str(
                    save_frame(df_loan_forecast, stage_dir / "loan_forecast")
                )

        summary = {
            "GROUP": run_cfg["name"],
            "MAX_MOB": run_cfg["max_mob"],
            "TARGET_MOBS": ", ".join(map(str, run_cfg["target_mobs"])) or "-",
            "ROWS_RAW": len(df_raw),
            "ROWS_GROUP_TOTAL": len(df_group_total_master),
            "ALLOCATED_LOANS": allocated_loans,
            "DEL90_K_SOURCE": run_cfg["del90_k_source"],
            "DEL90_BLEND_ROWS": len(del90_blend_curve),
            "DEL90_BLEND_FILE": str(blend_curve_file) if blend_curve_file else "-",
            "DEL90_CALIBRATION": (
                "enabled"
                if run_cfg["del90_portfolio_calibration_enabled"]
                else "disabled"
            ),
            "DEL90_CALIBRATION_ROWS": len(del90_calibration_curve),
            "DEL90_CALIBRATION_GUARDRAIL_REJECTED": int(
                (
                    del90_calibration_curve.get("STATUS", pd.Series(dtype=str))
                    == "guardrail_rejected"
                ).sum()
            ),
            "DEL90_CALIBRATION_DRIFT_WARNINGS": int(
                del90_calibration_curve.get(
                    "DRIFT_WARNING",
                    pd.Series(dtype=bool),
                ).sum()
            ),
            "DEL90_CALIBRATION_FILE": (
                str(calibration_curve_file) if calibration_curve_file else "-"
            ),
            "K_CURVE_FILE": str(k_curve_file),
            "GROUP_WORKBOOK": str(group_workbook) if group_workbook else "-",
            "LOAN_WORKBOOK": str(loan_workbook) if loan_workbook else "-",
            "STAGING_DIR": str(stage_dir),
            "STATUS": "ran",
        }

        _write_stage_manifest(
            stage_dir,
            run_cfg,
            stage_files,
            group_workbook,
            loan_workbook,
            summary,
            cache_signature,
            cache_signature_payload,
        )
        return summary
    finally:
        restore_project_settings(defaults)


def summary_from_stage(staging_root: Path, group_name: str) -> Dict:
    manifest = load_stage_manifest(staging_root, group_name)
    if "summary" in manifest:
        summary = dict(manifest["summary"])
        summary["STATUS"] = "cached"
        return summary

    stage_dir = group_stage_dir(staging_root, group_name)
    df_group_total = load_frame(stage_dir / "group_total_master")
    return {
        "GROUP": group_name,
        "MAX_MOB": manifest.get("config", {}).get("max_mob", "-"),
        "TARGET_MOBS": ", ".join(
            map(str, manifest.get("config", {}).get("target_mobs", []))
        )
        or "-",
        "ROWS_RAW": manifest.get("summary", {}).get("ROWS_RAW", "-"),
        "ROWS_GROUP_TOTAL": len(df_group_total),
        "ALLOCATED_LOANS": manifest.get("summary", {}).get("ALLOCATED_LOANS", "-"),
        "DEL90_BLEND_ROWS": manifest.get("summary", {}).get("DEL90_BLEND_ROWS", "-"),
        "DEL90_BLEND_FILE": manifest.get("summary", {}).get("DEL90_BLEND_FILE", "-"),
        "GROUP_WORKBOOK": manifest.get("group_workbook") or "-",
        "LOAN_WORKBOOK": manifest.get("loan_workbook") or "-",
        "STAGING_DIR": str(stage_dir),
        "STATUS": "cached",
    }


def run_selected_groups(
    group_runs: Iterable[Dict],
    output_root: Path,
    staging_root: Path,
    selected_groups: Optional[Iterable[str]] = None,
    skip_existing_stage: bool = True,
    force_groups: Optional[Iterable[str]] = None,
    save_full_cache: bool = False,
) -> pd.DataFrame:
    defaults = get_default_settings()
    selected = {str(name) for name in selected_groups} if selected_groups else None
    force = {str(name) for name in (force_groups or [])}

    rows: List[Dict] = []
    for raw_cfg in group_runs:
        run_cfg = normalize_run_cfg(raw_cfg)
        if selected is not None and run_cfg["name"] not in selected:
            continue
        if (
            skip_existing_stage
            and run_cfg["name"] not in force
            and stage_exists(staging_root, run_cfg["name"])
        ):
            is_compatible, reason = is_stage_compatible(
                staging_root=staging_root,
                raw_cfg=run_cfg,
                defaults=defaults,
            )
            if is_compatible:
                if reason != "signature_match":
                    print(
                        f"[WARN] Using legacy stage compatibility for group "
                        f"{run_cfg['name']} ({reason})."
                    )
                rows.append(summary_from_stage(staging_root, run_cfg["name"]))
                continue
            print(
                f"[WARN] Stage exists but incompatible for group {run_cfg['name']} "
                f"({reason}). Rerun this group."
            )
        rows.append(
            run_group_pipeline(
                run_cfg,
                output_root=output_root,
                staging_root=staging_root,
                save_full_cache=save_full_cache,
                defaults=defaults,
            )
        )
    return pd.DataFrame(rows)


def recalibrate_selected_groups_from_stage(
    group_runs: Iterable[Dict],
    output_root: Path,
    staging_root: Path,
    selected_groups: Optional[Iterable[str]] = None,
    force_groups: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    defaults = get_default_settings()
    selected = {str(name) for name in selected_groups} if selected_groups else None
    force = {str(name) for name in (force_groups or [])}

    rows: List[Dict] = []
    for raw_cfg in group_runs:
        run_cfg = normalize_run_cfg(raw_cfg)
        if selected is not None and run_cfg["name"] not in selected:
            continue
        if run_cfg["name"] not in force and stage_exists(staging_root, run_cfg["name"]):
            rows.append(summary_from_stage(staging_root, run_cfg["name"]))
            continue
        rows.append(
            recalibrate_group_pipeline_from_stage(
                run_cfg,
                output_root=output_root,
                staging_root=staging_root,
                defaults=defaults,
            )
        )
    return pd.DataFrame(rows)


def build_master_total_from_staging(
    group_runs: Iterable[Dict],
    master_portfolio_name: str,
    output_root: Path,
    staging_root: Path,
    use_all_staged_groups: bool = False,
    include_groups: Optional[Iterable[str]] = None,
    strict_config_match: bool = True,
) -> Dict:
    output_root = Path(output_root)
    staging_root = Path(staging_root)
    output_root.mkdir(parents=True, exist_ok=True)

    defaults = get_default_settings()
    normalized_cfgs = [normalize_run_cfg(cfg) for cfg in group_runs]
    run_cfg_by_name = {cfg["name"]: cfg for cfg in normalized_cfgs}
    expected_group_names = [cfg["name"] for cfg in normalized_cfgs]
    staged_group_names = list_staged_groups(staging_root)

    if use_all_staged_groups:
        group_names = list(staged_group_names)
        extras = sorted(set(group_names) - set(expected_group_names))
        if extras:
            print(
                "[WARN] use_all_staged_groups=True includes groups outside GROUP_RUNS: "
                + ", ".join(extras)
            )
    else:
        group_names = list(expected_group_names)

    if include_groups is not None:
        include_set = {str(name) for name in include_groups}
        unknown_include = sorted(include_set - set(group_names))
        if unknown_include:
            print(
                "[WARN] include_groups not found in selected source list: "
                + ", ".join(unknown_include)
            )
        group_names = [name for name in group_names if name in include_set]

    group_names = list(dict.fromkeys(group_names))
    if not group_names:
        raise ValueError("No groups selected for master build.")

    missing_stage_groups = [
        name for name in group_names if not stage_exists(staging_root, name)
    ]
    if missing_stage_groups:
        raise ValueError(
            "Missing staged data for groups: " + ", ".join(sorted(missing_stage_groups))
        )

    if strict_config_match:
        mismatches = []
        skipped_checks = []
        legacy_compatible = []
        for group_name in group_names:
            expected_cfg = run_cfg_by_name.get(group_name)
            if expected_cfg is None:
                skipped_checks.append(group_name)
                continue
            compatible, reason = is_stage_compatible(
                staging_root=staging_root,
                raw_cfg=expected_cfg,
                defaults=defaults,
            )
            if not compatible:
                mismatches.append((group_name, reason))
            elif reason != "signature_match":
                legacy_compatible.append((group_name, reason))

        if mismatches:
            mismatch_text = "; ".join(
                f"{group_name} ({reason})" for group_name, reason in mismatches
            )
            raise ValueError(
                "Staged groups are incompatible with current GROUP_RUNS config: "
                + mismatch_text
                + ". Rerun these groups (FORCE_GROUPS or SKIP_EXISTING_STAGE=False) "
                "before building master total."
            )
        if skipped_checks:
            raise ValueError(
                "strict_config_match=True cannot validate staged groups not found in "
                "GROUP_RUNS: "
                + ", ".join(sorted(skipped_checks))
                + ". Set use_all_staged_groups=False, or include_groups to a subset in "
                "GROUP_RUNS, or set strict_config_match=False."
            )
        if legacy_compatible:
            print(
                "[WARN] Master is using legacy-compatible stages (no signature): "
                + ", ".join(
                    f"{group_name} ({reason})"
                    for group_name, reason in sorted(legacy_compatible)
                )
            )

    group_frames = []
    actual_info_base = {}
    summary_rows = []

    for group_name in group_names:
        stage_dir = group_stage_dir(staging_root, group_name)
        df_group_total = load_frame(stage_dir / "group_total_master")
        df_actual_info = load_frame(stage_dir / "group_actual_info")
        manifest = load_stage_manifest(staging_root, group_name)

        if df_group_total.empty:
            continue

        df_group_total = df_group_total.copy()
        df_group_total["VINTAGE_DATE"] = pd.to_datetime(df_group_total["VINTAGE_DATE"])
        group_frames.append(df_group_total)
        actual_info_base.update(frame_to_actual_info(df_actual_info))

        cfg = manifest.get("config", {})
        summary_rows.append(
            {
                "GROUP": group_name,
                "MAX_MOB": cfg.get("max_mob", "-"),
                "TARGET_MOBS": ", ".join(map(str, cfg.get("target_mobs", []))) or "-",
                "ROWS_GROUP_TOTAL": len(df_group_total),
                "STAGING_DIR": str(stage_dir),
            }
        )

    if not group_frames:
        raise ValueError("No staged group totals were found.")

    df_master_products = pd.concat(group_frames, ignore_index=True)
    df_master_portfolio = aggregate_products_to_portfolio(
        df_master_products, portfolio_name=master_portfolio_name
    )
    df_master_all = pd.concat([df_master_products, df_master_portfolio], ignore_index=True)

    actual_info_master = extend_actual_info_with_portfolio(
        actual_info_base, portfolio_name=master_portfolio_name
    )
    coverage = (
        df_master_products.groupby("MOB")["PRODUCT_TYPE"]
        .nunique()
        .rename("N_GROUPS")
        .reset_index()
        .sort_values("MOB")
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    master_file = output_root / f"{master_portfolio_name}_{timestamp}.xlsx"
    export_lifecycle_all_products_one_file(
        df_master_all, actual_info_master, filename=str(master_file)
    )

    master_stage_dir = staging_root / "_master"
    master_stage_dir.mkdir(parents=True, exist_ok=True)
    save_frame(df_master_all, master_stage_dir / "master_total_all")
    save_frame(coverage, master_stage_dir / "master_coverage")

    summary_df = pd.DataFrame(summary_rows)
    summary_csv = output_root / f"{master_portfolio_name}_run_summary_{timestamp}.csv"
    summary_df.to_csv(summary_csv, index=False)

    manifest = {
        "master_portfolio_name": master_portfolio_name,
        "run_time": datetime.now().isoformat(),
        "master_file": str(master_file),
        "summary_csv": str(summary_csv),
        "use_all_staged_groups": use_all_staged_groups,
        "strict_config_match": strict_config_match,
        "staged_groups_snapshot": staged_group_names,
        "groups_used": group_names,
    }
    (master_stage_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )

    return {
        "master_file": master_file,
        "summary_df": summary_df,
        "coverage": coverage,
        "groups_used": group_names,
    }
