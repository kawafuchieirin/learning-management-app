# 学習記録管理アプリ 📚

学習記録を管理し、「理解できたこと」と「できなかったこと」をメモとして記録できるWebアプリケーションです。
**DynamoDB Local** を使用してローカル開発環境で柔軟なデータ管理を実現し、将来的にAWS DynamoDBへの移行も簡単に行えます。

## 🎯 機能

- **学習記録の追加**: 日付、内容、時間を記録
- **メモ機能**: 
  - 理解できたこと（振り返り・成長記録）
  - できなかったこと（改善課題の管理）
- **ダッシュボード**: 学習状況とメモのハイライト表示
- **全記録表示**: 学習履歴の一覧表示
- **メモ振り返り**: 理解できたことと改善すべきことの整理
- **CSVエクスポート**: 学習記録をCSV形式でダウンロード
- **DynamoDB Local**: ローカル開発環境でのNoSQLデータベース体験

## 🚀 セットアップ

### 1. 前提条件

- **Python 3.7+**: アプリケーション実行環境
- **Java 8+**: DynamoDB Local実行に必要

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. DynamoDB Local のセットアップと起動

**自動セットアップ (推奨)**:
```bash
python setup_dynamodb.py
```

**手動セットアップ**:
```bash
# DynamoDB Local のダウンロード
curl -o dynamodb_local.tar.gz https://d1ni2b6xgvw0s0.cloudfront.net/v2.x/dynamodb_local_latest.tar.gz
tar -xzf dynamodb_local.tar.gz -C dynamodb_local/

# DynamoDB Local の起動
cd dynamodb_local
java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb -port 8002
```

### 4. アプリケーションの起動

**方法1: 統合起動スクリプト（推奨） - 1つのターミナルで実行**
```bash
python run.py
```
このコマンドで、DynamoDB LocalとFlaskアプリが同時に起動します。

**方法2: 個別起動（従来の方法）**
```bash
# ターミナル1: DynamoDB Localを起動
python setup_dynamodb.py

# ターミナル2: Flaskアプリを起動
python app.py
```

### 5. ブラウザでアクセス

```
http://localhost:5000
```

### 6. アプリケーションの停止

`run.py`を使用している場合は、`Ctrl+C`で両方のサービスが自動的に停止します。

## 🗄️ データベース構造

### DynamoDB テーブル設計

**テーブル名**: `study_records`

**キー設計**:
- **Partition Key**: `user_id` (String) - ユーザー識別子
- **Sort Key**: `record_id` (String) - 記録ID（タイムスタンプ + UUID）

**属性**:
| 属性名 | 型 | 説明 | 必須 |
|--------|----|----|------|
| user_id | String | ユーザー識別子 | ✅ |
| record_id | String | 記録ID | ✅ |
| date | String | 記録日 (YYYY-MM-DD) | ✅ |
| content | String | 学習内容 | ✅ |
| time | Number | 学習時間（分） | ✅ |
| could_not_do | String | できなかったこと | ❌ |
| understood | String | 理解できたこと | ❌ |
| created_at | String | 作成日時 (ISO形式) | ✅ |

## 📱 使用方法

1. **記録追加**: 学習した内容と時間を記録
2. **メモ入力**: 理解できたことや課題を自由に記録
3. **ダッシュボード**: 学習状況とメモのハイライトを確認
4. **振り返り**: メモ機能で過去の学習を振り返り
5. **CSVエクスポート**: 学習データをExcelなどで分析

## 🔧 技術スタック

- **フロントエンド**: HTML, CSS, JavaScript, Bootstrap 5
- **バックエンド**: Python Flask
- **データベース**: DynamoDB Local (将来的にAWS DynamoDB)
- **アイコン**: Font Awesome
- **AWS SDK**: Boto3

## 🌟 DynamoDB Local の利点

- **ノーコスト開発**: AWS料金を気にせずに開発可能
- **高速レスポンス**: ローカル実行による高速なデータ操作
- **柔軟なスキーマ**: 後から属性を追加しやすいNoSQL設計
- **AWS互換**: AWS DynamoDBへの移行が簡単
- **オフライン開発**: インターネット接続なしでも開発可能

## 🔄 AWS DynamoDB への移行

本番環境でAWS DynamoDBを使用する場合は、`app.py`の以下の設定を変更してください：

```python
# ローカル開発用
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url="http://localhost:8002",  # この行を削除
    region_name="ap-northeast-1",
    aws_access_key_id="fakeMyKeyId",      # 実際のAWSクレデンシャルを設定
    aws_secret_access_key="fakeSecretAccessKey"  # 実際のAWSクレデンシャルを設定
)

# 本番環境用
dynamodb = boto3.resource(
    'dynamodb',
    region_name="ap-northeast-1"
)
```
