#!/usr/bin/env python3
"""
シンプルな統合起動スクリプト
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path

# プロセス管理
processes = []

def cleanup(signum=None, frame=None):
    """終了処理"""
    print("\n🛑 アプリケーションを停止しています...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
    for p in processes:
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()
    print("✅ 停止完了")
    sys.exit(0)

def check_port(port):
    """ポートが使用可能か確認"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

def main():
    print("🎯 学習記録管理アプリ - 起動中")
    print("=" * 50)
    
    # シグナルハンドラ設定
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Java確認
    try:
        subprocess.run(["java", "-version"], capture_output=True, check=True)
    except:
        print("❌ Javaがインストールされていません")
        sys.exit(1)
    
    # DynamoDB Localが必要かチェック
    if check_port(8002):
        print("🚀 DynamoDB Localを起動しています...")
        dynamodb_dir = Path("dynamodb_local")
        if not dynamodb_dir.exists():
            print("❌ DynamoDB Localがありません。setup_dynamodb.pyを実行してください")
            sys.exit(1)
        
        # DynamoDB Local起動
        dynamodb_process = subprocess.Popen(
            ["java", "-Djava.library.path=./DynamoDBLocal_lib", 
             "-jar", "DynamoDBLocal.jar", "-sharedDb", "-port", "8002"],
            cwd=dynamodb_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        processes.append(dynamodb_process)
        time.sleep(3)
        print("✅ DynamoDB Localが起動しました")
    else:
        print("ℹ️  DynamoDB Localは既に起動しています")
    
    # Flask起動
    print("🚀 Flaskアプリを起動しています...")
    flask_process = subprocess.Popen([sys.executable, "app.py"])
    processes.append(flask_process)
    print("✅ Flaskアプリが起動しました")
    print("\n📌 http://localhost:5000 でアクセスできます")
    print("📌 Ctrl+C で停止します\n")
    
    # Flaskプロセスを待つ
    try:
        flask_process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()