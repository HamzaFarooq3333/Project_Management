#!/usr/bin/env python3
"""
Download a lightweight text generation model for AI-powered recommendations
Uses GPT-2 Small - works on CPU, no API key needed
"""

def download_generation_model():
    print("\n" + "="*70)
    print("  DOWNLOADING TEXT GENERATION MODEL")
    print("="*70 + "\n")
    
    try:
        from transformers import GPT2LMHeadModel, GPT2Tokenizer
        
        model_name = "gpt2"
        
        print(f"Downloading: {model_name}")
        print("Size: ~500MB")
        print("This will take 2-5 minutes...\n")
        
        print("Step 1: Downloading tokenizer...")
        tokenizer = GPT2Tokenizer.from_pretrained(model_name)
        print("✅ Tokenizer ready\n")
        
        print("Step 2: Downloading model...")
        model = GPT2LMHeadModel.from_pretrained(model_name)
        print("✅ Model ready\n")
        
        print("="*70)
        print("  ✅ DOWNLOAD COMPLETE!")
        print("="*70)
        print(f"\nModel: {model_name}")
        print("Type: Text Generation")
        print("Runs on: CPU (no GPU required)")
        print("API Key: Not required\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    print("\nThis will download GPT-2 model for text generation.")
    print("Required: pip install transformers torch\n")
    
    success = download_generation_model()
    
    if success:
        print("Model is ready!")
        print("\nNext steps:")
        print("1. Clear cache: for /d /r . %d in (__pycache__) do @if exist \"%d\" rd /s /q \"%d\"")
        print("2. Start app: python run.py\n")
    else:
        print("\nTo install dependencies:")
        print("  pip install transformers torch\n")
    
    input("Press Enter to exit...")

