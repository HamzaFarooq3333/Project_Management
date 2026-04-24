#!/usr/bin/env python3
"""
Start the application with AI model pre-flight check
"""

import sys
import subprocess

def main():
    print("\n" + "="*70)
    print("  PM STANDARDS COMPARATOR - STARTUP")
    print("="*70 + "\n")
    
    # Step 1: Check AI model
    print("Running AI model pre-flight check...\n")
    
    result = subprocess.run([sys.executable, "check_model.py"], capture_output=False)
    
    if result.returncode != 0:
        print("\n" + "="*70)
        print("  ⚠️  STARTUP ABORTED")
        print("="*70)
        print("\nAI model check failed. Application cannot start.")
        print("\nOptions:")
        print("1. Install AI packages:")
        print("   pip install transformers>=4.30.0 torch>=2.0.0")
        print("\n2. Download model:")
        print("   python download_gen_model.py")
        print("\n3. Run check again:")
        print("   python check_model.py")
        print()
        return 1
    
    # Step 2: Start the application
    print("\n" + "="*70)
    print("  STARTING APPLICATION")
    print("="*70 + "\n")
    
    subprocess.run([sys.executable, "run.py"])
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

