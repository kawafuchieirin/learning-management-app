#!/usr/bin/env python3
# DynamoDB接続テスト

import boto3
from datetime import datetime
import uuid

# DynamoDB設定
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url="http://localhost:8002",
    region_name="ap-northeast-1",
    aws_access_key_id="fakeMyKeyId",
    aws_secret_access_key="fakeSecretAccessKey"
)

ROADMAP_TABLE_NAME = 'learning_roadmaps'
DEFAULT_USER_ID = 'default_user'

def test_dynamodb():
    try:
        # テーブル取得
        table = dynamodb.Table(ROADMAP_TABLE_NAME)
        print(f"Table: {table}")
        
        # テストデータ作成
        roadmap_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        created_at = datetime.now().isoformat()
        
        milestones = [{
            'id': str(uuid.uuid4())[:8],
            'title': 'テストマイルストーン',
            'description': 'テスト説明',
            'estimated_hours': 10,
            'completed': False,
            'completed_date': None
        }]
        
        item = {
            'user_id': DEFAULT_USER_ID,
            'roadmap_id': roadmap_id,
            'title': 'テストロードマップ',
            'description': 'テスト説明',
            'goal': 'テスト目標',
            'milestones': milestones,
            'created_at': created_at,
            'status': 'active',
            'source': 'test'
        }
        
        print(f"Saving item: {item}")
        
        # DynamoDBに保存
        table.put_item(Item=item)
        print("Successfully saved to DynamoDB!")
        
        # 確認のため取得
        response = table.get_item(
            Key={'user_id': DEFAULT_USER_ID, 'roadmap_id': roadmap_id}
        )
        
        if 'Item' in response:
            print(f"Retrieved item: {response['Item']}")
        else:
            print("Item not found after saving!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dynamodb()