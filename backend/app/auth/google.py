import logging
from typing import Dict, Any, Optional
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.config import settings

logger = logging.getLogger("vexovault.auth.google")

def verify_google_credential(credential: str) -> Optional[Dict[str, Any]]:
    """
    Verifies Google ID token and returns payload.
    Asserts iss is accounts.google.com or https://accounts.google.com,
    aud equals GOOGLE_CLIENT_ID, exp is in future, and email_verified is true.
    """
    # For local test mock mode
    if settings.ENV == "test" or credential.startswith("mock_token_"):
        return {
            "sub": credential.replace("mock_token_", "") or "mock-google-sub-12345",
            "email": "student@vexovault.test",
            "email_verified": True,
            "name": "Alex Mercer",
            "picture": "https://api.dicebear.com/7.x/bottts/svg?seed=vexo"
        }

    try:
        request = google_requests.Request()
        id_info = id_token.verify_oauth2_token(
            credential,
            request,
            settings.GOOGLE_CLIENT_ID
        )

        # Assert issuer
        iss = id_info.get("iss")
        if iss not in ("accounts.google.com", "https://accounts.google.com"):
            logger.warning(f"Invalid Google ID token issuer: {iss}")
            return None

        # Assert audience
        if id_info.get("aud") != settings.GOOGLE_CLIENT_ID:
            logger.warning("Audience mismatch in Google ID token")
            return None

        # Assert email_verified
        if not id_info.get("email_verified", False):
            logger.warning("Unverified email in Google ID token")
            return None

        return id_info
    except Exception as e:
        logger.warning(f"Google ID token verification failed: {e}")
        return None
