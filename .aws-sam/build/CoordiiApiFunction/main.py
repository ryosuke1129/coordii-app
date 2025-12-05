import json
import resources
from services import user_service, cloth_service, weather_service, coord_service, tryon_service

def handler(event, context):
    try:
        resources.initialize()
    except Exception as e:
        return {"statusCode": 500, "headers": {}, "body": json.dumps({"message": "Init Error", "error": str(e)})}

    # 非同期ワーカー分岐
    if not event.get('httpMethod'):
        task = event.get('task')
        if task == 'try_on_worker':
            return tryon_service.worker(event)
        if task == 'coord_worker': # ★追加
            return coord_service.worker(event)

    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE"
    }

    if event['httpMethod'] == 'OPTIONS':
        return {"statusCode": 200, "headers": headers, "body": ""}

    path = event['path']
    method = event['httpMethod']

    if path == '/users':
        if method == 'POST': return user_service.register_user(event, headers)
        if method == 'GET': return user_service.get_user(event, headers)

    if path == '/clothes':
        if method == 'POST': return cloth_service.register_cloth(event, headers)
        if method == 'GET': return cloth_service.get_clothes(event, headers)
        if method == 'PUT': return cloth_service.update_cloth(event, headers)
        if method == 'DELETE': return cloth_service.delete_cloth(event, headers)

    if path == '/upload-url' and method == 'POST':
        return cloth_service.get_upload_url(event, headers)

    if path == '/analyze' and method == 'POST':
        return cloth_service.analyze_cloth(event, headers)

    if path == '/weather' and method == 'POST':
        return weather_service.get_weather(event, headers)

    if path == '/coordinates':
        if method == 'POST': return coord_service.start_create_coordinate(event, headers, context) # ★変更
        if method == 'GET': return coord_service.get_history(event, headers)

    # ★追加: コーデ状況確認
    if path == '/coordinates/status':
        if method == 'GET': return coord_service.check_status(event, headers)

    if path == '/try-on':
        if method == 'POST': return tryon_service.start_try_on(event, headers, context)
        if method == 'GET': return tryon_service.check_try_on(event, headers)

    return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Not Found"})}




# import json
# import os
# import boto3
# import time
# import uuid
# import requests
# from openai import OpenAI
# import google.generativeai as genai
# from decimal import Decimal
# from datetime import datetime, timedelta, timezone
# from boto3.dynamodb.conditions import Key

# # 初期化print("DEBUG: Global scope started")
# client = None
# dynamodb = None
# s3_client = None
# cloth_table = None
# weather_table = None
# coordinate_table = None
# user_table = None
# BUCKET_NAME = os.environ.get('BUCKET_NAME')
# WEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY')
# GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
# GOOGLE_GENAI_KEY = os.environ.get('GOOGLE_GENAI_KEY')
# if GOOGLE_GENAI_KEY:
#     genai.configure(api_key=GOOGLE_GENAI_KEY)

# # --- 共通ヘルパー: 署名付きURL生成 ---
# def sign_s3_url(image_url):
#     """
#     生のS3 URLを受け取り、有効期限付きの署名付きURLに変換して返す
#     URLがS3のものでない場合や、解析失敗時は元のURLを返す
#     """
#     if not image_url or BUCKET_NAME not in image_url:
#         return image_url
    
#     try:
#         # URLからファイル名(Key)を抽出
#         file_key = image_url.split('/')[-1]
        
#         presigned_url = s3_client.generate_presigned_url(
#             ClientMethod='get_object',
#             Params={'Bucket': BUCKET_NAME, 'Key': file_key},
#             ExpiresIn=3600  # 1時間有効
#         )
#         return presigned_url
#     except Exception as e:
#         print(f"Failed to sign URL: {e}")
#         return image_url

# def initialize_resources():
#     global client, dynamodb, s3_client, cloth_table, weather_table, coordinate_table, user_table
    
#     # すでに初期化済みなら何もしない
#     if client and dynamodb: return

#     print("DEBUG: Initializing resources...")
#     try:
#         client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
#         dynamodb = boto3.resource('dynamodb')
#         s3_client = boto3.client('s3')
        
#         # テーブル名が環境変数にない場合のエラーハンドリング
#         if not os.environ.get('TABLE_CLOTH'):
#             raise Exception("Environment variable TABLE_CLOTH is missing")
            
#         cloth_table = dynamodb.Table(os.environ.get('TABLE_CLOTH'))
#         weather_table = dynamodb.Table(os.environ.get('TABLE_WEATHER'))
#         coordinate_table = dynamodb.Table(os.environ.get('TABLE_COORDINATE'))
#         user_table = dynamodb.Table(os.environ.get('TABLE_USER'))
#         print("DEBUG: Resources initialized successfully.")
#     except Exception as e:
#         print(f"CRITICAL: Resource initialization failed: {e}")
#         raise e

