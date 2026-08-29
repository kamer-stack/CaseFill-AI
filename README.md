# CaseFill-AI — OFSP Document Intake Tool

AI-powered document extraction and cross-validation tool for the Orphan Family Support Programme (OFSP). Upload documents (B-form, CNIC, death certificate, result card, etc.), extract fields using a multimodal LLM, cross-check values across documents, and submit cases.

## Architecture

```
┌─────────────────────┐       ┌──────────────────────┐
│   React Frontend     │──────▶│   FastAPI Backend     │
│   (Vite, port 5173)  │ proxy │   (port 8000)         │
│   TypeScript + Tailwind│ /api │   Python + Uvicorn    │
└─────────────────────┘       └───────┬──────────────┘
                                      │
                              ┌───────▼──────────────┐
                              │  Qwen-VL (DashScope)  │
                              │  Multimodal LLM API   │
                              └──────────────────────┘
                                      │
                              ┌───────▼──────────────┐
                              │  SQLite (extractions.db)│
                              └──────────────────────┘
```

- **Frontend** — React 19 + TypeScript + Tailwind CSS 4, served by Vite dev server
- **Backend** — FastAPI + Uvicorn, handles uploads, extraction, cross-checking, and submission
- **AI Model** — Qwen-VL via Alibaba Cloud DashScope (OpenAI-compatible API)
- **Database** — SQLite (auto-created on first run)

---

## Prerequisites

Make sure you have these installed on your machine:

| Tool | Minimum Version | Check Command |
|------|----------------|---------------|
| **Python** | 3.10+ | `python --version` |
| **Node.js** | 18+ | `node --version` |
| **npm** | 9+ | `npm --version` |
| **Git** | 2.x | `git --version` |

---

## Quick Start (Local Development)

### 1. Clone the Repository

```bash
git clone https://github.com/kamer-stack/CaseFill-AI.git
cd CaseFill-AI
```

### 2. Set Up the Backend

#### a) Create a Python virtual environment (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

#### b) Install Python dependencies

```bash
pip install -r requirements.txt
```

#### c) Verify `API_Key.env` exists

The AI extraction uses the Qwen-VL model via DashScope. The `API_Key.env` file is **already included in this private repo** — just make sure it's present in the project root:

```env
API_KEY=sk-ws-...
BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

> **Note:** If the file is missing or you need a new key, ask the project maintainer or get one from [Alibaba Cloud DashScope](https://dashscope.console.aliyun.com/).

#### d) Verify the backend runs

```bash
python server.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Test the health endpoint (open a new terminal):
```bash
curl http://localhost:8000/api/health
```
Expected response: `{"status":"ok"}`

Keep the backend running — you'll need it for the frontend.

### 3. Set Up the Frontend

Open a **new terminal** (keep the backend running in the first one):

```bash
cd frontend
npm install
npm run dev
```

