import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MONGO_URI")

if not uri:
    print("MONGO_URI was not found in .env")
    exit()

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    # Test connection
    client.admin.command("ping")

    print("MongoDB Atlas connected successfully!")

    db_name = os.getenv("MONGO_DB_NAME", "college_voting")
    db = client[db_name]

    print("Database:", db.name)

except Exception as e:
    print("MongoDB connection failed:")
    print(e)