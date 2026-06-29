"""
Enhanced export function for Lifecycle with Config Info sheet
"""
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict


def export_lifecycle_with_config_info(
    df_del_prod,
    actual_info,
    df_raw,
    config_params,
    filename="Lifecycle_All_Products.xlsx"
):
    """
    Xuất Lifecycle_All_Products.xlsx với:
    1. Sheet "Config_Info": Thông tin cấu hình và metadata
    2. Các sheet Product × Metric như cũ (DEL30, DEL60, DEL90)
    
    Args:
        df_del_prod: DataFrame lifecycle data
        actual_info: Dict mapping (product, cohort) -> max_actual_mob
        df_raw: DataFrame raw data để lấy thông tin tổng quan
        config_params: Dict chứa các thông số config
        filename: Tên file output
    
    config_params example:
        {
            'DATA_PATH': 'path/to/data',
            'MAX_MOB': 13,
            'TARGET_MOBS': [12],
            'SEGMENT_COLS': ['PRODUCT_TYPE', 'RISK_SCORE'],
            'MIN_OBS': 100,
            'MIN_EAD': 100,
            'WEIGHT_METHOD': 'exp',
            'ROLL_WINDOW': 20,
            'DECAY_LAMBDA': 0.97,
        }
    """
    
    metric_map = {
        "DEL30": "DEL30_PCT",
        "DEL60": "DEL60_PCT",
        "DEL90": "DEL90_PCT",
    }

    products = df_del_prod["PRODUCT_TYPE"].unique()

    with pd.ExcelWriter(filename, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as writer:

        workbook = writer.book

        # ============================
        # 1. CREATE CONFIG_INFO SHEET
        # ============================
        _create_config_info_sheet(writer, workbook, df_raw, df_del_prod, config_params)

        # ============================
        # 2. FORMAT DEFINITIONS FOR DATA SHEETS
        # ============================

        fmt_header = workbook.add_format({
            "bold": True,
            "bg_color": "#D9D9D9",
            "border": 2,
            "align": "center",
        })

        fmt_cohort = workbook.add_format({
            "border": 1,
            "num_format": "yyyy-mm-dd",
        })

        fmt_data = workbook.add_format({
            "border": 1,
            "num_format": "0.00%",
        })

        fmt_forecast = workbook.add_format({
            "bg_color": "#FFF3B0",
            "border": 1,
            "num_format": "0.00%",
        })

        # Forecast start marker: ô forecast đầu tiên có viền đỏ trên/trái để thấy ranh giới
        fmt_forecast_start = workbook.add_format({
            "bg_color": "#FFF3B0",
            "border": 1,
            "top": 5,
            "top_color": "red",
            "left": 5,
            "left_color": "red",
            "num_format": "0.00%",
        })

        # Title format
        fmt_title = workbook.add_format({
            "bold": True,
            "font_size": 20,
            "font_color": "#00008B",
            "align": "center",
            "valign": "vcenter",
        })

        # ============================
        # 3. LOOP ALL PRODUCTS
        # ============================

        for product in products:

            df_prod = df_del_prod[df_del_prod["PRODUCT_TYPE"] == product]

            # Loop metrics (DEL30 / DEL60 / DEL90)
            for metric_name, colname in metric_map.items():

                sheet_name = f"{product}_{metric_name}"[:31]

                # Pivot table
                df_pivot = df_prod.pivot_table(
                    index="VINTAGE_DATE",
                    columns="MOB",
                    values=colname,
                ).fillna(0.0)
                df_pivot.index.name = "Cohort"

                n_rows, n_cols = df_pivot.shape

                # Write raw data starting at row 5 (startrow=4)
                df_pivot.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    startrow=4,
                    startcol=1,
                    header=False,
                    index=False,
                )

                worksheet = writer.sheets[sheet_name]
                worksheet.hide_gridlines(2)

                # ============================
                # TITLE ROW (A1:J1)
                # ============================
                title_text = f"{product}_{metric_name} Actual & Forecast"
                worksheet.merge_range("A1:J1", title_text, fmt_title)

                # ============================
                # HEADER ROW (row index 3 => dòng 4)
                # ============================
                header_row = 3
                worksheet.write(header_row, 0, "Cohort", fmt_header)

                for col_idx, mob in enumerate(df_pivot.columns, start=1):
                    worksheet.write(header_row, col_idx, mob, fmt_header)

                # ============================
                # HEATMAP RANGE
                # ============================
                if n_rows > 0 and n_cols > 0:
                    worksheet.conditional_format(
                        4, 1,
                        4 + n_rows - 1, 1 + n_cols - 1,
                        {
                            "type": "3_color_scale",
                            "min_color": "#63BE7B",
                            "mid_color": "#FFEB84",
                            "max_color": "#F8696B",
                        }
                    )

                # ============================
                # FORMAT TỪNG CELL
                # ============================
                for i, cohort in enumerate(df_pivot.index):
                    r_idx = 4 + i

                    # Cột A: Cohort
                    worksheet.write(r_idx, 0, cohort, fmt_cohort)

                    max_actual = actual_info.get((product, cohort), None)

                    for j, mob in enumerate(df_pivot.columns):
                        c_idx = 1 + j
                        raw_value = df_pivot.iat[i, j]

                        try:
                            value = round(float(raw_value), 4)
                        except:
                            value = raw_value

                        # Chọn format actual vs forecast
                        if (max_actual is not None) and (mob == max_actual + 1):
                            fmt = fmt_forecast_start
                        elif (max_actual is not None) and (mob > max_actual):
                            fmt = fmt_forecast
                        else:
                            fmt = fmt_data

                        worksheet.write(r_idx, c_idx, value, fmt)

                # ============================
                # AUTO COLUMN WIDTH
                # ============================

                worksheet.set_column(0, 0, 12)

                for j, mob in enumerate(df_pivot.columns):
                    width = max(8, len(str(mob)))
                    worksheet.set_column(1 + j, 1 + j, width + 2)

        # ============================
        # 4. MOVE CONFIG_INFO AND PORTFOLIO SHEETS TO TOP
        # ============================
        sheetnames = writer.book.worksheets()
        
        config_sheet = [s for s in sheetnames if s.name == "Config_Info"]
        portfolio_sheets = [s for s in sheetnames if "Portfolio" in s.name and s.name != "Config_Info"]
        other_sheets = [s for s in sheetnames if "Portfolio" not in s.name and s.name != "Config_Info"]
        
        # Xếp lại: Config_Info đầu tiên, Portfolio thứ hai, rồi các sheet còn lại
        writer.book.worksheets_objs = config_sheet + portfolio_sheets + other_sheets

    print(f"✔ Export lifecycle với Config_Info thành công → {filename}")


