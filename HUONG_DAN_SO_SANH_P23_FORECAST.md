# 🔬 Hướng Dẫn So Sánh P_23 Movement vs Forecast Slope

## ✅ Đã Hoàn Thành

### 1. Sửa Lỗi Trong `compare_p24_vs_forecast.py`

**Lỗi tìm thấy**:
- Dòng 223: `row['p24_movement']` → Sửa thành `row['p_mob_movement']`
- Dòng 236: `df['p24_movement_pct']` → Sửa thành `df['p_mob_movement_pct']`

**Nguyên nhân**: Tên biến không khớp với tên cột trong DataFrame

**Kết quả**: ✅ Script đã được sửa và sẵn sàng chạy

---

### 2. Thêm Cell Mới Vào Notebook

**File**: `notebooks/Markovchain_With_Diagnostic_Clean.ipynb`

**Vị trí**: Cell 27 và 28 (trước phần "HOÀN THÀNH")

**Nội dung**:
- Cell 27: Markdown giải thích mục đích
- Cell 28: Code chạy so sánh với MOB 23

**Tham số**:
```python
compare_p24_vs_forecast(
    matrices_by_mob=matrices_by_mob,
    forecast_results=forecast_results,
    actual_results=actual_results,
    disb_total_by_vintage=disb_total_by_vintage,
    buckets_30p=BUCKETS_30P,
    target_mob=23,  # ← Dùng MOB 23 thay vì 24
    forecast_mob_end=29  # ← Forecast đến MOB 29
)
```

---

## 📝 Cách Chạy

### Option 1: Chạy Toàn Bộ Notebook (Khuyến Nghị)

1. Mở notebook: `notebooks/Markovchain_With_Diagnostic_Clean.ipynb`
2. Restart kernel: `Kernel → Restart & Run All`
3. Đợi chạy xong (khoảng 5-10 phút)
4. Xem kết quả ở cell 28

### Option 2: Chỉ Chạy Cell Mới

**Điều kiện**: Bạn đã chạy notebook từ đầu và có các biến:
- `matrices_by_mob`
- `forecast_results`
- `actual_results`
- `disb_total_by_vintage`
- `BUCKETS_30P`

**Các bước**:
1. Mở notebook
2. Scroll xuống cell 27-28
3. Chạy cell 28
4. Xem kết quả

---

## 🔍 Kết Quả Mong Đợi

### Trường Hợp 1: Forecast Match Với P_23 ✅

```
================================================================================
KẾT LUẬN:
================================================================================

📊 Trung bình:
   P_23 movement:   1.5000% per month
   Forecast slope:  1.5200% per month
   Diff:            0.0200% per month

✅ FORECAST MATCH VỚI P_23!
   → Forecast slope ≈ P_23 movement
   → K = 1.0 đang work đúng
   → Vấn đề là P_23 có movement 1.5000%
   → Nếu muốn flatten, cần giảm K hoặc chấp nhận reality
```

**Giải thích**:
- P_23 có movement ~1.5% per month
- Forecast slope cũng ~1.5% per month
- → K = 1.0 đang apply đúng P_23 movement
- → **Vấn đề KHÔNG phải do forecast logic**
- → **Vấn đề là P_23 có movement (không phải 0%)**

**Giải pháp**:
1. **Option 1**: Giảm K xuống 0.0-0.3 cho MOB 24+ → Flatten curve
2. **Option 2**: Chấp nhận P_23 có movement (đây là reality từ data)

---

### Trường Hợp 2: Forecast Cao Hơn P_23 ❌

```
================================================================================
KẾT LUẬN:
================================================================================

📊 Trung bình:
   P_23 movement:   0.5000% per month
   Forecast slope:  1.5000% per month
   Diff:            1.0000% per month

❌ FORECAST CAO HƠN P_23 NHIỀU!
   → Forecast slope cao hơn P_23 movement 1.0000%
   → Có vấn đề trong forecast logic hoặc K values
   → Cần kiểm tra lại code
```

**Giải thích**:
- P_23 chỉ có movement 0.5% per month
- Nhưng forecast slope là 1.5% per month (cao gấp 3x!)
- → **Có vấn đề trong forecast logic**

**Nguyên nhân có thể**:
1. K > 1.0 (không hợp lý)
2. Partial-step formula sai
3. Absorbing states không work
4. Nhiều cohorts dùng parent fallback (rates cao hơn)

**Giải pháp**: Kiểm tra chi tiết từng cohort

---

### Trường Hợp 3: P_23 Thực Sự Ổn Định ✅

```
================================================================================
KẾT LUẬN:
================================================================================

📊 Trung bình:
   P_23 movement:   0.0500% per month
   Forecast slope:  0.0600% per month
   Diff:            0.0100% per month

✅ FORECAST MATCH VỚI P_23!
   → P_23 rất ổn định (< 0.1% movement)
   → K = 1.0 là hợp lý
   → Forecast cũng gần như flatten
```

**Giải thích**:
- P_23 rất ổn định (0.05% movement)
- Forecast cũng gần như flatten (0.06%)
- → **Không có vấn đề gì!**

---

## 📊 Phân Tích Chi Tiết

Script sẽ xuất ra các phân tích:

### 1. Top Cohorts Có Diff Lớn

```
TOP 10 COHORTS CÓ FORECAST > P_23 NHIỀU NHẤT:
================================================================================

Product    Score                     Vintage      P_23       Forecast   Diff       Fallback  
------------------------------------------------------------------------------------------------
T          NA                        2023-07-01   0.5000%    1.8000%    1.3000%    ✓
T          NA                        2023-09-01   0.6000%    1.3000%    0.7000%    ✓
X          D                         2025-12-01   0.8000%    1.1000%    0.3000%    
```

