"""
Script để thêm cells kiểm tra cả 3 giả thuyết vào notebook.
"""

import json

# Read notebook
with open('notebooks/Markovchain_With_Diagnostic_Clean.ipynb', 'r', encoding='utf-8') as f:
    notebook = json.load(f)

# New cells for all 3 hypotheses
new_cells = []

# ============================================================================
# HYPOTHESIS 2: Transition Stability
# ============================================================================
new_cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 1️⃣4️⃣ GIẢI THUYẾT 2: KIỂM TRA TRANSITION STABILITY\n",
        "\n",
        "**Mục đích**: Kiểm tra xem transitions có thực sự ổn định không?\n",
        "- P_23, P_24, P_25 có movement bao nhiêu?\n",
        "- Movement có tăng sau MOB 24 không?\n",
        "- Có cohorts nào có movement cao bất thường không?"
    ]
})

new_cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "print(\"=\" * 100)\n",
        "print(\"🔍 GIẢI THUYẾT 2: KIỂM TRA TRANSITION STABILITY\")\n",
        "print(\"=\" * 100)\n",
        "\n",
        "# Find a test cohort (not using fallback)\n",
        "test_prod = None\n",
        "test_score = None\n",
        "\n",
        "for prod_str in matrices_by_mob.keys():\n",
        "    if 23 in matrices_by_mob[prod_str]:\n",
        "        for score_str in matrices_by_mob[prod_str][23].keys():\n",
        "            if not matrices_by_mob[prod_str][23][score_str].get(\"is_fallback\", False):\n",
        "                test_prod = prod_str\n",
        "                test_score = score_str\n",
        "                break\n",
        "    if test_prod:\n",
        "        break\n",
        "\n",
        "if test_prod and test_score:\n",
        "    print(f\"\\n📊 Test cohort: {test_prod}/{test_score}\")\n",
        "    print(\"\\n   MOB  |  DPD0→DEL30+  |  Change  |  Status  |  Fallback\")\n",
        "    print(\"   -----|---------------|----------|----------|----------\")\n",
        "    \n",
        "    prev_rate = None\n",
        "    movements = []\n",
        "    \n",
        "    for mob in range(20, 31):\n",
        "        if mob not in matrices_by_mob[test_prod]:\n",
        "            continue\n",
        "        \n",
        "        if test_score not in matrices_by_mob[test_prod][mob]:\n",
        "            continue\n",
        "        \n",
        "        P = matrices_by_mob[test_prod][mob][test_score][\"P\"]\n",
        "        is_fallback = matrices_by_mob[test_prod][mob][test_score].get(\"is_fallback\", False)\n",
        "        \n",
        "        if \"DPD0\" not in P.index:\n",
        "            continue\n",
        "        \n",
        "        # Calculate DPD0 → DEL30+ rate\n",
        "        del30_states = [s for s in BUCKETS_30P if s in P.columns]\n",
        "        rate = sum(P.loc[\"DPD0\", s] for s in del30_states)\n",
        "        \n",
        "        if prev_rate is not None:\n",
        "            change = rate - prev_rate\n",
        "            change_str = f\"{change:+.6f}\"\n",
        "            movements.append((mob, change))\n",
        "            \n",
        "            if abs(change) > 0.001:\n",
        "                status = \"⚠️ Movement\"\n",
        "            else:\n",
        "                status = \"✅ Stable\"\n",
        "        else:\n",
        "            change_str = \"N/A\"\n",
        "            status = \"✅ Start\"\n",
        "        \n",
        "        fallback_str = \"❌ Yes\" if is_fallback else \"✅ No\"\n",
        "        print(f\"   {mob:4d} | {rate:13.6f} | {change_str:8s} | {status:8s} | {fallback_str}\")\n",
        "        prev_rate = rate\n",
        "    \n",
        "    # Statistics\n",
        "    if movements:\n",
        "        print(\"\\n\" + \"-\" * 100)\n",
        "        \n",
        "        movements_before_24 = [abs(m[1]) for m in movements if m[0] < 24]\n",
        "        movements_after_24 = [abs(m[1]) for m in movements if m[0] >= 24]\n",
        "        \n",
        "        avg_movement = np.mean([abs(m[1]) for m in movements])\n",
        "        max_movement = max([abs(m[1]) for m in movements])\n",
        "        \n",
        "        print(f\"\\n📊 THỐNG KÊ MOVEMENT:\")\n",
        "        print(f\"   - Average movement (all):     {avg_movement:.6f} ({avg_movement*100:.4f}%)\")\n",
        "        print(f\"   - Max movement:               {max_movement:.6f} ({max_movement*100:.4f}%)\")\n",
        "        \n",
        "        if movements_before_24 and movements_after_24:\n",
        "            avg_before = np.mean(movements_before_24)\n",
        "            avg_after = np.mean(movements_after_24)\n",
        "            print(f\"   - Average movement BEFORE 24: {avg_before:.6f} ({avg_before*100:.4f}%)\")\n",
        "            print(f\"   - Average movement AFTER 24:  {avg_after:.6f} ({avg_after*100:.4f}%)\")\n",
        "            print(f\"   - Chênh lệch:                 {avg_after - avg_before:+.6f} ({(avg_after/avg_before - 1)*100:+.1f}%)\")\n",
        "        \n",
        "        print(\"\\n\" + \"-\" * 100)\n",
        "        \n",
        "        if avg_movement > 0.001:\n",
        "            print(f\"\\n❌ TRANSITIONS KHÔNG ỔN ĐỊNH!\")\n",
        "            print(f\"   - Average movement {avg_movement*100:.4f}% > 0.1%\")\n",
        "            print(f\"   - Đây có thể là lý do DEL tăng!\")\n",
        "            print(f\"\\n💡 Giải thích:\")\n",
        "            print(f\"   - P_m có movement cao → Forecast sẽ tăng\")\n",
        "            print(f\"   - Ngay cả khi K ổn định, P_m movement cao cũng gây DEL tăng\")\n",
        "        else:\n",
        "            print(f\"\\n✅ Transitions ổn định (movement < 0.1%)\")\n",
        "            print(f\"   - P_m movement thấp → Không phải nguyên nhân chính\")\n",
        "else:\n",
        "    print(\"\\n⚠️ Không tìm thấy cohort để test\")\n",
        "\n",
        "print(\"\\n\" + \"=\" * 100)"
    ]
})

