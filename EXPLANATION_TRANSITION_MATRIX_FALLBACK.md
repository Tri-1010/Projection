# Giải Thích Logic Transition Matrix Fallback
# Explanation of Transition Matrix Fallback Logic

## Câu hỏi / Question

**Tiếng Việt:**
Nếu TARGET_MOB = 24, MAX_MOB = 36, thì các ma trận transition thiếu từ MOB 25-36 lấy ở đâu và như thế nào?

**English:**
If TARGET_MOB = 24, MAX_MOB = 36, where do the missing transition matrices from MOB 25-36 come from and how are they obtained?

---

## Trả lời Chi tiết / Detailed Answer

### 1. Cấu trúc Dữ liệu Historical / Historical Data Structure

**Tiếng Việt:**
Giả sử dữ liệu historical của bạn chỉ có đến MOB 24:

```
matrices_by_mob[product][mob][score] = {"P": DataFrame, ...}

Ví dụ:
matrices_by_mob["C"][1]["650+_POS"] = {"P": P_matrix_1, ...}
matrices_by_mob["C"][2]["650+_POS"] = {"P": P_matrix_2, ...}
...
matrices_by_mob["C"][24]["650+_POS"] = {"P": P_matrix_24, ...}
# Không có MOB 25, 26, ..., 36
```

**English:**
Assume your historical data only goes up to MOB 24:

---

### 2. Logic Fallback trong `_get_P_for_segment()` / Fallback Logic

**Code:**
```python
def _get_P_for_segment(matrices_by_mob, parent_fallback, product, score, mob, states):
    """
    Select P_m for (product, score, mob) with fallbacks:
    exact mob -> last available mob -> parent fallback -> identity.
    """
    prod_str = str(product)
    score_str = str(score)

    mob_dict = matrices_by_mob.get(prod_str, {})
    P_df = None

    # Bước 1: Tìm exact MOB
    if mob in mob_dict and score_str in mob_dict[mob]:
        P_df = mob_dict[mob][score_str]["P"]
    else:
        # Bước 2: Nếu không có exact MOB → dùng LAST AVAILABLE MOB
        if mob_dict:
            last_mob = max(mob_dict.keys())  # ← Đây là MOB 24
            if score_str in mob_dict[last_mob]:
                P_df = mob_dict[last_mob][score_str]["P"]

    # Bước 3: Nếu vẫn không có → dùng parent_fallback
    if P_df is None and parent_fallback is not None:
        key_exact = (prod_str, score_str)
        if key_exact in parent_fallback:
            P_df = parent_fallback[key_exact]
        else:
            candidate = [k for k in parent_fallback.keys() if k[0] == prod_str]
            if candidate:
                P_df = parent_fallback[candidate[0]]

    # Bước 4: Nếu vẫn không có → dùng Identity Matrix
    if P_df is None:
        eye = np.eye(len(states))
        P_df = pd.DataFrame(eye, index=states, columns=states)

    return P_df.reindex(index=states, columns=states, fill_value=0.0)
```

---

### 3. Ví dụ Cụ thể / Concrete Example

**Scenario:**
- Historical data: MOB 1-24
- Forecast: MOB 25-36
- Product: "C"
- Score: "650+_POS"

**Tiếng Việt:**

#### MOB 1-24 (có dữ liệu):
```python
for mob in range(1, 25):  # MOB 1 → 24
    P_df = _get_P_for_segment(..., mob=mob, ...)
    # → Trả về P_matrix_mob (exact match)
```

#### MOB 25-36 (KHÔNG có dữ liệu):
```python
for mob in range(25, 37):  # MOB 25 → 36
    P_df = _get_P_for_segment(..., mob=mob, ...)
    # mob=25 không tồn tại trong matrices_by_mob["C"]
    # → Fallback: last_mob = max(mob_dict.keys()) = 24
    # → Trả về P_matrix_24 (ma trận của MOB 24)
```