# # --- Handler ---
# def handler(event, context):
#     print(f"DEBUG: Handler started. Path: {event.get('path')}")
#     # ★修正: ここで初期化を実行 (try-catchで守られる)
#     try:
#         initialize_resources()
#     except Exception as e:
#         return {"statusCode": 500, "headers": {}, "body": json.dumps({"message": "Init Error", "error": str(e)})}
#     headers = {
#         "Access-Control-Allow-Origin": "*",
#         "Access-Control-Allow-Headers": "Content-Type",
#         "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT"
#     }

#     if event['httpMethod'] == 'OPTIONS':
#         return {"statusCode": 200, "headers": headers, "body": ""}

#     path = event['path']

#     # 1. ユーザー管理
#     if path == '/users':
#         if event['httpMethod'] == 'POST':
#             return register_user(event, headers)
#         if event['httpMethod'] == 'GET':
#             return get_user(event, headers)

#     # 2. 洋服関連
#     if path == '/clothes':
#         if event['httpMethod'] == 'POST':
#             return register_cloth(event, headers)
#         if event['httpMethod'] == 'GET':
#             return get_clothes(event, headers)
#         if event['httpMethod'] == 'DELETE':
#             return delete_cloth(event, headers)
#         if event['httpMethod'] == 'PUT': 
#             return update_cloth(event, headers)

#     if path == '/analyze' and event['httpMethod'] == 'POST':
#         return analyze_cloth(event, headers)

#     if path == '/upload-url' and event['httpMethod'] == 'POST':
#         return get_upload_url(event, headers)

#     # 3. 天気関連
#     if path == '/weather' and event['httpMethod'] == 'POST':
#         return get_weather(event, headers)

#     # 4. コーデ関連
#     if path == '/coordinates':
#         if event['httpMethod'] == 'POST':
#             return create_coordinate(event, headers)
#         if event['httpMethod'] == 'GET':
#             return get_history(event, headers)
        
#     # 5. バーチャル試着 (Virtual Mirror)
#     if path == '/try-on':
#         if event['httpMethod'] == 'POST':
#             return start_try_on(event, headers, context) # 受付
#         if event['httpMethod'] == 'GET':
#             return check_try_on(event, headers)      # 確認

#     # ★重要: 非同期呼び出し(Event)された場合の分岐
#     # API Gateway経由ではなく、LambdaがLambdaを呼んだ時は 'httpMethod' がありません
#     if not event.get('httpMethod') and event.get('task') == 'try_on_worker':
#         return try_on_worker(event)
    
#     return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Not Found"})}

# # --- 以下、各機能の関数 ---

# def update_cloth(event, headers):
#     try:
#         body = json.loads(event['body'])
#         user_id = body.get('userId')
#         old_cloth_id = body.get('clothId')
        
#         if not user_id or not old_cloth_id:
#             return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId and clothId are required"})}

#         # 1. 旧レコードを論理削除
#         cloth_table.update_item(
#             Key={'userId': user_id, 'clothId': int(old_cloth_id)},
#             UpdateExpression="set deleteFlag = :f",
#             ExpressionAttributeValues={':f': 1}
#         )

#         # 2. 新規レコード作成
#         new_cloth_id = int(time.time() * 1000)
        
#         item = {
#             'userId': user_id,
#             'clothId': new_cloth_id,
#             'imageUrl': body.get('imageUrl'),
#             'category': body.get('category'),
#             'brand': body.get('brand'),
#             'size': body.get('size'),
#             'color': body.get('color'),
#             'material': body.get('material'),
#             'seasons': body.get('seasons'),
#             'style': body.get('style'),
#             'suitableMinTemp': body.get('suitableMinTemp'),
#             'suitableMaxTemp': body.get('suitableMaxTemp'),
#             'description': body.get('description'),
#             'createDatetime': time.strftime('%Y-%m-%dT%H:%M:%S'),
#             'deleteFlag': 0
#         }
#         cloth_table.put_item(Item=item)

#         return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Updated successfully", "data": item}, default=str)}

#     except Exception as e:
#         print(f"Error: {e}")
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# def delete_cloth(event, headers):
#     try:
#         body = json.loads(event['body'])
#         user_id = body.get('userId')
#         cloth_id = body.get('clothId')
#         if not user_id or not cloth_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId and clothId are required"})}
#         cloth_table.update_item(Key={'userId': user_id, 'clothId': int(cloth_id)}, UpdateExpression="set deleteFlag = :f", ExpressionAttributeValues={':f': 1})
#         return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Deleted successfully"}, default=str)}
#     except Exception as e: return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# def get_clothes(event, headers):
#     try:
#         params = event.get('queryStringParameters') or {}
#         user_id = params.get('userId')
#         target_category = params.get('category')
#         if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
#         response = cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
#         items = response.get('Items', [])
        
#         valid_items = []
#         for item in items:
#             if item.get('deleteFlag', 0) == 0:
#                 if target_category and item.get('category') != target_category:
#                     continue
                
#                 if 'imageUrl' in item:
#                     item['imageUrl'] = sign_s3_url(item['imageUrl'])
                
#                 valid_items.append(item)
                
