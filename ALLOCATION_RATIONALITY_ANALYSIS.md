# Phân tích tính hợp lý của Allocation Logic

## ❓ Câu hỏi: Logic hiện tại có hợp lý không?

## ✅ **TRẢ LỜI: CÓ, logic này HỢP LÝ và là best practice**

---

## 🎯 Phân tích chi tiết

### 1️⃣ **Proportional Allocation - Hợp lý**

#### ✅ **Tại sao hợp lý?**

**Giả định cơ bản:**
> "Loans có EAD lớn hơn sẽ đóng góp nhiều hơn vào tổng EAD forecast"

**Ví dụ thực tế:**

```
Cohort có 3 loans @ DPD0:
  LOAN_001: 10 triệu (doanh nghiệp lớn)
  LOAN_002: 1 triệu (cá nhân)
  LOAN_003: 100 nghìn (micro)

Lifecycle forecast @ DPD0 = 11 triệu

Nếu phân bổ ĐỀU:
  Mỗi loan: 11M / 3 = 3.67M
  → LOAN_003 (100k) được forecast 3.67M ❌ VÔ LÝ!

Nếu phân bổ PROPORTIONAL:
  LOAN_001: 10M × (11M/11.1M) = 9.91M ✅
  LOAN_002: 1M × (11M/11.1M) = 0.99M ✅
  LOAN_003: 100k × (11M/11.1M) = 99k ✅
```

**Kết luận:** Proportional giữ nguyên tỉ lệ size → Hợp lý ✅

---

### 2️⃣ **Risk qua STATE_CURRENT - Hợp lý**

#### ✅ **Tại sao hợp lý?**

**Giả định:**
> "Loan đang ở DPD30+ có risk cao hơn loan ở DPD0"

**Ví dụ:**

```
2 loans cùng cohort, cùng EAD = 1M:

LOAN_A: STATE_CURRENT = DPD0
  → Transition probs @ MOB 24:
    - DPD0: 85%
    - DPD30+: 10%
    - DPD90+: 5%
  → Xác suất cao ở DPD0 ✅

LOAN_B: STATE_CURRENT = DPD30+
  → Transition probs @ MOB 24:
    - DPD0: 20%
    - DPD30+: 50%
    - DPD90+: 30%
  → Xác suất cao ở bad states ✅
```

**Kết luận:** STATE_CURRENT phản ánh risk hiện tại → Hợp lý ✅

---

### 3️⃣ **Risk qua Transition Matrix - Hợp lý**

#### ✅ **Tại sao hợp lý?**

**Giả định:**
> "Score A có risk profile khác Score D"

**Ví dụ:**

```
2 loans cùng STATE_CURRENT = DPD0, cùng EAD = 1M:

LOAN_A: Score A (low risk)
  → Matrix A: DPD0 → DPD0 = 90%
  → Xác suất cao giữ DPD0 ✅

LOAN_B: Score D (high risk)
  → Matrix D: DPD0 → DPD0 = 70%
  → Xác suất thấp hơn giữ DPD0 ✅
```

**Kết luận:** Transition Matrix encode risk profile → Hợp lý ✅

---

## 🤔 Các vấn đề tiềm ẩn

### ⚠️ **Vấn đề 1: Không xét thêm factors**

**Hiện tại KHÔNG xét:**
- Collateral value
- Payment history (ngoài STATE_CURRENT)
- Customer segment (SME vs Retail)
- Geographic location
- Industry sector

**Có cần không?**

**Phụ thuộc vào:**
- Nếu factors này đã được encode trong RISK_SCORE → KHÔNG cần
- Nếu factors này quan trọng và chưa có trong model → CẦN

**Ví dụ cần adjust:**
```python
# Nếu có collateral
if loan.has_collateral and loan.ltv < 0.7:
    risk_adjustment = 0.8  # Giảm risk
else:
    risk_adjustment = 1.0

EAD_FORECAST = EAD_CURRENT × ratio × risk_adjustment
```

---

### ⚠️ **Vấn đề 2: Random sampling có thể không stable**

**Hiện tại:**
```python
STATE_FORECAST = np.random.choice(states, p=probs)
```

**Vấn đề:**
- Chạy 2 lần với seed khác → Kết quả khác
- Loan A có thể được assign DPD0 lần 1, DPD30+ lần 2

**Có vấn đề không?**

**KHÔNG**, vì:
- Aggregate level (cohort) vẫn match lifecycle
- Individual loan level là stochastic (bản chất của PD model)
- Seed cố định → Reproducible

**Nếu muốn deterministic:**
```python
# Thay vì random, dùng expected value
EAD_FORECAST_DPD0 = EAD_CURRENT × prob_DPD0 × ratio_DPD0
EAD_FORECAST_DPD30 = EAD_CURRENT × prob_DPD30 × ratio_DPD30
# ...
```

---

### ⚠️ **Vấn đề 3: Không xét correlation giữa loans**

**Hiện tại:**
- Mỗi loan được assign state độc lập
- Không xét correlation (ví dụ: cùng industry)

