"""
Configuration file for PM Standards Comparator
Contains settings for local text generation model
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Local Text Generation Model Configuration
# Using a lightweight model that runs on CPU without API key
LOCAL_GENERATION_MODEL = "distilgpt2"  # Small, fast, no API key needed
LOCAL_MAX_LENGTH = 512
LOCAL_TEMPERATURE = 0.8

# Application Settings
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production')

