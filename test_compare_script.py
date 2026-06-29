"""
Test script để kiểm tra compare_p24_vs_forecast có lỗi syntax không
"""

import sys

try:
    # Import script
    from compare_p24_vs_forecast import compare_p24_vs_forecast
    print("✅ Import thành công!")
    print(f"✅ Function signature: {compare_p24_vs_forecast.__name__}")
    print(f"✅ Docstring: {compare_p24_vs_forecast.__doc__[:100]}...")
    
    # Kiểm tra parameters
    import inspect
    sig = inspect.signature(compare_p24_vs_forecast)
    print(f"\n✅ Parameters:")
    for param_name, param in sig.parameters.items():
        default = param.default if param.default != inspect.Parameter.empty else "required"
        print(f"   - {param_name}: {default}")
    
    print("\n✅ Script không có lỗi syntax!")
    
except SyntaxError as e:
    print(f"❌ Lỗi syntax: {e}")
    print(f"   File: {e.filename}")
    print(f"   Line: {e.lineno}")
    print(f"   Text: {e.text}")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Lỗi khác: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