#         return {"statusCode": 200, "headers": headers, "body": json.dumps(valid_items, default=str, ensure_ascii=False)}
#     except Exception as e: return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# def get_upload_url(event, headers):
#     try:
#         body = json.loads(event['body'])
#         file_type = body.get('fileType', 'jpg')
#         content_type = f'image/{file_type}'
#         if file_type == 'jpg': content_type = 'image/jpeg'
        
#         file_name = f"{uuid.uuid4()}.{file_type}"
        
#         # 1. アップロード用 (PUT) - 署名付き
#         upload_url = s3_client.generate_presigned_url(
#             'put_object', 
#             Params={'Bucket': BUCKET_NAME, 'Key': file_name, 'ContentType': content_type}, 
#             ExpiresIn=300
#         )
        
#         # 2. ★追加: 直後のプレビュー表示用 (GET) - 署名付き
#         # (まだファイルがなくても、キーが合っていればURL自体は生成可能です)
#         download_url = s3_client.generate_presigned_url(
#             'get_object', 
#             Params={'Bucket': BUCKET_NAME, 'Key': file_name}, 
#             ExpiresIn=300
#         )
        
#         # 3. DB保存用 (Raw) - 署名なし
#         image_url = f"https://{BUCKET_NAME}.s3.ap-northeast-1.amazonaws.com/{file_name}"
        
#         return {
#             "statusCode": 200, 
#             "headers": headers, 
#             "body": json.dumps({
#                 "uploadUrl": upload_url, 
#                 "imageUrl": image_url,      # DB用
#                 "downloadUrl": download_url # 表示用
#             })
#         }
#     except Exception as e: 
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# def analyze_cloth(event, headers):
#     try:
#         body = json.loads(event['body'])
#         raw_image_url = body.get('imageUrl')
#         user_id = body.get('userId') 

#         if not raw_image_url:
#             return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "imageUrl is required"})}
        
#         # 署名付きURL生成
#         try:
#             file_key = raw_image_url.split('/')[-1]
#             ai_access_url = s3_client.generate_presigned_url(
#                 ClientMethod='get_object',
#                 Params={'Bucket': BUCKET_NAME, 'Key': file_key},
#                 ExpiresIn=300
#             )
#         except Exception as e:
#             print(f"URL generation failed: {e}")
#             ai_access_url = raw_image_url

#         # ★修正: ユーザー情報を取得してプロンプトに含める
#         user_info_text = ""
#         if user_id:
#             try:
#                 resp = user_table.query(
#                     KeyConditionExpression=Key('userId').eq(user_id),
#                     ScanIndexForward=False,
#                     Limit=1
#                 )
#                 items = resp.get('Items', [])
#                 if items:
#                     user = items[0]
#                     gender = user.get('gender', '不明')
#                     height = user.get('height', '不明')
#                     # 身長・性別を強調
#                     user_info_text = f"【着用者属性】性別: {gender}, 身長: {height}cm。これらを考慮して、この着用者に適したカテゴリやサイズ感を推測してください。"
#             except Exception as e:
#                 print(f"User fetch error: {e}")

#         prompt = f"""
#         この服の画像を解析し、以下のJSONフォーマットで情報を抽出してください。
#         {user_info_text}

#         {{
#           "category": "アウター" | "トップス" | "ボトムス" | "シューズ" | "ワンピース" | "小物",
#           "brand": "ロゴやタグから推測されるブランド名(判別できない場合は空文字)",
#           "size": "推測されるサイズ(S/M/L/フリーなど、わからなければフリー)",
#           "color": "主要な1色(例: ブラック, ネイビー, ホワイト)",
#           "material": "見た目から推測される主要な素材1つ(例: 綿, ナイロン, レザー)",
#           "seasons": ["春", "夏", "秋", "冬"] の中から該当するものを配列で,
#           "style": "カジュアル" | "きれいめ" | "スポーティ" | "フォーマル",
#           "suitableMinTemp": 着用可能な最低気温(整数),
#           "suitableMaxTemp": 着用可能な最高気温(整数),
#           "description": "服の特徴を短く説明した文章"
#         }}
#         JSONのみを返してください。
#         """
        
#         response = client.chat.completions.create(
#             model="gpt-5-nano", 
#             messages=[{
#                 "role": "user", 
#                 "content": [
#                     {"type": "text", "text": prompt},
#                     {"type": "image_url", "image_url": {"url": ai_access_url}},
#                 ]
#             }],
#             response_format={"type": "json_object"},
#         )
#         ai_result = json.loads(response.choices[0].message.content)
#         return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Analyzed successfully", "data": ai_result}, default=str)}

#     except Exception as e:
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}
    
