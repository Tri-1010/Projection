"""
Thêm cell phân tích P_23 vs Parent vào notebook
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
        "## 1️⃣2️⃣ PHÂN TÍCH P_23 vs PARENT FALLBACK\n",
        "\n",
        "**Mục đích**: Hiểu tại sao forecast cao hơn P_23 tới 1400 lần:\n",
        "1. P_23 có movement bao nhiêu?\n",
        "2. Parent fallback có movement bao nhiêu?\n",
        "3. Cohorts nào đang dùng parent fallback?\n",
        "4. Parent fallback có cao hơn P_23 không?"
    ]
}

# Cell code mới
code_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "from analyze_p23_vs_parent import analyze_p23_vs_parent\n",
        "\n",
        "print(\"🔬 PHÂN TÍCH P_23 vs PARENT FALLBACK\")\n",
        "print(\"=\"*100)\n",
        "\n",
        "df_p23_parent = analyze_p23_vs_parent(\n",
        "    matrices_by_mob=matrices_by_mob,\n",
        "    parent_fallback=parent_fallback,\n",
        "    buckets_30p=BUCKETS_30P\n",
        ")\n",
        "\n",
        "if df_p23_parent is not None:\n",
        "    print(\"\\n✅ Đã tạo df_p23_parent\")\n",
        "    print(\"\\n💡 Bạn có thể:\")\n",
        "    print(\"   - Xem top cohorts: df_p23_parent.head(20)\")\n",
        "    print(\"   - Export: df_p23_parent.to_excel('p23_vs_parent.xlsx', index=False)\")\n",
        "    print(\"   - Lọc cohorts dùng fallback: df_p23_parent[df_p23_parent['is_fallback']]\")\n",
        "else:\n",
        "    print(\"\\n❌ Không tìm thấy data\")"
    ]
}

# Tìm vị trí để insert (sau cell 28, trước cell "HOÀN THÀNH")
insert_index = 29  # Sau cell 28

# Insert cells
nb["cells"].insert(insert_index, code_cell)
nb["cells"].insert(insert_index, markdown_cell)

# Ghi lại notebook
with open("notebooks/Markovchain_With_Diagnostic_Clean.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("✅ Đã thêm cell phân tích P_23 vs Parent vào notebook!")
print(f"   Vị trí: Cell {insert_index} và {insert_index+1}")
print("\n💡 Bước tiếp theo:")
print("   1. Mở notebook: notebooks/Markovchain_With_Diagnostic_Clean.ipynb")
print("   2. Chạy cell mới (cell 29-30)")
print("   3. Xem kết quả phân tích")
