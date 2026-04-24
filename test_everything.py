#!/usr/bin/env python3
"""
Comprehensive test of EVERY component affecting generation
"""

import sys
import traceback

def test_step(step_name, test_func):
    """Run a test step and report result"""
    print(f"\n{'='*70}")
    print(f"  {step_name}")
    print('='*70)
    try:
        result = test_func()
        if result:
            print(f"✅ PASS: {step_name}")
            return True
        else:
            print(f"❌ FAIL: {step_name}")
            return False
    except Exception as e:
        print(f"❌ ERROR in {step_name}: {e}")
        traceback.print_exc()
        return False

def test_1_imports():
    """Test 1: Can we import all required modules?"""
    print("\n1. Testing imports...")
    
    # Core imports
    from app.services.local_ai import generate_process_recommendation, generate_summary
    print("   ✅ local_ai imported")
    
    from app.services.ai_generator import generate_process_recommendation_ai, generate_summary_ai
    print("   ✅ ai_generator imported")
    
    from app.services.search import get_engine
    print("   ✅ search imported")
    
    from app.routers import api
    print("   ✅ api router imported")
    
    return True

def test_2_search_engine():
    """Test 2: Can we load search engine and get data?"""
    print("\n2. Testing search engine...")
    
    from app.services.search import get_engine
    
    engine = get_engine()
    print("   ✅ Search engine loaded")
    
    # Test query
    results = engine.query("project management", k=5)
    print(f"   ✅ Query returned {len(results)} results")
    
    if results:
        r = results[0]
        print(f"   ✅ Sample result: {r.get('standard', '?')} - Page {r.get('page', '?')}")
        print(f"   ✅ Text length: {len(r.get('text', ''))} chars")
    
    # Test getting snippets for standard
    snippets = engine.get_all_snippets_for_standard("PMBOK")
    print(f"   ✅ Found {len(snippets)} snippets for PMBOK")
    
    return len(results) > 0

def test_3_ai_packages():
    """Test 3: Are AI packages installed?"""
    print("\n3. Testing AI packages...")
    
    try:
        import transformers
        print(f"   ✅ transformers installed: {transformers.__version__}")
    except ImportError:
        print("   ❌ transformers NOT installed")
        return False
    
    try:
        import torch
        print(f"   ✅ torch installed: {torch.__version__}")
    except ImportError:
        print("   ❌ torch NOT installed")
        return False
    
    return True

def test_4_load_model():
    """Test 4: Can we load GPT-2 model?"""
    print("\n4. Testing model loading...")
    
    from transformers import GPT2LMHeadModel, GPT2Tokenizer
    
    model_name = "gpt2"
    
    print(f"   Loading tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token
    print("   ✅ Tokenizer loaded")
    
    print(f"   Loading model...")
    model = GPT2LMHeadModel.from_pretrained(model_name)
    model.eval()
    print("   ✅ Model loaded")
    
    return True

def test_5_generate_text():
    """Test 5: Can we generate text with the model?"""
    print("\n5. Testing text generation...")
    
    from transformers import GPT2LMHeadModel, GPT2Tokenizer
    import torch
    
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token
    model = GPT2LMHeadModel.from_pretrained("gpt2")
    model.eval()
    
    prompt = "Project management is"
    inputs = tokenizer.encode(prompt, return_tensors="pt")
    
    print(f"   Prompt: '{prompt}'")
    print(f"   Generating...")
    
    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_length=50,
            num_return_sequences=1,
            pad_token_id=tokenizer.eos_token_id
        )
    
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"   ✅ Generated: '{generated[:100]}...'")
    
    return len(generated) > len(prompt)

def test_6_ai_generator_module():
    """Test 6: Does ai_generator module work?"""
    print("\n6. Testing ai_generator module...")
    
    from app.services.ai_generator import _model_available, generate_with_ai
    
    print(f"   Model available flag: {_model_available}")
    
    if not _model_available:
        print("   ❌ Model marked as NOT available in ai_generator")
        return False
    
    # Test generation
    test_prompt = "Project management involves"
    result = generate_with_ai(test_prompt, max_length=100)
    
    if result:
        print(f"   ✅ Generated {len(result)} characters")
        print(f"   ✅ Sample: '{result[:80]}...'")
        return True
    else:
        print("   ❌ generate_with_ai returned None")
        return False

