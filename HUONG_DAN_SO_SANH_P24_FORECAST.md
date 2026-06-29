# 🔬 Hướng Dẫn So Sánh P_24 Movement vs Forecast Slope

## Mục Đích

So sánh P_24 movement (từ transition matrix) với forecast slope (từ forecast results) để hiểu:
1. P_24 có movement bao nhiêu?
2. Forecast slope có match với P_24 không?
3. Nếu không match → Tại sao?

---

## Cách Chạy

Trong notebook, thêm cell:

```python
from compare_p24_vs_forecast import compare_p24_vs_forecast

df_comparison = compare_p24_vs_forecast(
    matrices_by_mob=matrices_by_mob,
    forecast_results=forecast_results,
    actual_results=actual_results,
    disb_total_by_vintage=disb_total_by_vintage,
    buckets_30p=BUCKETS_30P
)

# Xem kết quả
print(df_comparison.head(20))

# Export ra Excel để phân tích chi tiết
df_comparison.to_excel("comparison_p24_vs_forecast.xlsx", index=False)
```

---

## Kết Quả Mong Đợi

### Trường Hợp 1: Forecast Match Với P_24 ✅

```
================================================================================
KẾT LUẬN:
================================================================================

📊 Trung bình:
   P_24 movement:   1.5000% per month
   Forecast slope:  1.5200% per month
   Diff:            0.0200% per month

✅ FORECAST MATCH VỚI P_24!
   → Forecast slope ≈ P_24 movement
   → K = 1.0 đang work đúng
   → Vấn đề là P_24 có movement 1.5000%
   → Nếu muốn flatten, cần giảm K hoặc chấp nhận reality
```

**Giải thích**:
- P_24 có movement 1.5% per month
- Forecast slope cũng 1.5% per month
- → K = 1.0 đang apply đúng P_24 movement
- → Vấn đề KHÔNG phải do forecast logic
- → Vấn đề là P_24 có movement (không phải 0%)

**Giải pháp**:
- Option 1: Giảm K xuống 0.0 → Flatten hoàn toàn
- Option 2: Chấp nhận P_24 có movement (đây là reality)

---

### Trường Hợp 2: Forecast Cao Hơn P_24 ❌

```
================================================================================
KẾT LUẬN:
================================================================================

📊 Trung bình:
   P_24 movement:   0.5000% per month
   Forecast slope:  1.5000% per month
   Diff:            1.0000% per month

❌ FORECAST CAO HƠN P_24 NHIỀU!
   → Forecast slope cao hơn P_24 movement 1.0000%
   → Có vấn đề trong forecast logic hoặc K values
   → Cần kiểm tra lại code
```

**Giải thích**:
- P_24 chỉ có movement 0.5% per month
- Nhưng forecast slope là 1.5% per month (cao gấp 3x!)
- → Có vấn đề trong forecast logic

**Nguyên nhân có thể**:
1. K > 1.0 (không hợp lý)
2. Partial-step formula sai
3. Absorbing states không work
4. Nhiều cohorts dùng parent fallback (rates cao hơn)

**Giải pháp**: Kiểm tra chi tiết từng cohort

---

### Trường Hợp 3: P_24 Thực Sự Ổn Định ✅

```
================================================================================
KẾT LUẬN:
================================================================================

📊 Trung bình:
   P_24 movement:   0.0500% per month
   Forecast slope:  0.0600% per month
   Diff:            0.0100% per month

✅ FORECAST MATCH VỚI P_24!
   → P_24 rất ổn định (< 0.1% movement)
   → K = 1.0 là hợp lý
   → Forecast cũng gần như flatten
```

**Giải thích**:
- P_24 rất ổn định (0.05% movement)
- Forecast cũng gần như flatten (0.06%)
- → Không có vấn đề gì!

---

## Phân Tích Chi Tiết

### 1. Top Cohorts Có Diff Lớn

