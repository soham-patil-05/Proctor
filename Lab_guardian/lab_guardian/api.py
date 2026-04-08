"""api.py — HTTP client for the Lab Insight REST API."""

import requests
from . import config


def join_session(roll_no: str, session_id: str, password: str | None = None) -> dict:
    """
    POST /api/students/join-session
    Returns { token, studentId, sessionId, expiresIn }.
    Raises on HTTP error.
    """
    url = f"{config.API_BASE_URL}/api/students/join-session"
    payload = {"rollNo": roll_no, "sessionId": session_id}
    if password:
        payload["password"] = password

    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()
