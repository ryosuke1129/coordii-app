import json
import time
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key
import resources
from utils.helpers import get_lat_long, sign_s3_url

def register_user(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        address = body.get('address')
        
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}

        existing_resp = resources.user_table.query(
            KeyConditionExpression=Key('userId').eq(user_id)
        )
        existing_items = existing_resp.get('Items', [])
        
        for item in existing_items:
            if item.get('deleteFlag', 0) == 0:
                resources.user_table.update_item(
                    Key={
                        'userId': user_id, 
                        'createDatetime': item['createDatetime']
                    },
                    UpdateExpression="set deleteFlag = :f",
                    ExpressionAttributeValues={':f': 1}
                )

        lat, lon = None, None
        if address:
            lat, lon = get_lat_long(address)

        current_time = datetime.now(timezone(timedelta(hours=+9), 'JST')).strftime('%Y-%m-%dT%H:%M:%S')
        
        item = {
            'userId': user_id,
            'createDatetime': current_time,
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
        
        resources.user_table.put_item(Item=item)
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "User saved", "data": item}, default=str, ensure_ascii=False)}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def get_user(event, headers):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        if not user_id: return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}

        resp = resources.user_table.query(
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
        
        # ★修正: imageLink は上書きせず、signedImageLink に署名付きを入れる
        if 'imageLink' in active_user:
            active_user['signedImageLink'] = sign_s3_url(active_user['imageLink'])
            # active_user['imageLink'] は S3の生URL(https://bucket...) のまま残る

        return {"statusCode": 200, "headers": headers, "body": json.dumps(active_user, default=str, ensure_ascii=False)}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}