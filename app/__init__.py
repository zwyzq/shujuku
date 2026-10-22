from flask import Flask, render_template, redirect
from dotenv import load_dotenv
import os

from app.db import init_db, get_db


def create_app():
    load_dotenv()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
    )
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev")
    app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    app.config["MONGO_DB"] = os.getenv("MONGO_DB", "ecnu10245501461")

    init_db(app)

    from app.routes.health import bp as health_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.surveys import bp as surveys_bp
    from app.routes.fill import bp as fill_bp
    from app.routes.questions import bp as questions_bp
    from app.routes.stats import bp as stats_bp
    from app.routes.bank import bp as bank_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(surveys_bp, url_prefix="/api/surveys")
    app.register_blueprint(fill_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(bank_bp)

    @app.get("/")
    def page_home():
        return render_template("index.html")

    @app.get("/login")
    def page_login():
        return render_template("login.html")

    @app.get("/surveys/<survey_id>")
    def page_survey_edit(survey_id):
        return render_template("survey_edit.html")

    @app.get("/surveys/<survey_id>/stats")
    def page_stats(survey_id):
        return render_template("stats.html")

    @app.get("/fill/<token>")
    def page_fill(token):
        return render_template("fill.html")

    @app.get("/survey/<token>")
    def page_survey_alias(token):
        return render_template("fill.html")

    @app.get("/bank")
    def page_bank():
        return render_template("bank.html")

    @app.get("/bank/<item_id>")
    def page_bank_item(item_id):
        return render_template("bank_item.html")

    return app
