#!/usr/bin/env python3
"""
Script to install packages in the correct order with appropriate flags.
This script helps resolve dependency issues on platforms like Render.com
"""

import subprocess
import sys
import platform
import os

def print_info():
    """Print system information for debugging"""
    print(f"Python version: {platform.python_version()}")
    print(f"Python implementation: {platform.python_implementation()}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.machine()}")
    print(f"System: {platform.system()}")

def install_packages():
    """Install packages in the correct order with appropriate flags"""
    print("Installing base packages...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--upgrade", 
        "pip", "setuptools", "wheel", "cython"
    ])
    
    print("Installing scientific packages...")
    scientific_packages = [
        "numpy==1.24.4",
        "scipy==1.10.1", 
        "pandas==2.0.3",
        "scikit-learn==1.1.3",
        "joblib==1.3.2"
    ]
    
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--prefer-binary",
        "--only-binary=numpy,scipy,pandas,scikit-learn"
    ] + scientific_packages)
    
    print("Installing remaining packages from requirements.txt...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--prefer-binary",
        "-r", "requirements.txt"
    ])

def verify_packages():
    """Verify that key packages were installed correctly"""
    packages_to_check = [
        "numpy", "scipy", "pandas", "sklearn", "nltk", 
        "flask", "dropbox", "coremltools"
    ]
    
    print("\nVerifying installed packages:")
    for package in packages_to_check:
        try:
            module = __import__(package)
            version = getattr(module, "__version__", "unknown")
            print(f"✅ {package} version: {version}")
        except ImportError:
            print(f"❌ Failed to import {package}")

if __name__ == "__main__":
    print_info()
    install_packages()
    verify_packages()
    print("\nPackage installation completed.")