# def register_cloth(event, headers):
#     try:
#         body = json.loads(event['body'])
#         user_id = body.get('userId')
#         image_url = body.get('imageUrl')
#         category = body.get('category')
#         if not user_id or not image_url or not category: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "Required fields missing"})}
#         cloth_id = int(time.time() * 1000)
#         item = {
#             'userId': user_id, 'clothId': cloth_id, 'imageUrl': image_url, 'category': category,
#             'brand': body.get('brand'), 
#             'size': body.get('size'), 
#             'color': body.get('color'), 'material': body.get('material'), 'seasons': body.get('seasons'),
#             'style': body.get('style'), 'suitableMinTemp': body.get('suitableMinTemp'), 'suitableMaxTemp': body.get('suitableMaxTemp'),
#             'description': body.get('description'), 'createDatetime': time.strftime('%Y-%m-%dT%H:%M:%S'), 'deleteFlag': 0
#         }
#         cloth_table.put_item(Item=item)
#         return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Saved successfully!", "data": item}, default=str)}
#     except Exception as e: return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# def get_lat_long(address):
#     if not GOOGLE_API_KEY: return None, None
#     try:
#         url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_API_KEY}&language=ja"
#         res = requests.get(url)
#         data = res.json()
#         if data['status'] == 'OK':
#             loc = data['results'][0]['geometry']['location']
#             lat = Decimal(str(loc['lat'])).quantize(Decimal("0.01"))
#             lon = Decimal(str(loc['lng'])).quantize(Decimal("0.01"))
#             return lat, lon
#     except:
#         pass
#     return None, None

# def register_user(event, headers):
#     try:
#         body = json.loads(event['body'])
#         user_id = body.get('userId')
#         address = body.get('address')
        
#         if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}

#         existing_resp = user_table.query(
#             KeyConditionExpression=Key('userId').eq(user_id)
#         )
#         existing_items = existing_resp.get('Items', [])
        
#         for item in existing_items:
#             if item.get('deleteFlag', 0) == 0:
#                 user_table.update_item(
#                     Key={
#                         'userId': user_id, 
#                         'createDatetime': item['createDatetime']
#                     },
#                     UpdateExpression="set deleteFlag = :f",
#                     ExpressionAttributeValues={':f': 1}
#                 )

#         lat, lon = None, None
#         if address:
#             lat, lon = get_lat_long(address)

#         current_time = datetime.now(timezone(timedelta(hours=+9), 'JST')).strftime('%Y-%m-%dT%H:%M:%S')
        
#         item = {
#             'userId': user_id,
#             'createDatetime': current_time,
#             'gender': body.get('gender'),
#             'birthDay': body.get('birthDay'),
#             'height': body.get('height'),
#             'address': address,
#             'latitude': lat,
#             'longitude': lon,
#             'weeklySchedule': body.get('weeklySchedule') or {}, 
#             'imageLink': body.get('imageLink'),
#             'updateDatetime': current_time,
#             'deleteFlag': 0
#         }
        
#         user_table.put_item(Item=item)
#         return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "User saved", "data": item}, default=str, ensure_ascii=False)}

#     except Exception as e:
#         print(f"Error: {e}")
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# def get_user(event, headers):
#     try:
#         params = event.get('queryStringParameters') or {}
#         user_id = params.get('userId')
#         if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}

#         resp = user_table.query(
#             KeyConditionExpression=Key('userId').eq(user_id),
#             ScanIndexForward=False 
#         )
#         items = resp.get('Items', [])

#         active_user = None
#         for item in items:
#             if item.get('deleteFlag', 0) == 0:
#                 active_user = item
#                 break

#         if not active_user:
#             return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "User not found"})}
        
#         if 'imageLink' in active_user:
#             active_user['imageLink'] = sign_s3_url(active_user['imageLink'])

#         return {"statusCode": 200, "headers": headers, "body": json.dumps(active_user, default=str, ensure_ascii=False)}

#     except Exception as e:
#         print(f"Error: {e}")
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# def get_weather(event, headers):
#     try:
#         body = json.loads(event['body'])
#         user_id = body.get('userId')
#         city_name = body.get('city', '福岡市博多区')
#         if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
        
#         lat_dec, lon_dec = get_lat_long(city_name)
#         if not lat_dec: return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Location not found"})}

#         JST = timezone(timedelta(hours=+9), 'JST')
#         now_jst = datetime.now(JST)
#         if now_jst.hour >= 19: target_date = now_jst + timedelta(days=1)
#         else: target_date = now_jst
#         target_date_str = target_date.strftime('%Y-%m-%d')

#         res = requests.get(f"https://api.openweathermap.org/data/2.5/forecast?lat={lat_dec}&lon={lon_dec}&appid={WEATHER_API_KEY}&units=metric&lang=ja")
#         data = res.json()
#         if res.status_code != 200: return {"statusCode": res.status_code, "headers": headers, "body": json.dumps(data)}

