from pymongo import MongoClient


def db_connection(): 
    conn_str = f"mongodb://localhost:27017"
    client = MongoClient(conn_str, serverSelectionTimeoutMS=5000)
    # access the DB named anti_spam
    db = client.anti_spam
    return db


def add_banned_user(db, id: int) -> None:
    db.BannedUsers.insert_one({"id": id})

def banned_user_exists(db, id: int) -> bool:
    return db.BannedUsers.find_one({"id": id}) != None

def count_banned_users(db) -> int:
    return db.BannedUsers.count_documents({})

def remove_banned_user(db, id: int) -> None:
    db.BannedUsers.delete_one({"id": id})

def add_group(db, id: int) -> None:
    db.Groups.insert_one({"id": id})

def get_groups(db) -> list:
    data = db.Groups.find()
    return set(i["id"] for i in data)

def group_exists(db, id: int) -> bool:
    return db.Groups.find_one({"id": id}) != None

def count_groups(db) -> int:
    return db.Groups.count_documents({})

def save_message(db, collection, data):
    db[collection].insert_one(data)

def get_messages(db, collection: str, user_id: int) -> list:
    projection = {"_id": False, "chat_id": True, "message_id": True}
    data = db[collection].find({"user_id": user_id}, projection=projection)
    return list(data)

#by t.me/yehuda100