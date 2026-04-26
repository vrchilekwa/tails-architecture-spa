import os


class Settings:
    app_name: str = "Tails Target-State API"
    app_version: str = "0.2.0"

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://tails:tails@postgres:5432/tails",
    )
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    kafka_events_topic: str = os.getenv("KAFKA_EVENTS_TOPIC", "tails.events")
    kafka_consumer_group: str = os.getenv("KAFKA_CONSUMER_GROUP", "tails-api")

    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "change-me-in-prod")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
    jwt_issuer: str = os.getenv("JWT_ISSUER", "tails-api")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "tails-api")
    jwt_token_version: int = int(os.getenv("JWT_TOKEN_VERSION", "1"))
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "stub-google-client-id")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "stub-google-client-secret")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    aws_region: str = os.getenv("AWS_REGION", "eu-west-1")
    aws_cognito_user_pool_id: str = os.getenv("AWS_COGNITO_USER_POOL_ID", "")
    aws_cognito_client_id: str = os.getenv("AWS_COGNITO_CLIENT_ID", "")


settings = Settings()
