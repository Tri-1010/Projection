# 📚 Diagnostic DEL Tăng - Tài Liệu Đầy Đủ

## 🎯 Mục Đích

Chẩn đoán và sửa vấn đề: **DEL curve tăng liên tục sau MOB 24** thay vì đi ngang (flatten).

---

## 📁 Files Quan Trọng

### 🔴 Notebook (Chính)
| File | Mô Tả | Trạng Thái |
|------|-------|-----------|
| `notebooks/Markovchain_With_Diagnostic.ipynb` | Notebook chính - Model + Diagnostic + Giải pháp | ✅ Sẵn sàng |
| `notebooks/Markovchain_With_Diagnostic_Clean.ipynb` | Backup (re-formatted) | ✅ Sẵn sàng |

### 📘 Hướng Dẫn
| File | Mô Tả | Dành Cho |
|------|-------|----------|
| `QUICK_START_DIAGNOSTIC.md` | Quick start (3 bước) | Người mới |
| `DA_SUA_XONG.md` | Hướng dẫn đầy đủ (Vietnamese) | Tất cả |
| `DIAGNOSTIC_NOTEBOOK_READY.md` | Technical details | Advanced |
| `HUONG_DAN_CHAY_DIAGNOSTIC.md` | Hướng dẫn chi tiết + Giải pháp | Tất cả |
| `BAT_DAU_DIAGNOSTIC.md` | Quick start (cũ) | Reference |

### 🔧 Scripts
| File | Mô Tả | Cách Dùng |
|------|-------|-----------|
| `diagnose_why_increase_after_24.py` | Diagnostic script | Import vào notebook |
| `test_notebook_open.py` | Test notebook validity | `python test_notebook_open.py` |
| `validate_notebook.py` | Validate JSON | `python validate_notebook.py` |
| `check_notebook_encoding.py` | Check encoding | `python check_notebook_encoding.py` |

### 📊 Documentation
| File | Mô Tả |
|------|-------|
| `EXPLANATION_TRANSITION_MATRIX_FALLBACK.md` | Giải thích fallback logic |
| `CHECK_PARENT_FALLBACK_USAGE.md` | Kiểm tra parent fallback |
| `DIAGNOSIS_CONTINUOUS_INCREASE.md` | Phân tích vấn đề |
| `NEXT_STEPS_DIAGNOSIS.md` | Các bước tiếp theo |

---

## 🚀 Quick Start

### Bước 1: Mở Notebook
```bash
jupyter notebook notebooks/Markovchain_With_Diagnostic.ipynb
```

### Bước 2: Sửa Data Path (Cell 2)
```python
DATA_PATH = 'C:/Users/User/Projection_PB/Projection_pb/ETB_Parquet_YYYYMM'
MAX_MOB = 36
```

### Bước 3: Chạy Cells
1. **Cells 1-5**: Chạy model (Setup → Load → Build → Calibrate → Forecast)
2. **Cells 6-10**: Chạy diagnostic (K values → Fallback → Compare → Analyze → Conclude)
3. **Cells 11-12**: Áp dụng giải pháp (nếu cần)

---

## 📖 Cấu Trúc Notebook

### PHẦN 1: MODEL EXECUTION (Cells 1-5)
```
Cell 1: Setup & Import
  ↓
Cell 2: Load Data (⚠️ SỬA DATA_PATH Ở ĐÂY!)
  ↓
Cell 3: Build Transition Matrices
  ↓
Cell 4: Calibration (K values)
  ↓
Cell 5: Forecast
```

### PHẦN 2: DIAGNOSTIC (Cells 6-10)
```
Cell 6: Kiểm tra K values
  → Xem có MOB nào có K > 0.9 không?
  
Cell 7: Kiểm tra % cohorts dùng fallback
  → Xem có > 30% cohorts dùng fallback không?
  
Cell 8: So sánh P_24 vs Parent fallback
  → Xác nhận parent fallback có rates cao hơn
  
Cell 9: Phân tích từng cohort
  → Xem cohorts nào đang tăng mạnh
  
Cell 10: Kết luận và khuyến nghị
  → Đọc kết luận và quyết định giải pháp
```