**Kết luận:**
- **MOB 25-36 đều dùng ma trận transition của MOB 24**
- Giả định: Hành vi chuyển trạng thái ở MOB 24 đại diện cho MOB 25+

**English:**

#### MOB 1-24 (with data):
```python
for mob in range(1, 25):  # MOB 1 → 24
    P_df = _get_P_for_segment(..., mob=mob, ...)
    # → Returns P_matrix_mob (exact match)
```

#### MOB 25-36 (NO data):
```python
for mob in range(25, 37):  # MOB 25 → 36
    P_df = _get_P_for_segment(..., mob=mob, ...)
    # mob=25 does not exist in matrices_by_mob["C"]
    # → Fallback: last_mob = max(mob_dict.keys()) = 24
    # → Returns P_matrix_24 (transition matrix from MOB 24)
```

**Conclusion:**
- **MOB 25-36 all use the transition matrix from MOB 24**
- Assumption: Transition behavior at MOB 24 represents MOB 25+

---

### 4. Cascade Fallback / Chuỗi Fallback

**Tiếng Việt:**

Nếu không tìm thấy ma trận, hệ thống sẽ fallback theo thứ tự:

```
1. Exact MOB match (P_mob cho MOB cụ thể)
   ↓ (không có)
2. Last available MOB (P_24 - MOB cuối cùng có data)
   ↓ (không có)
3. Parent fallback (P_parent - tổng hợp TẤT CẢ MOB)
   ↓ (không có)
4. Identity matrix (trạng thái không đổi)
```

**English:**

If no matrix is found, the system falls back in this order:

```
1. Exact MOB match (P_mob for specific MOB)
   ↓ (not found)
2. Last available MOB (P_24 - last MOB with data)
   ↓ (not found)
3. Parent fallback (P_parent - aggregated across ALL MOBs)
   ↓ (not found)
4. Identity matrix (states don't change)
```

---

### 4.1 Chi tiết về Parent Fallback / Parent Fallback Details

**Tiếng Việt:**

**Parent fallback** là ma trận transition được tính từ **TẤT CẢ các MOB** trong dữ liệu, không phân tách theo MOB cụ thể.

#### Cách tạo Parent Fallback:

```python
# Bước 1: Lấy TẤT CẢ pairs của (product, score) - KHÔNG group theo MOB
for (prod, score), grp in pairs.groupby(["product_t", "score_t"]):
    # grp chứa pairs từ MOB 1, 2, 3, ..., 24 (tất cả)
    
    P_parent = compute_transition_from_pairs(
        grp,  # ← TẤT CẢ MOB
        value_col="ead_t",
        ...
    )
    parent_fallback[(prod, score)] = P_parent
```

#### Ví dụ:

```
Product "C", Score "650+_POS":

MOB-specific matrices:
- P_1: Ma trận từ pairs MOB 1 → 2
- P_2: Ma trận từ pairs MOB 2 → 3
- ...
- P_24: Ma trận từ pairs MOB 24 → 25

Parent fallback:
- P_parent: Ma trận từ TẤT CẢ pairs (MOB 1→2, 2→3, ..., 24→25)
```

#### Khi nào dùng Parent Fallback?

1. **Không có MOB-specific matrix** (vd: MOB 25-36)
2. **Không có Last available MOB** (trường hợp hiếm)
3. **MOB-specific matrix không đủ data** (n_obs < MIN_OBS hoặc EAD < MIN_EAD)

**English:**

**Parent fallback** is a transition matrix calculated from **ALL MOBs** in the data, without splitting by specific MOB.

#### How Parent Fallback is Created:

```python
# Step 1: Get ALL pairs for (product, score) - NO grouping by MOB
for (prod, score), grp in pairs.groupby(["product_t", "score_t"]):
    # grp contains pairs from MOB 1, 2, 3, ..., 24 (all)
    
    P_parent = compute_transition_from_pairs(
        grp,  # ← ALL MOBs
        value_col="ead_t",
        ...
    )
    parent_fallback[(prod, score)] = P_parent
```

