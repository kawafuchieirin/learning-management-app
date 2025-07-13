.PHONY: build deploy local clean

# SAMビルド
build:
	sam build

# SAMデプロイ（初回）
deploy-guided:
	sam deploy --guided

# SAMデプロイ（2回目以降）
deploy:
	sam deploy

# ローカル実行（Docker使用）
local:
	sam local start-api -p 3000 --env-vars env.json

# ローカル環境変数ファイル作成
create-env:
	@echo '{}' > env.json
	@echo 'env.jsonファイルを作成しました。必要に応じて環境変数を追加してください。'

# クリーンアップ
clean:
	rm -rf .aws-sam/

# ローカル開発環境起動（従来の方法）
run-local:
	python run.py