### PHẦN 3: GIẢI PHÁP (Cells 11-12)
```
Cell 11: Giải pháp 1 - Cap K ở MOB 25+
  → Chỉ chạy nếu Cell 10 khuyến nghị
  → Cap K xuống 0.3 cho MOB 25-36
  
Cell 12: Giải pháp 2 - Tăng MIN_OBS/MIN_EAD
  → Chỉ áp dụng nếu Cell 10 khuyến nghị
  → Sửa src/config.py và chạy lại từ đầu
```

---

## 🔍 Ba Nguyên Nhân Có Thể

### 1. K Values Quá Cao ở MOB 25+
**Triệu chứng**: Cell 6 cho thấy K > 0.9 ở MOB 25+

**Giải thích**:
- K cao → Model tin Markov quá nhiều
- Markov gây movement → DEL tăng
- Cần giảm K xuống ~0.3

**Giải pháp**: Chạy Cell 11 (Cap K)

### 2. Nhiều Cohorts Dùng Parent Fallback ở MOB 24
**Triệu chứng**: Cell 7 cho thấy > 30% cohorts dùng fallback

**Giải thích**:
- Cohorts không đủ data ở MOB 24 (n_obs < 100 hoặc EAD < 100)
- Dùng parent fallback (tổng hợp MOB 1-24)
- Parent fallback có rates cao hơn → DEL tăng

**Giải pháp**: Làm theo Cell 12 (Tăng MIN_OBS/MIN_EAD)

### 3. Aggregation Effect
**Triệu chứng**: Cell 9 cho thấy một số cohorts tăng mạnh

**Giải thích**:
- Khi tổng hợp cohorts lên product level
- Một số cohorts có weight cao đang kéo DEL tăng
- Cần phân tích chi tiết từng cohort

**Giải pháp**: Phân tích sâu hơn, có thể cần điều chỉnh weighting

---

## 📊 Kết Quả Mong Đợi

### Cell 6: K Values
```
================================================================================
1️⃣ KIỂM TRA K VALUES
================================================================================

   MOB  |  K value  |  Status
   -----|-----------|----------
   20   |   0.750   | ⚠️ Cao
   21   |   0.800   | ⚠️ Cao
   22   |   0.820   | ⚠️ Cao
   23   |   0.840   | ✅ Trung bình
   24   |   0.850   | ✅ Trung bình
   25   |   0.920   | ❌ Rất cao
   26   |   0.950   | ❌ Rất cao
   27   |   0.960   | ❌ Rất cao
   ...

--------------------------------------------------------------------------------

❌ PHÁT HIỆN VẤN ĐỀ: 3 MOBs có K quá cao
   - MOB 25: k=0.920
   - MOB 26: k=0.950
   - MOB 27: k=0.960

💡 Giải thích:
   - K cao → Model tin Markov quá nhiều
   - Markov gây movement → DEL tăng
   - Cần giảm K xuống ~0.3 cho MOB 25+
```

### Cell 7: Fallback Usage
```
================================================================================
2️⃣ KIỂM TRA % COHORTS DÙNG FALLBACK Ở MOB 24
================================================================================

   Tổng cohorts: 50
   Cohorts dùng fallback ở MOB 24: 20 (40.0%)

--------------------------------------------------------------------------------

❌ PHÁT HIỆN VẤN ĐỀ: Quá nhiều cohorts dùng fallback!

💡 Giải thích:
   - Các cohorts này dùng parent fallback (có movement cao)
   - Parent fallback tổng hợp MOB 1-24 (MOB sớm có rates cao)
   - Gây DEL tăng ở MOB 25+

   Chi tiết cohorts dùng fallback (top 10):
      - C/650+_10M-_POS: insufficient data at MOB 24
      - C/550-649_10M-_POS: insufficient data at MOB 24
      ...
```