#         temps, pops = [], []
#         weather_desc, icon_code = "", ""
#         humidity, wind_speed, wind_deg = 0, 0, 0
#         for item in data['list']:
#             if target_date_str in item['dt_txt']:
#                 temps.append(item['main']['temp_max'])
#                 temps.append(item['main']['temp_min'])
#                 pops.append(item.get('pop', 0))
#                 if "03:00:00" in item['dt_txt']:
#                     weather_desc = item['weather'][0]['description']
#                     icon_code = item['weather'][0]['icon']
#                     humidity = item['main']['humidity']
#                     wind_speed = item['wind']['speed']
#                     wind_deg = item['wind']['deg']
#         if not weather_desc and temps:
#             first = [x for x in data['list'] if target_date_str in x['dt_txt']][0]
#             weather_desc = first['weather'][0]['description']
#             icon_code = first['weather'][0]['icon']
#             humidity = first['main']['humidity']
#             wind_speed = first['wind']['speed']
#             wind_deg = first['wind']['deg']
#         if not temps: return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": f"Forecast for {target_date_str} not found"})}

#         item = {
#             'userId': user_id, 'targetDate': target_date_str, 'latitude': lat_dec, 'longitude': lon_dec,
#             'weather': weather_desc, 'iconUrl': f"https://openweathermap.org/img/wn/{icon_code}@2x.png" if icon_code else None,
#             'max': Decimal(str(max(temps))).quantize(Decimal("0.1")), 'min': Decimal(str(min(temps))).quantize(Decimal("0.1")),
#             'humidity': Decimal(str(humidity)), 'pop': Decimal(str(int(max(pops) * 100))),
#             'windSpeed': Decimal(str(wind_speed)).quantize(Decimal("0.1")), 'windDirection': get_wind_direction_jp(wind_deg),
#             'city': city_name, 'createDatetime': now_jst.strftime('%Y-%m-%dT%H:%M:%S'), 'deleteFlag': 0
#         }
#         weather_table.put_item(Item=item)
#         return {"statusCode": 200, "headers": headers, "body": json.dumps(item, default=str, ensure_ascii=False)}
#     except Exception as e:
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# def get_wind_direction_jp(degrees):
#     directions = ["北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東", "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"]
#     index = int((degrees + 11.25) / 22.5) % 16
#     return directions[index]

# def get_current_season(date_str):
#     dt = datetime.strptime(date_str, '%Y-%m-%d')
#     month = dt.month
#     if 3 <= month <= 5: return '春'
#     if 6 <= month <= 9: return '夏'
#     if 10 <= month <= 11: return '秋'
#     return '冬'

# def create_coordinate(event, headers):
#     print("DEBUG [create_coordinate]: Start")
#     try:
#         body = json.loads(event['body'])
#         user_id = body.get('userId')
#         anchor_cloth_id = body.get('anchorClothId')
        
#         if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
        
#         JST = timezone(timedelta(hours=+9), 'JST')
#         now_jst = datetime.now(JST)
        
#         if now_jst.hour >= 19: 
#             target_date = now_jst + timedelta(days=1)
#         else: 
#             target_date = now_jst
#         target_date_str = target_date.strftime('%Y-%m-%d')
        
#         weekday_index = target_date.weekday()
#         weekdays_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
#         current_weekday_str = weekdays_map[weekday_index]

#         # --- ユーザー情報 & 曜日設定取得 ---
#         print("DEBUG [create_coordinate]: Fetching User...")
#         user_resp = user_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
#         weekly_style = ""
#         user_attributes = ""

#         if user_resp['Items']:
#             user_data = user_resp['Items'][0]
#             # 1. 曜日設定の取得
#             schedule = user_data.get('weeklySchedule') or {}
#             weekly_style = schedule.get(current_weekday_str, "")
            
#             # 2. ★追加: ユーザー属性(性別・身長)の取得
#             u_gender = user_data.get('gender', '不明')
#             u_height = user_data.get('height', '不明')
#             user_attributes = f"【着用者属性】性別: {u_gender}, 身長: {u_height}cm"
#             print(f"DEBUG [create_coordinate]: User Fetched. Style: {weekly_style}")

#         # --- 天気取得 ---
#         print("DEBUG [create_coordinate]: Fetching Weather...")
#         weather_resp = weather_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
#         if not weather_resp['Items'] or weather_resp['Items'][0].get('targetDate') != target_date_str:
#              return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Weather data for target date not found."})}
#         weather_data = weather_resp['Items'][0]
#         print("DEBUG [create_coordinate]: Weather Fetched.")

#         # --- 服データ全件取得 ---
#         print("DEBUG [create_coordinate]: Fetching Clothes...")
#         cloth_resp = cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
#         all_clothes = cloth_resp['Items']
#         if not all_clothes: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "No clothes registered."})}
        
#         cloth_map = {int(c['clothId']): c['imageUrl'] for c in all_clothes}
#         print(f"DEBUG [create_coordinate]: Clothes Fetched. Count: {len(all_clothes)}")
        
#         # --- アンカー（固定アイテム）の特定 ---
#         anchor_cloth_info = ""
#         anchor_category = ""
#         if anchor_cloth_id:
#             anchor_item = next((c for c in all_clothes if int(c['clothId']) == int(anchor_cloth_id)), None)
#             if anchor_item:
#                 anchor_category = anchor_item.get('category')
#                 anchor_cloth_info = f"""
#                 【必須固定アイテム】
#                 この服は必ずコーデに含めてください。
#                 id: {anchor_cloth_id}
#                 category: {anchor_category}
#                 color: {anchor_item.get('color')}
#                 desc: {anchor_item.get('description')}
#                 """

