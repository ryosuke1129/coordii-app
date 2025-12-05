import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key
import resources
from utils.helpers import sign_s3_url, get_current_season

# --- 1. 受付API (POST /coordinates) ---
def start_create_coordinate(event, headers, context):
    print("DEBUG: start_create_coordinate")
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        anchor_cloth_id = body.get('anchorClothId')
        
        if not user_id:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId required"})}

        # IDとなる日時を決定
        JST = timezone(timedelta(hours=+9), 'JST')
        now_jst = datetime.now(JST)
        target_date = now_jst + timedelta(days=1) if now_jst.hour >= 19 else now_jst
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        # レコードID (ソートキー)
        create_datetime = now_jst.strftime('%Y-%m-%dT%H:%M:%S')
        job_id = str(uuid.uuid4())

        # 1. "PROCESSING" 状態でDBに先行登録
        item = {
            'userId': user_id,
            'createDatetime': create_datetime,
            'targetDate': target_date_str,
            'anchorClothId': int(anchor_cloth_id) if anchor_cloth_id else None,
            'processStatus': 'PROCESSING', # ★追加: 処理状態
            'jobId': job_id,
            'deleteFlag': 0
        }
        resources.coordinate_table.put_item(Item=item)

        # 2. 非同期ワーカー起動
        payload = {
            'task': 'coord_worker', # 識別子
            'userId': user_id,
            'createDatetime': create_datetime,
            'targetDate': target_date_str,
            'anchorClothId': anchor_cloth_id,
            'jobId': job_id
        }
        
        resources.lambda_client.invoke(
            FunctionName=context.function_name,
            InvocationType='Event', # Fire and forget
            Payload=json.dumps(payload)
        )

        # 3. 即レスポンス (IDを返す)
        return {"statusCode": 202, "headers": headers, "body": json.dumps({
            "message": "Accepted", 
            "coordinateId": create_datetime,
            "jobId": job_id
        })}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# --- 2. 状況確認API (GET /coordinates/status) ---
def check_status(event, headers):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        coord_id = params.get('coordinateId')
        
        if not user_id or not coord_id:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "Missing params"})}

        resp = resources.coordinate_table.get_item(Key={'userId': user_id, 'createDatetime': coord_id})
        item = resp.get('Item')
        
        if not item:
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Not found"})}
            
        status = item.get('processStatus', 'COMPLETED') # 古いデータはCOMPLETED扱い
        
        # 完了していれば画像URL等を付与して返す
        result_data = {}
        if status == 'COMPLETED':
            result_data = item.copy()
            # 服全件取得して画像マッピング
            cloth_resp = resources.cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
            cloth_map = {int(c['clothId']): c['imageUrl'] for c in cloth_resp.get('Items', [])}
            _attach_images(result_data, cloth_map)

        # エラー理由があれば返す
        fail_reason = item.get('failReason', '')

        return {"statusCode": 200, "headers": headers, "body": json.dumps({
            "status": status,
            "data": result_data,
            "failReason": fail_reason
        }, default=str, ensure_ascii=False)}

    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

