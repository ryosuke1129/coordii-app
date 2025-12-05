import requests
from decimal import Decimal
from datetime import datetime
import resources

def sign_s3_url(image_url):
    if not image_url or not isinstance(image_url, str):
        return image_url
    if not resources.BUCKET_NAME or resources.BUCKET_NAME not in image_url:
        print(f"DEBUG: URL not signed (Bucket match fail): {image_url}") 
        return image_url
    try:
        if not resources.s3_client:
            resources.initialize()
        file_key = image_url.split('/')[-1]
        return resources.s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': resources.BUCKET_NAME, 'Key': file_key},
            ExpiresIn=3600
        )
    except Exception as e:
        print(f"Sign URL Error: {e}")
        return image_url

def get_lat_long(address):
    if not resources.GOOGLE_API_KEY: return None, None
    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={resources.GOOGLE_API_KEY}&language=ja"
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

def get_current_season(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    m = dt.month
    if 3 <= m <= 5: return '春'
    if 6 <= m <= 9: return '夏'
    if 10 <= m <= 11: return '秋'
    return '冬'