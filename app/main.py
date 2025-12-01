import json
import os
import boto3
import time
import uuid
import requests
from openai import OpenAI
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key

# 初期化
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
cloth_table = dynamodb.Table(os.environ.get('TABLE_CLOTH'))
weather_table = dynamodb.Table(os.environ.get('TABLE_WEATHER'))
coordinate_table = dynamodb.Table(os.environ.get('TABLE_COORDINATE'))
user_table = dynamodb.Table(os.environ.get('TABLE_USER'))
BUCKET_NAME = os.environ.get('BUCKET_NAME')
WEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

def handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT"
    }

    if event['httpMethod'] == 'OPTIONS':
        return {"statusCode": 200, "headers": headers, "body": ""}

    path = event['path']

    # 1. ユーザー管理
    if path == '/users':
        if event['httpMethod'] == 'POST':
            return register_user(event, headers)
        if event['httpMethod'] == 'GET':
            return get_user(event, headers)

    # 2. 洋服関連
    if path == '/clothes':
        if event['httpMethod'] == 'POST':
            return register_cloth(event, headers)
        if event['httpMethod'] == 'GET':
            return get_clothes(event, headers)
        if event['httpMethod'] == 'DELETE':
            return delete_cloth(event, headers)
        if event['httpMethod'] == 'PUT': return update_cloth(event, headers)

    if path == '/analyze' and event['httpMethod'] == 'POST':
        return analyze_cloth(event, headers)

    if path == '/upload-url' and event['httpMethod'] == 'POST':
        return get_upload_url(event, headers)

    # 3. 天気関連
    if path == '/weather' and event['httpMethod'] == 'POST':
        return get_weather(event, headers)

    # 4. コーデ関連
    if path == '/coordinates':
        if event['httpMethod'] == 'POST':
            return create_coordinate(event, headers)
        if event['httpMethod'] == 'GET':
            return get_history(event, headers)

    return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Not Found"})}

# --- 以下、各機能の関数 ---
def update_cloth(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        old_cloth_id = body.get('clothId')
        
        if not user_id or not old_cloth_id:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId and clothId are required"})}

        # 1. 旧レコードを論理削除
        cloth_table.update_item(
            Key={'userId': user_id, 'clothId': int(old_cloth_id)},
            UpdateExpression="set deleteFlag = :f",
            ExpressionAttributeValues={':f': 1}
        )

        # 2. 新規レコード作成
        new_cloth_id = int(time.time() * 1000)
        
        item = {
            'userId': user_id,
            'clothId': new_cloth_id,
            'imageUrl': body.get('imageUrl'),
            'category': body.get('category'),
            'brand': body.get('brand'), # ★追加
            'size': body.get('size'),   # ★追加
            'color': body.get('color'),
            'material': body.get('material'),
            'seasons': body.get('seasons'),
            'style': body.get('style'),
            'suitableMinTemp': body.get('suitableMinTemp'),
            'suitableMaxTemp': body.get('suitableMaxTemp'),
            'description': body.get('description'),
            'createDatetime': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'deleteFlag': 0
        }
        cloth_table.put_item(Item=item)

        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Updated successfully", "data": item}, default=str)}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def delete_cloth(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        cloth_id = body.get('clothId')
        if not user_id or not cloth_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId and clothId are required"})}
        cloth_table.update_item(Key={'userId': user_id, 'clothId': int(cloth_id)}, UpdateExpression="set deleteFlag = :f", ExpressionAttributeValues={':f': 1})
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Deleted successfully"}, default=str)}
    except Exception as e: return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def get_clothes(event, headers):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        target_category = params.get('category')
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
        response = cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
        items = response.get('Items', [])
        valid_items = [item for item in items if item.get('deleteFlag', 0) == 0]
        if target_category: valid_items = [item for item in valid_items if item.get('category') == target_category]
        return {"statusCode": 200, "headers": headers, "body": json.dumps(valid_items, default=str, ensure_ascii=False)}
    except Exception as e: return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def get_upload_url(event, headers):
    try:
        body = json.loads(event['body'])
        file_type = body.get('fileType', 'jpg')
        content_type = f'image/{file_type}'
        if file_type == 'jpg': content_type = 'image/jpeg'
        file_name = f"{uuid.uuid4()}.{file_type}"
        presigned_url = s3_client.generate_presigned_url('put_object', Params={'Bucket': BUCKET_NAME, 'Key': file_name, 'ContentType': content_type}, ExpiresIn=300)
        image_url = f"https://{BUCKET_NAME}.s3.ap-northeast-1.amazonaws.com/{file_name}"
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"uploadUrl": presigned_url, "imageUrl": image_url})}
    except Exception as e: return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def analyze_cloth(event, headers):
    try:
        body = json.loads(event['body'])
        image_url = body.get('imageUrl')
        user_id = body.get('userId') # ★追加: ユーザーIDを受け取る

        if not image_url:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "imageUrl is required"})}
        
        # ★追加: ユーザー情報を取得してプロンプトに含める
        user_info_text = ""
        if user_id:
            try:
                # 最新のユーザー情報を取得 (deleteFlag=0のチェックは簡易的に省略し最新を取得)
                resp = user_table.query(
                    KeyConditionExpression=Key('userId').eq(user_id),
                    ScanIndexForward=False,
                    Limit=1
                )
                items = resp.get('Items', [])
                if items:
                    user = items[0]
                    gender = user.get('gender', '不明')
                    height = user.get('height', '不明')
                    user_info_text = f"【着用者情報】性別: {gender}, 身長: {height}cm (この着用者情報を考慮して、最適なサイズを推測してください)"
            except Exception as e:
                print(f"User fetch error: {e}")
                # エラーでも解析自体は止めずに続行

        prompt = f"""
        この服の画像を解析し、以下のJSONフォーマットで情報を抽出してください。
        {user_info_text}

        {{
          "category": "アウター" | "トップス" | "ボトムス" | "シューズ" | "ワンピース" | "小物",
          "brand": "ロゴやタグから推測されるブランド名(判別できない場合は空文字)",
          "size": "推測されるサイズ(S/M/L/フリーなど、わからなければフリー)",
          "color": "主要な1色(例: ブラック, ネイビー, ホワイト)",
          "material": "見た目から推測される主要な素材1つ(例: 綿, ナイロン, レザー)",
          "seasons": ["春", "夏", "秋", "冬"] の中から該当するものを配列で,
          "style": "カジュアル" | "きれいめ" | "スポーティ" | "フォーマル",
          "suitableMinTemp": 着用可能な最低気温(整数),
          "suitableMaxTemp": 着用可能な最高気温(整数),
          "description": "服の特徴を短く説明した文章"
        }}
        JSONのみを返してください。
        """
        
        response = client.chat.completions.create(
            model="gpt-5-nano", 
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt},{"type": "image_url", "image_url": {"url": image_url}},]}],
            response_format={"type": "json_object"},
        )
        ai_result = json.loads(response.choices[0].message.content)
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Analyzed successfully", "data": ai_result}, default=str)}

    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}
    