#         # --- フィルタリング ---
#         current_season = get_current_season(target_date_str)
#         day_max_temp = float(weather_data['max'])
#         day_min_temp = float(weather_data['min'])
#         TEMP_BUFFER = 5.0 
        
#         filtered_clothes = []
#         for c in all_clothes:
#             if anchor_cloth_id and int(c['clothId']) == int(anchor_cloth_id):
#                 filtered_clothes.append(c)
#                 continue

#             if c.get('seasons') and current_season not in c['seasons']: continue 
#             c_min = float(c.get('suitableMinTemp', -50))
#             c_max = float(c.get('suitableMaxTemp', 50))
#             if c_min > (day_max_temp + TEMP_BUFFER): continue
#             if c_max < (day_min_temp - TEMP_BUFFER): continue
#             filtered_clothes.append(c)
        
#         target_clothes_list = filtered_clothes if len(filtered_clothes) > 0 else all_clothes
        
#         if len(target_clothes_list) == 1 and anchor_cloth_id:
#             target_clothes_list = all_clothes

#         closet_summary = []
#         for c in target_clothes_list:
#             closet_summary.append({
#                 "id": int(c['clothId']),
#                 "category": c['category'],
#                 "color": c.get('color'),
#                 "style": c.get('style'),
#                 "desc": c.get('description', '')
#             })

#         print(f"DEBUG [create_coordinate]: Filtered Count: {len(closet_summary)}")
#         style_instruction = f"本日のテーマ設定: '{weekly_style}'" if weekly_style else "TPOを考慮しておしゃれにしてください。"

#         # ★追加: user_attributes をプロンプトに挿入
#         prompt = f"""
#         あなたはプロのスタイリストです。以下の条件でコーディネートを1つ提案してください。

#         【ターゲット情報】
#         日付: {target_date_str} ({current_season})
#         天気: {weather_data['weather']}
#         最高気温: {weather_data['max']}°C
#         最低気温: {weather_data['min']}°C
#         湿度: {weather_data['humidity']}%
#         降水確率: {weather_data.get('pop', 0)}%
#         {style_instruction}

#         {user_attributes}

#         {anchor_cloth_info}

#         【手持ち服リスト(ID一覧)】
#         {json.dumps(closet_summary, ensure_ascii=False)}

#         【出力ルール】
#         1. 必ずJSONのみを返してください。
#         2. 固定アイテムがある場合は、そのIDを該当カテゴリのフィールドに必ず設定してください。
#         3. outer_clothId, tops_clothId(配列), bottoms_clothId, shoes_clothId を決定してください。
#         4. reason は100文字以内で、なぜこの組み合わせにしたか、指定テーマや天気にどう合わせたかを解説してください。

#         JSON Example:
#         {{
#             "outer_clothId": 123,
#             "tops_clothId": [456],
#             "bottoms_clothId": 789,
#             "shoes_clothId": 101,
#             "reason": "..."
#         }}
#         """
        
#         print("DEBUG [create_coordinate]: Calling OpenAI API...")
#         start_time = time.time()
#         response = client.chat.completions.create(model="gpt-5-mini", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
#         ai_result = json.loads(response.choices[0].message.content)
#         end_time = time.time()
#         print(f"DEBUG [create_coordinate]: OpenAI Responded in {end_time - start_time} seconds.")

#         print("DEBUG [create_coordinate]: Saving to DB...")
#         item = {
#             'userId': user_id,
#             'createDatetime': now_jst.strftime('%Y-%m-%dT%H:%M:%S'),
#             'targetDate': target_date_str,
#             'anchorClothId': int(anchor_cloth_id) if anchor_cloth_id else None,
#             'outer_clothId': ai_result.get('outer_clothId'),
#             'tops_clothId': ai_result.get('tops_clothId'),
#             'bottoms_clothId': ai_result.get('bottoms_clothId'),
#             'shoes_clothId': ai_result.get('shoes_clothId'),
#             'reason': ai_result.get('reason'),
#             'deleteFlag': 0
#         }
#         clean_item = {k: v for k, v in item.items() if v is not None}
#         coordinate_table.put_item(Item=clean_item)
#         print("DEBUG [create_coordinate]: Saved.")
        
#         response_data = clean_item.copy()
        
#         if response_data.get('outer_clothId'): 
#             url = cloth_map.get(int(response_data['outer_clothId']))
#             response_data['outer_image'] = sign_s3_url(url)
            
#         if response_data.get('bottoms_clothId'): 
#             url = cloth_map.get(int(response_data['bottoms_clothId']))
#             response_data['bottoms_image'] = sign_s3_url(url)
            
#         if response_data.get('shoes_clothId'): 
#             url = cloth_map.get(int(response_data['shoes_clothId']))
#             response_data['shoes_image'] = sign_s3_url(url)
            