#### Example:

```
Product "C", Score "650+_POS":

MOB-specific matrices:
- P_1: Matrix from pairs MOB 1 → 2
- P_2: Matrix from pairs MOB 2 → 3
- ...
- P_24: Matrix from pairs MOB 24 → 25

Parent fallback:
- P_parent: Matrix from ALL pairs (MOB 1→2, 2→3, ..., 24→25)
```

#### When is Parent Fallback Used?

1. **No MOB-specific matrix** (e.g., MOB 25-36)
2. **No Last available MOB** (rare case)
3. **MOB-specific matrix has insufficient data** (n_obs < MIN_OBS or EAD < MIN_EAD)

---

### 5. Ý Nghĩa Thực Tế / Practical Implications

**Tiếng Việt:**

#### Ưu điểm:
- ✅ Có thể forecast xa hơn dữ liệu historical
- ✅ Không cần ma trận cho mọi MOB
- ✅ Giả định hợp lý: hành vi ổn định ở MOB cao

#### Nhược điểm:
- ⚠️ Giả định MOB 24 đại diện cho MOB 25-36 có thể không chính xác
- ⚠️ Nếu hành vi thay đổi ở MOB cao (vd: prepayment tăng), model sẽ không bắt được

#### Khuyến nghị:
1. **Kiểm tra dữ liệu:** Xem MOB cao nhất trong historical data
2. **Validate:** So sánh forecast MOB 25+ với actual (nếu có)
3. **Điều chỉnh MAX_MOB:** Nếu không tin tưởng, giảm MAX_MOB xuống gần với dữ liệu

**English:**

#### Advantages:
- ✅ Can forecast beyond historical data
- ✅ Don't need matrices for every MOB
- ✅ Reasonable assumption: stable behavior at high MOB

#### Disadvantages:
- ⚠️ Assumption that MOB 24 represents MOB 25-36 may be inaccurate
- ⚠️ If behavior changes at high MOB (e.g., prepayment increases), model won't capture it

#### Recommendations:
1. **Check data:** See highest MOB in historical data
2. **Validate:** Compare forecast MOB 25+ with actual (if available)
3. **Adjust MAX_MOB:** If not confident, reduce MAX_MOB closer to data

---

### 6. Code Example / Ví dụ Code

**Tiếng Việt:**

```python
# Giả sử historical data có MOB 1-24
matrices_by_mob = {
    "C": {
        1: {"650+_POS": {"P": P_1, ...}},
        2: {"650+_POS": {"P": P_2, ...}},
        ...
        24: {"650+_POS": {"P": P_24, ...}},
        # Không có MOB 25+
    }
}

# Forecast từ MOB 24 → 36
for mob in range(24, 36):
    # mob=24: P_df = P_24 (exact match)
    # mob=25: P_df = P_24 (fallback to last_mob=24)
    # mob=26: P_df = P_24 (fallback to last_mob=24)
    # ...
    # mob=35: P_df = P_24 (fallback to last_mob=24)
    
    P_df = _get_P_for_segment(matrices_by_mob, parent_fallback, "C", "650+_POS", mob, states)
    v_hat = v_current @ P_df
    k_m = k_by_mob.get(mob, 1.0)
    v_next = v_current + k_m * (v_hat - v_current)
    v_current = v_next
```

**English:**

