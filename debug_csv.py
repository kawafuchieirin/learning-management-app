#!/usr/bin/env python3
# CSVインポートのデバッグ用スクリプト

import csv
import io

def test_csv_parsing(file_path):
    print(f"Testing CSV file: {file_path}")
    
    # ファイルを読み込み
    with open(file_path, 'rb') as f:
        file_bytes = f.read()
    
    print(f"File size: {len(file_bytes)} bytes")
    
    # エンコーディングをテスト
    encodings = ['utf-8', 'utf-8-sig', 'shift_jis', 'cp932']
    file_content = None
    used_encoding = None
    
    for encoding in encodings:
        try:
            file_content = file_bytes.decode(encoding)
            used_encoding = encoding
            print(f"Successfully decoded with {encoding}")
            break
        except UnicodeDecodeError:
            print(f"Failed to decode with {encoding}")
            continue
    
    if file_content is None:
        print("Could not decode file with any encoding!")
        return
    
    print(f"File content (first 200 chars): {repr(file_content[:200])}")
    
    # CSVパース
    stream = io.StringIO(file_content, newline=None)
    csv_input = csv.DictReader(stream)
    
    print(f"CSV headers: {csv_input.fieldnames}")
    
    row_count = 0
    for row in csv_input:
        row_count += 1
        print(f"Row {row_count}: {row}")
        
        title = row.get('ロードマップタイトル', '').strip()
        milestone_title = row.get('マイルストーンタイトル', '').strip()
        
        print(f"  -> Title: '{title}', Milestone: '{milestone_title}'")
    
    print(f"Total rows processed: {row_count}")

if __name__ == "__main__":
    test_csv_parsing("/Users/kawabuchieirin/learning-management-app/test_roadmap.csv")
    print("\n" + "="*50 + "\n")
    test_csv_parsing("/Users/kawabuchieirin/learning-management-app/simple_test.csv")