#         if response_data.get('tops_clothId'): 
#             response_data['tops_images'] = []
#             for tid in response_data['tops_clothId']:
#                 if int(tid) in cloth_map:
#                     url = cloth_map.get(int(tid))
#                     response_data['tops_images'].append(sign_s3_url(url))
#         print("DEBUG [create_coordinate]: Finished.")

#         return {"statusCode": 200, "headers": headers, "body": json.dumps(response_data, default=str, ensure_ascii=False)}

#     except Exception as e:
#         print(f"Error: {e}")
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}


# def get_history(event, headers):
#     try:
#         params = event.get('queryStringParameters') or {}
#         user_id = params.get('userId')
#         if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
        
#         coord_resp = coordinate_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False)
#         coords = coord_resp.get('Items', [])
#         if not coords: return {"statusCode": 200, "headers": headers, "body": json.dumps([], default=str)}
        
#         cloth_resp = cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
#         all_clothes = cloth_resp.get('Items', [])
        
#         cloth_map = {int(c['clothId']): c for c in all_clothes}
        
#         seen_dates = set()
#         unique_history = []
        
#         for item in coords:
#             if item.get('deleteFlag', 0) == 1: continue
#             t_date = item.get('targetDate')
#             if t_date in seen_dates: continue
#             seen_dates.add(t_date)
            
#             history_item = item.copy()
            
#             if item.get('outer_clothId'):
#                 c = cloth_map.get(int(item['outer_clothId']))
#                 if c:
#                     signed_url = sign_s3_url(c.get('imageUrl'))
#                     history_item['outer_image'] = signed_url
                    
#                     c_copy = c.copy()
#                     c_copy['imageUrl'] = signed_url
#                     history_item['outer_cloth'] = c_copy
            
#             if item.get('tops_clothId'):
#                 history_item['tops_images'] = []
#                 history_item['tops_clothes'] = [] 
#                 for tid in item['tops_clothId']:
#                     c = cloth_map.get(int(tid))
#                     if c:
#                         signed_url = sign_s3_url(c.get('imageUrl'))
#                         history_item['tops_images'].append(signed_url)
                        
#                         c_copy = c.copy()
#                         c_copy['imageUrl'] = signed_url
#                         history_item['tops_clothes'].append(c_copy)

#             if item.get('bottoms_clothId'):
#                 c = cloth_map.get(int(item['bottoms_clothId']))
#                 if c:
#                     signed_url = sign_s3_url(c.get('imageUrl'))
#                     history_item['bottoms_image'] = signed_url
                    
#                     c_copy = c.copy()
#                     c_copy['imageUrl'] = signed_url
#                     history_item['bottoms_cloth'] = c_copy

#             if item.get('shoes_clothId'):
#                 c = cloth_map.get(int(item['shoes_clothId']))
#                 if c:
#                     signed_url = sign_s3_url(c.get('imageUrl'))
#                     history_item['shoes_image'] = signed_url
                    
#                     c_copy = c.copy()
#                     c_copy['imageUrl'] = signed_url
#                     history_item['shoes_cloth'] = c_copy
            
#             unique_history.append(history_item)
            
#         return {"statusCode": 200, "headers": headers, "body": json.dumps(unique_history, default=str, ensure_ascii=False)}
#     except Exception as e:
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# # --- 1. 受付API (POST /try-on) ---
# def start_try_on(event, headers, context):
#     try:
#         body = json.loads(event['body'])
#         user_id = body.get('userId')
#         coord_id = body.get('coordinateId') # 試着したいコーデのID
        
#         if not user_id or not coord_id:
#             return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId and coordinateId required"})}

#         # ジョブIDの発行
#         job_id = str(uuid.uuid4())
        
#         # Lambda自身を非同期(Event)で呼び出す
#         # FunctionNameはContextから取得、または環境変数で指定
#         lambda_client = boto3.client('lambda')
#         function_name = context.function_name
        
#         payload = {
#             'task': 'try_on_worker', # ワーカー処理の識別子
#             'jobId': job_id,
#             'userId': user_id,
#             'coordinateId': coord_id
#         }
        
#         # 非同期起動 (InvocationType='Event' が重要)
#         lambda_client.invoke(
#             FunctionName=function_name,
#             InvocationType='Event', 
#             Payload=json.dumps(payload)
#         )
        
#         # ここで「処理中」としてDBに保存しておくのがベストですが、
#         # 今回は簡易的にS3にステータスファイルを置くか、DynamoDBのCoordinateTableを使います。
#         # CoordinateTableに jobStatus='PROCESSING', tryOnJobId=job_id を記録
#         coordinate_table.update_item(
#             Key={'userId': user_id, 'createDatetime': coord_id}, # ※coord_idはcreateDatetimeと仮定
#             UpdateExpression="set tryOnJobId = :j, tryOnStatus = :s",
#             ExpressionAttributeValues={':j': job_id, ':s': 'PROCESSING'}
#         )