def register_cloth(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        image_url = body.get('imageUrl')
        category = body.get('category')
        if not user_id or not image_url or not category: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "Required fields missing"})}
        cloth_id = int(time.time() * 1000)
        item = {
            'userId': user_id, 'clothId': cloth_id, 'imageUrl': image_url, 'category': category,
            'brand': body.get('brand'), # ★追加
            'size': body.get('size'),   # ★追加
            'color': body.get('color'), 'material': body.get('material'), 'seasons': body.get('seasons'),
            'style': body.get('style'), 'suitableMinTemp': body.get('suitableMinTemp'), 'suitableMaxTemp': body.get('suitableMaxTemp'),
            'description': body.get('description'), 'createDatetime': time.strftime('%Y-%m-%dT%H:%M:%S'), 'deleteFlag': 0
        }
        cloth_table.put_item(Item=item)
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Saved successfully!", "data": item}, default=str)}
    except Exception as e: return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}





# ★共通: Google Geo APIで住所から緯度経度を取得
def get_lat_long(address):
    if not GOOGLE_API_KEY: return None, None
    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_API_KEY}&language=ja"
        res = requests.get(url)
        data = res.json()
        if data['status'] == 'OK':
            loc = data['results'][0]['geometry']['location']
            lat = Decimal(str(loc['lat'])).quantize(Decimal("0.01"))
            lon = Decimal(str(loc['lng'])).quantize(Decimal("0.01"))
            return lat, lon
    except:
        pass
    return None, None

