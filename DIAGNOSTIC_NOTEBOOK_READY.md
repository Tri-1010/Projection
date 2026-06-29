# ✅ Notebook Diagnostic Đã Sẵn Sàng

## Trạng Thái

✅ **File notebook hợp lệ**: `notebooks/Markovchain_With_Diagnostic.ipynb`
✅ **JSON structure**: Valid (28 cells)
✅ **Encoding**: UTF-8 without BOM
✅ **Format**: Jupyter Notebook 4.4

## File Đã Tạo

### 1. Notebook Chính (Khuyến Nghị)
**File**: `notebooks/Markovchain_With_Diagnostic.ipynb`
- ✅ 28 cells hoàn chỉnh
- ✅ Bao gồm: Model execution + Diagnostic + Solutions
- ✅ Tất cả trong 1 file duy nhất

### 2. Notebook Clean (Backup)
**File**: `notebooks/Markovchain_With_Diagnostic_Clean.ipynb`
- ✅ Cùng nội dung nhưng đã được re-format
- ✅ Dùng nếu file chính không mở được

### 3. Scripts Hỗ Trợ
- `diagnose_why_increase_after_24.py` - Diagnostic script
- `validate_notebook.py` - Kiểm tra notebook
- `check_notebook_encoding.py` - Kiểm tra encoding

### 4. Tài Liệu
- `HUONG_DAN_CHAY_DIAGNOSTIC.md` - Hướng dẫn đầy đủ
- `BAT_DAU_DIAGNOSTIC.md` - Quick start
- `QUICK_START_DIAGNOSTIC.md` - Hướng dẫn nhanh

---

## Cấu Trúc Notebook

### PHẦN 1: MODEL EXECUTION (Cells 1-5)
1. **Cell 1**: Setup & Import
2. **Cell 2**: Load Data
3. **Cell 3**: Build Transition Matrices
4. **Cell 4**: Calibration (K values)
5. **Cell 5**: Forecast

### PHẦN 2: DIAGNOSTIC (Cells 6-10)
6. **Cell 6**: Diagnostic 1 - Check K Values
7. **Cell 7**: Diagnostic 2 - Check Fallback Usage
8. **Cell 8**: Diagnostic 3 - Compare P_24 vs Parent Fallback
9. **Cell 9**: Diagnostic 4 - Analyze Cohorts
10. **Cell 10**: Conclusions and Recommendations

### PHẦN 3: SOLUTIONS (Cells 11-12)
11. **Cell 11**: Solution 1 - Cap K at MOB 25+
12. **Cell 12**: Solution 2 - Increase MIN_OBS/MIN_EAD

---

## Cách Mở Notebook

### Cách 1: Jupyter Notebook
```bash
cd notebooks
jupyter notebook Markovchain_With_Diagnostic.ipynb
```

### Cách 2: JupyterLab
```bash
cd notebooks
jupyter lab Markovchain_With_Diagnostic.ipynb
```

### Cách 3: VS Code
1. Mở VS Code
2. File → Open File
3. Chọn `notebooks/Markovchain_With_Diagnostic.ipynb`
4. VS Code sẽ tự động mở Jupyter interface

### Cách 4: Google Colab
1. Upload file lên Google Drive
2. Right-click → Open with → Google Colaboratory

---

## Nếu Vẫn Không Mở Được

### Thử File Clean
```bash
jupyter notebook notebooks/Markovchain_With_Diagnostic_Clean.ipynb
```

### Kiểm Tra Jupyter
```bash
# Kiểm tra Jupyter đã cài chưa
jupyter --version

# Nếu chưa có, cài đặt
pip install jupyter notebook

# Hoặc
conda install jupyter notebook
```

### Kiểm Tra File
```bash
python validate_notebook.py
```

Kết quả mong đợi:
```
✅ JSON is valid!
   Cells: 28
   Has metadata: True
   Has kernelspec: True
   Notebook format: 4.4
```

---

## Cách Chạy (3 Bước)

### Bước 1: Cấu Hình Data Path
Mở notebook, sửa Cell 2:
```python
DATA_PATH = 'C:/Users/User/Projection_PB/Projection_pb/ETB_Parquet_YYYYMM'
MAX_MOB = 36
```

### Bước 2: Chạy Model (Cells 1-5)
Chạy lần lượt:
- Cell 1: Setup & Import
- Cell 2: Load Data
- Cell 3: Build Transition Matrices
- Cell 4: Calibration
- Cell 5: Forecast