**Nhận xét**:
- Cohorts có diff lớn thường dùng fallback (✓)
- → Parent fallback có rates cao hơn P_23
- → Đây là nguyên nhân chính

### 2. Phân Tích Theo Fallback

```
PHÂN TÍCH THEO FALLBACK:
================================================================================

Cohorts KHÔNG dùng fallback (200):
   P_23 movement:   0.8000%
   Forecast slope:  0.8500%
   Diff:            0.0500%

Cohorts DÙNG fallback (123):
   P_23 movement:   1.5000%  ← Cao hơn!
   Forecast slope:  1.5200%
   Diff:            0.0200%
```

**Nhận xét**:
- Cohorts dùng fallback có P_23 movement cao hơn (1.5% vs 0.8%)
- → Parent fallback có rates cao hơn P_23 thật
- → Đây là vấn đề chính

### 3. Phân Tích Theo Product/Score

```
PHÂN TÍCH THEO SCORE:
================================================================================

Score                     P_23       Forecast   Diff       % Fallback   N Cohorts  
------------------------------------------------------------------------------------
D                         1.2000%    1.2500%    0.0500%    45.0%        72
C                         1.0000%    1.0300%    0.0300%    38.0%        72
B                         0.8000%    0.8200%    0.0200%    25.0%        72
A                         0.5000%    0.5100%    0.0100%    15.0%        72
```

**Nhận xét**:
- Score D có P_23 movement cao nhất (1.2%)
- Score D cũng có % fallback cao nhất (45%)
- → Score D là vấn đề chính

---

## 💾 Export Kết Quả

Sau khi chạy cell, bạn có thể export kết quả:

```python
# Export toàn bộ
df_comparison.to_excel("comparison_p23_vs_forecast.xlsx", index=False)

# Lọc cohorts có diff lớn
df_large_diff = df_comparison[df_comparison["diff_pct"] > 0.5]
df_large_diff.to_excel("cohorts_large_diff.xlsx", index=False)

# Lọc cohorts dùng fallback
df_fallback = df_comparison[df_comparison["is_fallback"]]
df_fallback.to_excel("cohorts_fallback.xlsx", index=False)
```

---

## 🎯 Cách Diễn Giải Kết Quả

### Nếu Diff ≈ 0 (< 0.1%)

```
✅ Forecast match với P_23
→ K = 1.0 đang work đúng
→ Vấn đề là P_23 có movement
→ Giải pháp: Giảm K hoặc chấp nhận reality
```

**Hành động**:
1. Nếu muốn flatten → Giảm K xuống 0.0-0.3 cho MOB 24+
2. Nếu chấp nhận reality → Không cần làm gì

### Nếu Diff > 0.5%

```
❌ Forecast cao hơn P_23 nhiều
→ Có vấn đề trong forecast logic
→ Kiểm tra:
   1. K values có > 1.0 không?
   2. Nhiều cohorts dùng fallback không?
   3. Partial-step formula có đúng không?
```

**Hành động**:
1. Kiểm tra K values (cell 6 trong notebook)
2. Kiểm tra % fallback (cell 7 trong notebook)
3. Kiểm tra chi tiết cohorts có diff lớn

### Nếu P_23 Movement Cao (> 1%)

```
⚠️ P_23 có movement cao
→ Portfolio chưa thực sự ổn định ở MOB 23
→ Giải pháp:
   1. Giảm K để giảm ảnh hưởng
   2. Hoặc chấp nhận đây là reality
```

**Hành động**:
1. Xem lại data: P_23 có thực sự ổn định không?
2. Nếu không ổn định → Giảm K
3. Nếu ổn định → Chấp nhận movement này

---

## 🔄 So Sánh Với Kết Quả Trước

### Kết Quả Trước (MOB 24)

```
⚠️ Không tìm thấy cohorts nào có đủ data
```

**Nguyên nhân**: Không có đủ cohorts có data ở MOB 24

### Kết Quả Mới (MOB 23)

Sẽ có data vì:
- MOB 23 có nhiều cohorts hơn MOB 24
- Nhiều cohorts đã đến MOB 23 nhưng chưa đến MOB 24

---

## 📝 Tóm Tắt

### Đã Làm

1. ✅ Sửa lỗi trong `compare_p24_vs_forecast.py`
2. ✅ Thêm cell mới vào notebook để so sánh với MOB 23
3. ✅ Tạo hướng dẫn chi tiết

### Bước Tiếp Theo

1. **Chạy notebook** (Option 1 hoặc 2 ở trên)
2. **Xem kết quả** ở cell 28
3. **Diễn giải kết quả** theo hướng dẫn
4. **Quyết định giải pháp**:
   - Nếu forecast match với P_23 → Giảm K hoặc chấp nhận reality
   - Nếu forecast cao hơn P_23 → Kiểm tra lại code

### Câu Hỏi Sẽ Được Trả Lời

1. ✅ P_23 có movement bao nhiêu?
2. ✅ Forecast slope có match với P_23 không?
3. ✅ Nếu match → Vấn đề là P_23 có movement
4. ✅ Nếu không match → Có bug trong forecast logic
5. ✅ Cohorts nào có vấn đề?
6. ✅ Fallback có ảnh hưởng không?
7. ✅ Product/Score nào có vấn đề?

---

## 🎯 Kết Luận

Script này sẽ giúp bạn hiểu rõ:
- **Root cause** của vấn đề DEL tăng sau MOB 24
- **Forecast logic** có đúng không
- **K values** có hợp lý không
- **Giải pháp** cụ thể để fix

**Chạy notebook và cho tôi biết kết quả nhé!** 🚀