def test_7_process_recommendation():
    """Test 7: Does process recommendation work?"""
    print("\n7. Testing process recommendation...")
    
    from app.services.ai_generator import generate_process_recommendation_ai
    
    test_snippets = [
        {'standard': 'PMBOK', 'text': 'Project management is the application of knowledge, skills, tools, and techniques.', 'page': 10},
        {'standard': 'PMBOK', 'text': 'The project lifecycle provides a framework for managing projects.', 'page': 25},
    ]
    
    result = generate_process_recommendation_ai(
        project_type="software",
        project_size="small",
        industry="IT",
        methodology_preference="PMBOK",
        evidence_snippets=test_snippets
    )
    
    if result:
        print(f"   ✅ Generated {len(result)} characters")
        print(f"   ✅ Contains references: {'References Used' in result}")
        return True
    else:
        print("   ❌ generate_process_recommendation_ai returned None")
        return False

def test_8_summary_generation():
    """Test 8: Does summary generation work?"""
    print("\n8. Testing summary generation...")
    
    from app.services.ai_generator import generate_summary_ai
    
    test_snippets = [
        {'standard': 'PMBOK', 'text': 'PMBOK Guide provides guidelines for project management.', 'page': 5},
        {'standard': 'PMBOK', 'text': 'It covers knowledge areas and process groups.', 'page': 15},
    ]
    
    result = generate_summary_ai("PMBOK", test_snippets)
    
    if result:
        print(f"   ✅ Generated {len(result)} characters")
        print(f"   ✅ Contains references: {'References' in result}")
        return True
    else:
        print("   ❌ generate_summary_ai returned None")
        return False

def test_9_local_ai_integration():
    """Test 9: Does local_ai integrate with ai_generator?"""
    print("\n9. Testing local_ai integration...")
    
    from app.services.local_ai import generate_process_recommendation
    
    test_snippets = [
        {'standard': 'PMBOK', 'text': 'Test text for PMBOK', 'page': 1}
    ]
    
    result = generate_process_recommendation(
        project_type="software",
        project_size="small",
        industry="IT",
        methodology_preference="PMBOK",
        evidence_snippets=test_snippets
    )
    
    if result:
        print(f"   ✅ Generated {len(result)} characters")
        is_ai = "AI-Generated" in result
        is_template = "Executive Summary" in result
        print(f"   ✅ AI-generated: {is_ai}")
        print(f"   ✅ Template fallback: {is_template}")
        return True
    else:
        print("   ❌ generate_process_recommendation returned None")
        return False

def test_10_api_endpoint():
    """Test 10: Does API endpoint work?"""
    print("\n10. Testing API endpoint...")
    
    from app.services.search import get_engine
    from app.services.local_ai import generate_process_recommendation
    
    engine = get_engine()
    
    # Simulate what the API does
    search_queries = ["software project management", "small project planning"]
    all_results = []
    for query in search_queries:
        results = engine.query(query, k=5)
        all_results.extend(results)
    
    print(f"   ✅ Found {len(all_results)} search results")
    
    # Generate
    result = generate_process_recommendation(
        project_type="software",
        project_size="small",
        industry="IT",
        methodology_preference="PMBOK",
        evidence_snippets=all_results
    )
    
    if result:
        print(f"   ✅ API simulation successful ({len(result)} chars)")
        return True
    else:
        print("   ❌ API simulation failed")
        return False

# Main test runner
def main():
    print("\n" + "="*70)
    print("  COMPREHENSIVE GENERATION SYSTEM TEST")
    print("="*70)
    
    tests = [
        ("Test 1: Imports", test_1_imports),
        ("Test 2: Search Engine", test_2_search_engine),
        ("Test 3: AI Packages", test_3_ai_packages),
        ("Test 4: Load Model", test_4_load_model),
        ("Test 5: Generate Text", test_5_generate_text),
        ("Test 6: AI Generator Module", test_6_ai_generator_module),
        ("Test 7: Process Recommendation", test_7_process_recommendation),
        ("Test 8: Summary Generation", test_8_summary_generation),
        ("Test 9: Local AI Integration", test_9_local_ai_integration),
        ("Test 10: API Endpoint", test_10_api_endpoint),
    ]
    
    results = []
    for name, test_func in tests:
        passed = test_step(name, test_func)
        results.append((name, passed))
        if not passed:
            print(f"\n⚠️  Stopping at first failure: {name}")
            break
    
    # Summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(p for _, p in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("  ✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nGeneration system is working correctly.")
        print("\nIf app still fails:")
        print("1. Clear cache: for /d /r . %d in (__pycache__) do @if exist \"%d\" rd /s /q \"%d\"")
        print("2. Restart app: python run.py")
    else:
        print("  ❌ SOME TESTS FAILED")
        print("="*70)
        print("\nCheck the errors above to see what's broken.")
    
    print()
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

