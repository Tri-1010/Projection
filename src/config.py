from pathlib import Path
import pandas as pd


# ===== Resolve project root from this file path (stable across notebooks/scripts) =====
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # .../RR_model
OUT_ROOT     = PROJECT_ROOT / "outputs"

# Data source defaults to parquet for offline runs
DATA_SOURCE  = "parquet"  # options: "parquet" | "oracle"
PARQUET_DIR  = PROJECT_ROOT / "data" / "parquet"       # <-- FIXED: absolute path
PARQUET_FILE = None  # or "rollrate_base.parquet" if bạn dùng 1 file duy nhất

EXCEL_FILE   = PROJECT_ROOT / "data" / "rollrate_input.xlsx"   # 👈 đường dẫn mặc định nếu dùng Excel
EXCEL_SHEET  = "Data"    
# === COLUMNS CONFIG & others giữ nguyên ===

# ===========================
# A. Date Format Config
# ===========================
# Nếu DISBURSAL_DATE, CUTOFF_DATE là định dạng YYYYMM (int hoặc string)
# thì set DATE_FORMAT = "YYYYMM"
# Nếu là datetime thì set DATE_FORMAT = "datetime"
DATE_FORMAT = "YYYYMM"  # "YYYYMM" hoặc "datetime"


def parse_date(value):
    """
    Parse date từ nhiều định dạng khác nhau.
    - YYYYMM (int/string): 202501 -> 2025-01-01
    - datetime: giữ nguyên
    - string date: parse bình thường
    """
    if pd.isna(value):
        return pd.NaT
    
    # Nếu là int hoặc string dạng YYYYMM
    if isinstance(value, (int, float)):
        value = int(value)
        if 190001 <= value <= 209912:  # YYYYMM range
            year = value // 100
            month = value % 100
            return pd.Timestamp(year=year, month=month, day=1)
    
    # Nếu là string
    if isinstance(value, str):
        value = value.strip()
        # YYYYMM format
        if len(value) == 6 and value.isdigit():
            year = int(value[:4])
            month = int(value[4:6])
            return pd.Timestamp(year=year, month=month, day=1)
        # YYYY-MM format
        if len(value) == 7 and value[4] == '-':
            return pd.Timestamp(value + '-01')
    
    # Fallback: dùng pd.to_datetime
    try:
        return pd.to_datetime(value)
    except:
        return pd.NaT


def parse_date_column(series):
    """Parse toàn bộ column date."""
    return series.apply(parse_date)

# ===========================
# B. Model parameters
# ===========================
MIN_OBS = 100         # Số quan sát tối thiểu
MIN_EAD = 1e2         # Tổng dư nợ tối thiểu để build transition

# === K VALUE CONFIG ===
# K_GLOBAL_MULTIPLIER: Hệ số nhân chung cho tất cả k_final_by_mob
# - Nếu K_GLOBAL_MULTIPLIER = 1.0: Không thay đổi (mặc định)
# - Nếu K_GLOBAL_MULTIPLIER = 0.8: Giảm 20% tất cả K values → forecast tăng chậm hơn
# - Nếu K_GLOBAL_MULTIPLIER = 1.2: Tăng 20% tất cả K values → forecast tăng nhanh hơn
# - Công thức: k_adjusted = k_calibrated * K_GLOBAL_MULTIPLIER (clip to [0, 1])
K_GLOBAL_MULTIPLIER = 1  # Hệ số nhân chung (1.0 = không thay đổi)

