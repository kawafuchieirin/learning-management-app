#!/usr/bin/env python3
"""
DynamoDB Localのデータをバックアップするスクリプト
"""

import shutil
import os
from datetime import datetime
from pathlib import Path

def backup_dynamodb_data():
    """DynamoDB Localのデータをバックアップ"""
    
    # ソースファイル
    source_dir = Path("dynamodb_local")
    db_file = source_dir / "shared-local-instance.db"
    
    if not db_file.exists():
        print("❌ データベースファイルが見つかりません")
        return False
    
    # バックアップディレクトリを作成
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    # タイムスタンプ付きのバックアップファイル名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"backup_{timestamp}.db"
    
    try:
        # ファイルをコピー
        shutil.copy2(db_file, backup_file)
        print(f"✅ バックアップ完了: {backup_file}")
        
        # ファイルサイズを表示
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        print(f"📊 ファイルサイズ: {size_mb:.2f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ バックアップエラー: {e}")
        return False

def restore_backup(backup_file_name):
    """バックアップからデータを復元"""
    
    backup_file = Path("backups") / backup_file_name
    if not backup_file.exists():
        print(f"❌ バックアップファイルが見つかりません: {backup_file}")
        return False
    
    # 復元先
    target_dir = Path("dynamodb_local")
    target_file = target_dir / "shared-local-instance.db"
    
    try:
        # 現在のファイルをバックアップ
        if target_file.exists():
            shutil.copy2(target_file, str(target_file) + ".bak")
        
        # バックアップから復元
        shutil.copy2(backup_file, target_file)
        print(f"✅ 復元完了: {backup_file_name}")
        return True
        
    except Exception as e:
        print(f"❌ 復元エラー: {e}")
        return False

def list_backups():
    """利用可能なバックアップを一覧表示"""
    
    backup_dir = Path("backups")
    if not backup_dir.exists():
        print("バックアップはありません")
        return
    
    backups = sorted(backup_dir.glob("backup_*.db"))
    
    if not backups:
        print("バックアップはありません")
        return
    
    print("📁 利用可能なバックアップ:")
    for backup in backups:
        size_mb = backup.stat().st_size / (1024 * 1024)
        print(f"  - {backup.name} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python backup_data.py backup    # バックアップを作成")
        print("  python backup_data.py list      # バックアップ一覧を表示")
        print("  python backup_data.py restore <filename>  # バックアップから復元")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "backup":
        backup_dynamodb_data()
    elif command == "list":
        list_backups()
    elif command == "restore" and len(sys.argv) > 2:
        restore_backup(sys.argv[2])
    else:
        print("❌ 無効なコマンドです")