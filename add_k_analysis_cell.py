"""
Script để thêm cell phân tích K values vào notebook.
"""

import json

# Read notebook
with open('notebooks/Markovchain_With_Diagnostic_Clean.ipynb', 'r', encoding='utf-8') as f:
    notebook = json.load(f)

# New cell: K Values Analysis
new_cell_markdown = {
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 1️⃣3️⃣ PHÂN TÍCH K VALUES CHI TIẾT\n",
        "\n",
        "**Mục đích**: Trả lời câu hỏi:\n",
        "- K trước MOB 24 là bao nhiêu?\n",
        "- K sau MOB 24 là bao nhiêu?\n",
        "- Có K jumps lớn không?\n",
        "- Tại sao K là vấn đề nếu transitions đã ổn định?"
    ]
}

new_cell_code = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "print(\"=\" * 100)\n",
        "print(\"🔍 PHÂN TÍCH K VALUES CHI TIẾT\")\n",
        "print(\"=\" * 100)\n",
        "\n",
        "# 1. Show K values table\n",
        "print(\"\\n📊 K VALUES THEO MOB:\")\n",
        "print(\"\\n   MOB  |  K_raw  |  K_smooth  |  K_final  |  Change  |  Status\")\n",
        "print(\"   -----|---------|------------|-----------|----------|----------\")\n",
        "\n",
        "prev_k = None\n",
        "k_jumps = []\n",
        "\n",
        "for mob in range(1, 37):\n",
        "    k_raw = k_raw_by_mob.get(mob, np.nan)\n",
        "    k_smooth = k_smooth_by_mob.get(mob, np.nan)\n",
        "    k_final = k_final_by_mob.get(mob, 1.0)\n",
        "    \n",
        "    if prev_k is not None and not np.isnan(k_final):\n",
        "        change = k_final - prev_k\n",
        "        change_str = f\"{change:+.3f}\"\n",
        "        \n",
        "        # Detect jumps\n",
        "        if abs(change) > 0.2:\n",
        "            k_jumps.append((mob, prev_k, k_final, change))\n",
        "            status = \"⚠️ JUMP!\"\n",
        "        elif k_final > 0.9:\n",
        "            status = \"❌ Rất cao\"\n",
        "        elif k_final > 0.7:\n",
        "            status = \"⚠️ Cao\"\n",
        "        else:\n",
        "            status = \"✅ OK\"\n",
        "    else:\n",
        "        change_str = \"N/A\"\n",
        "        status = \"✅ Start\"\n",
        "    \n",
        "    k_raw_str = f\"{k_raw:.3f}\" if not np.isnan(k_raw) else \"N/A\"\n",
        "    k_smooth_str = f\"{k_smooth:.3f}\" if not np.isnan(k_smooth) else \"N/A\"\n",
        "    \n",
        "    print(f\"   {mob:4d} | {k_raw_str:7s} | {k_smooth_str:10s} | {k_final:9.3f} | {change_str:8s} | {status}\")\n",
        "    \n",
        "    if not np.isnan(k_final):\n",
        "        prev_k = k_final\n",
        "\n",
        "# 2. Statistics\n",
        "print(\"\\n\" + \"=\" * 100)\n",
        "print(\"📊 THỐNG KÊ K VALUES\")\n",
        "print(\"=\" * 100)\n",
        "\n",
        "# K values before and after MOB 24\n",
        "k_before_24 = [k_final_by_mob.get(m, np.nan) for m in range(12, 24)]\n",
        "k_after_24 = [k_final_by_mob.get(m, np.nan) for m in range(24, 30)]\n",
        "\n",
        "k_before_24 = [k for k in k_before_24 if not np.isnan(k)]\n",
        "k_after_24 = [k for k in k_after_24 if not np.isnan(k)]\n",
        "\n",
        "if k_before_24 and k_after_24:\n",
        "    avg_before = np.mean(k_before_24)\n",
        "    avg_after = np.mean(k_after_24)\n",
        "    \n",
        "    print(f\"\\n   K trung bình TRƯỚC MOB 24 (MOB 12-23): {avg_before:.3f}\")\n",
        "    print(f\"   K trung bình SAU MOB 24 (MOB 24-29):   {avg_after:.3f}\")\n",
        "    print(f\"   Chênh lệch:                             {avg_after - avg_before:+.3f} ({(avg_after/avg_before - 1)*100:+.1f}%)\")\n",
        "    \n",
        "    if avg_after > avg_before * 1.2:\n",
        "        print(f\"\\n   ❌ K SAU MOB 24 CAO HƠN TRƯỚC MOB 24 NHIỀU!\")\n",
        "        print(f\"   → Đây là lý do slope SAU mature cao hơn slope TRƯỚC mature\")\n",
        "        print(f\"   → Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng\")\n",
        "    else:\n",
        "        print(f\"\\n   ✅ K không thay đổi nhiều\")\n",
        "else:\n",
        "    print(\"\\n   ⚠️ Không đủ data để so sánh\")\n",
        "\n",
        "# 3. K jumps\n",
        "if k_jumps:\n",
        "    print(f\"\\n   ❌ PHÁT HIỆN {len(k_jumps)} K JUMPS (>0.2):\")\n",
        "    for mob, k_before, k_after, change in k_jumps:\n",
        "        print(f\"      - MOB {mob}: {k_before:.3f} → {k_after:.3f} (change: {change:+.3f})\")\n",
        "else:\n",
        "    print(f\"\\n   ✅ Không có K jumps lớn (>0.2)\")\n",
        "\n",
        "# 4. Explanation\n",
        "print(\"\\n\" + \"=\" * 100)\n",
        "print(\"💡 GIẢI THÍCH: TẠI SAO K LÀ VẤN ĐỀ?\")\n",
        "print(\"=\" * 100)\n",
        "\n",
        "print(\"\\n   Công thức forecast:\")\n",
        "print(\"   v_{m+1} = v_m + k_m * (v_hat - v_m)\")\n",
        "print(\"   where v_hat = v_m @ P_m\")\n",
        "\n",
        "print(\"\\n   Nếu P_m có movement (ví dụ: DPD0 → DEL30+ = 0.0004%):\")\n",
        "\n",
        "if k_before_24 and k_after_24:\n",
        "    avg_before = np.mean(k_before_24)\n",
        "    avg_after = np.mean(k_after_24)\n",
        "    \n",
        "    movement = 0.0004  # P_23 movement từ kết quả trước\n",
        "    \n",
        "    forecast_before = avg_before * movement\n",
        "    forecast_after = avg_after * movement\n",
        "    \n",
        "    print(f\"\\n   TRƯỚC MOB 24 (K = {avg_before:.3f}):\")\n",
        "    print(f\"      Forecast movement = {avg_before:.3f} * {movement:.4f}% = {forecast_before:.6f}%\")\n",
        "    \n",
        "    print(f\"\\n   SAU MOB 24 (K = {avg_after:.3f}):\")\n",
        "    print(f\"      Forecast movement = {avg_after:.3f} * {movement:.4f}% = {forecast_after:.6f}%\")\n",
        "    \n",
        "    print(f\"\\n   Chênh lệch: {forecast_after - forecast_before:.6f}% ({(forecast_after/forecast_before - 1)*100:+.1f}%)\")\n",
        "    \n",
        "    if forecast_after > forecast_before * 1.2:\n",
        "        print(f\"\\n   ❌ FORECAST MOVEMENT SAU MOB 24 CAO HƠN TRƯỚC MOB 24!\")\n",
        "        print(f\"   → Đây là lý do slope tăng\")\n",
        "        print(f\"   → Ngay cả khi P_m ổn định, K tăng cũng làm slope tăng\")\n",
        "\n",
        "# 5. Conclusion\n",
        "print(\"\\n\" + \"=\" * 100)\n",
        "print(\"KẾT LUẬN\")\n",
        "print(\"=\" * 100)\n",
        "\n",
        "print(\"\\n   'Ổn định' có 2 nghĩa:\")\n",
        "print(\"   1. P_m không thay đổi theo MOB (P_23 ≈ P_24 ≈ P_25)\")\n",
        "print(\"   2. P_m không gây movement (v_hat ≈ v_m)\")\n",
        "\n",
        "print(\"\\n   P_m có thể 'ổn định' theo nghĩa 1 nhưng vẫn có movement!\")\n",
        "print(\"   → K quyết định bao nhiêu % movement được áp dụng\")\n",
        "print(\"   → K tăng → Forecast movement tăng → Slope tăng\")\n",
        "\n",
        "if k_before_24 and k_after_24:\n",
        "    avg_before = np.mean(k_before_24)\n",
        "    avg_after = np.mean(k_after_24)\n",
        "    \n",
        "    if avg_after > avg_before * 1.2:\n",
        "        print(f\"\\n   ❌ K SAU MOB 24 ({avg_after:.3f}) cao hơn TRƯỚC MOB 24 ({avg_before:.3f})\")\n",
        "        print(f\"   → Đây là lý do slope SAU mature cao hơn slope TRƯỚC mature\")\n",
        "        print(f\"   → Giải pháp: Giảm K sau MOB 24 xuống {avg_before:.3f}\")\n",
        "\n",
        "print(\"\\n\" + \"=\" * 100)"
    ]
}