```python
# Assume historical data has MOB 1-24
matrices_by_mob = {
    "C": {
        1: {"650+_POS": {"P": P_1, ...}},
        2: {"650+_POS": {"P": P_2, ...}},
        ...
        24: {"650+_POS": {"P": P_24, ...}},
        # No MOB 25+
    }
}

# Forecast from MOB 24 → 36
for mob in range(24, 36):
    # mob=24: P_df = P_24 (exact match)
    # mob=25: P_df = P_24 (fallback to last_mob=24)
    # mob=26: P_df = P_24 (fallback to last_mob=24)
    # ...
    # mob=35: P_df = P_24 (fallback to last_mob=24)
    
    P_df = _get_P_for_segment(matrices_by_mob, parent_fallback, "C", "650+_POS", mob, states)
    v_hat = v_current @ P_df
    k_m = k_by_mob.get(mob, 1.0)
    v_next = v_current + k_m * (v_hat - v_current)
    v_current = v_next
```

---

### 7. Kiểm Tra Thực Tế / Practical Check

**Tiếng Việt:**

Để kiểm tra MOB cao nhất trong dữ liệu:

```python
# Kiểm tra MOB cao nhất trong matrices_by_mob
for product, mob_dict in matrices_by_mob.items():
    if mob_dict:
        max_mob_in_data = max(mob_dict.keys())
        print(f"Product {product}: Max MOB = {max_mob_in_data}")

# Kiểm tra MOB cao nhất trong actual_results
for (product, score, vintage), mob_dict in actual_results.items():
    if mob_dict:
        max_mob_actual = max(mob_dict.keys())
        print(f"{product}/{score}/{vintage}: Max MOB = {max_mob_actual}")
```

**English:**

To check the highest MOB in data:

```python
# Check highest MOB in matrices_by_mob
for product, mob_dict in matrices_by_mob.items():
    if mob_dict:
        max_mob_in_data = max(mob_dict.keys())
        print(f"Product {product}: Max MOB = {max_mob_in_data}")

# Check highest MOB in actual_results
for (product, score, vintage), mob_dict in actual_results.items():
    if mob_dict:
        max_mob_actual = max(mob_dict.keys())
        print(f"{product}/{score}/{vintage}: Max MOB = {max_mob_actual}")
```

---

## Tóm tắt / Summary

**Tiếng Việt:**

| MOB Range | Ma trận Transition | Nguồn |
|-----------|-------------------|-------|
| 1-24 | P_1, P_2, ..., P_24 | Historical data (exact match) |
| 25-36 | P_24, P_24, ..., P_24 | Fallback to last available MOB |

**Giả định chính:** Hành vi chuyển trạng thái ở MOB 24 đại diện cho tất cả MOB 25+.

**English:**

| MOB Range | Transition Matrix | Source |
|-----------|------------------|--------|
| 1-24 | P_1, P_2, ..., P_24 | Historical data (exact match) |
| 25-36 | P_24, P_24, ..., P_24 | Fallback to last available MOB |

**Main assumption:** Transition behavior at MOB 24 represents all MOB 25+.

---

## Khuyến nghị / Recommendations

**Tiếng Việt:**

1. **Kiểm tra dữ liệu:** Chạy code kiểm tra ở mục 7 để xác định MOB cao nhất
2. **Đặt MAX_MOB hợp lý:** Không nên forecast quá xa so với dữ liệu (vd: nếu data đến MOB 24, MAX_MOB = 30-36 là hợp lý)
3. **Validate forecast:** So sánh forecast với actual ở MOB cao (nếu có thêm dữ liệu sau)
4. **Xem xét parent_fallback:** Nếu lo ngại về MOB-specific behavior, có thể dùng parent_fallback (ma trận tổng hợp không phân tách MOB)

**English:**

1. **Check data:** Run the check code in section 7 to determine highest MOB
2. **Set reasonable MAX_MOB:** Don't forecast too far beyond data (e.g., if data goes to MOB 24, MAX_MOB = 30-36 is reasonable)
3. **Validate forecast:** Compare forecast with actual at high MOB (if more data becomes available)
4. **Consider parent_fallback:** If concerned about MOB-specific behavior, can use parent_fallback (aggregated matrix without MOB split)

---

*Document created: 2026-01-20*


---

