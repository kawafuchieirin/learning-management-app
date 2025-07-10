# 学習記録管理アプリ 📚

学習記録を管理し、「理解できたこと」と「できなかったこと」をメモとして記録できるWebアプリケーションです。

## 🎯 機能

- **学習記録の追加**: 日付、内容、時間を記録
- **メモ機能**: 
  - 理解できたこと（振り返り・成長記録）
  - できなかったこと（改善課題の管理）
- **ダッシュボード**: 学習状況とメモのハイライト表示
- **全記録表示**: 学習履歴の一覧表示
- **メモ振り返り**: 理解できたことと改善すべきことの整理

## 🚀 セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. アプリケーションの起動

```bash
python app.py
```

### 3. ブラウザでアクセス

```
http://localhost:5000
```

## 🗄️ データベース構造

```sql
CREATE TABLE study_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    content TEXT NOT NULL,
    time INTEGER NOT NULL,
    could_not_do TEXT,
    understood TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 📱 使用方法

1. **記録追加**: 学習した内容と時間を記録
2. **メモ入力**: 理解できたことや課題を自由に記録
3. **ダッシュボード**: 学習状況とメモのハイライトを確認
4. **振り返り**: メモ機能で過去の学習を振り返り

## 🔧 技術スタック

- **フロントエンド**: HTML, CSS, JavaScript, Bootstrap 5
- **バックエンド**: Python Flask
- **データベース**: SQLite
- **アイコン**: Font Awesome
