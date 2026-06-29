# Kiểm tra: Parent Fallback có được dùng ở MOB cao không?
# Check: Is Parent Fallback Used at High MOB?

## Phân tích Logic / Logic Analysis

### Code trong `_get_P_for_segment()`:

```python
def _get_P_for_segment(matrices_by_mob, parent_fallback, product, score, mob, states):
    prod_str = str(product)
    score_str = str(score)

    mob_dict = matrices_by_mob.get(prod_str, {})  # ← Lấy dict của product
    P_df = None

    # Bước 1: Tìm exact MOB
    if mob in mob_dict and score_str in mob_dict[mob]:
        P_df = mob_dict[mob][score_str]["P"]
    else:
        # Bước 2: Nếu không có exact MOB → Tìm last available MOB
        if mob_dict:  # ← Nếu mob_dict KHÔNG RỖNG
            last_mob = max(mob_dict.keys())  # ← Lấy MOB cao nhất
            if score_str in mob_dict[last_mob]:
                P_df = mob_dict[last_mob][score_str]["P"]  # ← Dùng P_24

    # Bước 3: Nếu P_df vẫn None → Dùng parent_fallback
    if P_df is None and parent_fallback is not None:
        key_exact = (prod_str, score_str)
        if key_exact in parent_fallback:
            P_df = parent_fallback[key_exact]
        else:
            candidate = [k for k in parent_fallback.keys() if k[0] == prod_str]
            if candidate:
                P_df = parent_fallback[candidate[0]]

    # Bước 4: Nếu vẫn None → Identity matrix
    if P_df is None:
        eye = np.eye(len(states))
        P_df = pd.DataFrame(eye, index=states, columns=states)

    return P_df.reindex(index=states, columns=states, fill_value=0.0)
```

---

## ⚠️ PHÁT HIỆN VẤN ĐỀ / ISSUE FOUND

### Scenario: MOB 25-36

**Giả sử:**
- Historical data: MOB 1-24
- Product: "C"
- Score: "650+_POS"

**Khi forecast MOB 25:**

```python
mob = 25
prod_str = "C"
score_str = "650+_POS"

# Bước 1: Tìm exact MOB 25
mob_dict = matrices_by_mob["C"]  # = {1: {...}, 2: {...}, ..., 24: {...}}
if 25 in mob_dict:  # ← FALSE (không có MOB 25)
    P_df = ...
else:
    # Bước 2: Tìm last available MOB
    if mob_dict:  # ← TRUE (mob_dict không rỗng, có MOB 1-24)
        last_mob = max(mob_dict.keys())  # ← last_mob = 24
        if "650+_POS" in mob_dict[24]:  # ← TRUE (có score này)
            P_df = mob_dict[24]["650+_POS"]["P"]  # ← ✅ DÙNG P_24
            # ← RETURN NGAY, KHÔNG BAO GIỜ ĐẾN BƯỚC 3 (parent_fallback)
```

**Kết luận:**
- ❌ **Parent fallback KHÔNG BAO GIỜ được dùng cho MOB 25-36**
- ✅ **Luôn dùng P_24 (last available MOB)**

---

## Tại sao Parent Fallback không được dùng? / Why Parent Fallback is Not Used?

### Điều kiện để dùng Parent Fallback:

```python
if P_df is None and parent_fallback is not None:
    # Dùng parent_fallback
```

**P_df chỉ = None khi:**
1. Không có exact MOB (MOB 25 không tồn tại) ✅
2. **VÀ** không có last available MOB ❌

**Nhưng:**
- `mob_dict` = {1, 2, ..., 24} → KHÔNG RỖNG
- `last_mob = max(mob_dict.keys())` = 24 → TỒN TẠI
- `P_df = mob_dict[24]["650+_POS"]["P"]` → P_df KHÔNG PHẢI None
- → **KHÔNG BAO GIỜ đến bước 3 (parent_fallback)**

---

## Khi nào Parent Fallback được dùng? / When is Parent Fallback Used?

### Case 1: Score không tồn tại ở MOB 24

```python
# Giả sử score "700+_NEW" không có trong MOB 24
mob = 25
score_str = "700+_NEW"

# Bước 1: Không có MOB 25
# Bước 2: Tìm last_mob = 24
if "700+_NEW" in mob_dict[24]:  # ← FALSE (score không tồn tại)
    P_df = ...  # ← Không set P_df

# P_df vẫn = None
# Bước 3: Dùng parent_fallback
if P_df is None:  # ← TRUE
    P_df = parent_fallback[("C", "700+_NEW")]  # ← ✅ DÙNG PARENT FALLBACK
```

### Case 2: Product không có historical data

```python
# Product "D" mới, không có trong matrices_by_mob
mob = 25
prod_str = "D"

mob_dict = matrices_by_mob.get("D", {})  # ← {} (rỗng)

# Bước 1: Không có MOB 25
# Bước 2: 
if mob_dict:  # ← FALSE (mob_dict rỗng)
    ...  # ← Không vào đây

# P_df vẫn = None
# Bước 3: Dùng parent_fallback
if P_df is None:  # ← TRUE
    # Tìm parent_fallback của product khác
    candidate = [k for k in parent_fallback.keys() if k[0] == "D"]
    if candidate:
        P_df = parent_fallback[candidate[0]]  # ← ✅ DÙNG PARENT FALLBACK
```

