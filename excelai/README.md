# ExcelAI

ExcelAI is a Phase 1 AI-assisted data extraction and Excel table creation app built with FastAPI and a custom dark-luxury frontend.

## Features

- JWT login and signup
- Text, image, and URL extraction flows
- Groq-powered structured table generation with fallback parsing
- Inline table editing and sorting
- Excel and CSV export
- Vercel deployment config

## Local Run

### Backend

```bash
cd excelai
python -m uvicorn backend.main:app --reload
```

### Frontend

Serve the `frontend` folder with any static file server, or open `frontend/index.html` through a local dev server.

## Demo Accounts

- `demo@excelai.dev` / `ExcelAI123!`
- `admin@excelai.dev` / `AdminExcelAI123!`

## Environment

Copy `backend/.env.example` to `.env` and set:

- `GROQ_API_KEY` — Your Groq API key from console.groq.com
- `SECRET_KEY` — A secure random string for JWT signing (min 32 chars)
- `ALGORITHM` — JWT algorithm (default: `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES` — Session duration in minutes (default: `1440` = 1 day)
- `CORS_ORIGINS` — Allowed frontend origins (dev: `http://localhost:3000`, production: your domain)
- `GROQ_MODEL` — Model name (default: `llama-3.3-70b-versatile`)

### Local Development

The `.env` file is automatically loaded when running the backend locally.

### Vercel Deployment

1. **Connect your repository** to Vercel
2. **Set environment variables** in Vercel project settings:
   - Go to **Settings → Environment Variables**
   - Add:
     - `GROQ_API_KEY` (keep secret)
     - `SECRET_KEY` (keep secret)
     - `ALGORITHM` = `HS256`
     - `ACCESS_TOKEN_EXPIRE_MINUTES` = `1440`
     - `CORS_ORIGINS` = your Vercel domain (e.g., `https://excelai-yourusername.vercel.app`)
     - `GROQ_MODEL` = `llama-3.3-70b-versatile`
3. **Deploy** — Vercel will automatically use these environment variables for both frontend and backend

**Note:** Update `CORS_ORIGINS` to your production domain after the first deployment.

**Pro Tip:** Use `vercel env pull` to download Vercel environment variables to `.env.local` for local testing with production settings:

## API Endpoints

- `POST /api/auth/login`
- `POST /api/auth/signup`
- `GET /api/auth/me`
- `POST /api/extract/text`
- `POST /api/extract/image`
- `POST /api/extract/url`
- `POST /api/export/excel`
- `POST /api/export/csv`
