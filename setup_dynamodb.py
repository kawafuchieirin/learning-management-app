#!/usr/bin/env python3
"""
DynamoDB Local setup script for the Learning Management App
"""

import subprocess
import sys
import os
import time
import requests
from pathlib import Path

DYNAMODB_LOCAL_URL = "https://d1ni2b6xgvw0s0.cloudfront.net/v2.x/dynamodb_local_latest.tar.gz"
DYNAMODB_LOCAL_DIR = "dynamodb_local"

def download_dynamodb_local():
    """Download and extract DynamoDB Local"""
    print("📥 Downloading DynamoDB Local...")
    
    # Create directory if it doesn't exist
    Path(DYNAMODB_LOCAL_DIR).mkdir(exist_ok=True)
    
    # Download and extract
    subprocess.run([
        "curl", "-o", "dynamodb_local.tar.gz", DYNAMODB_LOCAL_URL
    ], check=True)
    
    subprocess.run([
        "tar", "-xzf", "dynamodb_local.tar.gz", "-C", DYNAMODB_LOCAL_DIR
    ], check=True)
    
    # Clean up
    os.remove("dynamodb_local.tar.gz")
    print("✅ DynamoDB Local downloaded and extracted")

def start_dynamodb_local():
    """Start DynamoDB Local server"""
    print("🚀 Starting DynamoDB Local server...")
    
    # Change to DynamoDB Local directory
    os.chdir(DYNAMODB_LOCAL_DIR)
    
    # Start DynamoDB Local
    cmd = [
        "java", 
        "-Djava.library.path=./DynamoDBLocal_lib", 
        "-jar", "DynamoDBLocal.jar", 
        "-sharedDb",
        "-port", "8000"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    print("📍 DynamoDB Local will be available at: http://localhost:8000")
    print("🔄 Press Ctrl+C to stop the server")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 DynamoDB Local server stopped")

def check_java():
    """Check if Java is installed"""
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        print(f"✅ Java is installed: {result.stderr.split()[2]}")
        return True
    except FileNotFoundError:
        print("❌ Java is not installed. Please install Java 8+ to run DynamoDB Local")
        return False

def main():
    """Main setup function"""
    print("🎯 Learning Management App - DynamoDB Local Setup")
    print("=" * 50)
    
    # Check Java installation
    if not check_java():
        sys.exit(1)
    
    # Check if DynamoDB Local is already downloaded
    if not os.path.exists(DYNAMODB_LOCAL_DIR):
        download_dynamodb_local()
    else:
        print("✅ DynamoDB Local already exists")
    
    # Start DynamoDB Local
    start_dynamodb_local()

if __name__ == "__main__":
    main()