import os
from datetime import timedelta
from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()


class Config:
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "task_management")

    # URL.create safely handles special characters like @ # : / in the password
    SQLALCHEMY_DATABASE_URI = URL.create(
        "postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME,
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Set SQL_ECHO=1 in .env to print every SQL query in the terminal
    SQLALCHEMY_ECHO = os.getenv("SQL_ECHO", "0") == "1"

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-secret-change-me-before-going-live-0123456789")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", 30)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", 7)))
    # Tokens are sent as "Authorization: Bearer <token>" (OAuth 2.0 style)
    JWT_TOKEN_LOCATION = ["headers"]
