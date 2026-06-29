# Allocation Documentation - Index

## 📚 Tài liệu về Allocation Logic

### 🎯 Quick Start

1. **Quick Reference** → `ALLOCATION_QUICK_REF.md`
   - TL;DR: Công thức và ví dụ nhanh
   - Thời gian đọc: 2 phút

2. **Summary** → `ALLOCATION_SUMMARY.md`
   - Tóm tắt logic và FAQ
   - Thời gian đọc: 5 phút

3. **Detailed Explanation** → `ALLOCATION_LOGIC_EXPLAINED.md`
   - Giải thích chi tiết từng bước
   - So sánh các phương pháp
   - Thời gian đọc: 15 phút

### 🧪 Demo & Testing

4. **Demo Script** → `demo_allocation_logic.py`
   - Minh họa allocation logic với ví dụ cụ thể
   - Chạy: `python demo_allocation_logic.py`

5. **Test Optimized Allocation** → `test_optimized_allocation.py`
   - Test implementation mới (lấy actual từ df_raw)
   - Chạy: `python test_optimized_allocation.py`

### 💻 Implementation

6. **Optimized Allocation** → `IMPLEMENTATION_OPTIMIZED_ALLOCATION.md`
   - Implementation chi tiết của allocation_v2_optimized
   - Workflow: Actual first, then allocate
   - Usage guide

7. **Source Code**:
   - `src/rollrate/allocation_v2_optimized.py` - Main implementation (NEW)
   - `src/rollrate/allocation_v2_fast.py` - Fast allocation (CURRENT)
   - `src/rollrate/allocation_v2_ultra_fast.py` - Ultra fast (vectorized)

---

## 🗺️ Navigation Guide

### Nếu bạn muốn...

**Hiểu nhanh logic allocation:**
→ Đọc `ALLOCATION_QUICK_REF.md`

**Hiểu có xét risk không:**
→ Đọc `ALLOCATION_SUMMARY.md` (phần FAQ)

**Hiểu chi tiết từng bước:**
→ Đọc `ALLOCATION_LOGIC_EXPLAINED.md`

**Xem demo trực quan:**
→ Chạy `python demo_allocation_logic.py`

**Test implementation mới:**
→ Chạy `python test_optimized_allocation.py`

**Implement vào notebook:**
→ Đọc `IMPLEMENTATION_OPTIMIZED_ALLOCATION.md` (phần Usage)

---

## 📊 Workflow Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ALLOCATION WORKFLOW                       │
└─────────────────────────────────────────────────────────────┘

1. LOAD DATA
   ├─ df_raw (full history)
   ├─ df_loans_latest (current snapshot)
   └─ df_lifecycle_final (forecast)

2. CHECK ACTUAL vs FORECAST
   ├─ Cohort có actual @ target_mob? → Lấy từ df_raw
   └─ Cohort chỉ có forecast? → Allocate

3. ALLOCATE (cho cohorts cần forecast)
   ├─ BƯỚC 1: Assign STATE_FORECAST
   │   └─ Dựa trên STATE_CURRENT + Transition Matrix
   │
   └─ BƯỚC 2: Phân bổ EAD
       └─ Proportional theo EAD_CURRENT

4. COMBINE
   └─ Actual + Forecast → Final result
```

---

## 🎯 Key Concepts

### 1. Proportional Allocation
```python
EAD_FORECAST = EAD_CURRENT × (EAD_lifecycle / Total_EAD_CURRENT)
```

### 2. Risk Consideration
- ✅ Via STATE_CURRENT
- ✅ Via Transition Matrix
- ❌ NOT via separate risk weight

### 3. Optimization
- ✅ Lấy actual từ df_raw khi có
- ✅ Chỉ allocate khi cần
- ✅ Nhanh hơn 60% (nếu 60% cohorts có actual)

---

## 📞 Support

Nếu có câu hỏi:

1. Kiểm tra FAQ trong `ALLOCATION_SUMMARY.md`
2. Chạy demo script để xem ví dụ
3. Đọc detailed explanation
4. Hỏi developer

---

**Last Updated**: 2026-02-09  
**Version**: 1.0
