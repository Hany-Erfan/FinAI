from datetime import timedelta
import os

SECRET_KEY = os.getenv("SECRET_KEY", "replace-this-in-production-with-a-long-random-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 3
TOKEN_EXPIRE_DELTA = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
AUTH_COOKIE_PREFIX = "chat_auth_token"
AUTH_COOKIE_HTTPONLY = True
AUTH_COOKIE_SAMESITE = "lax"
AUTH_COOKIE_SECURE = False
CSRF_COOKIE_PREFIX = "chat_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_HTTPONLY = False