You should see:
```
  VITE v8.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

### 4. Open the App

Open your browser and go to **http://localhost:5173**

---

## How Frontend Connects to Backend

The Vite dev server is configured with a **proxy** in `frontend/vite.config.ts`:

```ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/uploads': 'http://localhost:8000',
  },
}
```

This means:
- All requests from the frontend to `/api/*` are automatically forwarded to the backend at `http://localhost:8000/api/*`
- All requests to `/uploads/*` are forwarded to `http://localhost:8000/uploads/*`
- **Both servers must be running** for the app to work in development

You do NOT need to change any URLs or worry about CORS during local development — the proxy handles it.

---

## Testing the Full Flow Locally

### Step-by-Step Test

1. **Start the backend** in Terminal 1:
   ```bash
   python server.py
   ```

2. **Start the frontend** in Terminal 2:
   ```bash
   cd frontend
   npm run dev
   ```

3. **Open** http://localhost:5173 in your browser

4. **Upload documents** — Use any of the test images in the repo root:
   - `test_bform.png` → select "B-Form" as document type
   - `test_cnic.png` → select "Father CNIC" or "Mother CNIC"
   - `test_death_certificate.png` → select "Death Certificate"
   - `test_result_card.png` → select "Result Card"

5. **Review extractions** — After each upload, the AI will extract fields. Verify the extracted data looks correct.

6. **Cross-check** — Once all documents are uploaded, the app runs cross-validation checks (e.g., father's CNIC on B-form vs. Father CNIC card).

7. **Submit** — Fill in the acknowledgment if there are flags, then submit the case.

### Quick Backend-Only Test (no frontend needed)

You can test the API directly with curl:

```bash
# Health check
curl http://localhost:8000/api/health

# Upload an image
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test_cnic.png"

# Extract from uploaded image (use the image_id from upload response)
curl -X POST http://localhost:8000/api/extract \
  -F "image_id=YOUR_IMAGE_ID" \
  -F "document_type=father_cnic"

# List all extractions
curl http://localhost:8000/api/extractions
```

### Running Automated Tests

```bash
python -m pytest test_pipeline.py -v
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/upload` | Upload an image (multipart form) |
| POST | `/api/extract` | Run AI extraction on uploaded image |
| POST | `/api/save-address` | Save manually-typed address |
| POST | `/api/cross-check` | Cross-validate all documents |
| POST | `/api/submit` | Submit a case |
| GET | `/api/extractions` | List all extractions from DB |

---

## Project Structure

```
CaseFill-AI/
├── frontend/              # React frontend
│   ├── src/
│   │   ├── components/    # UI screens and components
│   │   ├── context/       # React context (CaseContext)
│   │   ├── lib/           # API client and utilities
│   │   └── types/         # TypeScript type definitions
│   ├── vite.config.ts     # Vite config (proxy to backend)
│   └── package.json
├── server.py              # FastAPI backend (HTTP endpoints)
├── pipeline.py            # AI extraction logic (Qwen-VL)
├── schema.json            # Document field schemas
├── requirements.txt       # Python dependencies
├── API_Key.env            # API keys (included in private repo)
├── extractions.db         # SQLite database (auto-created)
├── uploads/               # Uploaded images (auto-created)
├── build.sh               # Build script for deployment
└── render.yaml            # Render.com deployment config
```

---

## Common Issues & Fixes

### "ModuleNotFoundError: No module named 'fastapi'"
You haven't installed the Python dependencies. Run:
```bash
pip install -r requirements.txt
```

### Frontend shows blank page or API errors
Make sure the **backend is running** on port 8000. The Vite dev server proxies API calls to it.

### "Connection refused" on upload/extract
Both the backend (`python server.py`) and frontend (`npm run dev`) must be running simultaneously.

### AI extraction returns errors or empty results
- Check that your `API_Key.env` file exists and has valid `API_KEY` and `BASE_URL` values
- Verify your DashScope API key is active and has quota remaining
- Check the backend terminal for error messages

### Port already in use
- Backend (8000): Change in `server.py` → `uvicorn.run(app, host="0.0.0.0", port=8001)`
- Frontend (5173): Run `npm run dev -- --port 5174`

### Windows: `python` not recognized
Try `python3` or `py` instead, or add Python to your system PATH.

---

## For Contributors

### Branch Naming
```
feature/short-description
fix/short-description
```

### Before Pushing
1. Make sure the backend starts without errors: `python server.py`
2. Make sure the frontend builds: `cd frontend && npm run build`
3. Test the full upload → extract → review → submit flow locally

### Environment Variables Summary

| Variable | Where | Required | Description |
|----------|-------|----------|-------------|
| `API_KEY` | `API_Key.env` | Yes | DashScope API key for Qwen-VL |
| `BASE_URL` | `API_Key.env` | Yes | DashScope API base URL |

---

## Production Deployment

The app is configured for deployment on **Render.com** via `render.yaml`:

```bash
# Build command
bash build.sh

# Start command
uvicorn server:app --host 0.0.0.0 --port $PORT
```

In production, the backend serves the built frontend directly from `frontend/dist/`. Set `API_KEY` and `BASE_URL` in the Render dashboard under Environment variables.

---

## Tech Stack

- **Frontend:** React 19, TypeScript, Tailwind CSS 4, Radix UI, Vite 8, Lucide Icons
- **Backend:** FastAPI, Uvicorn, Python 3.10+
- **AI:** Qwen-VL (multimodal LLM) via Alibaba Cloud DashScope
- **Database:** SQLite
- **Deployment:** Render.com