def _create_config_info_sheet(writer, workbook, df_raw, df_del_prod, config_params):
    """
    Tạo sheet Config_Info chứa:
    - Thông tin cấu hình model
    - Metadata về dữ liệu đầu vào
    - Thông tin tổng quan
    """
    
    # Create formats
    fmt_section_header = workbook.add_format({
        "bold": True,
        "font_size": 14,
        "font_color": "#FFFFFF",
        "bg_color": "#4472C4",
        "align": "left",
        "valign": "vcenter",
        "border": 1,
    })
    
    fmt_param_name = workbook.add_format({
        "bold": True,
        "bg_color": "#D9E1F2",
        "border": 1,
        "align": "left",
    })
    
    fmt_param_value = workbook.add_format({
        "border": 1,
        "align": "left",
    })
    
    fmt_timestamp = workbook.add_format({
        "italic": True,
        "font_color": "#7F7F7F",
    })
    
    # Create worksheet
    worksheet = workbook.add_worksheet("Config_Info")
    worksheet.hide_gridlines(2)
    
    # Set column widths
    worksheet.set_column(0, 0, 35)  # Column A: Parameter names
    worksheet.set_column(1, 1, 50)  # Column B: Values
    
    row = 0
    
    # ============================
    # HEADER: TIMESTAMP
    # ============================
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.write(row, 0, f"Generated: {timestamp}", fmt_timestamp)
    row += 2
    
    # ============================
    # SECTION 1: MODEL CONFIGURATION
    # ============================
    worksheet.merge_range(row, 0, row, 1, "📋 MODEL CONFIGURATION", fmt_section_header)
    row += 1
    
    config_items = [
        ("Data Path", config_params.get('DATA_PATH', 'N/A')),
        ("Max MOB", config_params.get('MAX_MOB', 'N/A')),
        ("Target MOBs", str(config_params.get('TARGET_MOBS', 'N/A'))),
        ("Segment Columns", ", ".join(config_params.get('SEGMENT_COLS', []))),
        ("Min Observations", config_params.get('MIN_OBS', 'N/A')),
        ("Min EAD", config_params.get('MIN_EAD', 'N/A')),
        ("Weight Method", config_params.get('WEIGHT_METHOD', 'N/A')),
        ("Roll Window", config_params.get('ROLL_WINDOW', 'N/A')),
        ("Decay Lambda", config_params.get('DECAY_LAMBDA', 'N/A')),
    ]
    
    for param_name, param_value in config_items:
        worksheet.write(row, 0, param_name, fmt_param_name)
        worksheet.write(row, 1, param_value, fmt_param_value)
        row += 1
    
    row += 1
    
    # ============================
    # SECTION 2: INPUT DATA SUMMARY
    # ============================
    worksheet.merge_range(row, 0, row, 1, "📊 INPUT DATA SUMMARY", fmt_section_header)
    row += 1
    
    # Calculate data statistics (optimized for large datasets)
    total_rows = len(df_raw)
    
    # Use nunique() directly without creating intermediate arrays
    total_loans = df_raw['AGREEMENT_ID'].nunique() if 'AGREEMENT_ID' in df_raw.columns else 'N/A'
    
    # Get unique products efficiently
    if 'PRODUCT_TYPE' in df_raw.columns:
        products = sorted(df_raw['PRODUCT_TYPE'].unique().tolist())
    else:
        products = []
    
    # Get cutoff date range using min/max directly (no intermediate array)
    if 'CUTOFF_DATE' in df_raw.columns:
        min_cutoff = df_raw['CUTOFF_DATE'].min()
        max_cutoff = df_raw['CUTOFF_DATE'].max()
        cutoff_range = f"{min_cutoff} to {max_cutoff}"
    else:
        cutoff_range = "N/A"
    
    # Get disbursal date range using min/max directly (no intermediate array)
    if 'DISBURSAL_DATE' in df_raw.columns:
        min_disb = df_raw['DISBURSAL_DATE'].min()
        max_disb = df_raw['DISBURSAL_DATE'].max()
        if pd.notna(min_disb) and pd.notna(max_disb):
            disb_range = f"{min_disb.strftime('%Y-%m-%d')} to {max_disb.strftime('%Y-%m-%d')}"
        else:
            disb_range = "N/A"
    else:
        disb_range = "N/A"
    
    # Sum operations are efficient
    total_ead = df_raw['PRINCIPLE_OUTSTANDING'].sum() if 'PRINCIPLE_OUTSTANDING' in df_raw.columns else 'N/A'
    total_disb = df_raw['DISBURSAL_AMOUNT'].sum() if 'DISBURSAL_AMOUNT' in df_raw.columns else 'N/A'
    
    # nunique() is efficient
    risk_scores = df_raw['RISK_SCORE'].nunique() if 'RISK_SCORE' in df_raw.columns else 'N/A'
    
    data_items = [
        ("Total Rows", f"{total_rows:,}"),
        ("Total Loans", f"{total_loans:,}" if isinstance(total_loans, int) else total_loans),
        ("Products", ", ".join(products)),
        ("Cutoff Date Range", cutoff_range),
        ("Disbursal Date Range", disb_range),
        ("Total EAD", f"{total_ead:,.2f}" if isinstance(total_ead, (int, float)) else total_ead),
        ("Total Disbursement", f"{total_disb:,.2f}" if isinstance(total_disb, (int, float)) else total_disb),
        ("Risk Score Groups", f"{risk_scores}" if isinstance(risk_scores, int) else risk_scores),
    ]
    
    for param_name, param_value in data_items:
        worksheet.write(row, 0, param_name, fmt_param_name)
        worksheet.write(row, 1, param_value, fmt_param_value)
        row += 1
    
    row += 1
    
    # ============================
    # SECTION 3: OUTPUT SUMMARY
    # ============================
    worksheet.merge_range(row, 0, row, 1, "📈 OUTPUT SUMMARY", fmt_section_header)
    row += 1
    
    # Calculate output statistics (optimized)
    total_cohorts = df_del_prod.groupby(['PRODUCT_TYPE', 'VINTAGE_DATE']).ngroups
    
    # Get vintage range using min/max directly (no intermediate array)
    if 'VINTAGE_DATE' in df_del_prod.columns:
        min_vintage = df_del_prod['VINTAGE_DATE'].min()
        max_vintage = df_del_prod['VINTAGE_DATE'].max()
        if pd.notna(min_vintage) and pd.notna(max_vintage):
            min_vintage_str = pd.to_datetime(min_vintage).strftime("%Y-%m-%d")
            max_vintage_str = pd.to_datetime(max_vintage).strftime("%Y-%m-%d")
            vintage_range = f"{min_vintage_str} to {max_vintage_str}"
        else:
            vintage_range = "N/A"
    else:
        vintage_range = "N/A"
    
    max_mob_output = df_del_prod['MOB'].max() if 'MOB' in df_del_prod.columns else 'N/A'
    
    # Count actual vs forecast rows
    if 'IS_FORECAST' in df_del_prod.columns:
        actual_rows = (df_del_prod['IS_FORECAST'] == 0).sum()
        forecast_rows = (df_del_prod['IS_FORECAST'] == 1).sum()
    else:
        actual_rows = 'N/A'
        forecast_rows = 'N/A'
    
    output_items = [
        ("Total Cohorts", f"{total_cohorts:,}"),
        ("Vintage Range", vintage_range),
        ("Max MOB in Output", f"{max_mob_output}"),
        ("Actual Data Points", f"{actual_rows:,}" if isinstance(actual_rows, int) else actual_rows),
        ("Forecast Data Points", f"{forecast_rows:,}" if isinstance(forecast_rows, int) else forecast_rows),
    ]
    
    for param_name, param_value in output_items:
        worksheet.write(row, 0, param_name, fmt_param_name)
        worksheet.write(row, 1, param_value, fmt_param_value)
        row += 1
    
    row += 2
    
    # ============================
    # FOOTER NOTE
    # ============================
    note_format = workbook.add_format({
        "italic": True,
        "font_size": 9,
        "font_color": "#7F7F7F",
        "text_wrap": True,
    })
    
    note_text = (
        "📝 Note: This configuration sheet contains all parameters and metadata needed to "
        "reproduce the results in this file. Keep this information for audit and validation purposes."
    )
    
    worksheet.merge_range(row, 0, row + 2, 1, note_text, note_format)
