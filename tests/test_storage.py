from datetime import datetime

import core.mongodb as mongodb


def test_one_motor_client_is_reused(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            created.append(self)
            self.closed = False
            self._dbs = {}

        def __getitem__(self, name):
            self._dbs.setdefault(name, name)
            return self._dbs[name]

        def close(self):
            self.closed = True

    monkeypatch.setattr(mongodb.motor.motor_asyncio, "AsyncIOMotorClient", FakeClient)
    mongodb.close_db_client()

    async def _use():
        first = await mongodb.db_connection()
        second = await mongodb.db_connection()
        assert first == second == "anti_spam"
        mongodb.close_db_client()
        assert created[0].closed is True
        await mongodb.db_connection()

    import asyncio

    asyncio.run(_use())
    assert len(created) == 2
    mongodb.close_db_client()


async def test_remove_group_does_not_drop_a_shared_bucket(database):
    first, second = -1001, -2001
    assert first % 1000 == second % 1000
    await mongodb.add_group(first)
    await mongodb.add_group(second)
    await mongodb.save_message(
        {"expireAt": datetime.now(), "user_id": 5, "chat_id": first, "message_id": 1}
    )
    await mongodb.save_message(
        {"expireAt": datetime.now(), "user_id": 5, "chat_id": second, "message_id": 2}
    )
    await mongodb.remove_group(first)

    assert not await mongodb.group_exists(first)
    assert await mongodb.group_exists(second)
    assert await mongodb.get_messages(5, first) == []
    assert await mongodb.get_messages(5, second) == [{"chat_id": second, "message_id": 2}]
    assert database["Messages"].dropped is False
    assert all(not collection.dropped for collection in database.collections.values())
    assert database["BannedUsers"].inserted == 0


async def test_banned_user_chats_are_a_set_and_upsert(database):
    await mongodb.add_banned_user(3, -10)
    await mongodb.add_banned_user(3, -10)
    await mongodb.add_banned_user(3, -11)
    chats = await mongodb.get_banned_user_chats(3)
    assert isinstance(chats, set)
    assert chats == {-10, -11}
    assert database["BannedUsers"].inserted == 1
    assert await mongodb.get_banned_user_chats(99) == set()
