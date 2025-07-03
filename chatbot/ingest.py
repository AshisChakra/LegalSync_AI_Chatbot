# File: chatbot/ingest.py
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import certifi

load_dotenv()

try:
    mongo_client = MongoClient(os.getenv("MONGO_URI"), tlsCAFile=certifi.where())
    # Test connection
    mongo_client.admin.command('ping')
    print("Connected to MongoDB Atlas successfully!")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    exit(1)

db = mongo_client[os.getenv("DB_NAME")]
col = db[os.getenv("COLLECTION_NAME")]

data = [{
    "chunk_id": "Family_HC_case123_p1-2",
    "case_title": "XYZ vs ABC",
    "year": 2023,
    "domain": "Family",
    "court": "HC",
    "page_numbers": [1, 2],
    "chunk_text": "The husband filed for eviction of his wife...",
    "keywords": ["eviction", "wife", "domestic violence"],
    "embedding": [0.123, 0.456, 0.789]
}]

def insert_data(data):
    """
    Insert data into MongoDB collection.
    
    :param data: Data to be inserted (list of dictionaries or single dictionary).
    """
    try:
        if isinstance(data, list):
            col.insert_many(data)
            print(f"Inserted {len(data)} documents successfully.")
        else:
            col.insert_one(data)
            print("Inserted one document successfully.")
    except Exception as e:
        print(f"An error occurred while inserting data: {e}")

if __name__ == "__main__":
    insert_data(data)