# chatbot-uni

Graduation project – simple full-stack chatbot demo.

## Backend

The backend is a FastAPI service located in `backend/`. It can respond with
intent-based canned answers or call Google Gemini if you provide an API key.

1. Create a virtual environment and install dependencies:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Create a `.env` file (see the table below) and add your Gemini credentials.
3. Run the server:
   ```bash
   uvicorn backend.main:app --reload
   ```

### Environment variables

| Name             | Description                                   |
| ---------------- | --------------------------------------------- |
| `GOOGLE_API_KEY` | Google AI Studio / Gemini API key (optional). |
| `GEMINI_MODEL`   | Model name, default `gemini-1.5-flash`.       |
| `ALLOWED_ORIGINS` | CORS için izin verilen origin'ler (virgülle ayrılmış, örn: `https://example.com,https://www.example.com`) |
| `BACKEND_URL`   | Backend API URL'i (opsiyonel, frontend için)  |

If no API key is supplied the backend falls back to the rule-based intent
classifier bundled with the repo.

**Önemli:** Production'da kendi domain'inizi `ALLOWED_ORIGINS` environment variable'ına ekleyin:
```bash
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## Frontend

The React frontend lives under `frontend/chatbot-arayuzu`. It now connects to
the backend API.

### Frontend Environment Variables

Create a `.env` file in `frontend/chatbot-arayuzu/`:

```bash
REACT_APP_BACKEND_URL=https://your-backend-url.com
```

If not set, it defaults to `http://localhost:8000` for local development.
