"""
Verification script to check if diagnostic setup is complete
"""

from pathlib import Path
import json

def verify_setup():
    """Verify that all diagnostic files are in place"""
    
    print("="*60)
    print("🔍 Verifying Diagnostic Setup")
    print("="*60)
    
    all_good = True
    
    # Check diagnostic scripts
    print("\n1️⃣ Checking diagnostic scripts...")
    scripts = [
        "diagnose_why_increase_after_24.py",
        "check_p24_quality.py",
        "diagnose_del_curve.py"
    ]
    
    for script in scripts:
        if Path(script).exists():
            print(f"   ✅ {script}")
        else:
            print(f"   ❌ {script} NOT FOUND")
            all_good = False
    
    # Check documentation
    print("\n2️⃣ Checking documentation...")
    docs = [
        "NEXT_STEPS_DIAGNOSIS.md",
        "HUONG_DAN_CHAY_DIAGNOSTIC.md",
        "DIAGNOSTIC_ADDED_SUMMARY.md",
        "DIAGNOSIS_CONTINUOUS_INCREASE.md",
        "CHECK_PARENT_FALLBACK_USAGE.md"
    ]
    
    for doc in docs:
        if Path(doc).exists():
            print(f"   ✅ {doc}")
        else:
            print(f"   ⚠️  {doc} not found (optional)")
    
    # Check notebook
    print("\n3️⃣ Checking notebook...")
    notebook_path = Path("notebooks/Markovchain.ipynb")
    
    if not notebook_path.exists():
        print(f"   ❌ {notebook_path} NOT FOUND")
        all_good = False
    else:
        print(f"   ✅ {notebook_path} exists")
        
        # Check if diagnostic section was added
        try:
            with open(notebook_path, 'r', encoding='utf-8') as f:
                nb = json.load(f)
            
            # Look for diagnostic section
            has_diagnostic = False
            for cell in nb['cells']:
                if cell['cell_type'] == 'markdown':
                    source = ''.join(cell['source'])
                    if 'DIAGNOSTIC: DEL CURVE ANALYSIS' in source:
                        has_diagnostic = True
                        break
            
            if has_diagnostic:
                print(f"   ✅ Diagnostic section found in notebook")
                print(f"   📊 Total cells: {len(nb['cells'])}")
            else:
                print(f"   ❌ Diagnostic section NOT found in notebook")
                print(f"   💡 Run: python add_diagnostic_to_markovchain.py")
                all_good = False
        except Exception as e:
            print(f"   ❌ Error reading notebook: {e}")
            all_good = False
    
    # Check imports
    print("\n4️⃣ Checking if diagnostic scripts can be imported...")
    try:
        from diagnose_why_increase_after_24 import diagnose_why_increase_after_24
        print("   ✅ diagnose_why_increase_after_24 can be imported")
    except ImportError as e:
        print(f"   ❌ Cannot import diagnose_why_increase_after_24: {e}")
        all_good = False
    
    try:
        from check_p24_quality import check_p24_quality
        print("   ✅ check_p24_quality can be imported")
    except ImportError as e:
        print(f"   ❌ Cannot import check_p24_quality: {e}")
        all_good = False
    
    try:
        from diagnose_del_curve import diagnose_del_curve
        print("   ✅ diagnose_del_curve can be imported")
    except ImportError as e:
        print(f"   ❌ Cannot import diagnose_del_curve: {e}")
        all_good = False
    
    # Summary
    print("\n" + "="*60)
    if all_good:
        print("✅ ALL CHECKS PASSED!")
        print("="*60)
        print("\n📝 Next steps:")
        print("   1. Open notebooks/Markovchain.ipynb")
        print("   2. Run all cells up to Section 8")
        print("   3. Run the diagnostic cells")
        print("   4. Follow the recommendations")
        print("\n📚 Documentation:")
        print("   - DIAGNOSTIC_ADDED_SUMMARY.md (Quick start)")
        print("   - NEXT_STEPS_DIAGNOSIS.md (English guide)")
        print("   - HUONG_DAN_CHAY_DIAGNOSTIC.md (Vietnamese guide)")
    else:
        print("❌ SOME CHECKS FAILED")
        print("="*60)
        print("\n💡 Please fix the issues above before proceeding")
    
    return all_good

if __name__ == "__main__":
    verify_setup()
