#!/usr/bin/env python3
"""
Launch script for the ChatGPT Micro-Cap Experiment web interface.
This script checks dependencies and starts the Streamlit app.
"""

import sys
import subprocess
import importlib
import os
from pathlib import Path

def check_and_install_dependencies():
    """Check if required dependencies are available, install if missing."""
    required_packages = {
        'streamlit': 'streamlit',
        'plotly': 'plotly', 
        'pandas': 'pandas',
        'numpy': 'numpy',
        'openai': 'openai',
        'yfinance': 'yfinance',
        'requests': 'requests',
        'matplotlib': 'matplotlib'
    }
    
    missing_packages = []
    
    for package_name, pip_name in required_packages.items():
        try:
            importlib.import_module(package_name)
            print(f"✅ {package_name} is available")
        except ImportError:
            print(f"❌ {package_name} is missing")
            missing_packages.append(pip_name)
    
    if missing_packages:
        print(f"\n🔧 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "--user", "--upgrade"
            ] + missing_packages)
            print("✅ Dependencies installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            print("\nPlease manually install the required packages:")
            print(f"pip3 install {' '.join(missing_packages)}")
            return False
    
    return True

def launch_app():
    """Launch the Streamlit application."""
    app_path = Path(__file__).parent / "app.py"
    
    if not app_path.exists():
        print("❌ app.py not found!")
        return False
    
    print(f"🚀 Starting Streamlit app from {app_path}")
    print("📱 The app will open in your default browser")
    print("🛑 Press Ctrl+C to stop the server")
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(app_path),
            "--server.address", "127.0.0.1",
            "--server.port", "8501"
        ])
    except KeyboardInterrupt:
        print("\n👋 App stopped by user")
    except FileNotFoundError:
        print("❌ Streamlit not found. Please install it first:")
        print("pip3 install streamlit")
        return False
    except Exception as e:
        print(f"❌ Error starting app: {e}")
        return False
    
    return True

def main():
    """Main launcher function."""
    print("🎯 ChatGPT Micro-Cap Experiment Launcher")
    print("=" * 50)
    
    print("\n📋 Checking dependencies...")
    if not check_and_install_dependencies():
        print("\n❌ Dependency check failed. Please resolve issues and try again.")
        sys.exit(1)
    
    print("\n🚀 Launching web interface...")
    if not launch_app():
        print("\n❌ Failed to launch app. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()