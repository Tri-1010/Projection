"""
Script kiểm tra P_24 có thực sự ổn định không
"""

def check_p24_stability(matrices_by_mob, parent_fallback):
    """
    Kiểm tra P_24 có thực sự ổn định không
    
    Nếu P_24 ổn định (< 1% movement) → K = 1.0 là ĐÚNG
    Nếu P_24 có movement (> 2%) → K = 1.0 gây DEL tăng
    """
    
    print("="*80)
    print("KIỂM TRA: P_24 CÓ THỰC SỰ ỔN ĐỊNH KHÔNG?")
    print("="*80)
    
    print("\n💡 Logic:")
    print("   - Nếu P_24 ổn định (< 1% movement) → K = 1.0 là ĐÚNG ✅")
    print("   - Nếu P_24 có movement (> 2%) → K = 1.0 gây DEL tăng ❌")
    
    # Lấy tất cả P_24
    p24_movements = []
    
    for prod_str in matrices_by_mob.keys():
        if 24 not in matrices_by_mob[prod_str]:
            continue
            
        for score_str in matrices_by_mob[prod_str][24].keys():
            # Skip fallback
            is_fallback = matrices_by_mob[prod_str][24][score_str].get("is_fallback", False)
            if is_fallback:
                continue
            
            P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
            
            # Tính movement từ DPD0 → DEL30+
            if "DPD0" in P_24.index:
                del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
                movement = sum(P_24.loc["DPD0", s] for s in del30_states if s in P_24.columns)
                
                p24_movements.append({
                    "product": prod_str,
                    "score": score_str,
                    "movement": movement
                })
    
    if not p24_movements:
        print("\n⚠️ Không tìm thấy P_24 nào!")
        return
    
    # Phân tích
    print(f"\n📊 Đã phân tích {len(p24_movements)} cohorts có P_24 thật:")
    print("\n   Product/Score | Movement | Status")
    print("   --------------|----------|--------")
    
    very_stable = []  # < 1%
    stable = []       # 1-2%
    moderate = []     # 2-3%
    high = []         # > 3%
    
    for item in sorted(p24_movements, key=lambda x: x["movement"], reverse=True)[:10]:
        prod = item["product"]
        score = item["score"]
        mov = item["movement"]
        
        if mov < 0.01:
            status = "✅ Rất ổn định"
            very_stable.append(item)
        elif mov < 0.02:
            status = "✅ Ổn định"
            stable.append(item)
        elif mov < 0.03:
            status = "⚠️ Hơi cao"
            moderate.append(item)
        else:
            status = "❌ Cao"
            high.append(item)
        
        print(f"   {prod}/{score[:20]:20s} | {mov:8.4f} | {status}")
    
    if len(p24_movements) > 10:
        print(f"   ... và {len(p24_movements)-10} cohorts khác")
    
    # Tổng hợp
    print("\n" + "-"*80)
    print("\n📈 TỔNG HỢP:")
    print(f"   - Rất ổn định (< 1%):  {len(very_stable):3d} cohorts ({len(very_stable)/len(p24_movements)*100:.1f}%)")
    print(f"   - Ổn định (1-2%):      {len(stable):3d} cohorts ({len(stable)/len(p24_movements)*100:.1f}%)")
    print(f"   - Hơi cao (2-3%):      {len(moderate):3d} cohorts ({len(moderate)/len(p24_movements)*100:.1f}%)")
    print(f"   - Cao (> 3%):          {len(high):3d} cohorts ({len(high)/len(p24_movements)*100:.1f}%)")
    
    # Kết luận
    print("\n" + "="*80)
    print("KẾT LUẬN:")
    print("="*80)
    
    if len(high) > len(p24_movements) * 0.3:
        print("\n❌ NHIỀU COHORTS CÓ P_24 KHÔNG ỔN ĐỊNH (> 3% movement)")
        print("\n💡 Giải thích:")
        print("   - P_24 vẫn có movement đáng kể")
        print("   - K = 1.0 + P_24 có movement = DEL tăng")
        print("   - Đây KHÔNG phải do K cao, mà do P_24 chưa ổn định")
        print("\n🔧 Giải pháp:")
        print("   1. Giảm K xuống 0.3-0.5 để giảm ảnh hưởng của movement")
        print("   2. HOẶC chấp nhận DEL tăng (nếu đây là reality của portfolio)")
        
    elif len(moderate) + len(high) > len(p24_movements) * 0.5:
        print("\n⚠️ MỘT SỐ COHORTS CÓ P_24 VẪN CÓ MOVEMENT (2-3%)")
        print("\n💡 Giải thích:")
        print("   - P_24 chưa hoàn toàn ổn định")
        print("   - K = 1.0 có thể gây DEL tăng nhẹ")
        print("\n🔧 Giải pháp:")
        print("   1. Xem xét giảm K xuống 0.5-0.7")
        print("   2. Hoặc chấp nhận DEL tăng nhẹ")
        
    else:
        print("\n✅ ĐA SỐ COHORTS CÓ P_24 ỔN ĐỊNH (< 2% movement)")
        print("\n💡 Giải thích:")
        print("   - P_24 đã ổn định tốt")
        print("   - K = 1.0 là HỢP LÝ")
        print("   - Nếu DEL vẫn tăng → Vấn đề KHÔNG phải do K cao")
        print("\n🔍 Cần kiểm tra:")
        print("   1. % cohorts dùng parent fallback (Cell 7)")
        print("   2. Aggregation effect (Cell 9)")
        print("   3. Có thể vấn đề là fallback, không phải K")
    
    print("\n" + "="*80)
    
    # So sánh với parent fallback
    print("\n🔬 SO SÁNH P_24 vs PARENT FALLBACK:")
    print("="*80)
    
    # Lấy 1 cohort để test
    if p24_movements:
        test_item = p24_movements[0]
        prod_str = test_item["product"]
        score_str = test_item["score"]
        
        P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
        key_parent = (prod_str, score_str)
        
        if key_parent in parent_fallback:
            P_parent = parent_fallback[key_parent]
            
            if "DPD0" in P_24.index and "DPD0" in P_parent.index:
                del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
                
                p24_mov = sum(P_24.loc["DPD0", s] for s in del30_states if s in P_24.columns)
                parent_mov = sum(P_parent.loc["DPD0", s] for s in del30_states if s in P_parent.columns)
                
                print(f"\nTest cohort: {prod_str}/{score_str}")
                print(f"   P_24 movement:    {p24_mov:.4f} ({p24_mov*100:.2f}%)")
                print(f"   Parent movement:  {parent_mov:.4f} ({parent_mov*100:.2f}%)")
                print(f"   Diff:             {parent_mov - p24_mov:+.4f} ({(parent_mov - p24_mov)*100:+.2f}%)")
                
                if parent_mov > p24_mov * 1.5:
                    print("\n✅ XÁC NHẬN: Parent fallback cao hơn P_24 NHIỀU")
                    print("   → Nếu nhiều cohorts dùng fallback → Đây là vấn đề chính")
                elif parent_mov > p24_mov:
                    print("\n✅ Parent fallback cao hơn P_24")
                else:
                    print("\n⚠️ P_24 cao hơn hoặc bằng parent fallback")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    print("Chạy script này từ notebook với:")
    print("check_p24_stability(matrices_by_mob, parent_fallback)")