# ============================================================================
# HYPOTHESIS 3: Fallback Usage
# ============================================================================
new_cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 1️⃣5️⃣ GIẢI THUYẾT 3: KIỂM TRA FALLBACK USAGE\n",
        "\n",
        "**Mục đích**: Kiểm tra xem % cohorts dùng fallback có tăng sau MOB 24 không?\n",
        "- % fallback ở MOB 20-30\n",
        "- Có tăng đột ngột sau MOB 24 không?\n",
        "- Parent fallback có movement cao hơn P_m không?"
    ]
})

new_cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "print(\"=\" * 100)\n",
        "print(\"🔍 GIẢI THUYẾT 3: KIỂM TRA FALLBACK USAGE\")\n",
        "print(\"=\" * 100)\n",
        "\n",
        "print(\"\\n📊 % COHORTS DÙNG FALLBACK THEO MOB:\")\n",
        "print(\"\\n   MOB  |  Total  |  Fallback  |  %     |  Status\")\n",
        "print(\"   -----|---------|------------|--------|----------\")\n",
        "\n",
        "fallback_by_mob = {}\n",
        "\n",
        "for mob in range(20, 31):\n",
        "    total_cohorts = 0\n",
        "    fallback_cohorts = 0\n",
        "    \n",
        "    for prod_str in matrices_by_mob.keys():\n",
        "        if mob in matrices_by_mob[prod_str]:\n",
        "            for score_str in matrices_by_mob[prod_str][mob].keys():\n",
        "                total_cohorts += 1\n",
        "                is_fallback = matrices_by_mob[prod_str][mob][score_str].get(\"is_fallback\", False)\n",
        "                if is_fallback:\n",
        "                    fallback_cohorts += 1\n",
        "    \n",
        "    if total_cohorts > 0:\n",
        "        fallback_pct = fallback_cohorts / total_cohorts * 100\n",
        "        fallback_by_mob[mob] = fallback_pct\n",
        "        \n",
        "        if fallback_pct > 50:\n",
        "            status = \"❌ Rất cao\"\n",
        "        elif fallback_pct > 30:\n",
        "            status = \"⚠️ Cao\"\n",
        "        else:\n",
        "            status = \"✅ OK\"\n",
        "        \n",
        "        print(f\"   {mob:4d} | {total_cohorts:7d} | {fallback_cohorts:10d} | {fallback_pct:5.1f}% | {status}\")\n",
        "\n",
        "# Statistics\n",
        "if fallback_by_mob:\n",
        "    print(\"\\n\" + \"-\" * 100)\n",
        "    \n",
        "    fallback_before_24 = [fallback_by_mob[m] for m in fallback_by_mob.keys() if m < 24]\n",
        "    fallback_after_24 = [fallback_by_mob[m] for m in fallback_by_mob.keys() if m >= 24]\n",
        "    \n",
        "    if fallback_before_24 and fallback_after_24:\n",
        "        avg_before = np.mean(fallback_before_24)\n",
        "        avg_after = np.mean(fallback_after_24)\n",
        "        \n",
        "        print(f\"\\n📊 THỐNG KÊ:\")\n",
        "        print(f\"   - Average % fallback BEFORE 24: {avg_before:.1f}%\")\n",
        "        print(f\"   - Average % fallback AFTER 24:  {avg_after:.1f}%\")\n",
        "        print(f\"   - Chênh lệch:                   {avg_after - avg_before:+.1f}% ({(avg_after/avg_before - 1)*100:+.1f}%)\")\n",
        "        \n",
        "        print(\"\\n\" + \"-\" * 100)\n",
        "        \n",
        "        if avg_after > avg_before * 1.2:\n",
        "            print(f\"\\n❌ % FALLBACK TĂNG ĐỘT NGỘT SAU MOB 24!\")\n",
        "            print(f\"   - % fallback tăng {(avg_after/avg_before - 1)*100:.1f}%\")\n",
        "            print(f\"   - Parent fallback có movement cao hơn P_m\")\n",
        "            print(f\"   - Đây có thể là lý do DEL tăng!\")\n",
        "            print(f\"\\n💡 Giải pháp:\")\n",
        "            print(f\"   - Tăng MIN_OBS để giảm % fallback\")\n",
        "            print(f\"   - Hoặc giảm K cho cohorts dùng fallback\")\n",
        "        else:\n",
        "            print(f\"\\n✅ % Fallback không tăng nhiều sau MOB 24\")\n",
        "            print(f\"   - Không phải nguyên nhân chính\")\n",
        "\n",
        "print(\"\\n\" + \"=\" * 100)"
    ]
})