#         # 即レスポンス (待たせない)
#         return {"statusCode": 202, "headers": headers, "body": json.dumps({"message": "Accepted", "jobId": job_id})}

#     except Exception as e:
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# # --- 2. 状況確認API (GET /try-on) ---
# def check_try_on(event, headers):
#     try:
#         params = event.get('queryStringParameters') or {}
#         user_id = params.get('userId')
#         coord_id = params.get('coordinateId')
        
#         # DBから状態を取得
#         resp = coordinate_table.get_item(Key={'userId': user_id, 'createDatetime': coord_id})
#         item = resp.get('Item')
        
#         if not item:
#             return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Coordinate not found"})}
            
#         status = item.get('tryOnStatus', 'NONE')
#         image_url = item.get('tryOnImageUrl')
        
#         # 画像があれば署名付きに変換
#         if image_url:
#             image_url = sign_s3_url(image_url)

#         return {"statusCode": 200, "headers": headers, "body": json.dumps({
#             "status": status, # PROCESSING, COMPLETED, FAILED
#             "imageUrl": image_url
#         })}

#     except Exception as e:
#         return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# # --- 3. バックグラウンドワーカー (裏方) ---
# def try_on_worker(event):
#     print(f"DEBUG: Worker started for Job {event['jobId']}")
#     job_id = event['jobId']
#     user_id = event['userId']
#     coord_id = event['coordinateId']
    
#     try:
#         # A. 必要なデータをDBから取得 (ユーザー写真、服写真)
#         user_resp = user_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
#         user_data = user_resp['Items'][0]
#         user_photo_url = user_data.get('imageLink') # プロフィール写真
        
#         coord_resp = coordinate_table.get_item(Key={'userId': user_id, 'createDatetime': coord_id})
#         coord_data = coord_resp['Item']
        
#         # 服のIDから画像URLを取得 (ClothTable参照)
#         # ※ここでは簡略化のため、アウターの画像だけ取得する例
#         outer_id = coord_data.get('outer_clothId')
#         if outer_id:
#             cloth_resp = cloth_table.get_item(Key={'userId': user_id, 'clothId': int(outer_id)})
#             cloth_url = cloth_resp['Item'].get('imageUrl')
#         else:
#             # 服がない場合は失敗にする等の処理
#             raise Exception("No outer cloth found")

#         # B. Google Gemini (Nano Banana) で生成
#         # ※注意: 実際のGoogle APIでの画像編集は、モデル 'gemini-1.5-pro' 等に画像とプロンプトを渡します
#         model = genai.GenerativeModel('gemini-1.5-pro')
        
#         # プロンプト例: "この人物(user_photo)に、この服(cloth_photo)を着せた画像を生成してください"
#         # 実際には画像をダウンロードしてBase64またはBlobで渡す必要があります
        
#         # (擬似コード: 実際の実装はGoogle SDKの仕様に合わせる必要があります)
#         # prompt = "Generate a photorealistic image of this person wearing this cloth."
#         # response = model.generate_content([prompt, user_img_blob, cloth_img_blob])
        
#         # ★今回はポートフォリオ用ダミーとして、OpenAI DALL-E3 で生成する例にします
#         # (Google APIでの画像生成コードは環境構築が複雑なため、既存のOpenAIクライアントを流用して成功体験を作ります)
#         # 本番ではここをGoogle GenAIのコードに差し替えます
        
#         prompt = f"A photorealistic fashion shot of a person wearing a specific jacket. The person has typical Japanese features. The jacket is {cloth_resp['Item'].get('color')} {cloth_resp['Item'].get('category')}."
        
#         dalle_resp = client.images.generate(
#             model="dall-e-3",
#             prompt=prompt,
#             size="1024x1024",
#             quality="standard",
#             n=1,
#         )
#         generated_url = dalle_resp.data[0].url
        
#         # C. 生成画像をS3に保存
#         # DALL-EのURLは一時的なので、ダウンロードしてS3にPUTする
#         img_data = requests.get(generated_url).content
#         file_name = f"tryon_{job_id}.png"
#         s3_client.put_object(Bucket=BUCKET_NAME, Key=file_name, Body=img_data, ContentType='image/png')
#         s3_url = f"https://{BUCKET_NAME}.s3.ap-northeast-1.amazonaws.com/{file_name}"

#         # D. DB更新 (完了)
#         coordinate_table.update_item(
#             Key={'userId': user_id, 'createDatetime': coord_id},
#             UpdateExpression="set tryOnStatus = :s, tryOnImageUrl = :u",
#             ExpressionAttributeValues={':s': 'COMPLETED', ':u': s3_url}
#         )
#         print("DEBUG: Worker completed successfully")

#     except Exception as e:
#         print(f"ERROR in Worker: {e}")
#         # 失敗ステータス更新
#         coordinate_table.update_item(
#             Key={'userId': user_id, 'createDatetime': coord_id},
#             UpdateExpression="set tryOnStatus = :s",
#             ExpressionAttributeValues={':s': 'FAILED'}
#         )