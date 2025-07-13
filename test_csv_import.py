#!/usr/bin/env python3
# CSVインポート機能のテスト

import sys
sys.path.append('.')

from app import save_roadmap_from_csv
import csv
import io

def test_csv_import(csv_file_path):
    print(f"Testing CSV import for file: {csv_file_path}")
    
    # CSVファイルを読み込み
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    print(f"CSV content: {file_content}")
    
    # CSVを解析
    stream = io.StringIO(file_content, newline=None)
    csv_input = csv.DictReader(stream)
    
    print(f"Headers: {csv_input.fieldnames}")
    
    roadmaps_created = 0
    current_roadmap = None
    current_milestones = []
    
    row_count = 0
    for row in csv_input:
        row_count += 1
        print(f"Row {row_count}: {row}")
        
        # Skip empty rows
        if not any(row.values()):
            print("Skipping empty row")
            continue
        
        # Extract data
        title = row.get('ロードマップタイトル', '').strip()
        description = row.get('説明', '').strip()
        goal = row.get('目標', '').strip()
        milestone_title = row.get('マイルストーンタイトル', '').strip()
        milestone_description = row.get('マイルストーン説明', '').strip()
        estimated_hours_str = row.get('推定時間', '8').strip()
        
        print(f"Extracted - title: '{title}', milestone: '{milestone_title}'")
        
        # Parse estimated hours
        try:
            estimated_hours = int(estimated_hours_str) if estimated_hours_str.isdigit() else 8
        except (ValueError, AttributeError):
            estimated_hours = 8
        
        # If we have a new roadmap title
        if title and (current_roadmap is None or current_roadmap['title'] != title):
            print(f"New roadmap detected: '{title}'")
            
            # Save previous roadmap if it exists
            if current_roadmap is not None:
                print(f"Saving previous roadmap: '{current_roadmap['title']}' with {len(current_milestones)} milestones")
                try:
                    save_roadmap_from_csv(current_roadmap, current_milestones)
                    roadmaps_created += 1
                    print(f"Saved successfully! Total: {roadmaps_created}")
                except Exception as e:
                    print(f"Error saving: {e}")
            
            # Start new roadmap
            print(f"Starting new roadmap: '{title}'")
            current_roadmap = {
                'title': title,
                'description': description,
                'goal': goal
            }
            current_milestones = []
        
        # Add milestone
        if milestone_title:
            if current_roadmap is not None:
                print(f"Adding milestone '{milestone_title}'")
                current_milestones.append({
                    'title': milestone_title,
                    'description': milestone_description,
                    'estimated_hours': estimated_hours
                })
                print(f"Total milestones: {len(current_milestones)}")
            else:
                print(f"Creating roadmap from milestone: '{milestone_title}'")
                current_roadmap = {
                    'title': milestone_title,
                    'description': '',
                    'goal': ''
                }
                current_milestones = [{
                    'title': milestone_title,
                    'description': milestone_description,
                    'estimated_hours': estimated_hours
                }]
    
    print(f"Finished processing {row_count} rows")
    print(f"Current roadmap: {current_roadmap}")
    print(f"Current milestones: {len(current_milestones) if current_milestones else 0}")
    
    # Save the last roadmap
    if current_roadmap is not None:
        print(f"Saving final roadmap: '{current_roadmap['title']}'")
        try:
            save_roadmap_from_csv(current_roadmap, current_milestones)
            roadmaps_created += 1
            print(f"Final save successful! Total: {roadmaps_created}")
        except Exception as e:
            print(f"Error saving final roadmap: {e}")
    else:
        print("No roadmap to save at the end")
    
    print(f"Total roadmaps created: {roadmaps_created}")

if __name__ == "__main__":
    test_csv_import("/Users/kawabuchieirin/learning-management-app/test_roadmap.csv")