# --- 3. バックグラウンドワーカー (裏方) ---
def worker(event):
    print(f"Coord Worker started: {event.get('jobId')}")
    user_id = event['userId']
    create_datetime = event['createDatetime']
    target_date_str = event['targetDate']
    anchor_cloth_id = event.get('anchorClothId')
    
    try:
        # === 既存のAI生成ロジック ===
        
        # 1. 情報収集
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        dt = datetime.strptime(target_date_str, '%Y-%m-%d')
        current_weekday = weekdays[dt.weekday()]
        season = get_current_season(target_date_str)

        user_resp = resources.user_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
        weekly_style, user_attr = "", ""
        if user_resp.get('Items'):
            u = user_resp['Items'][0]
            weekly_style = (u.get('weeklySchedule') or {}).get(current_weekday, "")
            user_attr = f"性別:{u.get('gender')}, 身長:{u.get('height')}cm"

        weather_resp = resources.weather_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
        if not weather_resp.get('Items'):
            weather = {'weather': '不明', 'max': 20, 'min': 15, 'humidity': 50}
        else:
            weather = weather_resp['Items'][0]

        cloth_resp = resources.cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
        all_clothes = cloth_resp.get('Items', [])
        if not all_clothes:
            raise Exception("No clothes registered")

        # 2. フィルタリング
        t_max = float(weather.get('max', 20))
        t_min = float(weather.get('min', 15))
        
        filtered = []
        for c in all_clothes:
            cid = int(c['clothId'])
            if anchor_cloth_id and cid == int(anchor_cloth_id):
                filtered.append(c)
                continue
            if c.get('seasons') and season not in c['seasons']: continue
            if float(c.get('suitableMinTemp', -50)) > t_max + 5: continue
            if float(c.get('suitableMaxTemp', 50)) < t_min - 5: continue
            filtered.append(c)
            
        target_list = filtered if filtered else all_clothes
        if len(target_list) == 1 and anchor_cloth_id: target_list = all_clothes

        summary = [{"id": int(c['clothId']), "cat": c['category'], "col": c.get('color'), "desc": c.get('description', '')} for c in target_list]
        anchor_info = f"【必須固定アイテム】ID:{anchor_cloth_id} を必ず使用してください。" if anchor_cloth_id else ""

        # プロンプト
        prompt = f"""
        あなたはプロのスタイリストです。以下の条件でコーディネートを1つ提案してください。
        【ターゲット情報】
        日付: {target_date_str} ({current_weekday}) {season}
        天気: {weather['weather']}, {weather['max']}°C / {weather['min']}°C
        湿度: {weather['humidity']}%
        降水確率: {weather.get('pop', 0)}%
        テーマ: {weekly_style if weekly_style else "TPOに合わせて"}
        ユーザー: {user_attr}
        {anchor_info}
        【手持ち服リスト(ID一覧)】
        {json.dumps(summary, ensure_ascii=False)}
        【出力ルール】
        1. 必ずJSONのみを返してください。
        2. 固定アイテムがある場合は、そのIDを該当カテゴリのフィールドに必ず設定してください。
        3. outer_clothId, tops_clothId(配列), bottoms_clothId, shoes_clothId を決定してください。
        4. reason は100文字以内で、なぜこの組み合わせにしたか、指定テーマや天気にどう合わせたかを解説してください。
        JSON Example:
        {{
            "outer_clothId": 123,
            "tops_clothId": [456],
            "bottoms_clothId": 789,
            "shoes_clothId": 101,
            "reason": "..."
        }}
        """

        # 3. AI生成
        print("DEBUG: Calling OpenAI...")
        res = resources.client.chat.completions.create(
            model="gpt-5-mini", 
            messages=[{"role": "user", "content": prompt}], 
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(res.choices[0].message.content)

        # 4. DB更新 (完了)
        outer = ai_data.get('outer_clothId')
        tops = ai_data.get('tops_clothId')
        bottoms = ai_data.get('bottoms_clothId')
        shoes = ai_data.get('shoes_clothId')

        resources.coordinate_table.update_item(
            Key={'userId': user_id, 'createDatetime': create_datetime},
            UpdateExpression="set processStatus=:s, outer_clothId=:o, tops_clothId=:t, bottoms_clothId=:b, shoes_clothId=:sh, reason=:r",
            ExpressionAttributeValues={
                ':s': 'COMPLETED',
                ':o': int(outer) if outer else None,
                ':t': [int(t) for t in tops] if tops else None,
                ':b': int(bottoms) if bottoms else None,
                ':sh': int(shoes) if shoes else None,
                ':r': ai_data.get('reason')
            }
        )
        print("DEBUG: Coord Worker completed")

    except Exception as e:
        print(f"Worker Error: {e}")
        # 失敗ステータス
        resources.coordinate_table.update_item(
            Key={'userId': user_id, 'createDatetime': create_datetime},
            UpdateExpression="set processStatus = :s, failReason = :r",
            ExpressionAttributeValues={':s': 'FAILED', ':r': str(e)}
        )

# --- 4. 履歴取得 (既存機能) ---
def get_history(event, headers):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId required"})}

        coord_resp = resources.coordinate_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False)
        cloth_resp = resources.cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
        cloth_map = {int(c['clothId']): c for c in cloth_resp.get('Items', [])}
        
        history = []
        seen = set()
        
        for item in coord_resp.get('Items', []):
            if item.get('deleteFlag', 0) == 1: continue
            
            # ★未完了のデータは履歴に出さない
            if item.get('processStatus') and item.get('processStatus') != 'COMPLETED':
                continue

            if item['targetDate'] in seen: continue
            seen.add(item['targetDate'])
            
            h_item = item.copy()
            _attach_full_cloth_data(h_item, cloth_map)
            
            if item.get('tryOnImageUrl'):
                h_item['tryOnImage'] = sign_s3_url(item['tryOnImageUrl'])
                
            history.append(h_item)
            
        return {"statusCode": 200, "headers": headers, "body": json.dumps(history, default=str, ensure_ascii=False)}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

# --- Helpers ---
def _attach_images(data, url_map):
    if data.get('outer_clothId'): data['outer_image'] = sign_s3_url(url_map.get(int(data['outer_clothId'])))
    if data.get('bottoms_clothId'): data['bottoms_image'] = sign_s3_url(url_map.get(int(data['bottoms_clothId'])))
    if data.get('shoes_clothId'): data['shoes_image'] = sign_s3_url(url_map.get(int(data['shoes_clothId'])))
    if data.get('tops_clothId'):
        data['tops_images'] = [sign_s3_url(url_map.get(int(tid))) for tid in data['tops_clothId'] if int(tid) in url_map]

def _attach_full_cloth_data(data, full_map):
    def _get_signed(c):
        cp = c.copy()
        cp['imageUrl'] = sign_s3_url(c.get('imageUrl'))
        return cp

    if data.get('outer_clothId'):
        c = full_map.get(int(data['outer_clothId']))
        if c: 
            data['outer_cloth'] = _get_signed(c)
            data['outer_image'] = data['outer_cloth']['imageUrl']
            
    if data.get('bottoms_clothId'):
        c = full_map.get(int(data['bottoms_clothId']))
        if c:
            data['bottoms_cloth'] = _get_signed(c)
            data['bottoms_image'] = data['bottoms_cloth']['imageUrl']
            
    if data.get('shoes_clothId'):
        c = full_map.get(int(data['shoes_clothId']))
        if c:
            data['shoes_cloth'] = _get_signed(c)
            data['shoes_image'] = data['shoes_cloth']['imageUrl']

    if data.get('tops_clothId'):
        data['tops_clothes'] = []
        data['tops_images'] = []
        for tid in data['tops_clothId']:
            c = full_map.get(int(tid))
            if c:
                signed_c = _get_signed(c)
                data['tops_clothes'].append(signed_c)
                data['tops_images'].append(signed_c['imageUrl'])