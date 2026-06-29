# ✅ Diagnostic Section Added to Markovchain.ipynb

## What Was Done

Successfully added a comprehensive diagnostic section (Section 8) to `notebooks/Markovchain.ipynb` to help identify why the DEL curve continues increasing at high MOB instead of flattening.

## New Section Structure

### Section 8: 🔍 DIAGNOSTIC: DEL CURVE ANALYSIS

The new section includes 6 cells:

1. **8.1 Import Diagnostic Scripts** - Imports the diagnostic functions
2. **8.2 Run Main Diagnostic** - Comprehensive analysis checking:
   - K values at MOB 25+
   - % cohorts using fallback at MOB 24
   - P_24 vs Parent Fallback comparison
   - Aggregation effects
   - Individual cohort analysis
3. **8.3 Check P_24 Quality** - Detailed analysis of P_24 matrix
4. **8.4 Visualize DEL Curve** - Creates charts for sample cohort
5. **8.5 Summary & Recommendations** - Markdown with solution examples
6. **8.6 Apply Fix** - Example code to apply fixes (commented out)

## How to Use

### Step 1: Open the Notebook

```bash
# Open in Jupyter
jupyter notebook notebooks/Markovchain.ipynb

# Or open in VS Code
code notebooks/Markovchain.ipynb
```

### Step 2: Run All Cells Up to Section 8

Run all cells from the beginning through Section 7 (Model Evaluation) to ensure all variables are available:
- `matrices_by_mob`
- `parent_fallback`
- `k_final_by_mob`
- `forecast_calibrated`
- `disb_total_by_vintage`
- `df_product` (optional)

### Step 3: Run Diagnostic Cells

Execute the cells in Section 8 one by one:

**Cell 8.1** - Import diagnostic scripts
```python
from diagnose_why_increase_after_24 import diagnose_why_increase_after_24
from check_p24_quality import check_p24_quality
from diagnose_del_curve import diagnose_del_curve
```

**Cell 8.2** - Run main diagnostic
This will print a comprehensive report showing:
- ✅ or ❌ indicators for each potential issue
- Specific values and percentages
- Clear conclusions and recommendations

**Cell 8.3** - Check P_24 quality (optional)
Detailed analysis of a sample cohort's P_24 matrix

**Cell 8.4** - Visualize DEL curve (optional)
Creates a chart showing the DEL curve for a sample cohort

### Step 4: Read the Results

The diagnostic will clearly indicate which issue(s) you have:

#### Issue 1: K Values Too High
```
❌ Phát hiện 8 MOBs có K quá cao:
   - MOB 25: k=0.920
   - MOB 26: k=0.950
   ...
→ K cao → Tin Markov → Gây movement → DEL tăng
```

#### Issue 2: Many Cohorts Use Fallback
```
❌ Quá nhiều cohorts dùng fallback!
Cohorts dùng fallback ở MOB 24: 20 (40.0%)
→ Các cohorts này dùng parent fallback (có movement cao)
→ Gây DEL tăng ở MOB 25+
```

#### Issue 3: Aggregation Effect
```
❌ Nhiều cohorts vẫn tăng sau MOB 24
Top cohorts tăng mạnh:
- C/650+_10M-_POS/2023-12-01: slope = 0.002500 (0.2500%/month)
  → ❌ Cohort này dùng FALLBACK ở MOB 24!
```

### Step 5: Apply the Fix

Based on the diagnostic results, uncomment and run the appropriate solution in Cell 8.6:

**Solution 1: Cap K at MOB 25+** (if K too high)
```python
for mob in range(25, 37):
    if mob in k_final_by_mob:
        k_final_by_mob[mob] = min(k_final_by_mob[mob], 0.3)
    else:
        k_final_by_mob[mob] = 0.3

# Re-run forecast
forecast_calibrated = forecast_all_vintages_partial_step(...)
```

