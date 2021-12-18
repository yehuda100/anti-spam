from pony.orm import *

db = Database()

class BannedUsers(db.Entity):
    id = PrimaryKey(int, size=64)

class Groups(db.Entity):
    id = PrimaryKey(int, size=64)


@db_session
def add_banned_user(id: int) -> None:
    BannedUsers(id=id)

@db_session
def get_banned_users() -> set:
    data = select(i.id for i in BannedUsers)
    return set(i for i in data)

@db_session
def banned_user_exists(id: int) -> bool:
    return BannedUsers.exists(id=id)

@db_session
def count_banned_users() -> int:
    return count(i for i in BannedUsers)

@db_session
def remove_banned_user(id: int) -> None:
    BannedUsers[id].delete()

@db_session
def add_group(id: int) -> None:
    Groups(id=id)

@db_session
def get_groups() -> list:
    data = select(i.id for i in Groups)
    return set(i for i in data)

@db_session
def group_exists(id: int) -> bool:
    return Groups.exists(id=id)

@db_session
def count_groups() -> int:
    return count(i for i in Groups)


db.bind(provider='sqlite', filename='database.db', create_db=True)
db.generate_mapping(create_tables=True)


#by t.me/yehuda100