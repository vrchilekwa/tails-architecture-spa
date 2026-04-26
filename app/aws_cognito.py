import json
from functools import lru_cache
from urllib.request import urlopen

from jose import jwt

from app.config import settings


def _issuer() -> str:
    return f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.aws_cognito_user_pool_id}"


def _jwks_url() -> str:
    return f"{_issuer()}/.well-known/jwks.json"


@lru_cache(maxsize=1)
def _load_jwks() -> dict:
    with urlopen(_jwks_url(), timeout=10) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)


def _find_jwk_for_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("Invalid AWS token header")
    keys = _load_jwks().get("keys", [])
    for key in keys:
        if key.get("kid") == kid:
            return key
    raise ValueError("AWS token key not found")


def verify_cognito_id_token(id_token: str) -> dict:
    if not settings.aws_cognito_user_pool_id or not settings.aws_cognito_client_id:
        raise ValueError("AWS Cognito is not configured")
    key = _find_jwk_for_token(id_token)
    try:
        return jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.aws_cognito_client_id,
            issuer=_issuer(),
            options={"verify_at_hash": False},
        )
    except Exception as exc:
        raise ValueError("Invalid AWS Cognito token") from exc
