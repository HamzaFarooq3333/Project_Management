#!/usr/bin/env python3
"""
Pre-flight check for AI model before starting the application
"""

def check_ai_model():
    """Check if AI model is available and working"""
    print("\n" + "="*70)
    print("  CHECKING AI MODEL")
    print("="*70 + "\n")
    
    # Step 1: Check if packages are installed
    print("Step 1: Checking if transformers and torch are installed...")
    try:
        import transformers
        import torch
        print("✅ Packages installed")
        print(f"   - transformers: {transformers.__version__}")
        print(f"   - torch: {torch.__version__}")
    except ImportError as e:
        print(f"❌ Required packages not installed: {e}")
        print("\nTo install:")
        print("  pip install transformers>=4.30.0 torch>=2.0.0")
        print("\nApplication cannot start without AI model.")
        return False
    
    print()
    
    # Step 2: Try to load the model
    print("Step 2: Loading GPT-2 model...")
    try:
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
        
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        print("\nModel needs to be downloaded first.")
        print("Run: python download_gen_model.py")
        return False
    
    print()
    
    # Step 3: Test generation
    print("Step 3: Testing model generation...")
    try:
        test_prompt = "Project management is"
        inputs = tokenizer.encode(test_prompt, return_tensors="pt")
        
        with torch.no_grad():
            outputs = model.generate(
                inputs,
                max_length=50,
                num_return_sequences=1,
                pad_token_id=tokenizer.eos_token_id
            )
        
        generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"   Test input: '{test_prompt}'")
        print(f"   Generated: '{generated[:80]}...'")
        print("   ✅ Generation working")
        
    except Exception as e:
        print(f"❌ Generation test failed: {e}")
        return False
    
    print()
    print("="*70)
    print("  ✅ AI MODEL IS READY!")
    print("="*70)
    print()
    return True


if __name__ == "__main__":
    import sys
    
    success = check_ai_model()
    
    if not success:
        print("\n⚠️  APPLICATION STARTUP BLOCKED")
        print("\nFix the issues above, then run:")
        print("  python check_model.py")
        print("\nOnce the check passes, start the app:")
        print("  python run.py")
        print()
        sys.exit(1)
    else:
        print("AI model check passed!")
        print("\nYou can now start the application:")
        print("  python run.py")
        print()
        sys.exit(0)

