import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from app.core.config import settings

import os

print("Looking for Firebase file at:", settings.FIREBASE_SERVICE_ACCOUNT_PATH)
print("Absolute path resolves to:", os.path.abspath(settings.FIREBASE_SERVICE_ACCOUNT_PATH))
print("File exists:", os.path.exists(settings.FIREBASE_SERVICE_ACCOUNT_PATH))

# Initialise the Firebase Admin SDK once when the app starts.
# It reads your service account JSON to get credentials.
_cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(_cred)


def verify_firebase_token(id_token: str) -> dict:
    """
    Verifies the Firebase ID token sent from the frontend.
    Returns the decoded token payload which contains:
      - uid: the Firebase user ID (stable, unique per user)
      - email: the user's email
      - name: display name (if set)
      - email_verified: bool
    Raises firebase_admin.auth.InvalidIdTokenError if invalid or expired.
    """
    decoded = firebase_auth.verify_id_token(id_token)
    return decoded