# ★修正: ユーザー登録・更新 (論理削除ロジック)
def register_user(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        address = body.get('address')
        
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}

        # 1. 既存の有効なレコード(deleteFlag=0)を全て論理削除(deleteFlag=1)にする
        existing_resp = user_table.query(
            KeyConditionExpression=Key('userId').eq(user_id)
        )
        existing_items = existing_resp.get('Items', [])
        
        for item in existing_items:
            if item.get('deleteFlag', 0) == 0:
                user_table.update_item(
                    Key={
                        'userId': user_id, 
                        'createDatetime': item['createDatetime']
                    },
                    UpdateExpression="set deleteFlag = :f",
                    ExpressionAttributeValues={':f': 1}
                )

        # 2. 新規レコード作成
        lat, lon = None, None
        if address:
            lat, lon = get_lat_long(address)

        current_time = datetime.now(timezone(timedelta(hours=+9), 'JST')).strftime('%Y-%m-%dT%H:%M:%S')
        
        item = {
            'userId': user_id,
            'createDatetime': current_time, # Sort Key
            'gender': body.get('gender'),
            'birthDay': body.get('birthDay'),
            'height': body.get('height'),
            'address': address,
            'latitude': lat,
            'longitude': lon,
            'weeklySchedule': body.get('weeklySchedule') or {},
            'imageLink': body.get('imageLink'),
            'updateDatetime': current_time,
            'deleteFlag': 0
        }
        
        user_table.put_item(Item=item)
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "User saved", "data": item}, default=str, ensure_ascii=False)}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# ★修正: ユーザー取得 (最新のdeleteFlag=0のみ取得)
def get_user(event, headers):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}

        resp = user_table.query(
            KeyConditionExpression=Key('userId').eq(user_id),
            ScanIndexForward=False 
        )
        items = resp.get('Items', [])

        active_user = None
        for item in items:
            if item.get('deleteFlag', 0) == 0:
                active_user = item
                break

        if not active_user:
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "User not found"})}

        return {"statusCode": 200, "headers": headers, "body": json.dumps(active_user, default=str, ensure_ascii=False)}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# --- 以下、省略されていた関数を復元 ---

