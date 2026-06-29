# ✅ Sửa Lại Logic MIN_OBS/MIN_EAD

## ❌ Logic Sai (Trong Diagnostic Cũ)

```
Vấn đề: Nhiều cohorts dùng parent fallback
Giải pháp: TĂNG MIN_OBS/MIN_EAD
Kết quả: ❌ SAI - Càng nhiều cohorts dùng fallback hơn!
```

## ✅ Logic Đúng

### MIN_OBS/MIN_EAD Làm Gì?

```python
# Trong code build transition matrix
if n_obs < MIN_OBS or ead < MIN_EAD:
    # Không đủ data → Dùng parent fallback
    use_fallback = True
else:
    # Đủ data → Dùng P_24 thật
    use_fallback = False
```

### Tăng MIN_OBS → Nhiều Fallback Hơn

```
MIN_OBS = 100:
  Cohort A: 150 obs → Dùng P_24 ✅
  Cohort B: 80 obs  → Dùng fallback ❌
  Cohort C: 120 obs → Dùng P_24 ✅
  → 2/3 dùng P_24

MIN_OBS = 200:
  Cohort A: 150 obs → Dùng fallback ❌
  Cohort B: 80 obs  → Dùng fallback ❌
  Cohort C: 120 obs → Dùng fallback ❌
  → 0/3 dùng P_24, 3/3 dùng fallback!
```

### Giảm MIN_OBS → Ít Fallback Hơn

```
MIN_OBS = 100:
  Cohort A: 150 obs → Dùng P_24 ✅
  Cohort B: 80 obs  → Dùng fallback ❌
  Cohort C: 120 obs → Dùng P_24 ✅
  → 2/3 dùng P_24

MIN_OBS = 50:
  Cohort A: 150 obs → Dùng P_24 ✅
  Cohort B: 80 obs  → Dùng P_24 ✅
  Cohort C: 120 obs → Dùng P_24 ✅
  → 3/3 dùng P_24, 0/3 dùng fallback!
```

---

## 🎯 Khi Nào Dùng Giải Pháp Nào?

### Tình Huống 1: P_24 Ổn Định, Nhiều Cohorts Dùng Fallback

**Triệu chứng**:
- P_24 ổn định từ dữ liệu quá khứ ✅
- Nhưng > 30% cohorts dùng parent fallback ❌
- Parent fallback có rates cao hơn P_24

**Nguyên nhân**:
- MIN_OBS/MIN_EAD quá cao
- Nhiều cohorts không đủ điều kiện dùng P_24
- Phải dùng parent fallback (rates cao)

**Giải pháp**: **GIẢM** MIN_OBS/MIN_EAD

```python
# Trong src/config.py
MIN_OBS = 50   # Thay vì 100
MIN_EAD = 50   # Thay vì 100
```

**Kết quả**:
- Nhiều cohorts đủ điều kiện dùng P_24 thật
- Ít cohorts dùng parent fallback
- DEL flatten hơn

---

### Tình Huống 2: P_24 Không Ổn Định Do Data Ít

**Triệu chứng**:
- P_24 có movement cao (> 3%) ❌
- Nhưng ít cohorts dùng fallback (< 10%) ✅
- P_24 không đáng tin do data ít

**Nguyên nhân**:
- MIN_OBS/MIN_EAD quá thấp
- Cohorts với data ít vẫn dùng P_24
- P_24 không đáng tin (noise)

**Giải pháp**: **TĂNG** MIN_OBS/MIN_EAD

```python
# Trong src/config.py
MIN_OBS = 200  # Thay vì 100
MIN_EAD = 500  # Thay vì 100
```

**Kết quả**:
- Chỉ cohorts có data đủ mới dùng P_24
- P_24 đáng tin cậy hơn
- Nhưng nhiều cohorts dùng fallback hơn (trade-off)

---

### Tình Huống 3: P_24 Ổn Định, Ít Cohorts Dùng Fallback

**Triệu chứng**:
- P_24 ổn định ✅
- Ít cohorts dùng fallback (< 10%) ✅
- Nhưng DEL vẫn tăng ❌

**Nguyên nhân**:
- KHÔNG phải do fallback
- KHÔNG phải do P_24 không ổn định
- Có thể là:
  1. Absorbing states chưa đúng
  2. Aggregation effect
  3. K values (nhưng bạn đã xác nhận P_24 ổn định)

**Giải pháp**: KHÔNG sửa MIN_OBS/MIN_EAD

Kiểm tra:
1. Absorbing states (DPD90+ → DPD120+, DPD180+?)
2. Aggregation effect (cohorts nào đang tăng?)

---

## 📊 Bảng Tóm Tắt

| P_24 Ổn Định? | % Fallback | Giải Pháp | Kết Quả |
|---------------|------------|-----------|---------|
| ✅ Có | ❌ Cao (> 30%) | **GIẢM** MIN_OBS | Ít fallback, DEL flatten |
| ❌ Không | ✅ Thấp (< 10%) | **TĂNG** MIN_OBS | P_24 đáng tin hơn |
| ✅ Có | ✅ Thấp | **KHÔNG sửa** | Kiểm tra absorbing states |
| ❌ Không | ❌ Cao | **Cả 2 đều sai** | Cần phân tích sâu hơn |

---

## 🔧 Trong Trường Hợp Của Bạn

Bạn nói: "Từ dữ liệu quá khứ tôi thấy nó ổn định"

→ P_24 ổn định ✅

**Nếu nhiều cohorts dùng fallback** (> 30%):
```python
# Giải pháp: GIẢM MIN_OBS/MIN_EAD
MIN_OBS = 50   # Thay vì 100
MIN_EAD = 50   # Thay vì 100
```

**Nếu ít cohorts dùng fallback** (< 10%):
```python
# Không sửa MIN_OBS/MIN_EAD
# Kiểm tra absorbing states thay vì
```

---

## 🎯 Kết Luận

### Bạn Đúng Khi Thắc Mắc!

Tăng MIN_OBS/MIN_EAD **KHÔNG** làm ổn định hơn trong trường hợp của bạn.

### Logic Đúng:

**Nếu P_24 ổn định + nhiều fallback**:
- Giải pháp: **GIẢM** MIN_OBS/MIN_EAD
- Kết quả: Nhiều cohorts dùng P_24 ổn định, ít fallback

**Nếu P_24 không ổn định + ít fallback**:
- Giải pháp: **TĂNG** MIN_OBS/MIN_EAD
- Kết quả: P_24 đáng tin hơn, nhưng nhiều fallback (trade-off)

### Trong Trường Hợp Của Bạn:

Nếu P_24 đã ổn định → Vấn đề có thể là:
1. **Nhiều cohorts dùng fallback** → GIẢM MIN_OBS
2. **Absorbing states chưa đúng** → Sửa BUCKETS_CANON
3. **Aggregation effect** → Phân tích chi tiết

---

**Xin lỗi về sự nhầm lẫn trong diagnostic trước!**