### Cell 10: Kết Luận
```
================================================================================
KẾT LUẬN
================================================================================

❌ K values quá cao ở MOB 25+ → Tin Markov quá nhiều
❌ Nhiều cohorts dùng parent fallback ở MOB 24 → Movement cao

================================================================================
KHUYẾN NGHỊ
================================================================================

1️⃣ GIẢM K Ở MOB 25+
   → Chạy cell 'Giải pháp 1' bên dưới

2️⃣ TĂNG MIN_OBS/MIN_EAD
   → Xem hướng dẫn trong cell 'Giải pháp 2'

================================================================================
```

---

## 🔧 Giải Pháp Chi Tiết

### Giải Pháp 1: Cap K ở MOB 25+

**Khi nào dùng**: Cell 10 khuyến nghị "GIẢM K Ở MOB 25+"

**Cách làm**: Chạy Cell 11

**Kết quả**:
```
🔧 ÁP DỤNG GIẢI PHÁP 1: Cap K ở MOB 25+
================================================================================

K values TRƯỚC KHI CAP:
  MOB 24: 0.850 ✅ OK
  MOB 25: 0.920 ❌ Cao
  MOB 26: 0.950 ❌ Cao
  MOB 27: 0.960 ❌ Cao

🔧 Đang cap K...

K values SAU KHI CAP:
  MOB 24: 0.850 ✅
  MOB 25: 0.300 ✅
  MOB 26: 0.300 ✅
  MOB 27: 0.300 ✅

================================================================================
✅ ĐÃ CAP K!
================================================================================

💡 Bước tiếp theo:
   1. Re-run cell 5 (Forecast) với k_final_by_mob đã được cap
   2. Re-run các cells diagnostic (6-10) để verify
   3. Kiểm tra lại kết quả
```

**Sau khi cap K**:
1. Chạy lại Cell 5 (Forecast)
2. Chạy lại Cells 6-10 (Diagnostic)
3. Kiểm tra xem DEL curve đã flatten chưa

### Giải Pháp 2: Tăng MIN_OBS/MIN_EAD

**Khi nào dùng**: Cell 10 khuyến nghị "TĂNG MIN_OBS/MIN_EAD"

**Cách làm**:
1. Mở file `src/config.py`
2. Tìm dòng: `MIN_OBS = 100`
3. Sửa thành: `MIN_OBS = 200`
4. Tìm dòng: `MIN_EAD = 1e2`
5. Sửa thành: `MIN_EAD = 5e2`
6. Save file
7. Restart kernel
8. Chạy lại từ Cell 1

**Giải thích**:
- Tăng threshold → Ít cohorts dùng fallback hơn
- Chỉ cohorts có đủ data mới dùng P_24 thật
- Giảm movement từ parent fallback

---

## ⚠️ Lưu Ý Quan Trọng

### 1. Phải Chạy Đúng Thứ Tự
- ❌ KHÔNG skip cells
- ❌ KHÔNG chạy ngược lại
- ✅ Chạy từ Cell 1 → 2 → 3 → ... → 12

### 2. Sửa Data Path
- Cell 2 có dòng: `DATA_PATH = '...'`
- Phải sửa cho đúng đường dẫn của bạn
- Ví dụ: `'C:/Users/User/Projection_PB/Projection_pb/ETB_Parquet_YYYYMM'`

### 3. Đọc Kỹ Output
- Mỗi cell có output rõ ràng
- Có ❌ hoặc ✅ để dễ nhận biết
- Đọc kỹ "💡 Giải thích" để hiểu vấn đề

### 4. Chỉ Áp Dụng Giải Pháp Khi Cần
- KHÔNG tự ý chạy Cell 11 hoặc 12
- Chỉ chạy khi Cell 10 khuyến nghị
- Có thể không cần giải pháp nào cả

### 5. Re-run Sau Khi Fix
- Sau khi áp dụng giải pháp
- Phải re-run forecast (Cell 5)
- Phải re-run diagnostic (Cells 6-10)
- Để verify kết quả

---

## 🐛 Troubleshooting

### Vấn Đề 1: "Cannot open notebook"
**Giải pháp**:
```bash
# Test file
python test_notebook_open.py

# Thử file clean
jupyter notebook notebooks/Markovchain_With_Diagnostic_Clean.ipynb

# Kiểm tra Jupyter
jupyter --version

# Update Jupyter
pip install --upgrade jupyter notebook
```

