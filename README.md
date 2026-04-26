# Tails Target-State API + React App

This repository now includes:
- `FastAPI` backend (PostgreSQL + Kafka + app-issued JWT bearer auth)
- `React` frontend that signs in with Cognito Hosted UI (OIDC)
- Token exchange endpoint so backend still uses app-issued JWTs
- Docker Compose for local full-stack startup

## Folder structure

- `app/` - FastAPI backend code
- `frontend/` - React app (Vite + `react-oidc-context`)
- `docker-compose.yml` - local orchestration for API, web, Postgres, Kafka
- `.env.example` - backend and compose environment template
- `frontend/.env.example` - frontend environment template

## Auth flow

1. User logs in on the React app using AWS Cognito.
2. Frontend sends Cognito `id_token` to `POST /auth/aws/exchange`.
3. FastAPI verifies Cognito token using Cognito JWKS and issues its own JWT.
4. Frontend calls protected backend routes with:
   - `Authorization: Bearer <app-issued-jwt>`

This keeps backend authorization based on your app-issued JWT bearer tokens.

## Backend endpoints (auth)

- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/aws/exchange` (Cognito ID token -> app JWT)
- `GET /auth/me` (test protected route with app JWT)
- `GET /auth/google/start`
- `GET /auth/google/callback?code=...` (stub)

## Environment setup

1. Copy `.env.example` to `.env` and set:
   - `JWT_SECRET_KEY`
   - `AWS_REGION`
   - `AWS_COGNITO_USER_POOL_ID`
   - `AWS_COGNITO_CLIENT_ID`
2. Copy `frontend/.env.example` to `frontend/.env` and set:
   - `VITE_API_BASE_URL`
   - `VITE_AWS_REGION`
   - `VITE_AWS_USER_POOL_ID`
   - `VITE_AWS_USER_POOL_CLIENT_ID`
   - `VITE_AWS_COGNITO_AUTHORITY`
   - `VITE_AWS_COGNITO_DOMAIN`
   - `VITE_AWS_REDIRECT_URI`
   - `VITE_AWS_LOGOUT_URI`
   - `VITE_AWS_OIDC_SCOPE`

## Run with Docker Compose

```bash
docker compose --env-file .env up --build
```

- React app: `http://localhost:5173`
- FastAPI docs: `http://localhost:8000/docs`

## Local scripts

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
