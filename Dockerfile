# Lambda用FlaskアプリケーションDockerfile (Mangum使用)
FROM public.ecr.aws/lambda/python:3.9

# 作業ディレクトリの設定
WORKDIR ${LAMBDA_TASK_ROOT}

# 依存関係のコピーとインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY app.py .
COPY lambda_handler.py .
COPY templates/ templates/

# Lambda関数のハンドラーを設定
CMD ["lambda_handler.handler"]