### Vấn Đề 2: "Kernel not found"
**Giải pháp**:
```bash
# Tạo kernel mới
python -m ipykernel install --user --name=python3

# Hoặc
conda install ipykernel
```

### Vấn Đề 3: "Module not found: src.config"
**Giải pháp**:
- Đảm bảo chạy từ project root
- Không chạy từ folder `notebooks`
```bash
cd C:\Users\User\Projection_PB\Projection_pb
jupyter notebook notebooks/Markovchain_With_Diagnostic.ipynb
```

### Vấn Đề 4: "File not found: ETB_Parquet_YYYYMM"
**Giải pháp**:
- Sửa DATA_PATH trong Cell 2
- Kiểm tra đường dẫn có đúng không
```python
import os
print(os.path.exists('ETB_Parquet_YYYYMM'))  # Should be True
```

### Vấn Đề 5: "NameError: name 'matrices_by_mob' is not defined"
**Giải pháp**:
- Bạn đã skip cells trước đó
- Phải chạy lại từ Cell 1

---

## 📚 Tài Liệu Tham Khảo

### Hướng Dẫn Sử Dụng
- **QUICK_START_DIAGNOSTIC.md** - Quick start (3 bước)
- **DA_SUA_XONG.md** - Hướng dẫn đầy đủ (Vietnamese)
- **DIAGNOSTIC_NOTEBOOK_READY.md** - Technical details
- **HUONG_DAN_CHAY_DIAGNOSTIC.md** - Hướng dẫn chi tiết + Giải pháp

### Tài Liệu Kỹ Thuật
- **EXPLANATION_TRANSITION_MATRIX_FALLBACK.md** - Giải thích fallback logic
- **CHECK_PARENT_FALLBACK_USAGE.md** - Kiểm tra parent fallback
- **DIAGNOSIS_CONTINUOUS_INCREASE.md** - Phân tích vấn đề
- **docs/MODEL_THEORY_METHODOLOGY.md** - Theory & methodology

### Scripts
- **diagnose_why_increase_after_24.py** - Diagnostic script
- **test_notebook_open.py** - Test notebook validity
- **validate_notebook.py** - Validate JSON
- **check_notebook_encoding.py** - Check encoding

---

## ✅ Checklist

### Trước Khi Chạy
- [ ] Đã cài Jupyter: `jupyter --version`
- [ ] Đã có data: `ETB_Parquet_YYYYMM` folder
- [ ] Đã sửa DATA_PATH trong Cell 2
- [ ] Đang ở project root folder

### Trong Khi Chạy
- [ ] Chạy đúng thứ tự: Cell 1 → 2 → 3 → ...
- [ ] Đọc kỹ output của mỗi cell
- [ ] Chú ý các ❌ và ✅
- [ ] Đọc "💡 Giải thích" để hiểu vấn đề

### Sau Khi Chạy
- [ ] Đã xác định nguyên nhân (K cao / fallback / aggregation)
- [ ] Đã áp dụng giải pháp phù hợp
- [ ] Đã re-run forecast và diagnostic
- [ ] Đã verify kết quả

---

## 🎯 Mục Tiêu Cuối Cùng

Sau khi chạy notebook này, bạn sẽ:
1. ✅ Hiểu tại sao DEL tăng sau MOB 24
2. ✅ Xác định được nguyên nhân cụ thể
3. ✅ Áp dụng giải pháp phù hợp
4. ✅ Verify kết quả đã được cải thiện
5. ✅ DEL curve flatten sau MOB 24 như mong đợi

---

## 📞 Hỗ Trợ

Nếu vẫn gặp vấn đề:
1. Kiểm tra file với: `python test_notebook_open.py`
2. Thử file clean: `Markovchain_With_Diagnostic_Clean.ipynb`
3. Xem log lỗi chi tiết từ Jupyter
4. Đọc lại hướng dẫn trong `DA_SUA_XONG.md`

---

**Tạo ngày**: 2026-01-21  
**Trạng thái**: ✅ Hoàn chỉnh  
**Version**: 1.0  
**Notebook**: `notebooks/Markovchain_With_Diagnostic.ipynb`
