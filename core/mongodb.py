from functools import wraps

import motor.motor_asyncio
from pymongo import DESCENDING


# One client per process. Motor connects lazily and is not safe to construct
# on every call without closing the previous client.
_client = None

MESSAGES = "Messages"


def get_client():
    global _client
    if _client is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
    return _client


def close_db_client() -> None:
    global _client
    client = _client
    _client = None
    if client is not None:
        client.close()


async def db_connection():
    return get_client()["anti_spam"]


def with_db_connection(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        db = await db_connection()
        return await func(*args, **kwargs, db=db)
    return wrapper


async def _ensure_message_index(db) -> None:
    await db[MESSAGES].create_index(
        [("expireAt", DESCENDING)],
        background=True,
        expireAfterSeconds=0,
    )


@with_db_connection
async def ensure_message_index(db=None) -> None:
    await _ensure_message_index(db)


# Banned users. Each document is one user; chats are the groups they were
# banned in, so a later unban can cover every stored chat.
@with_db_connection
async def add_banned_user(id: int, chat_id, db=None) -> None:
    await db.BannedUsers.update_one(
        {"_id": id},
        {"$addToSet": {"chats": chat_id}},
        upsert=True,
    )


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


@with_db_connection
async def get_banned_user_chats(id: int, db=None) -> set:
    chats = await db.BannedUsers.find_one(
        {"_id": id},
        {"_id": 0, "chats": 1},
    )
    if chats and "chats" in chats:
        return set(chats["chats"])
    return set()


# Groups share one Messages collection keyed by chat_id. Removing a group
# deletes only that chat's documents. A collection named by chat id % 1000
# would drop every other group that lands in the same bucket.
@with_db_connection
async def add_group(chat_id: int, db=None) -> None:
    await _ensure_message_index(db)
    await db.Groups.update_one(
        {"_id": chat_id},
        {"$setOnInsert": {"_id": chat_id}},
        upsert=True,
    )


@with_db_connection
async def remove_group(chat_id: int, db=None) -> None:
    await db[MESSAGES].delete_many({"chat_id": chat_id})
    await db.Groups.delete_one({"_id": chat_id})


@with_db_connection
async def get_groups(db=None) -> set:
    groups = set()
    async for group in db.Groups.find():
        groups.add(group["_id"])
    return groups


@with_db_connection
async def group_exists(id: int, db=None) -> bool:
    group = await db.Groups.find_one({"_id": id})
    return group is not None


@with_db_connection
async def count_groups(db=None) -> int:
    return await db.Groups.count_documents({})


@with_db_connection
async def save_message(data, db=None) -> None:
    await db[MESSAGES].insert_one(data)


@with_db_connection
async def get_messages(user_id: int, chat_id: int, db=None) -> list:
    projection = {"_id": False, "chat_id": True, "message_id": True}
    cursor = db[MESSAGES].find(
        {"user_id": user_id, "chat_id": chat_id},
        projection=projection,
    )
    messages = []
    async for message in cursor:
        messages.append(message)
    return messages


#by t.me/yehuda100