### Case 3: MOB 24 có is_fallback = True

```python
# Nếu MOB 24 đã dùng parent fallback (insufficient data)
matrices_by_mob["C"][24]["650+_POS"] = {
    "P": P_parent,  # ← Đây là parent fallback
    "is_fallback": True,
    "reason": "insufficient data"
}

# Khi forecast MOB 25:
# Bước 2: Tìm last_mob = 24
P_df = mob_dict[24]["650+_POS"]["P"]  # ← P_parent (đã là parent fallback rồi)
# → Dùng parent fallback gián tiếp
```

---

## ✅ KẾT LUẬN / CONCLUSION

**Tiếng Việt:**

1. **Parent fallback KHÔNG được dùng trực tiếp cho MOB 25-36** trong trường hợp bình thường
2. **Luôn dùng P_24** (last available MOB) cho MOB 25-36
3. Parent fallback chỉ được dùng khi:
   - Score không tồn tại ở MOB 24
   - Product không có historical data
   - MOB 24 đã dùng parent fallback (insufficient data)

**Vậy nguyên nhân DEL tăng liên tục là:**
- ✅ **Dùng P_24 cho MOB 25-36**
- ❌ **KHÔNG PHẢI do parent fallback**

**English:**

1. **Parent fallback is NOT directly used for MOB 25-36** in normal cases
2. **Always uses P_24** (last available MOB) for MOB 25-36
3. Parent fallback is only used when:
   - Score doesn't exist at MOB 24
   - Product has no historical data
   - MOB 24 already uses parent fallback (insufficient data)

**So the reason for continuous DEL increase is:**
- ✅ **Using P_24 for MOB 25-36**
- ❌ **NOT because of parent fallback**

---

## 🔍 Vậy tại sao P_24 gây tăng liên tục? / Why Does P_24 Cause Continuous Increase?

### Giả thuyết của bạn đúng!

**Bạn nói:** "Nếu theo đúng thì tại MOB cao transition matrix tại P_24 sẽ không làm đổi nhiều"

**Lý thuyết:** P_24 nên có transition rates thấp (portfolio đã mature)

**Thực tế có thể:**
- P_24 có transition rates cao hơn mong đợi
- Do data quality issues
- Do seasonality
- Do sample size nhỏ

### Kiểm tra P_24:

```python
# Kiểm tra P_24
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]

print("Transition from DPD0:")
print(P_24.loc["DPD0"])

# Kiểm tra:
# - DPD0 → DPD0 phải cao (> 0.95)
# - DPD0 → DPD30+ phải thấp (< 0.02)
# - DPD0 → PREPAY phải có (> 0.01)

print("\nTransition from DPD30+:")
print(P_24.loc["DPD30+"])

# Kiểm tra:
# - DPD30+ → DPD30+ phải thấp (< 0.3)
# - DPD30+ → DPD90+ phải cao (> 0.3)
# - DPD30+ → WRITEOFF phải có (> 0.05)
```

---

## 🎯 GIẢI PHÁP MỚI / NEW SOLUTION

Vì parent fallback KHÔNG được dùng, giải pháp tốt nhất là:

### Giải pháp 1: **Kiểm tra và fix P_24**

```python
# Kiểm tra P_24
P_24 = matrices_by_mob["C"][24]["650+_POS"]["P"]

# Nếu P_24 có vấn đề, thay bằng parent fallback
if P_24.loc["DPD0", "DPD30+"] > 0.03:  # Quá cao
    print("⚠️ P_24 có transition rates quá cao, thay bằng parent fallback")
    P_parent = parent_fallback[("C", "650+_POS")]
    matrices_by_mob["C"][24]["650+_POS"]["P"] = P_parent
```

### Giải pháp 2: **Force dùng parent fallback cho MOB 25+**

Sửa `_get_P_for_segment()`:

```python
def _get_P_for_segment(matrices_by_mob, parent_fallback, product, score, mob, states):
    prod_str = str(product)
    score_str = str(score)

    mob_dict = matrices_by_mob.get(prod_str, {})
    P_df = None

    # ⭐ THÊM: Force dùng parent fallback cho MOB > 24
    if mob > 24:
        if parent_fallback is not None:
            key_exact = (prod_str, score_str)
            if key_exact in parent_fallback:
                return parent_fallback[key_exact].reindex(index=states, columns=states, fill_value=0.0)
    
    # Logic cũ...
    if mob in mob_dict and score_str in mob_dict[mob]:
        P_df = mob_dict[mob][score_str]["P"]
    else:
        if mob_dict:
            last_mob = max(mob_dict.keys())
            if score_str in mob_dict[last_mob]:
                P_df = mob_dict[last_mob][score_str]["P"]

    if P_df is None and parent_fallback is not None:
        key_exact = (prod_str, score_str)
        if key_exact in parent_fallback:
            P_df = parent_fallback[key_exact]
        else:
            candidate = [k for k in parent_fallback.keys() if k[0] == prod_str]
            if candidate:
                P_df = parent_fallback[candidate[0]]

    if P_df is None:
        eye = np.eye(len(states))
        P_df = pd.DataFrame(eye, index=states, columns=states)

    return P_df.reindex(index=states, columns=states, fill_value=0.0)
```

---

*Document created: 2026-01-20*