# K_POST_MATURE: Giá trị K sử dụng cho MOB >= TARGET_MOB (sau khi mature)
# - Nếu K_POST_MATURE = None: Sử dụng K từ calibration (k_final_by_mob)
# - Nếu K_POST_MATURE = 0.3: Sử dụng K = 0.3 cho tất cả MOB >= TARGET_MOB
# - Giá trị khuyến nghị: 0.3 - 0.5 (để giảm slope sau mature)
# - Lưu ý: K_POST_MATURE được áp dụng SAU K_GLOBAL_MULTIPLIER
K_POST_MATURE = 0.03   # K value cho MOB >= TARGET_MOB (None = dùng calibrated K)
K_POST_MATURE_DEL90 = None  # DEL90-specific post-mature K override (None = dùng calibrated K)
# === BUCKETS CONFIG ===
# Khai báo đầy đủ các buckets - code sẽ tự động filter chỉ lấy các cột có trong data
BUCKETS_30P = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
BUCKETS_60P = ["DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
BUCKETS_90P = ["DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
# === COLUMNS CONFIG ===
CFG = dict(
    loan="AGREEMENT_ID",
    mob="MOB",
    state="STATE_MODEL",
    orig_date="DISBURSAL_DATE",
    ead="PRINCIPLE_OUTSTANDING",
    disb="DISBURSAL_AMOUNT",
    cutoff="CUTOFF_DATE",
)

# === SEGMENTATION CONFIG ===
# Các cột dùng để phân nhóm (segment) khi tính transition matrix và forecast
# Thay đổi list này để thêm/bớt segment dimensions
# Lưu ý: Code sử dụng 2 cột cố định: PRODUCT_TYPE và RISK_SCORE
# - PRODUCT_TYPE: giữ nguyên từ data
# - RISK_SCORE: sẽ được tạo tự động từ các cột trong SEGMENT_COLS (trừ PRODUCT_TYPE)
#
# Ví dụ:
# - SEGMENT_COLS = ["PRODUCT_TYPE", "RISK_SCORE"] => giữ nguyên RISK_SCORE từ data
# - SEGMENT_COLS = ["PRODUCT_TYPE", "RISK_SCORE", "GENDER"] => RISK_SCORE = "RISK_SCORE_GENDER"
#SEGMENT_COLS = ["PRODUCT_TYPE", "RISK_SCORE", "GENDER", "LA_GROUP"] => RISK_SCORE = "RISK_SCORE_GENDER_LA_GROUP"
#SEGMENT_COLS = ["PRODUCT_TYPE", "RISK_SCORE", "GENDER", "LA_GROUP"]  # Mặc định: giữ nguyên RISK_SCORE từ data
#SEGMENT_COLS = ["PRODUCT_TYPE", "RISK_SCORE","SALE_CHANNEL"]
SEGMENT_COLS = ["PRODUCT_TYPE", "RISK_SCORE"]
def get_cohort_cols():
    """Trả về list columns để định nghĩa 1 cohort: SEGMENT_COLS + VINTAGE_DATE"""
    return ["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE"]

def get_cohort_mob_cols():
    """Trả về list columns để định nghĩa 1 cohort tại 1 MOB"""
    return ["PRODUCT_TYPE", "RISK_SCORE", "VINTAGE_DATE", "MOB"]

def create_segment_columns(df):
    """
    Tạo cột PRODUCT_TYPE và RISK_SCORE từ SEGMENT_COLS.
    
    Logic:
    - Nếu SEGMENT_COLS = ["PRODUCT_TYPE", "RISK_SCORE"]: giữ nguyên
    - Nếu SEGMENT_COLS = ["PRODUCT_TYPE", "GRADE", "GENDER", "LA_GROUP"]:
      + PRODUCT_TYPE: giữ nguyên
      + RISK_SCORE = "GRADE_GENDER_LA_GROUP" (ghép các giá trị)
    
    Returns:
        DataFrame với cột PRODUCT_TYPE và RISK_SCORE đã được chuẩn hóa
    """
    df = df.copy()
    
    # Lấy các cột segment (trừ PRODUCT_TYPE)
    other_cols = [c for c in SEGMENT_COLS if c != "PRODUCT_TYPE"]
    
    if not other_cols:
        # Không có cột nào khác, tạo RISK_SCORE mặc định
        if "RISK_SCORE" not in df.columns:
            df["RISK_SCORE"] = "ALL"
    elif other_cols == ["RISK_SCORE"]:
        # Chỉ có RISK_SCORE, giữ nguyên
        df["RISK_SCORE"] = df["RISK_SCORE"].astype(str)
    else:
        # Ghép nhiều cột thành RISK_SCORE
        # Kiểm tra các cột có tồn tại không
        missing_cols = [c for c in other_cols if c not in df.columns]
        if missing_cols:
            raise KeyError(f"SEGMENT_COLS chứa các cột không tồn tại trong data: {missing_cols}")
        
        # Ghép các cột thành RISK_SCORE
        df["RISK_SCORE"] = df[other_cols].astype(str).agg("_".join, axis=1)
        print(f"   ✅ Tạo RISK_SCORE từ {other_cols}: {df['RISK_SCORE'].nunique()} unique values")
    
    # Đảm bảo PRODUCT_TYPE là string
    if "PRODUCT_TYPE" in df.columns:
        df["PRODUCT_TYPE"] = df["PRODUCT_TYPE"].astype(str)
    
    return df

SEGMENT_MAP = {
    "RISK_SCORE": ["LOW", "MEDIUM", "HIGH"],
    "PRODUCT_TYPE": ["PL", "CC"],
}


# === SMOOTHING CONFIG ===
ALPHA_SMOOTH = 0.5

# === STATE DEFINITIONS ===
BUCKETS_CANON = [
    "DPD0", "DPD1+", "DPD30+", "DPD60+", "DPD90+",
    "PREPAY", "WRITEOFF", "SOLDOUT"
]

#ABSORBING_BASE = ["WRITEOFF", "PREPAY", "SOLDOUT"]
ABSORBING_BASE = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"] # PD model

DEFAULT = {"DPD90+"}

# === MODEL CONFIG ===
WEIGHT_METHOD = "exp"
#WEIGHT_METHOD = None
ROLL_WINDOW = 20
CFG["WEIGHT_METHOD"] = WEIGHT_METHOD
CFG["ROLL_WINDOW"] = ROLL_WINDOW
DECAY_LAMBDA = 0.5 ** (1/20)
CFG["DECAY_LAMBDA"] = DECAY_LAMBDA
# === MACRO & COLLX ADJUSTMENT CONFIG (optional, not wired by default) ===
MACRO_INDICATORS = {
    "GDP_GROWTH": {"weight": -0.3},
    "UNEMPLOYMENT_RATE": {"weight": +0.5},
    "CPI": {"weight": +0.2},
    "POLICY_RATE": {"weight": +0.3},
}
COLLX_CONFIG = {
    "COLLX_INDEX": {
        "weight": -0.4,
        "ref_value": 1.0,
        "min_adj": -0.3,
        "max_adj": +0.3,
    }
}
ADJUST_METHOD = "multiplicative"
MACRO_LAG = 1
MACRO_SOURCE = "sql/macro_data.sql"
COLLX_SOURCE = "sql/collx_index.sql"


# ===========================
# C. Excel Export Helper
# ===========================
EXCEL_MAX_ROWS = 1_000_000  # Excel limit is 1,048,576, use 1M for safety


def export_large_dataframe(df, filepath, sheet_prefix="Data", index=False):
    """
    Export DataFrame lớn ra Excel, tự động chia thành nhiều sheet nếu vượt quá giới hạn.
    
    Args:
        df: DataFrame cần export
        filepath: Đường dẫn file Excel (str hoặc Path)
        sheet_prefix: Tên prefix cho sheet (mặc định "Data")
        index: Có ghi index không (mặc định False)
    
    Returns:
        int: Số sheet đã tạo
    
    Example:
        export_large_dataframe(df_loan_forecast, "outputs/Loan_Forecast.xlsx", "Loans")
        # Nếu df có 2.5M rows -> tạo 3 sheets: Loans_1, Loans_2, Loans_3
    """
    filepath = Path(filepath)
    n_rows = len(df)
    
    if n_rows <= EXCEL_MAX_ROWS:
        # Đủ nhỏ, ghi 1 sheet
        df.to_excel(filepath, sheet_name=sheet_prefix, index=index, engine="xlsxwriter")
        print(f"   ✅ Exported {n_rows:,} rows to {filepath}")
        return 1
    
    # Cần chia nhiều sheet
    n_sheets = (n_rows // EXCEL_MAX_ROWS) + 1
    print(f"   ⚠️ Data có {n_rows:,} rows > {EXCEL_MAX_ROWS:,} limit")
    print(f"   📊 Chia thành {n_sheets} sheets...")
    
    with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
        for i in range(n_sheets):
            start_idx = i * EXCEL_MAX_ROWS
            end_idx = min((i + 1) * EXCEL_MAX_ROWS, n_rows)
            
            sheet_name = f"{sheet_prefix}_{i+1}"
            df_chunk = df.iloc[start_idx:end_idx]
            df_chunk.to_excel(writer, sheet_name=sheet_name, index=index)
            
            print(f"      Sheet {sheet_name}: rows {start_idx:,} → {end_idx:,} ({len(df_chunk):,} rows)")
    
    print(f"   ✅ Exported {n_rows:,} rows to {filepath} ({n_sheets} sheets)")
    return n_sheets


def export_loan_forecast_excel(df, filepath, target_mobs=None, include_del_sheets=True):
    """
    Export loan forecast ra Excel với nhiều sheets.
    Tự động chia nhỏ nếu data quá lớn.
    
    Args:
        df: DataFrame loan forecast
        filepath: Đường dẫn file Excel
        target_mobs: List MOBs (vd: [12, 24]) để tạo sheet DEL riêng
        include_del_sheets: Có tạo sheet riêng cho DEL90 không
    
    Example:
        export_loan_forecast_excel(
            df_loan_forecast, 
            "outputs/Loan_Forecast.xlsx",
            target_mobs=[12, 24],
            include_del_sheets=True
        )
    """
    filepath = Path(filepath)
    n_rows = len(df)
    
    if n_rows <= EXCEL_MAX_ROWS:
        # Đủ nhỏ, ghi bình thường với nhiều sheets
        with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="All_Loans", index=False)
            
            if include_del_sheets and target_mobs:
                for mob in target_mobs:
                    col = f'DEL90_FLAG_MOB{mob}'
                    if col in df.columns:
                        df_del = df[df[col] == 1]
                        if len(df_del) > 0:
                            df_del.to_excel(writer, sheet_name=f"DEL90_MOB{mob}", index=False)
        
        print(f"   ✅ Exported {n_rows:,} rows to {filepath}")
        return
    
    # Data quá lớn, cần chia nhỏ
    print(f"   ⚠️ Data có {n_rows:,} rows > {EXCEL_MAX_ROWS:,} limit")
    
    n_sheets = (n_rows // EXCEL_MAX_ROWS) + 1
    print(f"   📊 Chia All_Loans thành {n_sheets} sheets...")
    
    with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
        # Chia All_Loans thành nhiều sheets
        for i in range(n_sheets):
            start_idx = i * EXCEL_MAX_ROWS
            end_idx = min((i + 1) * EXCEL_MAX_ROWS, n_rows)
            
            sheet_name = f"All_Loans_{i+1}" if n_sheets > 1 else "All_Loans"
            df_chunk = df.iloc[start_idx:end_idx]
            df_chunk.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"      {sheet_name}: {len(df_chunk):,} rows")
        
        # DEL sheets (thường nhỏ hơn nhiều)
        if include_del_sheets and target_mobs:
            for mob in target_mobs:
                col = f'DEL90_FLAG_MOB{mob}'
                if col in df.columns:
                    df_del = df[df[col] == 1]
                    if len(df_del) > 0:
                        if len(df_del) <= EXCEL_MAX_ROWS:
                            df_del.to_excel(writer, sheet_name=f"DEL90_MOB{mob}", index=False)
                            print(f"      DEL90_MOB{mob}: {len(df_del):,} rows")
                        else:
                            # DEL cũng quá lớn, chia nhỏ
                            n_del_sheets = (len(df_del) // EXCEL_MAX_ROWS) + 1
                            for j in range(n_del_sheets):
                                s = j * EXCEL_MAX_ROWS
                                e = min((j + 1) * EXCEL_MAX_ROWS, len(df_del))
                                df_del.iloc[s:e].to_excel(
                                    writer, 
                                    sheet_name=f"DEL90_MOB{mob}_{j+1}", 
                                    index=False
                                )
    
    print(f"   ✅ Exported {n_rows:,} rows to {filepath}")
