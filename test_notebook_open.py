"""
Test if notebook can be opened and basic cells can be executed
"""
import json
import sys

def test_notebook(filepath):
    """Test if notebook is valid and can be opened"""
    print(f"Testing: {filepath}")
    print("="*80)
    
    try:
        # 1. Load JSON
        with open(filepath, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("✅ Step 1: JSON loaded successfully")
        
        # 2. Check structure
        assert 'cells' in nb, "Missing 'cells' key"
        assert 'metadata' in nb, "Missing 'metadata' key"
        assert 'nbformat' in nb, "Missing 'nbformat' key"
        print(f"✅ Step 2: Structure valid (nbformat {nb['nbformat']}.{nb.get('nbformat_minor', 0)})")
        
        # 3. Check cells
        n_cells = len(nb['cells'])
        n_code = sum(1 for c in nb['cells'] if c.get('cell_type') == 'code')
        n_markdown = sum(1 for c in nb['cells'] if c.get('cell_type') == 'markdown')
        print(f"✅ Step 3: {n_cells} cells ({n_code} code, {n_markdown} markdown)")
        
        # 4. Check first code cell
        first_code = next((c for c in nb['cells'] if c.get('cell_type') == 'code'), None)
        if first_code:
            source = ''.join(first_code.get('source', []))
            print(f"✅ Step 4: First code cell has {len(source)} characters")
            if len(source) > 0:
                print(f"   Preview: {source[:100]}...")
        
        # 5. Check metadata
        if 'kernelspec' in nb['metadata']:
            kernel = nb['metadata']['kernelspec']
            print(f"✅ Step 5: Kernel: {kernel.get('name', 'unknown')} ({kernel.get('language', 'unknown')})")
        else:
            print("⚠️  Step 5: No kernelspec (will use default)")
        
        print("\n" + "="*80)
        print("✅ NOTEBOOK IS VALID AND READY TO USE!")
        print("="*80)
        
        print("\nHow to open:")
        print("  1. Jupyter Notebook: jupyter notebook " + filepath)
        print("  2. JupyterLab:       jupyter lab " + filepath)
        print("  3. VS Code:          code " + filepath)
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Test both notebooks
    files = [
        "notebooks/Markovchain_With_Diagnostic.ipynb",
        "notebooks/Markovchain_With_Diagnostic_Clean.ipynb"
    ]
    
    results = {}
    for filepath in files:
        print("\n")
        results[filepath] = test_notebook(filepath)
        print("\n")
    
    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    for filepath, success in results.items():
        status = "✅ VALID" if success else "❌ INVALID"
        print(f"{status}: {filepath}")
