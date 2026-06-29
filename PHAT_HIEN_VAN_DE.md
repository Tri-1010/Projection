# 🎯 Phát Hiện Vấn Đề: Tại Sao DEL Tăng Sau MOB 24?

## ✅ Bạn Đúng!

Nếu từ dữ liệu quá khứ P_24 ổn định → K = 1.0 là ĐÚNG!

Vậy tại sao DEL vẫn tăng?

---

## 🔍 Có 3 Khả Năng

### Khả Năng 1: Nhiều Cohorts Dùng Parent Fallback ⚠️

**Vấn đề**:
```
Cohort A (đủ data): Dùng P_24 ổn định → Flatten ✅
Cohort B (thiếu data): Dùng Parent fallback → Tăng ❌
Cohort C (thiếu data): Dùng Parent fallback → Tăng ❌
```

**Tại sao parent fallback cao hơn P_24?**
- Parent fallback = Tổng hợp MOB 1-24
- MOB 1-12: Movement cao (portfolio mới)
- MOB 13-24: Movement thấp (portfolio mature)
- Trung bình → Cao hơn P_24 thuần túy

**Cách kiểm tra**:
```python
# Chạy Cell 7 trong notebook
# Xem % cohorts dùng fallback
```

**Nếu > 30% dùng fallback** → Đây là vấn đề chính!

---

### Khả Năng 2: Absorbing States Chưa Đúng ❌

**Config hiện tại**:
```python
BUCKETS_CANON = [
    "DPD0", "DPD1+", "DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+",
    "PREPAY", "WRITEOFF", "SOLDOUT"
]

ABSORBING_BASE = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]
```

**Vấn đề**:
- DPD90+ là absorbing state
- Nhưng vẫn có DPD120+ và DPD180+ trong BUCKETS_CANON
- → DPD90+ có thể chuyển sang DPD120+, DPD180+
- → DEL vẫn tăng!

**Ví dụ**:
```
Tháng 24: 100 loans ở DPD90+
Tháng 25: 
  - 80 loans ở DPD90+ (stay)
  - 15 loans → DPD120+ (deteriorate)
  - 5 loans → DPD180+ (deteriorate)

→ DEL90+ không đổi (100 loans)
→ Nhưng DEL120+ tăng (15 loans)
→ DEL180+ tăng (5 loans)
```

**Giải pháp**:

**Option 1**: Bỏ DPD120+ và DPD180+ khỏi BUCKETS_CANON
```python
BUCKETS_CANON = [
    "DPD0", "DPD1+", "DPD30+", "DPD60+", "DPD90+",
    "PREPAY", "WRITEOFF", "SOLDOUT"
]
```

**Option 2**: Thay đổi absorbing states
```python
ABSORBING_BASE = ["DPD180+", "WRITEOFF", "PREPAY", "SOLDOUT"]
```

**Option 3**: Gộp DPD90+, DPD120+, DPD180+ thành 1 state
```python
# Trong data preprocessing
df.loc[df["STATE_MODEL"].isin(["DPD120+", "DPD180+"]), "STATE_MODEL"] = "DPD90+"
```

---

### Khả Năng 3: Aggregation Effect 📊

**Vấn đề**: Khi tổng hợp nhiều cohorts lên product level

**Ví dụ**:
```
Cohort 2023-01 (weight 30%): Flatten ✅
Cohort 2023-02 (weight 25%): Flatten ✅
Cohort 2023-03 (weight 20%): Flatten ✅
Cohort 2023-04 (weight 15%): Tăng mạnh ❌
Cohort 2023-05 (weight 10%): Tăng mạnh ❌

Tổng hợp: 75% flatten + 25% tăng = Tăng nhẹ
```

**Cách kiểm tra**:
```python
# Chạy Cell 9 trong notebook
# Xem cohorts nào đang tăng
```

---

## 🔬 Cách Kiểm Tra Từng Khả Năng

### Bước 1: Kiểm tra % Fallback