**Có vấn đề không?**

**Phụ thuộc:**
- Nếu portfolio diversified → KHÔNG vấn đề
- Nếu concentrated (ví dụ: 80% real estate) → CẦN xét

**Giải pháp nếu cần:**
```python
# Copula-based sampling
# Hoặc scenario-based allocation
```

---

## 📊 So sánh với các phương pháp khác

### **Phương pháp 1: Equal Distribution**

```python
EAD_FORECAST = EAD_lifecycle / N_loans
```

**Ưu điểm:** Đơn giản
**Nhược điểm:** Không phản ánh size → ❌ KHÔNG hợp lý

---

### **Phương pháp 2: Proportional (ĐANG DÙNG)** ✅

```python
EAD_FORECAST = EAD_CURRENT × ratio
```

**Ưu điểm:** 
- Giữ tỉ lệ size
- Đơn giản
- Dễ giải thích

**Nhược điểm:**
- Không xét thêm factors (nếu cần)

**Kết luận:** ✅ **HỢP LÝ cho hầu hết trường hợp**

---

### **Phương pháp 3: Risk-Weighted**

```python
risk_weight = f(STATE, SCORE, COLLATERAL, ...)
EAD_FORECAST = EAD_CURRENT × ratio × risk_weight
```

**Ưu điểm:**
- Xét nhiều factors
- Chính xác hơn (nếu có data)

**Nhược điểm:**
- Phức tạp
- Cần nhiều data
- Khó giải thích

**Khi nào cần:**
- Có data về collateral, payment history, ...
- Factors này KHÔNG được encode trong RISK_SCORE
- Business yêu cầu adjust riêng

---

## 🎯 Kết luận

### ✅ **Logic hiện tại HỢP LÝ vì:**

1. **Proportional allocation** giữ nguyên tỉ lệ size → Phản ánh thực tế
2. **Risk qua STATE_CURRENT** → Xét risk hiện tại của loan
3. **Risk qua Transition Matrix** → Xét risk profile (score)
4. **Đơn giản và dễ giải thích** → Dễ audit và maintain
5. **Match với lifecycle** → Aggregate level chính xác

### ⚠️ **Có thể cải thiện nếu:**

1. **Có thêm data quan trọng:**
   - Collateral value
   - Payment history chi tiết
   - Customer segment
   
2. **Business yêu cầu:**
   - Penalize high-risk loans nhiều hơn
   - Ưu tiên certain types
   - Scenario-based allocation

3. **Portfolio concentrated:**
   - Cần xét correlation
   - Stress testing

### 📝 **Khuyến nghị:**

**GIỮ NGUYÊN logic hiện tại**, trừ khi:

1. ✅ Có data mới quan trọng (collateral, payment history)
2. ✅ Business có yêu cầu cụ thể
3. ✅ Audit/Regulator yêu cầu adjust

**Nếu cần thay đổi:**

1. **Bước 1:** Validate với actual data
   - Backtest: So sánh forecast vs actual
   - Check accuracy per segment

2. **Bước 2:** Implement phiên bản mới
   - Thêm risk adjustment factors
   - Test thoroughly

3. **Bước 3:** Compare
   - Old vs New
   - Accuracy improvement?
   - Complexity trade-off?

---

## 📊 Validation Checklist

Để verify logic hợp lý, check:

- [ ] Aggregate EAD match lifecycle? ✅
- [ ] Tỉ lệ size giữa loans được giữ? ✅
- [ ] Risk được xét qua STATE_CURRENT? ✅
- [ ] Risk được xét qua Transition Matrix? ✅
- [ ] Backtest accuracy acceptable? (Cần test)
- [ ] Business logic satisfied? (Cần confirm)
- [ ] Audit requirements met? (Cần confirm)

---

## 🔍 Câu hỏi để xác định có cần thay đổi

### 1. **Data availability:**
   - Có data về collateral không?
   - Có payment history chi tiết không?
   - Có customer segment data không?

### 2. **Business requirements:**
   - Có cần penalize high-risk loans không?
   - Có cần ưu tiên certain segments không?
   - Có regulatory requirements đặc biệt không?

### 3. **Model performance:**
   - Backtest accuracy như thế nào?
   - Có systematic bias không?
   - Có segment nào forecast kém không?

### 4. **Portfolio characteristics:**
   - Portfolio có diversified không?
   - Có concentration risk không?
   - Có correlation cao giữa loans không?

**Nếu TẤT CẢ câu trả lời là "KHÔNG" hoặc "Acceptable":**
→ ✅ **GIỮ NGUYÊN logic hiện tại**

**Nếu có câu trả lời "CÓ" hoặc "Cần cải thiện":**
→ ⚠️ **XEM XÉT thay đổi**

---

**Kết luận cuối cùng:** 

Logic hiện tại **HỢP LÝ và là best practice** cho allocation problem. Chỉ cần thay đổi nếu có data mới hoặc business requirements đặc biệt.

---

**Author**: Kiro AI  
**Date**: 2026-02-09  
**Version**: 1.0
