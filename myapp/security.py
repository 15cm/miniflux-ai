import hmac
from flask import jsonify, request
from common.config import Config


def require_bearer(protected: bool):
    config = Config()
    if not protected:
        return None
    token = config.api_bearer_token
    header = request.headers.get("Authorization", "")
    supplied = header[7:] if header.startswith("Bearer ") else ""
    if not token or not hmac.compare_digest(str(token), supplied):
        return jsonify({"status": "error", "message": "unauthorized"}), 401
    return None
