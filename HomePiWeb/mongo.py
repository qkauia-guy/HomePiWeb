from pymongo import MongoClient
from django.conf import settings

client = MongoClient(
    host=settings.MONGO_CONFIG["HOST"],
    port=settings.MONGO_CONFIG["PORT"],
)

db = client[settings.MONGO_CONFIG["DB_NAME"]]

# 對應的 collection
device_ping_logs = db["device_ping_logs"]
