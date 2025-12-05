import os
import boto3
from botocore.config import Config
from openai import OpenAI
import google.generativeai as genai

# グローバル変数
client = None
dynamodb = None
s3_client = None
cloth_table = None
weather_table = None
coordinate_table = None
user_table = None

# 環境変数
BUCKET_NAME = os.environ.get('BUCKET_NAME')
WEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
GOOGLE_GENAI_KEY = os.environ.get('GOOGLE_GENAI_KEY')

def initialize():
    global client, dynamodb, s3_client, lambda_client
    global cloth_table, weather_table, coordinate_table, user_table

    if client and dynamodb:
        return

    print("DEBUG: Initializing resources...")
    
    # AI Clients
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    if GOOGLE_GENAI_KEY:
        genai.configure(api_key=GOOGLE_GENAI_KEY)

    # AWS Clients
    # DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
    
    # ★修正: S3クライアントにリージョンと署名バージョンを明示する
    s3_client = boto3.client(
        's3', 
        region_name='ap-northeast-1',
        config=Config(signature_version='s3v4')
    )
    
    lambda_client = boto3.client('lambda', region_name='ap-northeast-1')

    # DB Tables
    cloth_table = dynamodb.Table(os.environ.get('TABLE_CLOTH'))
    weather_table = dynamodb.Table(os.environ.get('TABLE_WEATHER'))
    coordinate_table = dynamodb.Table(os.environ.get('TABLE_COORDINATE'))
    user_table = dynamodb.Table(os.environ.get('TABLE_USER'))
    
    print("DEBUG: Resources initialized successfully.")