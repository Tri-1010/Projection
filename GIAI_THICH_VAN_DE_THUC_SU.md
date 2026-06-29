# 🔍 GIẢI THÍCH VẤN ĐỀ THỰC SỰ: Tại sao K=1.0 gây DEL tăng?

## Câu hỏi của bạn

> "nhưng tại sao k tăng tiến đến 1 lại là vấn đề nếu như các transition đã ổn định? 
> code lấy số forecast gần nhất phân bổ (đã có k) và nhân tiếp transition 
> => vậy ở các transition đã ổn định thì k = 1 cũng sẽ ổn định chứ?"

**Đây là câu hỏi RẤT HAY!** Bạn đã chỉ ra một điểm quan trọng trong logic.

---

## Công thức Forecast

```python
v_{m+1} = v_m + k_m * (v_hat - v_m)
where v_hat = v_m @ P_m
```

Nếu `P_m` ổn định (tức `v_hat ≈ v_m`), thì:
- `k_m = 1.0` → `v_{m+1} = v_hat` (full Markov)
- `k_m = 0.0` → `v_{m+1} = v_m` (no change)
- `k_m = 0.5` → `v_{m+1} = v_m + 0.5 * (v_hat - v_m)` (partial step)

**Logic của bạn đúng**: Nếu `v_hat ≈ v_m`, thì `k_m` không quan trọng!

---

## Vậy tại sao K=1.0 lại gây vấn đề?

Có **3 giả thuyết** cần kiểm tra:

### Giả thuyết 1: Transitions KHÔNG thực sự ổn định

**Phát hiện từ data:**
- P_23 movement = 0.0004% per month
- Forecast slope = 0.5636% per month
- **Chênh lệch 1400x!**

**Giải thích:**
- P_23 movement 0.0004% là **average** của nhiều cohorts
- Nhưng **từng cohort riêng lẻ** có thể có movement cao hơn
- Khi aggregate, các cohorts có movement cao sẽ kéo DEL tăng

**Cần kiểm tra:**
- Distribution của P_23 movement (min, max, median, std)
- Có bao nhiêu cohorts có movement > 0.001%?
- Có bao nhiêu cohorts có movement > 0.005%?

### Giả thuyết 2: K values có jumps lớn

**Phát hiện từ data:**
- Slope TRƯỚC mature (MOB 12→24): 0.3314%/month
- Slope SAU mature (MOB 23→29): 0.5636%/month
- **Slope SAU mature cao hơn!** (bất thường)

**Giải thích:**
- Nếu K values trước MOB 24 thấp (0.5-0.7), sau MOB 24 nhảy lên 1.0
- Việc thay đổi K sẽ thay đổi forecast behavior
- Ngay cả khi P_24 ổn định, việc K jump cũng gây DEL tăng

**Ví dụ:**
```
MOB 23: k=0.7, P_23 movement=0.0004%
  → Forecast movement = 0.7 * 0.0004% = 0.00028%

MOB 24: k=1.0, P_24 movement=0.0004%
  → Forecast movement = 1.0 * 0.0004% = 0.0004%
  
→ Forecast movement tăng 43% chỉ vì K jump!
```

**Cần kiểm tra:**
- K values từ MOB 1 đến 36
- Có K jumps lớn (>0.2) không?
- K jumps xảy ra ở MOB nào?

### Giả thuyết 3: Parent fallback được dùng nhiều hơn sau MOB 24

**Phát hiện từ data:**
- 54.5% cohorts dùng fallback ở MOB 23
- Parent fallback movement = 0.0008% (cao hơn P_23 2.2x)

**Giải thích:**
- Nếu nhiều cohorts chuyển sang dùng parent fallback sau MOB 24
- Parent fallback có movement cao hơn → DEL tăng

**Nhưng:**
- Parent fallback chỉ cao hơn 2.2x (0.0008% vs 0.0004%)
- Không đủ để giải thích chênh lệch 1400x!

**Cần kiểm tra:**
- % cohorts dùng fallback ở từng MOB (20-30)
- Có tăng đột ngột sau MOB 24 không?

---

## Kết luận tạm thời

**Logic của bạn đúng**: Nếu transitions thực sự ổn định, K=1.0 không gây vấn đề.

**Nhưng:**
1. Transitions có thể KHÔNG thực sự ổn định (cần kiểm tra distribution)
2. K values có thể có jumps lớn (cần kiểm tra K curve)
3. Parent fallback có thể được dùng nhiều hơn (cần kiểm tra fallback usage)

**Giả thuyết mạnh nhất:** K values có jumps lớn ở MOB 24-25
- Slope SAU mature cao hơn slope TRƯỚC mature → Bất thường!
- Chỉ có thể giải thích bằng K jump hoặc fallback usage tăng

---

## Script để kiểm tra

Tôi đã tạo script `diagnose_why_increase_after_24.py` để kiểm tra 3 giả thuyết trên:

```bash
python diagnose_why_increase_after_24.py
```

Script sẽ:
1. ✅ Phân tích K values theo MOB (tìm K jumps)
2. ✅ Phân tích transition stability (tìm cohorts không ổn định)
3. ✅ Simulate forecast với các K scenarios (so sánh K=1.0 vs K=0.3)

---

## Kết quả mong đợi

### Nếu Giả thuyết 1 đúng (Transitions không ổn định):
```
❌ TRANSITIONS KHÔNG ỔN ĐỊNH!
   - Average movement 0.0050% > 0.1%
   - Đây là lý do DEL tăng!
```

→ **Giải pháp:** Tăng MIN_OBS để lọc cohorts không ổn định

### Nếu Giả thuyết 2 đúng (K jumps):
```
❌ PHÁT HIỆN 3 K JUMPS:
   - MOB 24: 0.700 → 0.950 (change: +0.250)
   - MOB 25: 0.950 → 1.000 (change: +0.050)
```

→ **Giải pháp:** Smooth K values hoặc cap K ở MOB 25+

### Nếu Giả thuyết 3 đúng (Fallback usage tăng):
```
❌ % FALLBACK TĂNG ĐỘT NGỘT:
   - MOB 23: 54.5%
   - MOB 24: 75.2%
   - MOB 25: 82.1%
```

→ **Giải pháp:** Tăng MIN_OBS hoặc giảm K cho cohorts dùng fallback

---

## Câu hỏi tiếp theo

Sau khi chạy script, chúng ta sẽ biết:
1. K values có jumps không?
2. Transitions có thực sự ổn định không?
3. Fallback usage có tăng không?

Từ đó, chúng ta sẽ biết **nguyên nhân thực sự** và áp dụng giải pháp phù hợp.

---

## Tóm tắt

**Câu hỏi của bạn rất đúng!** Nếu transitions ổn định, K=1.0 không gây vấn đề.

**Nhưng có 3 khả năng:**
1. Transitions không thực sự ổn định (distribution có outliers)
2. K values có jumps lớn (thay đổi forecast behavior)
3. Parent fallback được dùng nhiều hơn (movement cao hơn)

**Chạy script để kiểm tra!**