```
TOP 10 COHORTS CÓ FORECAST > P_24 NHIỀU NHẤT:
================================================================================

Product    Score                     Vintage      P_24       Forecast   Diff       Fallback  
------------------------------------------------------------------------------------------------
T          NA                        2023-07-01   0.5000%    1.8000%    1.3000%    ✓
T          NA                        2023-09-01   0.6000%    1.3000%    0.7000%    ✓
X          D                         2025-12-01   0.8000%    1.1000%    0.3000%    
```

**Nhận xét**:
- Cohorts có diff lớn thường dùng fallback (✓)
- → Parent fallback có rates cao hơn P_24
- → Đây là nguyên nhân chính

### 2. Phân Tích Theo Fallback

```
PHÂN TÍCH THEO FALLBACK:
================================================================================

Cohorts KHÔNG dùng fallback (200):
   P_24 movement:   0.8000%
   Forecast slope:  0.8500%
   Diff:            0.0500%

Cohorts DÙNG fallback (123):
   P_24 movement:   1.5000%  ← Cao hơn!
   Forecast slope:  1.5200%
   Diff:            0.0200%
```

**Nhận xét**:
- Cohorts dùng fallback có P_24 movement cao hơn (1.5% vs 0.8%)
- → Parent fallback có rates cao hơn P_24 thật
- → Đây là vấn đề chính

### 3. Phân Tích Theo Product/Score

```
PHÂN TÍCH THEO SCORE:
================================================================================

Score                     P_24       Forecast   Diff       % Fallback   N Cohorts  
------------------------------------------------------------------------------------
D                         1.2000%    1.2500%    0.0500%    45.0%        72
C                         1.0000%    1.0300%    0.0300%    38.0%        72
B                         0.8000%    0.8200%    0.0200%    25.0%        72
A                         0.5000%    0.5100%    0.0100%    15.0%        72
```

**Nhận xét**:
- Score D có P_24 movement cao nhất (1.2%)
- Score D cũng có % fallback cao nhất (45%)
- → Score D là vấn đề chính

---

## Cách Diễn Giải

### Nếu Diff ≈ 0 (< 0.1%)

```
✅ Forecast match với P_24
→ K = 1.0 đang work đúng
→ Vấn đề là P_24 có movement
→ Giải pháp: Giảm K hoặc chấp nhận reality
```

### Nếu Diff > 0.5%

```
❌ Forecast cao hơn P_24 nhiều
→ Có vấn đề trong forecast logic
→ Kiểm tra:
   1. K values có > 1.0 không?
   2. Nhiều cohorts dùng fallback không?
   3. Partial-step formula có đúng không?
```

### Nếu P_24 Movement Cao (> 1%)

```
⚠️ P_24 có movement cao
→ Portfolio chưa thực sự ổn định ở MOB 24
→ Giải pháp:
   1. Giảm K để giảm ảnh hưởng
   2. Hoặc chấp nhận đây là reality
```

---

## Export Kết Quả

```python
# Export ra Excel
df_comparison.to_excel("comparison_p24_vs_forecast.xlsx", index=False)

# Lọc cohorts có diff lớn
df_large_diff = df_comparison[df_comparison["diff_pct"] > 0.5]
df_large_diff.to_excel("cohorts_large_diff.xlsx", index=False)

# Lọc cohorts dùng fallback
df_fallback = df_comparison[df_comparison["is_fallback"]]
df_fallback.to_excel("cohorts_fallback.xlsx", index=False)
```

---

## Tóm Tắt

Script này giúp bạn:
1. ✅ Xem P_24 có movement bao nhiêu (actual)
2. ✅ Xem forecast slope là bao nhiêu (predicted)
3. ✅ So sánh diff → Hiểu forecast có match với P_24 không
4. ✅ Phân tích theo fallback, product, score
5. ✅ Tìm cohorts có vấn đề

**Chạy script và cho tôi biết kết quả nhé!**