# Insert new cells before the last markdown cell (before "HOÀN THÀNH")
# Find the index of the last markdown cell
last_markdown_idx = None
for i in range(len(notebook['cells']) - 1, -1, -1):
    if notebook['cells'][i]['cell_type'] == 'markdown':
        if '## ✅ HOÀN THÀNH!' in ''.join(notebook['cells'][i]['source']):
            last_markdown_idx = i
            break

if last_markdown_idx is not None:
    # Insert before the last markdown
    notebook['cells'].insert(last_markdown_idx, new_cell_markdown)
    notebook['cells'].insert(last_markdown_idx + 1, new_cell_code)
else:
    # Append at the end
    notebook['cells'].append(new_cell_markdown)
    notebook['cells'].append(new_cell_code)

# Write back
with open('notebooks/Markovchain_With_Diagnostic_Clean.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)

print("✅ Đã thêm cell phân tích K values vào notebook!")
print("📝 Cell mới: 1️⃣3️⃣ PHÂN TÍCH K VALUES CHI TIẾT")
print("\\n💡 Cell này sẽ:")
print("   1. Hiển thị K values từ MOB 1-36")
print("   2. So sánh K trước và sau MOB 24")
print("   3. Tìm K jumps lớn")
print("   4. Giải thích tại sao K là vấn đề")
