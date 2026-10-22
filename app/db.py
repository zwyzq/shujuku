from pymongo import MongoClient, ASCENDING
from flask import current_app, g


_client = None


def init_db(app):
    global _client
    _client = MongoClient(app.config["MONGO_URI"])
    # 启动时确保索引
    with app.app_context():
        db = _client[app.config["MONGO_DB"]]
        db.users.create_index("username", unique=True)
        db.surveys.create_index("public_token", unique=True, sparse=True)
        db.surveys.create_index("owner_id")
        db.questions.create_index([("survey_id", ASCENDING), ("order", ASCENDING)])
        db.responses.create_index("survey_id")
        db.question_items.create_index("owner_id")
        db.question_items.create_index("shared_with")
        db.question_versions.create_index([("item_id", ASCENDING), ("version", ASCENDING)], unique=True)
        db.questions.create_index("bank_version_id")
        db.questions.create_index("bank_item_id")
    app.teardown_appcontext(_close_db)


def get_db():
    if "db" not in g:
        g.db = _client[current_app.config["MONGO_DB"]]
    return g.db


def _close_db(exception=None):
    g.pop("db", None)
