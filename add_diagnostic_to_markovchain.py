"""
Script to add diagnostic section to Markovchain.ipynb notebook
"""

import json
from pathlib import Path

def add_diagnostic_section():
    """Add diagnostic section to Markovchain notebook"""
    
    notebook_path = Path("notebooks/Markovchain.ipynb")
    
    # Read notebook
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    # Create new cells for diagnostic section
    diagnostic_cells = [
        # Markdown header
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "\n",
                "## 🔍 DIAGNOSTIC: DEL CURVE ANALYSIS\n",
                "\n",
                "Chẩn đoán tại sao DEL curve tăng liên tục thay vì flatten ở MOB cao.\n",
                "\n",
                "**Kiểm tra:**\n",
                "1. K values ở MOB 25+\n",
                "2. % cohorts dùng parent fallback ở MOB 24\n",
                "3. So sánh P_24 vs Parent Fallback\n",
                "4. Aggregation effect\n",
                "5. Phân tích từng cohort"
            ]
        },
        # Import diagnostic script
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ============================================================\n",
                "# 8.1 IMPORT DIAGNOSTIC SCRIPTS\n",
                "# ============================================================\n",
                "\n",
                "print(\"📥 Importing diagnostic scripts...\")\n",
                "\n",
                "try:\n",
                "    from diagnose_why_increase_after_24 import diagnose_why_increase_after_24\n",
                "    from check_p24_quality import check_p24_quality\n",
                "    from diagnose_del_curve import diagnose_del_curve\n",
                "    print(\"✅ Diagnostic scripts imported successfully\")\n",
                "except ImportError as e:\n",
                "    print(f\"❌ Error importing diagnostic scripts: {e}\")\n",
                "    print(\"   Make sure the diagnostic scripts are in the project root directory\")"
            ]
        },
        # Main diagnostic
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ============================================================\n",
                "# 8.2 RUN MAIN DIAGNOSTIC\n",
                "# ============================================================\n",
                "\n",
                "print(\"🔍 Running comprehensive diagnostic...\")\n",
                "print(\"   This will check:\")\n",
                "print(\"   1. K values at MOB 25+\")\n",
                "print(\"   2. % cohorts using fallback at MOB 24\")\n",
                "print(\"   3. P_24 vs Parent Fallback comparison\")\n",
                "print(\"   4. Aggregation effects\")\n",
                "print(\"   5. Individual cohort analysis\")\n",
                "print(\"\\n\" + \"=\"*80)\n",
                "\n",
                "# Prepare df_del_product if available\n",
                "df_del_product = None\n",
                "if 'df_product' in globals():\n",
                "    df_del_product = df_product\n",
                "    print(\"✅ Using df_product for aggregation analysis\")\n",
                "else:\n",
                "    print(\"⚠️  df_product not found, skipping aggregation analysis\")\n",
                "\n",
                "# Run diagnostic\n",
                "try:\n",
                "    diagnose_why_increase_after_24(\n",
                "        matrices_by_mob=matrices_by_mob,\n",
                "        parent_fallback=parent_fallback,\n",
                "        k_final_by_mob=k_final_by_mob,\n",
                "        forecast_results=forecast_calibrated,\n",
                "        disb_total_by_vintage=disb_total_by_vintage,\n",
                "        df_del_product=df_del_product\n",
                "    )\n",
                "except Exception as e:\n",
                "    print(f\"\\n❌ Error running diagnostic: {e}\")\n",
                "    import traceback\n",
                "    traceback.print_exc()"
            ]
        },
        # Check P_24 quality
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ============================================================\n",
                "# 8.3 CHECK P_24 QUALITY (OPTIONAL)\n",
                "# ============================================================\n",
                "\n",
                "print(\"\\n\" + \"=\"*80)\n",
                "print(\"🔍 Checking P_24 Quality for Sample Cohort\")\n",
                "print(\"=\"*80)\n",
                "\n",
                "# Get a sample cohort to check\n",
                "if matrices_by_mob:\n",
                "    sample_product = list(matrices_by_mob.keys())[0]\n",
                "    \n",
                "    if 24 in matrices_by_mob[sample_product]:\n",
                "        sample_score = list(matrices_by_mob[sample_product][24].keys())[0]\n",
                "        \n",
                "        print(f\"\\n📊 Analyzing: Product={sample_product}, Score={sample_score}\")\n",
                "        \n",
                "        try:\n",
                "            P_24, P_parent = check_p24_quality(\n",
                "                matrices_by_mob=matrices_by_mob,\n",
                "                parent_fallback=parent_fallback,\n",
                "                product=sample_product,\n",
                "                score=sample_score\n",
                "            )\n",
                "        except Exception as e:\n",
                "            print(f\"\\n❌ Error checking P_24 quality: {e}\")\n",
                "    else:\n",
                "        print(\"⚠️  MOB 24 not found in matrices_by_mob\")\n",
                "else:\n",
                "    print(\"⚠️  matrices_by_mob is empty\")"
            ]
        },
        # Visualize DEL curve
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ============================================================\n",
                "# 8.4 VISUALIZE DEL CURVE FOR SAMPLE COHORT\n",
                "# ============================================================\n",
                "\n",
                "print(\"\\n\" + \"=\"*80)\n",
                "print(\"📊 Visualizing DEL Curve for Sample Cohort\")\n",
                "print(\"=\"*80)\n",
                "\n",
                "# Get a sample cohort with good data\n",
                "if forecast_calibrated:\n",
                "    # Find a cohort with data at MOB 24\n",
                "    sample_cohort = None\n",
                "    for cohort_key, forecast_data in forecast_calibrated.items():\n",
                "        if 24 in forecast_data and len(forecast_data) > 10:\n",
                "            sample_cohort = cohort_key\n",
                "            break\n",
                "    \n",
                "    if sample_cohort:\n",
                "        product, score, vintage = sample_cohort\n",
                "        print(f\"\\n📊 Analyzing: Product={product}, Score={score}, Vintage={vintage}\")\n",
                "        \n",
                "        try:\n",
                "            diagnose_del_curve(\n",
                "                matrices_by_mob=matrices_by_mob,\n",
                "                parent_fallback=parent_fallback,\n",
                "                k_final_by_mob=k_final_by_mob,\n",
                "                forecast_results=forecast_calibrated,\n",
                "                disb_total_by_vintage=disb_total_by_vintage,\n",
                "                product=product,\n",
                "                score=score,\n",
                "                vintage=vintage\n",
                "            )\n",
                "        except Exception as e:\n",
                "            print(f\"\\n❌ Error visualizing DEL curve: {e}\")\n",
                "            import traceback\n",
                "            traceback.print_exc()\n",
                "    else:\n",
                "        print(\"⚠️  No suitable cohort found for visualization\")\n",
                "else:\n",
                "    print(\"⚠️  forecast_calibrated is empty\")"
            ]
        },
        # Summary and recommendations
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 8.5 Diagnostic Summary & Next Steps\n",
                "\n",
                "**Based on the diagnostic results above:**\n",
                "\n",
                "#### If K values are too high (K > 0.9 at MOB 25+):\n",
                "```python\n",
                "# Solution: Cap K at MOB 25+\n",
                "for mob in range(25, 37):\n",
                "    if mob in k_final_by_mob:\n",
                "        k_final_by_mob[mob] = min(k_final_by_mob[mob], 0.3)\n",
                "    else:\n",
                "        k_final_by_mob[mob] = 0.3\n",
                "\n",
                "# Re-run forecast with adjusted K\n",
                "forecast_calibrated = forecast_all_vintages_partial_step(\n",
                "    actual_results=actual_results,\n",
                "    matrices_by_mob=matrices_by_mob,\n",
                "    parent_fallback=parent_fallback,\n",
                "    max_mob=MAX_MOB,\n",
                "    k_by_mob=k_final_by_mob,\n",
                "    states=BUCKETS_CANON,\n",
                ")\n",
                "```\n",
                "\n",
                "#### If many cohorts use fallback at MOB 24 (> 30%):\n",
                "```python\n",
                "# Solution A: Increase MIN_OBS/MIN_EAD in src/config.py\n",
                "# MIN_OBS = 200  # Instead of 100\n",
                "# MIN_EAD = 500  # Instead of 100\n",
                "# Then re-run from step 2 (Build Transition Matrices)\n",
                "\n",
                "# Solution B: Force use parent fallback for MOB 25+\n",
                "# See NEXT_STEPS_DIAGNOSIS.md for code modification\n",
                "```\n",
                "\n",
                "#### If aggregation issue:\n",
                "- Check which cohorts are driving the increase\n",
                "- Investigate cohort-level weights\n",
                "- Consider separate forecasts for high-risk cohorts\n",
                "\n",
                "**📚 For detailed solutions, see:**\n",
                "- `NEXT_STEPS_DIAGNOSIS.md` (English)\n",
                "- `HUONG_DAN_CHAY_DIAGNOSTIC.md` (Vietnamese)"
            ]
        },
        # Apply fix example
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ============================================================\n",
                "# 8.6 APPLY FIX (EXAMPLE - UNCOMMENT TO USE)\n",
                "# ============================================================\n",
                "\n",
                "# Uncomment the solution that matches your diagnostic results\n",
                "\n",
                "# # SOLUTION 1: Cap K at MOB 25+\n",
                "# print(\"🔧 Applying Solution 1: Capping K at MOB 25+\")\n",
                "# print(\"\\nK values before:\")\n",
                "# for mob in range(24, 37):\n",
                "#     print(f\"  MOB {mob}: {k_final_by_mob.get(mob, 1.0):.3f}\")\n",
                "\n",
                "# for mob in range(25, 37):\n",
                "#     if mob in k_final_by_mob:\n",
                "#         k_final_by_mob[mob] = min(k_final_by_mob[mob], 0.3)\n",
                "#     else:\n",
                "#         k_final_by_mob[mob] = 0.3\n",
                "\n",
                "# print(\"\\nK values after:\")\n",
                "# for mob in range(24, 37):\n",
                "#     print(f\"  MOB {mob}: {k_final_by_mob.get(mob, 1.0):.3f}\")\n",
                "\n",
                "# # Re-run forecast\n",
                "# print(\"\\n🔄 Re-running forecast with adjusted K...\")\n",
                "# forecast_calibrated = forecast_all_vintages_partial_step(\n",
                "#     actual_results=actual_results,\n",
                "#     matrices_by_mob=matrices_by_mob,\n",
                "#     parent_fallback=parent_fallback,\n",
                "#     max_mob=MAX_MOB,\n",
                "#     k_by_mob=k_final_by_mob,\n",
                "#     states=BUCKETS_CANON,\n",
                "# )\n",
                "# print(\"✅ Forecast updated with adjusted K\")\n",
                "\n",
                "# # Re-run diagnostic to verify\n",
                "# print(\"\\n🔍 Re-running diagnostic to verify fix...\")\n",
                "# diagnose_why_increase_after_24(\n",
                "#     matrices_by_mob=matrices_by_mob,\n",
                "#     parent_fallback=parent_fallback,\n",
                "#     k_final_by_mob=k_final_by_mob,\n",
                "#     forecast_results=forecast_calibrated,\n",
                "#     disb_total_by_vintage=disb_total_by_vintage,\n",
                "#     df_del_product=df_del_product\n",
                "# )\n",
                "\n",
                "print(\"💡 Uncomment the solution code above to apply the fix\")\n",
                "print(\"   Choose the solution based on your diagnostic results\")"
            ]
        }
    ]
    
    # Find the insertion point (after model evaluation, before export section)
    insertion_index = None
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if 'EXPORT CHI TIẾT FORECAST CHO SẾP' in source:
                insertion_index = i
                break
    
    if insertion_index is None:
        print("❌ Could not find insertion point")
        print("   Looking for '## 📊 EXPORT CHI TIẾT FORECAST CHO SẾP' section")
        return False
    
    # Insert diagnostic cells before the export section
    for i, cell in enumerate(diagnostic_cells):
        nb['cells'].insert(insertion_index + i, cell)
    
    # Save updated notebook
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    
    print(f"✅ Successfully added diagnostic section to {notebook_path}")
    print(f"   Added {len(diagnostic_cells)} cells at position {insertion_index}")
    print(f"   Total cells now: {len(nb['cells'])}")
    return True

if __name__ == "__main__":
    print("="*60)
    print("Adding Diagnostic Section to Markovchain.ipynb")
    print("="*60)
    
    success = add_diagnostic_section()
    
    if success:
        print("\n" + "="*60)
        print("✅ DONE!")
        print("="*60)
        print("\n📝 Next steps:")
        print("   1. Open notebooks/Markovchain.ipynb")
        print("   2. Run all cells up to section 8 (Diagnostic)")
        print("   3. Run the diagnostic cells to identify the issue")
        print("   4. Apply the appropriate fix based on results")
        print("\n📚 Documentation:")
        print("   - NEXT_STEPS_DIAGNOSIS.md (English)")
        print("   - HUONG_DAN_CHAY_DIAGNOSTIC.md (Vietnamese)")
    else:
        print("\n❌ Failed to add diagnostic section")
        print("   Please check the notebook structure")