### Bước 3: Chạy Diagnostic (Cells 6-10)
Chạy lần lượt các cells diagnostic để xem kết quả.

### Bước 4: Áp Dụng Giải Pháp (Nếu Cần)
- Nếu thấy ❌ K values quá cao → Chạy Cell 11
- Nếu thấy ❌ Nhiều cohorts dùng fallback → Làm theo Cell 12

---

## Các Vấn Đề Có Thể Gặp

### 1. "Kernel not found"
**Giải pháp**: 
```bash
# Tạo kernel mới
python -m ipykernel install --user --name=rrmodel
```

Sau đó chọn kernel "rrmodel" trong notebook.

### 2. "Module not found"
**Giải pháp**:
```bash
# Cài các package cần thiết
pip install pandas numpy matplotlib
```

### 3. "File not found"
**Giải pháp**: Kiểm tra DATA_PATH trong Cell 2 có đúng không.

### 4. "Cannot open file"
**Giải pháp**: 
1. Thử file clean: `Markovchain_With_Diagnostic_Clean.ipynb`
2. Kiểm tra Jupyter version: `jupyter --version`
3. Update Jupyter: `pip install --upgrade jupyter notebook`

---

## Thông Tin Kỹ Thuật

### Notebook Format
- **Format**: Jupyter Notebook 4.4
- **Kernel**: Python 3
- **Encoding**: UTF-8 (no BOM)
- **Line endings**: CRLF (Windows)

### Dependencies
```python
import pandas as pd
import numpy as np
from datetime import datetime
from src.config import CFG, BUCKETS_CANON, BUCKETS_30P, BUCKETS_90P
from src.data_loader import load_data
from src.rollrate.transition import compute_transition_by_mob
from src.rollrate.lifecycle import get_actual_all_vintages_amount
from src.rollrate.calibration_kmob import (
    fit_k_raw, smooth_k, fit_alpha,
    forecast_all_vintages_partial_step,
)
```

### Config Settings (src/config.py)
```python
MIN_OBS = 100         # Minimum observations
MIN_EAD = 1e2         # Minimum EAD
ABSORBING_BASE = ["DPD90+", "WRITEOFF", "PREPAY", "SOLDOUT"]
BUCKETS_30P = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
```

---

## Kết Quả Mong Đợi

### Diagnostic Output
```
================================================================================
1️⃣ KIỂM TRA K VALUES
================================================================================

   MOB  |  K value  |  Status
   -----|-----------|----------
   24   |   0.850   | ✅ Trung bình
   25   |   0.920   | ❌ Rất cao
   26   |   0.950   | ❌ Rất cao
   ...

❌ PHÁT HIỆN VẤN ĐỀ: 2 MOBs có K quá cao
   - MOB 25: k=0.920
   - MOB 26: k=0.950

💡 Giải thích:
   - K cao → Model tin Markov quá nhiều
   - Markov gây movement → DEL tăng
   - Cần giảm K xuống ~0.3 cho MOB 25+
```

### Solution Output
```
🔧 ÁP DỤNG GIẢI PHÁP 1: Cap K ở MOB 25+
================================================================================

K values TRƯỚC KHI CAP:
  MOB 24: 0.850 ✅ OK
  MOB 25: 0.920 ❌ Cao
  MOB 26: 0.950 ❌ Cao

🔧 Đang cap K...

K values SAU KHI CAP:
  MOB 24: 0.850 ✅
  MOB 25: 0.300 ✅
  MOB 26: 0.300 ✅

✅ ĐÃ CAP K!
```

---

## Liên Hệ & Hỗ Trợ

Nếu vẫn gặp vấn đề:
1. Kiểm tra file với: `python validate_notebook.py`
2. Thử file clean: `Markovchain_With_Diagnostic_Clean.ipynb`
3. Xem log lỗi chi tiết từ Jupyter
4. Cung cấp thông tin:
   - Jupyter version: `jupyter --version`
   - Python version: `python --version`
   - Error message cụ thể

---

**Tạo ngày**: 2026-01-21  
**Trạng thái**: ✅ Sẵn sàng sử dụng  
**File chính**: `notebooks/Markovchain_With_Diagnostic.ipynb`  
**File backup**: `notebooks/Markovchain_With_Diagnostic_Clean.ipynb`