# ============================================================================
# SUMMARY: All 3 Hypotheses
# ============================================================================
new_cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 1️⃣6️⃣ TÓM TẮT: CẢ 3 GIẢI THUYẾT\n",
        "\n",
        "**Mục đích**: Tổng hợp kết quả từ cả 3 giải thuyết để xác định nguyên nhân chính."
    ]
})

new_cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "print(\"=\" * 100)\n",
        "print(\"📊 TÓM TẮT: CẢ 3 GIẢI THUYẾT\")\n",
        "print(\"=\" * 100)\n",
        "\n",
        "# Hypothesis 1: K values\n",
        "print(\"\\n1️⃣ GIẢI THUYẾT 1: K VALUES\")\n",
        "print(\"-\" * 100)\n",
        "\n",
        "k_before_24 = [k_final_by_mob.get(m, np.nan) for m in range(12, 24)]\n",
        "k_after_24 = [k_final_by_mob.get(m, np.nan) for m in range(24, 30)]\n",
        "k_before_24 = [k for k in k_before_24 if not np.isnan(k)]\n",
        "k_after_24 = [k for k in k_after_24 if not np.isnan(k)]\n",
        "\n",
        "hypothesis_1_result = \"⚠️ Không đủ data\"\n",
        "if k_before_24 and k_after_24:\n",
        "    avg_k_before = np.mean(k_before_24)\n",
        "    avg_k_after = np.mean(k_after_24)\n",
        "    k_change_pct = (avg_k_after / avg_k_before - 1) * 100\n",
        "    \n",
        "    print(f\"   K trung bình TRƯỚC MOB 24: {avg_k_before:.3f}\")\n",
        "    print(f\"   K trung bình SAU MOB 24:   {avg_k_after:.3f}\")\n",
        "    print(f\"   Chênh lệch:                {avg_k_after - avg_k_before:+.3f} ({k_change_pct:+.1f}%)\")\n",
        "    \n",
        "    if avg_k_after > avg_k_before * 1.2:\n",
        "        hypothesis_1_result = \"❌ K TĂNG CAO (>20%)\"\n",
        "        print(f\"\\n   {hypothesis_1_result}\")\n",
        "        print(f\"   → Đây có thể là nguyên nhân chính!\")\n",
        "    else:\n",
        "        hypothesis_1_result = \"✅ K không thay đổi nhiều\"\n",
        "        print(f\"\\n   {hypothesis_1_result}\")\n",
        "\n",
        "# Hypothesis 2: Transition stability\n",
        "print(\"\\n2️⃣ GIẢI THUYẾT 2: TRANSITION STABILITY\")\n",
        "print(\"-\" * 100)\n",
        "\n",
        "hypothesis_2_result = \"⚠️ Chưa kiểm tra\"\n",
        "if 'movements' in locals() and movements:\n",
        "    avg_movement = np.mean([abs(m[1]) for m in movements])\n",
        "    print(f\"   Average movement: {avg_movement:.6f} ({avg_movement*100:.4f}%)\")\n",
        "    \n",
        "    if avg_movement > 0.001:\n",
        "        hypothesis_2_result = \"❌ TRANSITIONS KHÔNG ỔN ĐỊNH (>0.1%)\"\n",
        "        print(f\"\\n   {hypothesis_2_result}\")\n",
        "        print(f\"   → Đây có thể là nguyên nhân chính!\")\n",
        "    else:\n",
        "        hypothesis_2_result = \"✅ Transitions ổn định\"\n",
        "        print(f\"\\n   {hypothesis_2_result}\")\n",
        "else:\n",
        "    print(f\"   {hypothesis_2_result}\")\n",
        "\n",
        "# Hypothesis 3: Fallback usage\n",
        "print(\"\\n3️⃣ GIẢI THUYẾT 3: FALLBACK USAGE\")\n",
        "print(\"-\" * 100)\n",
        "\n",
        "hypothesis_3_result = \"⚠️ Không đủ data\"\n",
        "if fallback_by_mob:\n",
        "    fallback_before_24 = [fallback_by_mob[m] for m in fallback_by_mob.keys() if m < 24]\n",
        "    fallback_after_24 = [fallback_by_mob[m] for m in fallback_by_mob.keys() if m >= 24]\n",
        "    \n",
        "    if fallback_before_24 and fallback_after_24:\n",
        "        avg_fb_before = np.mean(fallback_before_24)\n",
        "        avg_fb_after = np.mean(fallback_after_24)\n",
        "        fb_change_pct = (avg_fb_after / avg_fb_before - 1) * 100\n",
        "        \n",
        "        print(f\"   % fallback TRƯỚC MOB 24: {avg_fb_before:.1f}%\")\n",
        "        print(f\"   % fallback SAU MOB 24:   {avg_fb_after:.1f}%\")\n",
        "        print(f\"   Chênh lệch:              {avg_fb_after - avg_fb_before:+.1f}% ({fb_change_pct:+.1f}%)\")\n",
        "        \n",
        "        if avg_fb_after > avg_fb_before * 1.2:\n",
        "            hypothesis_3_result = \"❌ FALLBACK TĂNG CAO (>20%)\"\n",
        "            print(f\"\\n   {hypothesis_3_result}\")\n",
        "            print(f\"   → Đây có thể là nguyên nhân chính!\")\n",
        "        else:\n",
        "            hypothesis_3_result = \"✅ Fallback không tăng nhiều\"\n",
        "            print(f\"\\n   {hypothesis_3_result}\")\n",
        "else:\n",
        "    print(f\"   {hypothesis_3_result}\")\n",
        "\n",
        "# Final conclusion\n",
        "print(\"\\n\" + \"=\" * 100)\n",
        "print(\"KẾT LUẬN CUỐI CÙNG\")\n",
        "print(\"=\" * 100)\n",
        "\n",
        "print(f\"\\n   1️⃣ K values:            {hypothesis_1_result}\")\n",
        "print(f\"   2️⃣ Transition stability: {hypothesis_2_result}\")\n",
        "print(f\"   3️⃣ Fallback usage:       {hypothesis_3_result}\")\n",
        "\n",
        "# Determine primary cause\n",
        "causes = []\n",
        "if \"❌\" in hypothesis_1_result:\n",
        "    causes.append(\"K values tăng\")\n",
        "if \"❌\" in hypothesis_2_result:\n",
        "    causes.append(\"Transitions không ổn định\")\n",
        "if \"❌\" in hypothesis_3_result:\n",
        "    causes.append(\"Fallback usage tăng\")\n",
        "\n",
        "print(\"\\n\" + \"-\" * 100)\n",
        "\n",
        "if causes:\n",
        "    print(f\"\\n❌ NGUYÊN NHÂN CHÍNH: {', '.join(causes)}\")\n",
        "    print(f\"\\n💡 GIẢI PHÁP:\")\n",
        "    \n",
        "    if \"K values tăng\" in causes:\n",
        "        print(f\"   1. Giảm K sau MOB 24 (xem cell 'Giải pháp 1')\")\n",
        "    \n",
        "    if \"Transitions không ổn định\" in causes:\n",
        "        print(f\"   2. Tăng MIN_OBS để lọc cohorts không ổn định\")\n",
        "    \n",
        "    if \"Fallback usage tăng\" in causes:\n",
        "        print(f\"   3. Tăng MIN_OBS để giảm % fallback\")\n",
        "else:\n",
        "    print(f\"\\n✅ Không phát hiện nguyên nhân rõ ràng\")\n",
        "    print(f\"   → Có thể là aggregation effect hoặc weighting\")\n",
        "    print(f\"   → Cần kiểm tra thêm chi tiết từng cohort\")\n",
        "\n",
        "print(\"\\n\" + \"=\" * 100)"
    ]
})