### 8. So sánh 3 loại Ma trận / Comparison of 3 Matrix Types

**Tiếng Việt:**

| Loại Ma trận | Dữ liệu nguồn | Khi nào dùng | Ví dụ |
|--------------|---------------|--------------|-------|
| **MOB-specific** | Pairs từ MOB m → m+1 | MOB có đủ data (n_obs ≥ MIN_OBS) | P_5 từ pairs MOB 5→6 |
| **Last available MOB** | Pairs từ MOB_max → MOB_max+1 | MOB > MOB_max trong data | P_24 cho MOB 25-36 |
| **Parent fallback** | Pairs từ TẤT CẢ MOB (1→2, 2→3, ..., 24→25) | MOB không đủ data HOẶC không có last MOB | P_parent từ tất cả MOB |

**English:**

| Matrix Type | Source Data | When Used | Example |
|-------------|-------------|-----------|---------|
| **MOB-specific** | Pairs from MOB m → m+1 | MOB has sufficient data (n_obs ≥ MIN_OBS) | P_5 from pairs MOB 5→6 |
| **Last available MOB** | Pairs from MOB_max → MOB_max+1 | MOB > MOB_max in data | P_24 for MOB 25-36 |
| **Parent fallback** | Pairs from ALL MOBs (1→2, 2→3, ..., 24→25) | MOB has insufficient data OR no last MOB | P_parent from all MOBs |

---

### 9. Ví dụ Thực tế với Parent Fallback / Real Example with Parent Fallback

**Scenario:**
- Product: "C"
- Score: "650+_POS"
- Historical data: MOB 1-24
- Forecast: MOB 1-36

**Tiếng Việt:**

#### Dữ liệu:
```python
# MOB-specific matrices (có đủ data)
matrices_by_mob["C"][1]["650+_POS"] = {"P": P_1, "is_fallback": False}
matrices_by_mob["C"][2]["650+_POS"] = {"P": P_2, "is_fallback": False}
...
matrices_by_mob["C"][24]["650+_POS"] = {"P": P_24, "is_fallback": False}

# Parent fallback (tổng hợp tất cả MOB 1-24)
parent_fallback[("C", "650+_POS")] = P_parent
```

#### Forecast Logic:

```python
for mob in range(1, 37):  # MOB 1 → 36
    P_df = _get_P_for_segment(matrices_by_mob, parent_fallback, "C", "650+_POS", mob, states)
    
    if mob <= 24:
        # Có exact match
        # P_df = P_mob (MOB-specific)
        print(f"MOB {mob}: Dùng P_{mob} (exact match)")
    
    elif mob >= 25:
        # Không có exact match
        # last_mob = max(matrices_by_mob["C"].keys()) = 24
        # P_df = P_24 (last available MOB)
        print(f"MOB {mob}: Dùng P_24 (last available MOB)")
        
        # Nếu không có P_24 (trường hợp hiếm):
        # P_df = P_parent (parent fallback)
        # print(f"MOB {mob}: Dùng P_parent (parent fallback)")
```

**English:**

#### Data:
```python
# MOB-specific matrices (sufficient data)
matrices_by_mob["C"][1]["650+_POS"] = {"P": P_1, "is_fallback": False}
matrices_by_mob["C"][2]["650+_POS"] = {"P": P_2, "is_fallback": False}
...
matrices_by_mob["C"][24]["650+_POS"] = {"P": P_24, "is_fallback": False}

# Parent fallback (aggregated across all MOB 1-24)
parent_fallback[("C", "650+_POS")] = P_parent
```

#### Forecast Logic:

