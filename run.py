#!/usr/bin/env python3
"""
統合起動スクリプト - DynamoDB LocalとFlaskアプリを同時に起動
"""

import subprocess
import sys
import os
import time
import signal
import atexit
from pathlib import Path

# グローバル変数でプロセスを管理
dynamodb_process = None
flask_process = None

def cleanup():
    """終了時のクリーンアップ処理"""
    global dynamodb_process, flask_process
    
    print("\n🛑 アプリケーションを停止しています...")
    
    if flask_process and flask_process.poll() is None:
        flask_process.terminate()
        try:
            flask_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            flask_process.kill()
        print("✅ Flaskアプリを停止しました")
    
    if dynamodb_process and dynamodb_process.poll() is None:
        dynamodb_process.terminate()
        try:
            dynamodb_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            dynamodb_process.kill()
        print("✅ DynamoDB Localを停止しました")

def signal_handler(sig, frame):
    """Ctrl+Cのハンドリング"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # 追加のSIGINTを無視
    cleanup()
    sys.exit(0)

def check_java():
    """Javaがインストールされているか確認"""
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False

def is_port_in_use(port):
    """指定されたポートが使用中かチェック"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def start_dynamodb():
    """DynamoDB Localをバックグラウンドで起動"""
    global dynamodb_process
    
    # ポートが既に使用されているかチェック
    if is_port_in_use(8002):
        print("⚠️  DynamoDB Local (port 8002) は既に起動しています")
        return True
    
    print("🚀 DynamoDB Localを起動しています...")
    
    # DynamoDB Localディレクトリに移動
    dynamodb_dir = Path("dynamodb_local")
    if not dynamodb_dir.exists():
        print("❌ DynamoDB Localがインストールされていません。先にsetup_dynamodb.pyを実行してください。")
        return False
    
    # DynamoDB Localを起動
    cmd = [
        "java", 
        "-Djava.library.path=./DynamoDBLocal_lib", 
        "-jar", "DynamoDBLocal.jar", 
        "-sharedDb",
        "-port", "8002"
    ]
    
    try:
        # STDOUTとSTDERRを抑制してバックグラウンドで実行
        dynamodb_process = subprocess.Popen(
            cmd,
            cwd=dynamodb_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # 起動を待つ
        time.sleep(3)
        
        # プロセスが正常に起動したか確認
        if dynamodb_process.poll() is not None:
            print("❌ DynamoDB Localの起動に失敗しました")
            return False
        
        print("✅ DynamoDB Localが起動しました (http://localhost:8002)")
        return True
        
    except Exception as e:
        print(f"❌ DynamoDB Localの起動エラー: {e}")
        return False

def start_flask():
    """Flaskアプリを起動"""
    global flask_process
    
    print("🚀 Flaskアプリを起動しています...")
    
    try:
        # 環境変数を設定してFlaskアプリを起動
        env = os.environ.copy()
        env['FLASK_ENV'] = 'development'
        env['DYNAMODB_ENDPOINT_URL'] = 'http://localhost:8002'
        env['AWS_ACCESS_KEY_ID'] = 'fakeMyKeyId'
        env['AWS_SECRET_ACCESS_KEY'] = 'fakeSecretAccessKey'
        env['AWS_REGION'] = 'ap-northeast-1'
        # WERKZEUG_RUN_MAINは削除（問題の原因）
        
        # Flaskアプリを起動
        flask_process = subprocess.Popen(
            [sys.executable, "app.py"],
            env=env
        )
        
        print("✅ Flaskアプリが起動しました (http://localhost:5000)")
        
        # Flaskプロセスが終了するまで待つ
        flask_process.wait()
        
    except Exception as e:
        print(f"❌ Flaskアプリの起動エラー: {e}")
        return False

def main():
    """メイン処理"""
    print("🎯 学習記録管理アプリ - 統合起動")
    print("=" * 50)
    
    # シグナルハンドラとクリーンアップの設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup)
    
    # Javaの確認
    if not check_java():
        print("❌ Javaがインストールされていません。Java 8+をインストールしてください。")
        sys.exit(1)
    
    # DynamoDB Localを起動
    if not start_dynamodb():
        sys.exit(1)
    
    # Flaskアプリを起動
    start_flask()

if __name__ == "__main__":
    main()