import base64
import json
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from app.core.config import settings

import os

def _init_firebase():
    b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64")
    if b64:
        # Decode from base64 env var (production)
        data = json.loads(base64.b64decode(b64).decode())
        cred = credentials.Certificate(data)
    else:
        # Load from file (local development)
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)

_init_firebase()

def verify_firebase_token(id_token: str) -> dict:
    return firebase_auth.verify_id_token(id_token)