# Find the index to insert (before "HOÀN THÀNH")
last_markdown_idx = None
for i in range(len(notebook['cells']) - 1, -1, -1):
    if notebook['cells'][i]['cell_type'] == 'markdown':
        if '## ✅ HOÀN THÀNH!' in ''.join(notebook['cells'][i]['source']):
            last_markdown_idx = i
            break

if last_markdown_idx is not None:
    # Insert all new cells before the last markdown
    for i, cell in enumerate(new_cells):
        notebook['cells'].insert(last_markdown_idx + i, cell)
else:
    # Append at the end
    notebook['cells'].extend(new_cells)

# Write back
with open('notebooks/Markovchain_With_Diagnostic_Clean.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)

print("✅ Đã thêm cells kiểm tra cả 3 giải thuyết vào notebook!")
print("\\n📝 Cells mới:")
print("   1️⃣3️⃣ PHÂN TÍCH K VALUES CHI TIẾT")
print("   1️⃣4️⃣ GIẢI THUYẾT 2: KIỂM TRA TRANSITION STABILITY")
print("   1️⃣5️⃣ GIẢI THUYẾT 3: KIỂM TRA FALLBACK USAGE")
print("   1️⃣6️⃣ TÓM TẮT: CẢ 3 GIẢI THUYẾT")
print("\\n💡 Các cells này sẽ:")
print("   1. Kiểm tra K values (đã có)")
print("   2. Kiểm tra transition stability")
print("   3. Kiểm tra fallback usage")
print("   4. Tổng hợp kết quả và đưa ra kết luận")
