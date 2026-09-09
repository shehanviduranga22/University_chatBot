# University AI Chatbot — Llama 3.2:1B + RAG

A complete local university knowledge-base chatbot using:

- React + Vite frontend
- Flask backend
- Ollama + Llama 3.2:1B
- ChromaDB
- Sentence Transformers embeddings
- PDF ingestion
- University website crawling
- Browser voice input
- Browser text-to-speech
- Source references
- Conversation history

## 1. Requirements

Install:

- Python 3.10 or 3.11 recommended
- Node.js 20+ recommended
- Ollama

Pull the Llama model:

```powershell
ollama pull llama3.2:1b
```

Test:

```powershell
ollama run llama3.2:1b
```

## 2. Backend setup — Windows PowerShell

Open:

```powershell
cd backend
```

Create virtual environment:

```powershell
py -3.11 -m venv venv
```

Activate:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Install packages:

```powershell
pip install -r requirements.txt
```

## 3. Add university PDFs

Copy official university PDFs into:

```text
backend/documents/
```

Examples:

```text
student_handbook.pdf
prospectus.pdf
admission.pdf
examination_rules.pdf
hostel.pdf
regulations.pdf
```

Then create the vector database:

```powershell
python ingest.py
```

The first embedding-model download needs internet access.

## 4. Website ingestion

Open:

```text
backend/.env.example
```

Copy it to `.env` if you want custom settings.

Example:

```text
UNIVERSITY_URL=https://www.sab.ac.lk/
MAX_PAGES=100
```

Then:

```powershell
python web_ingest.py
```

IMPORTANT:
Only crawl websites that you are authorized to crawl. Follow the university website's robots.txt and terms.

## 5. Start backend

Make sure Ollama is running.

Then:

```powershell
python app.py
```

Backend:

```text
http://127.0.0.1:5000
```

Health check:

```text
http://127.0.0.1:5000/api/health
```

## 6. Start React frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally:

```text
http://localhost:5173
```

## 7. Architecture

```text
User
 |
 | text / voice
 v
React
 |
 v
Flask
 |
 +--> query embedding --> ChromaDB
 |                         |
 |                         +--> relevant chunks
 |
 +--> conversation history
 |
 v
Llama 3.2:1B via Ollama
 |
 v
Answer + sources
 |
 v
React
 |
 +--> text
 +--> browser TTS
```

## 8. Accuracy strategy

The chatbot is intentionally instructed not to answer from general model knowledge.

It uses:

1. Query embedding
2. ChromaDB retrieval
3. Similarity threshold
4. Top relevant chunks
5. Strict context-only prompt
6. Source metadata
7. Low temperature
8. Short conversation history

For a production university deployment, add a cross-encoder reranker and build a 100–300 question evaluation set.

## 9. Voice

The frontend uses the browser Speech Recognition API.

Chrome generally provides the best support.

For stronger Sinhala / multilingual speech recognition, replace the browser recognizer with a local Whisper service later.

## 10. Important

Do not expose Ollama port 11434 directly to the public internet.

Use:

```text
Internet -> React -> Flask -> Ollama
```

not:

```text
Internet -> Ollama
```

## 11. Updating knowledge

When official PDFs change:

```powershell
python ingest.py
```

For website updates:

```powershell
python web_ingest.py
```

The current PDF ingestion rebuilds the collection so old PDF chunks are removed.

## 12. If ChromaDB or embedding packages fail

Use Python 3.10 or 3.11 in a clean virtual environment.

Then:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```