def get_weather(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        city_name = body.get('city', '福岡市博多区')
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
        
        lat_dec, lon_dec = get_lat_long(city_name)
        if not lat_dec: return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Location not found"})}

        JST = timezone(timedelta(hours=+9), 'JST')
        now_jst = datetime.now(JST)
        if now_jst.hour >= 19: target_date = now_jst + timedelta(days=1)
        else: target_date = now_jst
        target_date_str = target_date.strftime('%Y-%m-%d')

        res = requests.get(f"https://api.openweathermap.org/data/2.5/forecast?lat={lat_dec}&lon={lon_dec}&appid={WEATHER_API_KEY}&units=metric&lang=ja")
        data = res.json()
        if res.status_code != 200: return {"statusCode": res.status_code, "headers": headers, "body": json.dumps(data)}

        temps, pops = [], []
        weather_desc, icon_code = "", ""
        humidity, wind_speed, wind_deg = 0, 0, 0
        for item in data['list']:
            if target_date_str in item['dt_txt']:
                temps.append(item['main']['temp_max'])
                temps.append(item['main']['temp_min'])
                pops.append(item.get('pop', 0))
                if "03:00:00" in item['dt_txt']:
                    weather_desc = item['weather'][0]['description']
                    icon_code = item['weather'][0]['icon']
                    humidity = item['main']['humidity']
                    wind_speed = item['wind']['speed']
                    wind_deg = item['wind']['deg']
        if not weather_desc and temps:
            first = [x for x in data['list'] if target_date_str in x['dt_txt']][0]
            weather_desc = first['weather'][0]['description']
            icon_code = first['weather'][0]['icon']
            humidity = first['main']['humidity']
            wind_speed = first['wind']['speed']
            wind_deg = first['wind']['deg']
        if not temps: return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": f"Forecast for {target_date_str} not found"})}

        item = {
            'userId': user_id, 'targetDate': target_date_str, 'latitude': lat_dec, 'longitude': lon_dec,
            'weather': weather_desc, 'iconUrl': f"https://openweathermap.org/img/wn/{icon_code}@2x.png" if icon_code else None,
            'max': Decimal(str(max(temps))).quantize(Decimal("0.1")), 'min': Decimal(str(min(temps))).quantize(Decimal("0.1")),
            'humidity': Decimal(str(humidity)), 'pop': Decimal(str(int(max(pops) * 100))),
            'windSpeed': Decimal(str(wind_speed)).quantize(Decimal("0.1")), 'windDirection': get_wind_direction_jp(wind_deg),
            'city': city_name, 'createDatetime': now_jst.strftime('%Y-%m-%dT%H:%M:%S'), 'deleteFlag': 0
        }
        weather_table.put_item(Item=item)
        return {"statusCode": 200, "headers": headers, "body": json.dumps(item, default=str, ensure_ascii=False)}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def get_wind_direction_jp(degrees):
    directions = ["北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東", "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"]
    index = int((degrees + 11.25) / 22.5) % 16
    return directions[index]

def get_current_season(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    month = dt.month
    if 3 <= month <= 5: return '春'
    if 6 <= month <= 9: return '夏'
    if 10 <= month <= 11: return '秋'
    return '冬'

# ★修正: コーデ作成 (重複targetDateの論理削除)
def create_coordinate(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        anchor_cloth_id = body.get('anchorClothId') # ★追加: 起点となる服ID
        
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
        
        JST = timezone(timedelta(hours=+9), 'JST')
        now_jst = datetime.now(JST)
        
        # 19時以降は明日のコーデ
        if now_jst.hour >= 19: 
            target_date = now_jst + timedelta(days=1)
        else: 
            target_date = now_jst
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        # 曜日 (0:Mon, ... 6:Sun)
        weekday_index = target_date.weekday()
        weekdays_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        current_weekday_str = weekdays_map[weekday_index]

        # --- ユーザー情報 & 曜日設定取得 ---
        user_resp = user_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
        weekly_style = ""
        if user_resp['Items']:
            user_data = user_resp['Items'][0]
            # weeklySchedule: {"Mon": "Office", "Sat": "Casual"}
            schedule = user_data.get('weeklySchedule') or {}
            weekly_style = schedule.get(current_weekday_str, "")

        # --- 天気取得 ---
        weather_resp = weather_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
        if not weather_resp['Items'] or weather_resp['Items'][0].get('targetDate') != target_date_str:
             return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Weather data for target date not found."})}
        weather_data = weather_resp['Items'][0]

        # --- 服データ全件取得 ---
        cloth_resp = cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
        all_clothes = cloth_resp['Items']
        if not all_clothes: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "No clothes registered."})}
        
        cloth_map = {int(c['clothId']): c['imageUrl'] for c in all_clothes}
        
        # --- アンカー（固定アイテム）の特定 ---
        anchor_cloth_info = ""
        anchor_category = ""
        if anchor_cloth_id:
            anchor_item = next((c for c in all_clothes if int(c['clothId']) == int(anchor_cloth_id)), None)
            if anchor_item:
                anchor_category = anchor_item.get('category')
                anchor_cloth_info = f"""
                【必須固定アイテム】
                ユーザーはこの服を着たいと指定しています。必ずコーデに含めてください。
                ID: {anchor_cloth_id}
                カテゴリ: {anchor_category}
                色: {anchor_item.get('color')}
                特徴: {anchor_item.get('description')}
                """

        # --- フィルタリング (季節・気温) ---
        current_season = get_current_season(target_date_str)
        day_max_temp = float(weather_data['max'])
        day_min_temp = float(weather_data['min'])
        TEMP_BUFFER = 5.0 
        
        filtered_clothes = []
        for c in all_clothes:
            # アンカーアイテム自体はフィルタリングしない（強制採用のため）
            if anchor_cloth_id and int(c['clothId']) == int(anchor_cloth_id):
                filtered_clothes.append(c)
                continue

            if c.get('seasons') and current_season not in c['seasons']: continue 
            c_min = float(c.get('suitableMinTemp', -50))
            c_max = float(c.get('suitableMaxTemp', 50))
            if c_min > (day_max_temp + TEMP_BUFFER): continue
            if c_max < (day_min_temp - TEMP_BUFFER): continue
            filtered_clothes.append(c)
        
        target_clothes_list = filtered_clothes if len(filtered_clothes) > 0 else all_clothes
        
        # アンカーのみしか残らない場合のガード
        if len(target_clothes_list) == 1 and anchor_cloth_id:
            target_clothes_list = all_clothes

        closet_summary = []
        for c in target_clothes_list:
            closet_summary.append({
                "id": int(c['clothId']),
                "category": c['category'],
                "color": c.get('color'),
                "style": c.get('style'),
                "desc": c.get('description', '')
            })

        # --- プロンプト構築 ---
        style_instruction = f"本日のテーマ設定: '{weekly_style}'" if weekly_style else "TPOを考慮しておしゃれにしてください。"

        prompt = f"""
        あなたはプロのスタイリストです。以下の条件でコーディネートを1つ提案してください。

        【ターゲット情報】
        日付: {target_date_str} ({current_weekday_str}曜日) ({current_season})
        天気: {weather_data['weather']}
        最高気温: {weather_data['max']}°C
        最低気温: {weather_data['min']}°C
        湿度: {weather_data['humidity']}%
        降水確率: {weather_data.get('pop', 0)}%
        風: {weather_data.get('windDirection', '')} {weather_data.get('windSpeed', 0)}m/s
        {style_instruction}

        {anchor_cloth_info}

        【手持ち服リスト(ID一覧)】
        {json.dumps(closet_summary, ensure_ascii=False)}

        【出力ルール】
        1. 必ずJSONのみを返してください。
        2. 固定アイテムがある場合は、そのIDを該当カテゴリのフィールドに必ず設定してください。
        3. outer_clothId, tops_clothId(配列), bottoms_clothId, shoes_clothId を決定してください。
        4. reason は100文字以内で、なぜこの組み合わせにしたか、指定テーマや天気にどう合わせたかを解説してください。

        JSON Example:
        {{
            "outer_clothId": ID数値 (不要ならnull),
            "tops_clothId": [ID数値] (配列),
            "bottoms_clothId": ID数値 (ワンピースの場合はnull),
            "shoes_clothId": ID数値 (不要ならnull),
            "reason": "選定理由(100文字以内)"
        }}
        """
        
        response = client.chat.completions.create(model="gpt-5-nano", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
        ai_result = json.loads(response.choices[0].message.content)

        # 3. 保存 (アンカー情報も記録)
        item = {
            'userId': user_id,
            'createDatetime': now_jst.strftime('%Y-%m-%dT%H:%M:%S'),
            'targetDate': target_date_str,
            'anchorClothId': int(anchor_cloth_id) if anchor_cloth_id else None, # ★追加
            'outer_clothId': ai_result.get('outer_clothId'),
            'tops_clothId': ai_result.get('tops_clothId'),
            'bottoms_clothId': ai_result.get('bottoms_clothId'),
            'shoes_clothId': ai_result.get('shoes_clothId'),
            'reason': ai_result.get('reason'),
            'deleteFlag': 0
        }
        clean_item = {k: v for k, v in item.items() if v is not None}
        coordinate_table.put_item(Item=clean_item)
        
        # 画像マッピング (フロント表示用)
        response_data = clean_item.copy()
        if response_data.get('outer_clothId'): response_data['outer_image'] = cloth_map.get(int(response_data['outer_clothId']))
        if response_data.get('bottoms_clothId'): response_data['bottoms_image'] = cloth_map.get(int(response_data['bottoms_clothId']))
        if response_data.get('shoes_clothId'): response_data['shoes_image'] = cloth_map.get(int(response_data['shoes_clothId']))
        if response_data.get('tops_clothId'): response_data['tops_images'] = [cloth_map.get(int(tid)) for tid in response_data['tops_clothId'] if int(tid) in cloth_map]

        return {"statusCode": 200, "headers": headers, "body": json.dumps(response_data, default=str, ensure_ascii=False)}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}