**Solution 2: Increase MIN_OBS/MIN_EAD** (if many cohorts use fallback)
```python
# Edit src/config.py:
MIN_OBS = 200  # Instead of 100
MIN_EAD = 500  # Instead of 100

# Then re-run from Section 2 (Build Transition Matrices)
```

**Solution 3: Force Parent Fallback for MOB 25+**
See `NEXT_STEPS_DIAGNOSIS.md` for code modification details

### Step 6: Verify the Fix

After applying the fix, re-run the diagnostic (Cell 8.2) to verify that the issue is resolved.

## Files Created

1. **`add_diagnostic_to_markovchain.py`** - Script that added the diagnostic section
2. **`NEXT_STEPS_DIAGNOSIS.md`** - Detailed English guide
3. **`HUONG_DAN_CHAY_DIAGNOSTIC.md`** - Detailed Vietnamese guide
4. **`DIAGNOSTIC_ADDED_SUMMARY.md`** - This file

## Diagnostic Scripts Required

Make sure these files are in your project root:
- `diagnose_why_increase_after_24.py` ✅ (already exists)
- `check_p24_quality.py` ✅ (already exists)
- `diagnose_del_curve.py` ✅ (already exists)

## Expected Output

When you run Cell 8.2, you should see output like:

```
================================================================================
CHẨN ĐOÁN: TẠI SAO DEL TĂNG SAU MOB 24?
================================================================================

1️⃣ KIỂM TRA K VALUES:
   MOB  |  K value  |  Status
   -----|-----------|----------
   20   |   0.750   | ✅ Trung bình
   21   |   0.800   | ✅ Trung bình
   ...
   25   |   0.920   | ❌ Rất cao
   26   |   0.950   | ❌ Rất cao

2️⃣ KIỂM TRA % COHORTS DÙNG FALLBACK Ở MOB 24:
   Tổng cohorts: 50
   Cohorts dùng fallback ở MOB 24: 15 (30.0%)
   ⚠️ Có một số cohorts dùng fallback

3️⃣ SO SÁNH P_24 vs PARENT FALLBACK:
   Test cohort: C/650+_10M-_POS
   DPD0 → DEL30+ comparison:
   P_24:    0.0150 (1.50%)
   Parent:  0.0350 (3.50%)
   Diff:    +0.0200 (+2.00%)
   ✅ BẠN ĐÚNG! Parent fallback có movement cao hơn P_24

...

================================================================================
KẾT LUẬN:
================================================================================

❌ K values quá cao ở MOB 25+ → Tin Markov quá nhiều

================================================================================
KHUYẾN NGHỊ:
================================================================================

1. Giảm K ở MOB 25+:
   for mob in range(25, 37):
       k_final_by_mob[mob] = min(k_final_by_mob.get(mob, 1.0), 0.3)
```

## Troubleshooting

### If imports fail:
```python
# Make sure diagnostic scripts are in project root
import sys
from pathlib import Path
project_root = Path(".").resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
```

### If variables are missing:
Run all cells from Section 1-7 first to ensure all required variables are created.

### If diagnostic shows no issues:
The problem might be:
- Data quality issues
- Business logic assumptions
- Aggregation/weighting effects at portfolio level

## Next Steps

1. ✅ Open `notebooks/Markovchain.ipynb`
2. ✅ Run all cells up to Section 8
3. ✅ Run diagnostic cells (8.1 - 8.4)
4. ✅ Read the diagnostic results
5. ✅ Apply the appropriate fix (Cell 8.6)
6. ✅ Re-run forecast and verify

## Documentation

For more details, see:
- **English**: `NEXT_STEPS_DIAGNOSIS.md`
- **Vietnamese**: `HUONG_DAN_CHAY_DIAGNOSTIC.md`

---

**Created**: 2026-01-21
**Status**: Ready to use
**Notebook**: `notebooks/Markovchain.ipynb` (Section 8 added)
