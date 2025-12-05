import json
import requests
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import resources
from utils.helpers import get_lat_long

def get_weather(event, headers):
    try:
        body = json.loads(event['body'])
        user_id = body.get('userId')
        city_name = body.get('city', '福岡市博多区')
        
        if not user_id: 
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"message": "userId is required"})}
        
        # 緯度経度取得
        lat_dec, lon_dec = get_lat_long(city_name)
        if not lat_dec:
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Location not found"})}

        # 日付決定 (19時以降は明日)
        JST = timezone(timedelta(hours=+9), 'JST')
        now_jst = datetime.now(JST)
        target_date = now_jst + timedelta(days=1) if now_jst.hour >= 19 else now_jst
        target_date_str = target_date.strftime('%Y-%m-%d')

        # OpenWeatherMap API
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat_dec}&lon={lon_dec}&appid={resources.WEATHER_API_KEY}&units=metric&lang=ja"
        res = requests.get(url)
        data = res.json()
        
        if res.status_code != 200:
            return {"statusCode": res.status_code, "headers": headers, "body": json.dumps(data)}

        # データ集計
        temps, pops = [], []
        weather_desc, icon_code = "", ""
        humidity, wind_speed, wind_deg = 0, 0, 0
        
        for item in data['list']:
            if target_date_str in item['dt_txt']:
                temps.append(item['main']['temp_max'])
                temps.append(item['main']['temp_min'])
                pops.append(item.get('pop', 0))
                # 代表的な時間帯(03:00 UTC = 12:00 JST)の天気を使用
                if "03:00:00" in item['dt_txt']:
                    weather_desc = item['weather'][0]['description']
                    icon_code = item['weather'][0]['icon']
                    humidity = item['main']['humidity']
                    wind_speed = item['wind']['speed']
                    wind_deg = item['wind']['deg']
        
        # データ不足時の補完
        if not temps:
             return {"statusCode": 404, "headers": headers, "body": json.dumps({"message": "Forecast not found"})}
        if not weather_desc: # 03:00がない場合
             first = [x for x in data['list'] if target_date_str in x['dt_txt']][0]
             weather_desc = first['weather'][0]['description']
             icon_code = first['weather'][0]['icon']

        # 保存と返却
        item = {
            'userId': user_id, 'targetDate': target_date_str, 
            'latitude': lat_dec, 'longitude': lon_dec,
            'weather': weather_desc, 
            'iconUrl': f"https://openweathermap.org/img/wn/{icon_code}@2x.png" if icon_code else None,
            'max': Decimal(str(max(temps))).quantize(Decimal("0.1")), 
            'min': Decimal(str(min(temps))).quantize(Decimal("0.1")),
            'humidity': Decimal(str(humidity)), 
            'pop': Decimal(str(int(max(pops) * 100))),
            'windSpeed': Decimal(str(wind_speed)).quantize(Decimal("0.1")), 
            'windDirection': _get_wind_dir(wind_deg),
            'city': city_name, 
            'createDatetime': now_jst.strftime('%Y-%m-%dT%H:%M:%S'), 
            'deleteFlag': 0
        }
        resources.weather_table.put_item(Item=item)
        return {"statusCode": 200, "headers": headers, "body": json.dumps(item, default=str, ensure_ascii=False)}

    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"message": "Error", "error": str(e)})}

def _get_wind_dir(degrees):
    directions = ["北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東", "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"]
    return directions[int((degrees + 11.25) / 22.5) % 16]