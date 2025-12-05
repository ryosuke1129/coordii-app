import json
import uuid
import os
import requests
# import boto3
import base64
# from PIL import Image
# from io import BytesIO
from boto3.dynamodb.conditions import Key
import resources
from utils.helpers import sign_s3_url

# Google API設定
GOOGLE_GENAI_KEY = os.environ.get('GOOGLE_GENAI_KEY')

def start_try_on(event, headers, context):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        coord_id = body.get('coordinateId')
        
        if not user_id or not coord_id:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "Missing params"})}

        job_id = str(uuid.uuid4())
        
        payload = {
            'task': 'try_on_worker',
            'jobId': job_id,
            'userId': user_id,
            'coordinateId': coord_id
        }
        
        resources.lambda_client.invoke(
            FunctionName=context.function_name,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        resources.coordinate_table.update_item(
            Key={'userId': user_id, 'createDatetime': coord_id},
            UpdateExpression="set tryOnJobId = :j, tryOnStatus = :s",
            ExpressionAttributeValues={':j': job_id, ':s': 'PROCESSING'}
        )

        return {"statusCode": 202, "headers": headers, "body": json.dumps({"message": "Accepted", "jobId": job_id})}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

def check_try_on(event, headers):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        coord_id = params.get('coordinateId')
        
        resp = resources.coordinate_table.get_item(Key={'userId': user_id, 'createDatetime': coord_id})
        item = resp.get('Item')
        if not item: return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Not found"})}
        
        status = item.get('tryOnStatus', 'NONE')
        url = item.get('tryOnImageUrl')
        if url: url = sign_s3_url(url)
        fail_reason = item.get('tryOnFailReason', '')
        
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": status, "imageUrl": url, "failReason": fail_reason})}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

def worker(event):
    print(f"Worker started: {event.get('jobId')}")
    job_id = event['jobId']
    user_id = event['userId']
    coord_id = event['coordinateId']
    
    try:
        # --- 1. データ収集 ---
        user_resp = resources.user_table.query(KeyConditionExpression=Key('userId').eq(user_id), ScanIndexForward=False, Limit=1)
        if not user_resp['Items']: raise Exception("User not found")
        user_data = user_resp['Items'][0]
        
        coord_resp = resources.coordinate_table.get_item(Key={'userId': user_id, 'createDatetime': coord_id})
        if 'Item' not in coord_resp: raise Exception("Coordinate not found")
        coord_data = coord_resp['Item']
        
        # 画像データを格納するリスト (API送信順序用: [ユーザー写真, 服1, 服2...])
        image_parts = []
        
        # 1-1. ユーザー写真取得
        user_img_url = user_data.get('imageLink')
        if user_img_url:
            img_bytes, mime = _download_image_as_base64(user_img_url)
            image_parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": img_bytes
                }
            })
        else:
            raise Exception("User profile image required")

        # 1-2. 服写真取得
        target_cloth_ids = []
        if coord_data.get('outer_clothId'): target_cloth_ids.append(int(coord_data['outer_clothId']))
        if coord_data.get('tops_clothId'): target_cloth_ids.extend([int(tid) for tid in coord_data['tops_clothId']])
        if coord_data.get('bottoms_clothId'): target_cloth_ids.append(int(coord_data['bottoms_clothId']))
        if coord_data.get('shoes_clothId'): target_cloth_ids.append(int(coord_data['shoes_clothId']))

        cloth_descriptions = []
        
        for cid in target_cloth_ids:
            c_resp = resources.cloth_table.get_item(Key={'userId': user_id, 'clothId': cid})
            if 'Item' in c_resp:
                c = c_resp['Item']
                if c.get('imageUrl'):
                    img_bytes, mime = _download_image_as_base64(c['imageUrl'])
                    image_parts.append({
                        "inline_data": {
                            "mime_type": mime,
                            "data": img_bytes
                        }
                    })
                    # プロンプト補強用にテキスト情報も記録
                    cloth_descriptions.append(f"{c.get('color')} {c.get('category')}")

        if len(image_parts) < 2:
            raise Exception("At least one cloth image is required")

        # --- 2. Gemini 3 Pro へのリクエスト ---
        print(f"DEBUG: Calling Google Gemini 3 Pro with {len(image_parts)} images...")
        
        # モデル名: ユーザー指定のプレビューモデル
        model_name = "gemini-3-pro-image-preview" 
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GOOGLE_GENAI_KEY}"
        
        # プロンプト: 1枚目が人物、2枚目以降が服であることを明示
        prompt_text = f"""
        Generate a photorealistic fashion image of the person shown in the first image, wearing the clothing items shown in the subsequent images.
        
        Input Images:
        1. The Person (Reference for face, body type, pose)
        2+. Clothing Items (Reference for outfit details)
        
        Outfit details: {', '.join(cloth_descriptions)}
        
        Requirements:
        - Maintain the person's facial features and body proportions exactly.
        - Naturally fit the provided clothes onto the person.
        - High quality, 8k resolution, professional fashion photography style.
        - Simple studio background.
        """

        # リクエストボディ作成 (テキスト + 画像リスト)
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    *image_parts # 画像を展開して追加
                ]
            }],
            "generationConfig": {
                "temperature": 0.4,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": 2048, # 画像生成を含む場合、仕様による
            }
        }
        
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        
        if response.status_code != 200:
            raise Exception(f"Google API Error ({response.status_code}): {response.text}")
            
        result = response.json()
        
        # --- 3. 画像データの抽出 (修正箇所) ---
        try:
            candidates = result.get('candidates', [])
            if not candidates: raise Exception("No candidates returned")
            
            parts = candidates[0].get('content', {}).get('parts', [])
            img_b64 = None
            
            for part in parts:
                # ★修正: APIのバージョンによって inlineData (Camel) か inline_data (Snake) か異なるため両方チェック
                if 'inlineData' in part:
                    img_b64 = part['inlineData']['data']
                    break
                if 'inline_data' in part:
                    img_b64 = part['inline_data']['data']
                    break
            
            if not img_b64:
                print(f"DEBUG: No image data found. Response: {json.dumps(result)[:200]}...")
                raise Exception("Model returned text but no image data")
                
            img_data = base64.b64decode(img_b64)

        except Exception as parse_err:
            raise Exception(f"Failed to parse image: {parse_err}")

        # --- 4. S3保存 ---
        print("DEBUG: Saving to S3...")
        file_name = f"tryon_{job_id}.png"
        resources.s3_client.put_object(
            Bucket=resources.BUCKET_NAME, 
            Key=file_name, 
            Body=img_data, 
            ContentType='image/png'
        )
        s3_url = f"https://{resources.BUCKET_NAME}.s3.ap-northeast-1.amazonaws.com/{file_name}"

        # --- 5. 完了更新 ---
        resources.coordinate_table.update_item(
            Key={'userId': user_id, 'createDatetime': coord_id},
                UpdateExpression="SET tryOnStatus = :s, tryOnImageUrl = :u ADD tryOnSuccessCount :inc",
                ExpressionAttributeValues={
                    ':s': 'COMPLETED',
                    ':u': s3_url,
                    ':inc': 1  # 加算する値
                },
        )
        print("DEBUG: Worker completed successfully")

    except Exception as e:
        print(f"ERROR in Worker: {e}")
        error_msg = str(e)[:200]
        try:
            resources.coordinate_table.update_item(
                Key={'userId': user_id, 'createDatetime': coord_id},
                UpdateExpression="set tryOnStatus = :s, tryOnFailReason = :r",
                ExpressionAttributeValues={':s': 'FAILED', ':r': error_msg}
            )
        except Exception as db_e:
            print(f"CRITICAL: DB Write Error: {db_e}")

def _download_image_as_base64(url):
    """S3等のURLから画像をDLし、Gemini API用のBase64文字列とMIMEタイプを返す"""
    signed_url = sign_s3_url(url)
    resp = requests.get(signed_url)
    if resp.status_code != 200:
        raise Exception(f"Failed to download image: {url}")
    
    # データをPILで読み込んでJPEG/PNGに統一しても良いが、
    # ここではそのままBase64化する (Geminiは主要フォーマットに対応)
    content_type = resp.headers.get('Content-Type', 'image/jpeg')
    b64_data = base64.b64encode(resp.content).decode('utf-8')
    return b64_data, content_type