```python
for mob in range(1, 37):  # MOB 1 → 36
    P_df = _get_P_for_segment(matrices_by_mob, parent_fallback, "C", "650+_POS", mob, states)
    
    if mob <= 24:
        # Has exact match
        # P_df = P_mob (MOB-specific)
        print(f"MOB {mob}: Use P_{mob} (exact match)")
    
    elif mob >= 25:
        # No exact match
        # last_mob = max(matrices_by_mob["C"].keys()) = 24
        # P_df = P_24 (last available MOB)
        print(f"MOB {mob}: Use P_24 (last available MOB)")
        
        # If no P_24 (rare case):
        # P_df = P_parent (parent fallback)
        # print(f"MOB {mob}: Use P_parent (parent fallback)")
```

---

### 10. Khi nào Parent Fallback được dùng thực sự? / When is Parent Fallback Actually Used?

**Tiếng Việt:**

Parent fallback thường được dùng trong các trường hợp:

#### Case 1: MOB có ít data
```python
# MOB 23 có quá ít quan sát
if n_obs < MIN_OBS or total_ead < MIN_EAD:
    # Dùng parent fallback thay vì P_23
    matrices_by_mob["C"][23]["650+_POS"] = {
        "P": P_parent,  # ← Parent fallback
        "is_fallback": True,
        "reason": "insufficient data"
    }
```

#### Case 2: Score mới không có historical data
```python
# Score "700+_NEW" không có trong historical data
# Không có P_1, P_2, ..., P_24 cho score này
# → Dùng parent fallback của product "C" (tổng hợp tất cả scores)
```

#### Case 3: Product mới
```python
# Product "D" mới, không có historical data
# → Dùng parent fallback của product khác (nếu có)
# → Hoặc dùng identity matrix
```

**English:**

Parent fallback is typically used in these cases:

#### Case 1: MOB with little data
```python
# MOB 23 has too few observations
if n_obs < MIN_OBS or total_ead < MIN_EAD:
    # Use parent fallback instead of P_23
    matrices_by_mob["C"][23]["650+_POS"] = {
        "P": P_parent,  # ← Parent fallback
        "is_fallback": True,
        "reason": "insufficient data"
    }
```

#### Case 2: New score without historical data
```python
# Score "700+_NEW" not in historical data
# No P_1, P_2, ..., P_24 for this score
# → Use parent fallback of product "C" (aggregated across all scores)
```

#### Case 3: New product
```python
# Product "D" is new, no historical data
# → Use parent fallback of another product (if available)
# → Or use identity matrix
```

---

### 11. Tóm tắt Cuối cùng / Final Summary

**Tiếng Việt:**

Để trả lời câu hỏi gốc: **"Parent fallback là lấy trên tất cả MOB, dữ liệu hay sao?"**

✅ **Đúng!** Parent fallback được tính từ **TẤT CẢ các MOB** trong dữ liệu historical.

**Quy trình:**
1. Lấy tất cả pairs từ MOB 1→2, 2→3, ..., 24→25
2. Gộp tất cả lại (không phân tách theo MOB)
3. Tính ma trận transition từ tập hợp pairs này
4. Kết quả: Ma trận "trung bình" đại diện cho hành vi chuyển trạng thái tổng quát

**Khi nào dùng:**
- MOB không có data (vd: MOB 25-36) → Dùng **last available MOB** (P_24) trước
- Nếu không có last available MOB → Dùng **parent fallback**
- MOB có ít data (n_obs < MIN_OBS) → Dùng **parent fallback** luôn

**English:**

To answer the original question: **"Is parent fallback calculated from all MOBs in the data?"**

✅ **Yes!** Parent fallback is calculated from **ALL MOBs** in the historical data.

**Process:**
1. Get all pairs from MOB 1→2, 2→3, ..., 24→25
2. Aggregate all together (no MOB split)
3. Calculate transition matrix from this combined set of pairs
4. Result: "Average" matrix representing general transition behavior

**When used:**
- MOB without data (e.g., MOB 25-36) → Use **last available MOB** (P_24) first
- If no last available MOB → Use **parent fallback**
- MOB with little data (n_obs < MIN_OBS) → Use **parent fallback** directly

---

*Document updated: 2026-01-20*
