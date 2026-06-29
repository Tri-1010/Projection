# 🚀 Quick Start - Diagnostic DEL Tăng

## 3 Bước Đơn Giản

### 1️⃣ Mở Notebook
```bash
jupyter notebook notebooks/Markovchain_With_Diagnostic.ipynb
```

### 2️⃣ Sửa Data Path (Cell 2)
```python
DATA_PATH = 'C:/Users/User/Projection_PB/Projection_pb/ETB_Parquet_YYYYMM'
```

### 3️⃣ Chạy Từng Cell
- Cells 1-5: Chạy model
- Cells 6-10: Xem diagnostic
- Cells 11-12: Áp dụng giải pháp (nếu cần)

---

## Đọc Kết Quả

### ❌ Nếu Thấy: "K values quá cao"
→ Chạy **Cell 11** (Cap K ở MOB 25+)

### ❌ Nếu Thấy: "Nhiều cohorts dùng fallback"
→ Làm theo **Cell 12** (Tăng MIN_OBS/MIN_EAD)

### ✅ Nếu Thấy: "Không phát hiện vấn đề"
→ Có thể là aggregation effect, cần phân tích sâu hơn

---

## Files

- **Chính**: `notebooks/Markovchain_With_Diagnostic.ipynb`
- **Backup**: `notebooks/Markovchain_With_Diagnostic_Clean.ipynb`
- **Hướng dẫn**: `DA_SUA_XONG.md`

---

## Nếu Không Mở Được

```bash
# Kiểm tra file
python test_notebook_open.py

# Thử file clean
jupyter notebook notebooks/Markovchain_With_Diagnostic_Clean.ipynb

# Kiểm tra Jupyter
jupyter --version
```

---

**Thời gian**: ~10 phút  
**Trạng thái**: ✅ Sẵn sàng
