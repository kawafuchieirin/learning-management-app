"""
AWS Lambda handler for Flask application using Mangum
"""
import os
from mangum import Mangum

# 本番環境でのinit_db実行を防ぐため、環境変数を設定
os.environ.setdefault('AWS_LAMBDA_FUNCTION_NAME', 'lambda')

from app import app

# Lambda handler using Mangum with proper WSGI application
handler = Mangum(app.wsgi_app, lifespan="off")