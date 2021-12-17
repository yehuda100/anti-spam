from pony.orm import *

db = Database()

class BannedUsers(db.Entity):
    id = PrimaryKey(int)

class Groups(db.Entity):
    id = PrimaryKey(int)


@db_session
def add_banned_user(id: int) -> None:
    BannedUsers(id=id)

@db_session
def get_banned_users() -> set:
    return set(select(id for id in BannedUsers))

@db_session
def add_group(id: int) -> None:
    Groups(id=id)

@db_session
def get_groups() -> list:
    return set(select(id for id in Groups))


db.bind(provider='sqlite', filename='database.db', create_db=True)
db.generate_mapping(create_tables=True)


#by t.me/yehuda100