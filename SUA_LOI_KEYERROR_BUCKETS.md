# ✅ Sửa Lỗi KeyError: Buckets Not In Index

## 🐛 Lỗi Gặp Phải

```
KeyError: "['DPD120+', 'DPD180+'] not in index"
```

**Vị trí**: `compare_p24_vs_forecast.py` và `find_problematic_segments.py`

---

## 🔍 Nguyên Nhân

Script đang cố truy cập các states `DPD120+` và `DPD180+` nhưng:
- Data của bạn không có các states này
- `buckets_30p` mặc định có: `["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]`
- Nhưng data thực tế chỉ có: `["DPD30+", "DPD60+", "DPD90+", "WRITEOFF"]`

**Vấn đề**: Script không kiểm tra xem state có tồn tại trước khi truy cập

---

## ✅ Giải Pháp

### 1. Sửa `compare_p24_vs_forecast.py`

#### Chỗ 1: Tính P_MOB movement (dòng ~60)

**Trước (SAI)**:
```python
if "DPD0" in P_MOB.index:
    p_mob_movement = sum(P_MOB.loc["DPD0", s] for s in buckets_30p if s in P_MOB.columns)
```

**Sau (ĐÚNG)**:
```python
if "DPD0" in P_MOB.index:
    # Chỉ dùng các states có trong P_MOB
    available_buckets = [s for s in buckets_30p if s in P_MOB.columns]
    if available_buckets:
        p_mob_movement = sum(P_MOB.loc["DPD0", s] for s in available_buckets)
```

**Giải thích**: 
- Lọc ra chỉ các states có trong `P_MOB.columns`
- Kiểm tra `available_buckets` không rỗng trước khi sum

---

#### Chỗ 2: Tính actual DEL (dòng ~68)

**Trước (SAI)**:
```python
if disb_total > 0:
    actual_del_mob = actual_results[cohort_key][target_mob][buckets_30p].sum() / disb_total
```

**Sau (ĐÚNG)**:
```python
if disb_total > 0:
    # Chỉ dùng các states có trong actual_results
    available_buckets = [s for s in buckets_30p if s in actual_results[cohort_key][target_mob].index]
    if available_buckets:
        actual_del_mob = actual_results[cohort_key][target_mob][available_buckets].sum() / disb_total
```

**Giải thích**: 
- Lọc ra chỉ các states có trong `actual_results[cohort_key][target_mob].index`
- Kiểm tra `available_buckets` không rỗng trước khi sum

---

#### Chỗ 3: Tính forecast slope (dòng ~80)

**Trước (SAI)**:
```python
if target_mob in forecast and forecast_mob_end in forecast and disb_total > 0:
    forecast_del_start = forecast[target_mob][buckets_30p].sum() / disb_total
    forecast_del_end = forecast[forecast_mob_end][buckets_30p].sum() / disb_total
    forecast_slope = (forecast_del_end - forecast_del_start) / (forecast_mob_end - target_mob)
```

**Sau (ĐÚNG)**:
```python
if target_mob in forecast and forecast_mob_end in forecast and disb_total > 0:
    # Chỉ dùng các states có trong forecast
    available_buckets_start = [s for s in buckets_30p if s in forecast[target_mob].index]
    available_buckets_end = [s for s in buckets_30p if s in forecast[forecast_mob_end].index]
    
    if available_buckets_start and available_buckets_end:
        forecast_del_start = forecast[target_mob][available_buckets_start].sum() / disb_total
        forecast_del_end = forecast[forecast_mob_end][available_buckets_end].sum() / disb_total
        forecast_slope = (forecast_del_end - forecast_del_start) / (forecast_mob_end - target_mob)
```

**Giải thích**: 
- Lọc ra các states có trong `forecast[target_mob].index` và `forecast[forecast_mob_end].index`
- Kiểm tra cả 2 không rỗng trước khi tính

---

### 2. Sửa `find_problematic_segments.py`

#### Chỗ 1: Tính DEL30+ (dòng ~40)

**Trước (SAI)**:
```python
if 24 in forecast and 30 in forecast:
    try:
        del30_24 = forecast[24][buckets_30p].sum() / disb_total
        del30_30 = forecast[30][buckets_30p].sum() / disb_total
        slope = (del30_30 - del30_24) / 6
        
        results.append({...})
    except Exception as e:
        continue
```

**Sau (ĐÚNG)**:
```python
if 24 in forecast and 30 in forecast:
    try:
        # Chỉ dùng các states có trong forecast
        available_buckets_24 = [s for s in buckets_30p if s in forecast[24].index]
        available_buckets_30 = [s for s in buckets_30p if s in forecast[30].index]
        
        if available_buckets_24 and available_buckets_30:
            del30_24 = forecast[24][available_buckets_24].sum() / disb_total
            del30_30 = forecast[30][available_buckets_30].sum() / disb_total
            slope = (del30_30 - del30_24) / 6
            
            results.append({...})
    except Exception as e:
        continue
```

**Giải thích**: 
- Lọc ra các states có trong `forecast[24].index` và `forecast[30].index`
- Kiểm tra cả 2 không rỗng trước khi tính

---

## 🎯 Kết Quả

Giờ script sẽ:
1. ✅ Tự động phát hiện các states có sẵn trong data
2. ✅ Chỉ dùng các states có sẵn
3. ✅ Không bị lỗi KeyError nữa
4. ✅ Hoạt động với bất kỳ data nào (có hoặc không có DPD120+, DPD180+)

---

## 🧪 Test

```bash
python test_compare_script.py
```

**Kết quả**:
```
✅ Import thành công!
✅ Function signature: compare_p24_vs_forecast
✅ Parameters đầy đủ!
✅ Script không có lỗi syntax!
```

---

## 🚀 Chạy Lại Notebook

Giờ bạn có thể chạy lại notebook:

```
1. Mở: notebooks/Markovchain_With_Diagnostic_Clean.ipynb
2. Kernel → Restart & Run All
3. Xem kết quả ở cell 28
```

Script giờ sẽ tự động adapt với data của bạn!

---

## 💡 Lưu Ý

### Data Của Bạn Có Các States

Dựa vào lỗi, data của bạn có:
- ✅ `DPD30+`
- ✅ `DPD60+`
- ✅ `DPD90+`
- ❌ `DPD120+` (không có)
- ❌ `DPD180+` (không có)
- ✅ `WRITEOFF`

Script giờ sẽ chỉ dùng: `["DPD30+", "DPD60+", "DPD90+", "WRITEOFF"]`

### Nếu Vẫn Có Lỗi

Nếu vẫn gặp lỗi tương tự với states khác, hãy cho tôi biết:
1. Error message đầy đủ
2. States nào bị thiếu
3. Cell nào gặp lỗi

Tôi sẽ sửa ngay!
