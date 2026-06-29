"""
Script để thêm cell so sánh P_23 vs forecast vào notebook
"""

import json

# Đọc notebook
with open("notebooks/Markovchain_With_Diagnostic_Clean.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

# Cell markdown mới
markdown_cell = {
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 1️⃣1️⃣ SO SÁNH P_23 MOVEMENT vs FORECAST SLOPE\n",
        "\n",
        "**Mục đích**: So sánh P_23 movement (từ transition matrix) với forecast slope (MOB 23 → 29) để hiểu:\n",
        "1. P_23 có movement bao nhiêu?\n",
        "2. Forecast slope có match với P_23 không?\n",
        "3. Nếu match → K=1.0 đang work đúng, vấn đề là P_23 có movement\n",
        "4. Nếu không match → Có bug trong forecast logic"
    ]
}

# Cell code mới
code_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "from compare_p24_vs_forecast import compare_p24_vs_forecast\n",
        "\n",
        "print(\"🔬 SO SÁNH P_23 MOVEMENT vs FORECAST SLOPE\")\n",
        "print(\"=\"*100)\n",
        "\n",
        "df_comparison = compare_p24_vs_forecast(\n",
        "    matrices_by_mob=matrices_by_mob,\n",
        "    forecast_results=forecast_results,\n",
        "    actual_results=actual_results,\n",
        "    disb_total_by_vintage=disb_total_by_vintage,\n",
        "    buckets_30p=BUCKETS_30P,\n",
        "    target_mob=23,  # Dùng MOB 23 thay vì 24\n",
        "    forecast_mob_end=29  # Forecast đến MOB 29\n",
        ")\n",
        "\n",
        "if df_comparison is not None:\n",
        "    print(\"\\n✅ Đã tạo df_comparison\")\n",
        "    print(\"\\n💡 Bạn có thể:\")\n",
        "    print(\"   - Xem top cohorts: df_comparison.head(20)\")\n",
        "    print(\"   - Export: df_comparison.to_excel('comparison_p23_vs_forecast.xlsx', index=False)\")\n",
        "    print(\"   - Lọc cohorts có diff lớn: df_comparison[df_comparison['diff_pct'] > 0.5]\")\n",
        "else:\n",
        "    print(\"\\n❌ Không tìm thấy data\")"
    ]
}

# Tìm vị trí để insert (trước cell "HOÀN THÀNH")
insert_index = None
for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] == "markdown":
        source = "".join(cell["source"])
        if "HOÀN THÀNH" in source:
            insert_index = i
            break

if insert_index is None:
    # Nếu không tìm thấy, thêm vào cuối
    insert_index = len(nb["cells"])

# Insert cells
nb["cells"].insert(insert_index, code_cell)
nb["cells"].insert(insert_index, markdown_cell)

# Ghi lại notebook
with open("notebooks/Markovchain_With_Diagnostic_Clean.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("✅ Đã thêm cell so sánh P_23 vs forecast vào notebook!")
print(f"   Vị trí: Cell {insert_index} và {insert_index+1}")
print("\n💡 Bước tiếp theo:")
print("   1. Mở notebook: notebooks/Markovchain_With_Diagnostic_Clean.ipynb")
print("   2. Chạy lại từ đầu (hoặc chỉ chạy cell mới)")
print("   3. Xem kết quả so sánh")
