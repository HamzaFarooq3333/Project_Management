#!/usr/bin/env python3
"""
Startup script for the PM Standards Comparator application.
This script handles model downloading and starts the FastAPI server.
"""

import sys
import subprocess
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import fastapi
        import uvicorn
        import sentence_transformers
        import faiss
        import numpy
        print("✅ All required dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def download_model():
    """Download the sentence-transformers model if not already cached."""
    try:
        from sentence_transformers import SentenceTransformer
        model_name = 'sentence-transformers/all-MiniLM-L6-v2'
        print(f"Checking for model: {model_name}")
        
        # Try to load the model (this will download if not cached)
        model = SentenceTransformer(model_name)
        print("✅ Model is ready")
        return True
    except Exception as e:
        print(f"❌ Error with model: {e}")
        return False

def start_server():
    """Start the FastAPI server."""
    try:
        print("🚀 Starting PM Standards Comparator server...")
        print("📍 Server will be available at: http://127.0.0.1:8000")
        print("📖 API documentation at: http://127.0.0.1:8000/docs")
        print("🛑 Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Start the server
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "127.0.0.1", 
            "--port", "8000", 
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

def main():
    """Main function to run the application."""
    print("🔧 PM Standards Comparator - Startup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("app/main.py").exists():
        print("❌ Please run this script from the project root directory")
        print("   The directory should contain the 'app' folder")
        return
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Download model
    if not download_model():
        return
    
    # Start server
    start_server()

if __name__ == "__main__":
    main()
