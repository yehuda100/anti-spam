import motor.motor_asyncio
from functools import wraps
from bson import int64
from pymongo import errors, DESCENDING


# Database Connection
# Functions to establish and manage the connection to the MongoDB database.
async def db_connection(): 
    client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.anti_spam
    return db

# Decorator that provides a database connection
# to the decorated function by adding the 'db' keyword argument.
def with_db_connection(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        db = await db_connection()
        result = await func(*args, **kwargs, db=db)
        return result
    return wrapper

# Banned Users Management
# Functions to handle operations related to banned users.
@with_db_connection
async def add_banned_user(id: int, db=None) -> None:
    try:
        await db.BannedUsers.insert_one({"_id": int64.Int64(id)})
    except errors. DuplicateKeyError:
        return

@with_db_connection
async def banned_user_exists(id: int, db=None) -> bool:
    user = await db.BannedUsers.find_one({"_id": id})
    return user is not None

@with_db_connection
async def count_banned_users(db=None) -> int:
    return await db.BannedUsers.count_documents({})

@with_db_connection
async def remove_banned_user(id: int, db=None) -> None:
    await db.BannedUsers.delete_one({"_id": id})

# Groups Management
# Functions to manage groups in the database.
@with_db_connection
async def add_group(collection: str, id: int, db=None) -> None:
    await db[collection].create_index([("expireAt", DESCENDING)], background=True, expireAfterSeconds=0)
    try:
        await db.Groups.insert_one({"_id": int64.Int64(id)})
    except errors.DuplicateKeyError:
        return

@with_db_connection
async def remove_group(collection: str, id: int, db=None) -> None:
    await db[collection].drop()
    await db.Groups.delete_one({"_id": int64.Int64(id)})

@with_db_connection
async def get_groups(db=None) -> set:
    data = db.Groups.find()
    groups = set()
    async for i in data:
        groups.add(i["_id"])
    return groups

@with_db_connection
async def group_exists(id: int, db=None) -> bool:
    group = await db.Groups.find_one({"_id": id})
    return group is not None

@with_db_connection
async def count_groups(db=None) -> int:
    return await db.Groups.count_documents({})

# Message Handling
# Functions to store and retrieve messages from the database.
@with_db_connection
async def save_message(collection, data, db=None) -> None:
    await db[collection].insert_one(data)

@with_db_connection
async def get_messages(collection: str, user_id: int, db=None) -> list:
    projection = {"_id": False, "chat_id": True, "message_id": True}
    data = db[collection].find({"user_id": user_id}, projection=projection)
    messages = []
    async for message in data:
        messages.append(message)
    return messages


#by t.me/yehuda100