```python
# Trong notebook, thêm cell:

total_cohorts = 0
fallback_cohorts = 0

for prod_str in matrices_by_mob.keys():
    if 24 in matrices_by_mob[prod_str]:
        for score_str in matrices_by_mob[prod_str][24].keys():
            total_cohorts += 1
            is_fallback = matrices_by_mob[prod_str][24][score_str].get("is_fallback", False)
            if is_fallback:
                fallback_cohorts += 1

fallback_pct = fallback_cohorts / total_cohorts * 100 if total_cohorts > 0 else 0

print(f"Tổng cohorts: {total_cohorts}")
print(f"Cohorts dùng fallback: {fallback_cohorts} ({fallback_pct:.1f}%)")

if fallback_pct > 30:
    print("\n❌ VẤN ĐỀ: Quá nhiều cohorts dùng fallback!")
    print("   → Đây là nguyên nhân chính")
elif fallback_pct > 10:
    print("\n⚠️ Có một số cohorts dùng fallback")
else:
    print("\n✅ Ít cohorts dùng fallback")
```

### Bước 2: Kiểm tra Absorbing States

```python
# Kiểm tra P_24 có movement từ DPD90+ không

prod_str = "C"  # Thay bằng product của bạn
score_str = "650+_10M-_POS"  # Thay bằng score của bạn

if 24 in matrices_by_mob[prod_str] and score_str in matrices_by_mob[prod_str][24]:
    P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
    
    if "DPD90+" in P_24.index:
        print("Transition rates từ DPD90+:")
        print(P_24.loc["DPD90+"])
        
        # Kiểm tra có movement sang DPD120+, DPD180+ không
        if "DPD120+" in P_24.columns:
            rate_120 = P_24.loc["DPD90+", "DPD120+"]
            print(f"\nDPD90+ → DPD120+: {rate_120:.4f} ({rate_120*100:.2f}%)")
            
            if rate_120 > 0.01:
                print("❌ VẤN ĐỀ: DPD90+ vẫn chuyển sang DPD120+!")
                print("   → Absorbing state không đúng")
        
        if "DPD180+" in P_24.columns:
            rate_180 = P_24.loc["DPD90+", "DPD180+"]
            print(f"DPD90+ → DPD180+: {rate_180:.4f} ({rate_180*100:.2f}%)")
            
            if rate_180 > 0.01:
                print("❌ VẤN ĐỀ: DPD90+ vẫn chuyển sang DPD180+!")
                print("   → Absorbing state không đúng")
```

### Bước 3: Kiểm tra Aggregation

```python
# Chạy Cell 9 trong notebook
# Xem cohorts nào đang tăng
```

---

## 🎯 Kết Luận

### Nếu Bạn Thấy P_24 Ổn Định Từ Dữ Liệu Quá Khứ:

✅ **K = 1.0 là ĐÚNG**
✅ **Vấn đề KHÔNG phải do K cao**

### Vấn Đề Thực Sự Có Thể Là:

1. **Nhiều cohorts dùng parent fallback** (> 30%)
   - Parent fallback có rates cao hơn P_24
   - → Giải pháp: Tăng MIN_OBS/MIN_EAD

2. **Absorbing states chưa đúng**
   - DPD90+ vẫn chuyển sang DPD120+, DPD180+
   - → Giải pháp: Sửa BUCKETS_CANON hoặc ABSORBING_BASE

3. **Aggregation effect**
   - Một số cohorts tăng mạnh kéo tổng tăng
   - → Giải pháp: Phân tích chi tiết từng cohort

---

## 🔧 Giải Pháp Đề Xuất

### Giải Pháp 1: Sửa Absorbing States (Khuyến Nghị) ⭐

**Nếu bạn muốn DEL90+ flatten**:

```python
# Trong src/config.py
BUCKETS_CANON = [
    "DPD0", "DPD1+", "DPD30+", "DPD60+", "DPD90+",
    "PREPAY", "WRITEOFF", "SOLDOUT"
]

ABSORBING_BASE = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]
```

**Hoặc nếu bạn muốn track DPD120+, DPD180+**:

```python
ABSORBING_BASE = ["DPD180+", "WRITEOFF", "PREPAY", "SOLDOUT"]
```

### Giải Pháp 2: Tăng MIN_OBS/MIN_EAD

**Nếu nhiều cohorts dùng fallback**:

```python
# Trong src/config.py
MIN_OBS = 200  # Thay vì 100
MIN_EAD = 500  # Thay vì 100
```

---

## 📝 Tóm Tắt

**Bạn đúng**: K = 1.0 không phải vấn đề nếu P_24 ổn định

**Vấn đề thực sự**: 
1. Nhiều cohorts dùng parent fallback (rates cao hơn)
2. Absorbing states chưa đúng (DPD90+ → DPD120+, DPD180+)
3. Aggregation effect

**Cần làm**: Chạy 2 cells kiểm tra ở trên để xác định nguyên nhân chính xác
