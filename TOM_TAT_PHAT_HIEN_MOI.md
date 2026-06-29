# 📋 TÓM TẮT: Phát hiện mới về vấn đề DEL tăng sau MOB 24

## Câu hỏi của bạn

> "nhưng tại sao k tăng tiến đến 1 lại là vấn đề nếu như các transition đã ổn định?"

**Đây là câu hỏi RẤT HAY!** Bạn đã chỉ ra một điểm quan trọng trong logic.

---

## Phát hiện quan trọng

### 1. Logic của bạn đúng!

Công thức forecast:
```
v_{m+1} = v_m + k_m * (v_hat - v_m)
where v_hat = v_m @ P_m
```

**Nếu P_m ổn định** (v_hat ≈ v_m), thì k_m không quan trọng!

### 2. Nhưng có điều bất thường!

**Từ kết quả của bạn:**
- Slope TRƯỚC mature (MOB 12→24): **0.3314%/month**
- Slope SAU mature (MOB 23→29): **0.5636%/month**

**❌ Slope SAU mature cao hơn slope TRƯỚC mature!**

Điều này **BẤT THƯỜNG** vì:
- Portfolio đã mature ở MOB 24
- Transitions nên ổn định hơn
- Slope nên thấp hơn hoặc bằng

### 3. Giả thuyết mới

Có **3 khả năng** giải thích:

#### Giả thuyết 1: K values có jumps lớn ở MOB 24-25
- K trước MOB 24: 0.5-0.7
- K sau MOB 24: 0.9-1.0
- **K jump → Forecast behavior thay đổi → DEL tăng**

#### Giả thuyết 2: Transitions không thực sự ổn định
- P_23 movement = 0.0004% là **average**
- Nhưng **từng cohort riêng lẻ** có thể có movement cao hơn
- **Distribution có outliers → DEL tăng**

#### Giả thuyết 3: Parent fallback được dùng nhiều hơn sau MOB 24
- Parent fallback movement = 0.0008% (cao hơn P_23 2.2x)
- Nếu % fallback tăng sau MOB 24 → DEL tăng

---

## Script để kiểm tra

Tôi đã tạo script `diagnose_why_increase_after_24.py` để kiểm tra 3 giả thuyết:

```bash
python diagnose_why_increase_after_24.py
```

### Script sẽ làm gì?

1. **Phân tích K values theo MOB**
   - Tìm K jumps lớn (>0.2)
   - Xem K có thay đổi đột ngột ở MOB 24-25 không

2. **Phân tích transition stability**
   - Xem P_23, P_24, P_25 có thực sự ổn định không
   - Tính average movement và max movement
   - Tìm cohorts có movement cao

3. **Simulate forecast với các K scenarios**
   - K=0.0 (No Markov)
   - K=0.3 (Low)
   - K=0.5 (Medium)
   - K=1.0 (Full Markov)
   - So sánh slope để xem K có impact không

---

## Kết quả mong đợi

### Nếu Giả thuyết 1 đúng (K jumps):
```
❌ PHÁT HIỆN 3 K JUMPS:
   - MOB 24: 0.700 → 0.950 (change: +0.250)
   - MOB 25: 0.950 → 1.000 (change: +0.050)

💡 SO SÁNH K=1.0 vs K=0.3:
   - K=1.0 slope: 0.005636 (0.5636%)
   - K=0.3 slope: 0.001500 (0.1500%)
   - Diff:        0.004136 (0.4136%)

❌ K=1.0 GÂY DEL TĂNG CAO HƠN K=0.3 NHIỀU!
   → Giảm K xuống 0.3 sẽ giảm slope 0.4136%
```

→ **Giải pháp:** Cap K ở MOB 25+ xuống 0.3

### Nếu Giả thuyết 2 đúng (Transitions không ổn định):
```
❌ TRANSITIONS KHÔNG ỔN ĐỊNH!
   - Average movement: 0.0050% (0.50%)
   - Max movement:     0.0120% (1.20%)
   - Average movement 0.50% > 0.1%
   - Đây là lý do DEL tăng!
```

→ **Giải pháp:** Tăng MIN_OBS để lọc cohorts không ổn định

### Nếu Giả thuyết 3 đúng (Fallback usage tăng):
```
❌ % FALLBACK TĂNG ĐỘT NGỘT:
   - MOB 23: 54.5%
   - MOB 24: 75.2%
   - MOB 25: 82.1%
```

→ **Giải pháp:** Tăng MIN_OBS hoặc giảm K cho cohorts dùng fallback

---

## Files đã tạo

1. **`diagnose_why_increase_after_24.py`**
   - Script để kiểm tra 3 giả thuyết
   - Chạy: `python diagnose_why_increase_after_24.py`

2. **`GIAI_THICH_VAN_DE_THUC_SU.md`**
   - Giải thích chi tiết về vấn đề
   - Phân tích 3 giả thuyết
   - Hướng dẫn cách kiểm tra

---

## Bước tiếp theo

1. **Chạy script:**
   ```bash
   python diagnose_why_increase_after_24.py
   ```

2. **Xem kết quả:**
   - K values có jumps không?
   - Transitions có ổn định không?
   - Fallback usage có tăng không?

3. **Áp dụng giải pháp phù hợp:**
   - Nếu K jumps → Cap K ở MOB 25+
   - Nếu transitions không ổn định → Tăng MIN_OBS
   - Nếu fallback usage tăng → Tăng MIN_OBS hoặc giảm K

---

## Tóm tắt

**Câu hỏi của bạn rất đúng!** Logic của bạn hoàn toàn hợp lý.

**Nhưng có điều bất thường:**
- Slope SAU mature cao hơn slope TRƯỚC mature
- Chỉ có thể giải thích bằng 1 trong 3 giả thuyết

**Chạy script để tìm ra nguyên nhân thực sự!**
