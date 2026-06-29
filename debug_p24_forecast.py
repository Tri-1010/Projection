"""
Script debug đơn giản để kiểm tra P_24 và forecast
"""

def debug_p24_forecast(matrices_by_mob, forecast_results, disb_total_by_vintage):
    """
    Debug script đơn giản để xem P_24 và forecast
    """
    
    print("="*80)
    print("DEBUG: KIỂM TRA P_24 VÀ FORECAST")
    print("="*80)
    
    # 1. Kiểm tra matrices_by_mob
    print("\n1️⃣ KIỂM TRA MATRICES_BY_MOB:")
    print(f"   Type: {type(matrices_by_mob)}")
    print(f"   Products: {list(matrices_by_mob.keys())}")
    
    for prod in list(matrices_by_mob.keys())[:2]:  # Chỉ xem 2 products đầu
        print(f"\n   Product {prod}:")
        print(f"      MOBs available: {list(matrices_by_mob[prod].keys())}")
        
        if 24 in matrices_by_mob[prod]:
            print(f"      Scores at MOB 24: {list(matrices_by_mob[prod][24].keys())[:5]}")
            
            # Lấy 1 score để test
            first_score = list(matrices_by_mob[prod][24].keys())[0]
            print(f"\n      Test score: {first_score}")
            
            matrix_info = matrices_by_mob[prod][24][first_score]
            print(f"         Keys: {matrix_info.keys()}")
            print(f"         Is fallback: {matrix_info.get('is_fallback', False)}")
            
            P = matrix_info.get("P")
            if P is not None:
                print(f"         P shape: {P.shape}")
                print(f"         P index: {list(P.index)[:5]}")
                print(f"         P columns: {list(P.columns)[:5]}")
                
                # Tính movement
                if "DPD0" in P.index:
                    del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
                    movement = sum(P.loc["DPD0", s] for s in del30_states if s in P.columns)
                    print(f"         Movement DPD0 → DEL30+: {movement:.4f} ({movement*100:.2f}%)")
    
    # 2. Kiểm tra forecast_results
    print("\n\n2️⃣ KIỂM TRA FORECAST_RESULTS:")
    print(f"   Type: {type(forecast_results)}")
    print(f"   N cohorts: {len(forecast_results)}")
    
    # Lấy 1 cohort để test
    first_cohort = list(forecast_results.keys())[0]
    print(f"\n   Test cohort: {first_cohort}")
    
    forecast = forecast_results[first_cohort]
    print(f"      Type: {type(forecast)}")
    print(f"      MOBs available: {list(forecast.keys())[:10]}")
    
    if 24 in forecast:
        print(f"\n      At MOB 24:")
        print(f"         Type: {type(forecast[24])}")
        print(f"         Keys/columns: {list(forecast[24].keys()) if hasattr(forecast[24], 'keys') else list(forecast[24].index)}")
        
        # Tính DEL
        buckets_30p = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
        try:
            del30_24 = forecast[24][buckets_30p].sum()
            print(f"         DEL30+ amount: {del30_24:.2f}")
            
            disb = disb_total_by_vintage.get(first_cohort, 1.0)
            print(f"         Disb total: {disb:.2f}")
            print(f"         DEL30+ %: {del30_24/disb*100:.2f}%")
        except Exception as e:
            print(f"         Error calculating DEL: {e}")
    
    if 30 in forecast:
        print(f"\n      At MOB 30:")
        try:
            del30_30 = forecast[30][buckets_30p].sum()
            disb = disb_total_by_vintage.get(first_cohort, 1.0)
            print(f"         DEL30+ %: {del30_30/disb*100:.2f}%")
            
            if 24 in forecast:
                del30_24 = forecast[24][buckets_30p].sum()
                slope = (del30_30 - del30_24) / disb / 6
                print(f"         Slope MOB 24-30: {slope*100:.4f}% per month")
        except Exception as e:
            print(f"         Error: {e}")
    
    # 3. Thử match cohort với matrix
    print("\n\n3️⃣ THỬ MATCH COHORT VỚI MATRIX:")
    
    product, score, vintage = first_cohort
    prod_str = str(product)
    score_str = str(score)
    
    print(f"   Cohort: {first_cohort}")
    print(f"   Product str: '{prod_str}'")
    print(f"   Score str: '{score_str}'")
    
    if prod_str in matrices_by_mob:
        print(f"   ✅ Product found in matrices_by_mob")
        
        if 24 in matrices_by_mob[prod_str]:
            print(f"   ✅ MOB 24 found")
            
            if score_str in matrices_by_mob[prod_str][24]:
                print(f"   ✅ Score found at MOB 24")
                
                P_24 = matrices_by_mob[prod_str][24][score_str]["P"]
                
                if "DPD0" in P_24.index:
                    del30_states = ["DPD30+", "DPD60+", "DPD90+", "DPD120+", "DPD180+", "WRITEOFF"]
                    movement = sum(P_24.loc["DPD0", s] for s in del30_states if s in P_24.columns)
                    print(f"   ✅ P_24 movement: {movement*100:.2f}%")
                    
                    # So sánh với forecast
                    if 24 in forecast and 30 in forecast:
                        disb = disb_total_by_vintage.get(first_cohort, 1.0)
                        del30_24 = forecast[24][buckets_30p].sum() / disb
                        del30_30 = forecast[30][buckets_30p].sum() / disb
                        slope = (del30_30 - del30_24) / 6
                        
                        print(f"   ✅ Forecast slope: {slope*100:.2f}%")
                        print(f"   ✅ Diff: {(slope - movement)*100:.2f}%")
                        
                        if abs(slope - movement) < 0.001:
                            print(f"\n   ✅ MATCH! Forecast ≈ P_24")
                        elif slope > movement:
                            print(f"\n   ⚠️ Forecast > P_24 by {(slope - movement)*100:.2f}%")
                        else:
                            print(f"\n   ⚠️ Forecast < P_24 by {(movement - slope)*100:.2f}%")
                else:
                    print(f"   ❌ DPD0 not in P_24 index")
            else:
                print(f"   ❌ Score '{score_str}' not found at MOB 24")
                print(f"   Available scores: {list(matrices_by_mob[prod_str][24].keys())[:5]}")
        else:
            print(f"   ❌ MOB 24 not found")
            print(f"   Available MOBs: {list(matrices_by_mob[prod_str].keys())}")
    else:
        print(f"   ❌ Product '{prod_str}' not found")
        print(f"   Available products: {list(matrices_by_mob.keys())}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    print("Chạy script này từ notebook với:")
    print("debug_p24_forecast(matrices_by_mob, forecast_results, disb_total_by_vintage)")
