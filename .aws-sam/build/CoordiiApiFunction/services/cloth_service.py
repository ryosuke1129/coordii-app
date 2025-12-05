import json
import time
import uuid
from boto3.dynamodb.conditions import Key
import resources
from utils.helpers import sign_s3_url

def get_clothes(event, headers):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        target_category = params.get('category')
        
        if not user_id:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
            
        response = resources.cloth_table.query(KeyConditionExpression=Key('userId').eq(user_id))
        
        valid_items = []
        for item in response.get('Items', []):
            if item.get('deleteFlag', 0) == 0:
                if target_category and item.get('category') != target_category:
                    continue
                if 'imageUrl' in item:
                    item['imageUrl'] = sign_s3_url(item['imageUrl'])
                valid_items.append(item)
                
        return {"statusCode": 200, "headers": headers, "body": json.dumps(valid_items, default=str, ensure_ascii=False)}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def register_cloth(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        # ... バリデーション ...
        if not user_id or not body.get('imageUrl') or not body.get('category'):
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "Required fields missing"})}
            
        cloth_id = int(time.time() * 1000)
        item = {
            'userId': user_id, 'clothId': cloth_id, 
            'imageUrl': body.get('imageUrl'), 'category': body.get('category'),
            'brand': body.get('brand'), 'size': body.get('size'), 
            'color': body.get('color'), 'material': body.get('material'), 
            'seasons': body.get('seasons'), 'style': body.get('style'),
            'suitableMinTemp': body.get('suitableMinTemp'), 
            'suitableMaxTemp': body.get('suitableMaxTemp'),
            'description': body.get('description'), 
            'createDatetime': time.strftime('%Y-%m-%dT%H:%M:%S'), 
            'deleteFlag': 0
        }
        resources.cloth_table.put_item(Item=item)
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Saved", "data": item}, default=str)}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def update_cloth(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        old_cloth_id = body.get('clothId')
        
        if not user_id or not old_cloth_id:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId/clothId required"})}

        # 論理削除 -> 新規作成 (履歴保持のため)
        resources.cloth_table.update_item(
            Key={'userId': user_id, 'clothId': int(old_cloth_id)},
            UpdateExpression="set deleteFlag = :f", ExpressionAttributeValues={':f': 1}
        )
        
        new_cloth_id = int(time.time() * 1000)
        item = body.copy()
        item['clothId'] = new_cloth_id
        item['createDatetime'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        item['deleteFlag'] = 0
        resources.cloth_table.put_item(Item=item)
        
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Updated", "data": item}, default=str)}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def delete_cloth(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        cloth_id = body.get('clothId')
        
        if not user_id or not cloth_id:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId/clothId required"})}
            
        resources.cloth_table.update_item(
            Key={'userId': user_id, 'clothId': int(cloth_id)},
            UpdateExpression="set deleteFlag = :f", ExpressionAttributeValues={':f': 1}
        )
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Deleted"}, default=str)}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def get_upload_url(event, headers):
    try:
        body = json.loads(event['body'])
        file_type = body.get('fileType', 'jpg')
        content_type = 'image/jpeg' if file_type == 'jpg' else f'image/{file_type}'
        file_name = f"{uuid.uuid4()}.{file_type}"
        
        # PUT用 (アップロード)
        upload_url = resources.s3_client.generate_presigned_url(
            'put_object', 
            Params={'Bucket': resources.BUCKET_NAME, 'Key': file_name, 'ContentType': content_type}, 
            ExpiresIn=300
        )
        # GET用 (プレビュー)
        download_url = resources.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': resources.BUCKET_NAME, 'Key': file_name},
            ExpiresIn=300
        )
        
        image_url = f"https://{resources.BUCKET_NAME}.s3.ap-northeast-1.amazonaws.com/{file_name}"
        
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"uploadUrl": upload_url, "imageUrl": image_url, "downloadUrl": download_url})}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def analyze_cloth(event, headers):
    try:
        body = json.loads(event['body'])
        raw_image_url = body.get('imageUrl')
        user_id = body.get('userId')
        
        if not raw_image_url:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "imageUrl is required"})}

        # AI用の署名付きURL生成
        ai_access_url = sign_s3_url(raw_image_url)

        # ユーザー属性取得
        user_info_text = ""
        if user_id:
            try:
                resp = resources.user_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
                if resp['Items']:
                    u = resp['Items'][0]
                    user_info_text = f"【着用者属性】性別: {u.get('gender')}, 身長: {u.get('height')}cm"
            except: pass

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
        
        response = resources.client.chat.completions.create(
            model="gpt-5-nano",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": ai_access_url}}]}],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Analyzed", "data": result}, default=str)}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}