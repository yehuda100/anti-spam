"""A tiny in-memory stand-in for the Motor calls this bot makes."""


def _match(doc, query):
    if not query:
        return True
    return all(doc.get(key) == value for key, value in query.items())


def _project(doc, projection):
    if not projection:
        return dict(doc)
    include = [key for key, flag in projection.items() if flag and key != "_id"]
    hide_id = projection.get("_id", 1) in (False, 0)
    if include:
        result = {key: doc[key] for key in include if key in doc}
    else:
        result = dict(doc)
    if hide_id:
        result.pop("_id", None)
    return result


class MemoryCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class MemoryCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []
        self.dropped = False
        self.indexes = []
        self.inserted = 0

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        self.inserted += 1

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if _match(doc, query):
                del self.docs[index]
                return

    async def delete_many(self, query):
        self.docs = [doc for doc in self.docs if not _match(doc, query)]

    async def update_one(self, query, update, upsert=False):
        found = next((doc for doc in self.docs if _match(doc, query)), None)
        if found is None:
            if not upsert:
                return
            doc = dict(query)
            doc.update(update.get("$setOnInsert", {}))
            for key, value in update.get("$set", {}).items():
                doc[key] = value
            for key, value in update.get("$addToSet", {}).items():
                doc[key] = [value]
            self.docs.append(doc)
            self.inserted += 1
            return
        for key, value in update.get("$set", {}).items():
            found[key] = value
        for key, value in update.get("$addToSet", {}).items():
            values = found.setdefault(key, [])
            if value not in values:
                values.append(value)

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            if _match(doc, query):
                return _project(doc, projection)
        return None

    def find(self, query=None, projection=None):
        query = query or {}
        matched = [
            _project(doc, projection) for doc in self.docs if _match(doc, query)
        ]
        return MemoryCursor(matched)

    async def count_documents(self, query):
        return sum(1 for doc in self.docs if _match(doc, query))

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    async def drop(self):
        self.dropped = True
        self.docs.clear()


class MemoryDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MemoryCollection(name)
        return self.collections[name]

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]
