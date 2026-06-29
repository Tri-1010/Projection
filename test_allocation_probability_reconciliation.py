import numpy as np
import pandas as pd

from src.config import BUCKETS_CANON, CFG
from src.rollrate.allocation_v2_ultra_fast import allocate_ultra_fast


def build_identity_matrix():
    matrix = pd.DataFrame(
        np.eye(len(BUCKETS_CANON)),
        index=BUCKETS_CANON,
        columns=BUCKETS_CANON,
    )
    return {"P": matrix}


def main():
    target_mob = 12
    vintage = pd.Timestamp("2024-01-01")

    df_loans = pd.DataFrame(
        [
            {
                CFG["loan"]: "LOAN_BAD",
                "PRODUCT_TYPE": "TEST",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                CFG["state"]: "DPD90+",
                CFG["mob"]: 11,
                CFG["ead"]: 100.0,
                "DISBURSAL_AMOUNT": 100.0,
            },
            {
                CFG["loan"]: "LOAN_GOOD",
                "PRODUCT_TYPE": "TEST",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                CFG["state"]: "DPD0",
                CFG["mob"]: 11,
                CFG["ead"]: 100.0,
                "DISBURSAL_AMOUNT": 100.0,
            },
        ]
    )

    df_lifecycle = pd.DataFrame(
        [
            {
                "PRODUCT_TYPE": "TEST",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                "MOB": target_mob,
                "IS_FORECAST": 1,
                "DEL30_PCT": 0.50,
                "DEL90_PCT": 0.50,
                "DPD0": 100.0,
                "DPD1+": 0.0,
                "DPD30+": 0.0,
                "DPD60+": 0.0,
                "DPD90+": 100.0,
                "PREPAY": 0.0,
                "WRITEOFF": 0.0,
                "SOLDOUT": 0.0,
            }
        ]
    )

    matrices_by_mob = {"TEST": {11: {"A": build_identity_matrix()}}}
    parent_fallback = {("TEST", "A"): build_identity_matrix()["P"]}

    df_result = allocate_ultra_fast(
        df_loans_latest=df_loans,
        df_lifecycle_final=df_lifecycle,
        matrices_by_mob=matrices_by_mob,
        target_mob=target_mob,
        parent_fallback=parent_fallback,
        seed=42,
    )

    bad_prob = float(
        df_result.loc[df_result[CFG["loan"]] == "LOAN_BAD", "PROB_DEL90"].iloc[0]
    )
    good_prob = float(
        df_result.loc[df_result[CFG["loan"]] == "LOAN_GOOD", "PROB_DEL90"].iloc[0]
    )
    total_ead_del90 = float(df_result["EAD_DEL90"].sum())
    target_ead_del90 = float(
        (df_result["DISBURSAL_AMOUNT"] * 0.50).sum()
    )

    assert bad_prob > good_prob, (bad_prob, good_prob)
    assert abs(total_ead_del90 - target_ead_del90) < 1e-6, (
        total_ead_del90,
        target_ead_del90,
    )
    bad_flag = int(
        df_result.loc[df_result[CFG["loan"]] == "LOAN_BAD", "DEL90_FLAG"].iloc[0]
    )
    good_flag = int(
        df_result.loc[df_result[CFG["loan"]] == "LOAN_GOOD", "DEL90_FLAG"].iloc[0]
    )
    assert bad_flag == 1 and good_flag == 0, (bad_flag, good_flag)

    print("PASS")
    print(f"LOAN_BAD PROB_DEL90 = {bad_prob:.6f}")
    print(f"LOAN_GOOD PROB_DEL90 = {good_prob:.6f}")
    print(f"TOTAL EAD_DEL90 = {total_ead_del90:.6f}")

    fixed_states = pd.DataFrame(
        [
            {
                CFG["loan"]: "LOAN_WRITEOFF",
                "PRODUCT_TYPE": "TEST",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                CFG["state"]: "WRITEOFF",
                CFG["mob"]: 11,
                CFG["ead"]: 0.0,
                "DISBURSAL_AMOUNT": 100.0,
            },
            {
                CFG["loan"]: "LOAN_PREPAY",
                "PRODUCT_TYPE": "TEST",
                "RISK_SCORE": "A",
                "VINTAGE_DATE": vintage,
                CFG["state"]: "PREPAY",
                CFG["mob"]: 11,
                CFG["ead"]: 0.0,
                "DISBURSAL_AMOUNT": 100.0,
            },
        ]
    )
    fixed_lifecycle = df_lifecycle.copy()
    fixed_lifecycle["DEL30_PCT"] = 0.50
    fixed_lifecycle["DEL90_PCT"] = 0.50
    fixed_result = allocate_ultra_fast(
        df_loans_latest=fixed_states,
        df_lifecycle_final=fixed_lifecycle,
        matrices_by_mob={},
        target_mob=target_mob,
        parent_fallback={},
        seed=42,
    )
    writeoff = fixed_result[fixed_result[CFG["loan"]] == "LOAN_WRITEOFF"].iloc[0]
    prepay = fixed_result[fixed_result[CFG["loan"]] == "LOAN_PREPAY"].iloc[0]
    assert float(writeoff["PROB_DEL90"]) == 1.0
    assert int(writeoff["DEL90_FLAG"]) == 1
    assert float(prepay["PROB_DEL90"]) == 0.0
    assert int(prepay["DEL90_FLAG"]) == 0


if __name__ == "__main__":
    main()