def get_history(event, headers):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
        
        # 1. 履歴取得
        coord_resp = coordinate_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False)
        coords = coord_resp.get('Items', [])
        if not coords: return {"statusCode": 200, "headers": headers, "body": json.dumps([], default=str)}
        
        # 2. 服全件取得
        cloth_resp = cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
        all_clothes = cloth_resp.get('Items', [])
        
        # IDをキーにして服データ丸ごと引ける辞書を作成
        cloth_map = {int(c['clothId']): c for c in all_clothes}
        
        seen_dates = set()
        unique_history = []
        
        for item in coords:
            if item.get('deleteFlag', 0) == 1: continue
            t_date = item.get('targetDate')
            if t_date in seen_dates: continue
            seen_dates.add(t_date)
            
            history_item = item.copy()
            
            # --- 各パーツのデータを付与 (画像URLだけでなく、詳細データと削除フラグを含むオブジェクト) ---
            
            # アウター
            if item.get('outer_clothId'):
                c = cloth_map.get(int(item['outer_clothId']))
                if c:
                    history_item['outer_image'] = c.get('imageUrl')
                    history_item['outer_cloth'] = c # 詳細データ
            
            # トップス (配列)
            if item.get('tops_clothId'):
                history_item['tops_images'] = []
                history_item['tops_clothes'] = [] # 詳細データリスト
                for tid in item['tops_clothId']:
                    c = cloth_map.get(int(tid))
                    if c:
                        history_item['tops_images'].append(c.get('imageUrl'))
                        history_item['tops_clothes'].append(c)

            # ボトムス
            if item.get('bottoms_clothId'):
                c = cloth_map.get(int(item['bottoms_clothId']))
                if c:
                    history_item['bottoms_image'] = c.get('imageUrl')
                    history_item['bottoms_cloth'] = c

            # シューズ
            if item.get('shoes_clothId'):
                c = cloth_map.get(int(item['shoes_clothId']))
                if c:
                    history_item['shoes_image'] = c.get('imageUrl')
                    history_item['shoes_cloth'] = c
            
            unique_history.append(history_item)
            
        return {"statusCode": 200, "headers": headers, "body": json.dumps(unique_history, default=str, ensure_ascii=False)}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}