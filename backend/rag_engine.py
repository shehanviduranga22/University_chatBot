import os
import re
import requests
from typing import List, Dict

import chromadb
from sentence_transformers import SentenceTransformer

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)
TOP_K = int(os.getenv("TOP_K", "8"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.28"))

SYSTEM_PROMPT = """
You are a friendly and professional university information assistant.

Answer questions ONLY using the supplied university context.

RESPONSE STYLE:
- Make every answer clear, organized and easy to scan.
- Use Markdown formatting.
- Use ## or ### headings when the answer has sections.
- Use **bold** for important terms, names, requirements and key information.
- Use *italic* for emphasis when appropriate.
- Use bullet points for lists.
- Use numbered lists for procedures or steps.
- Use tables only when they make comparisons easier.
- Keep paragraphs short.
- Use emojis sparingly when appropriate.
- Put important warnings or notes under a clear heading such as **Important**.
- Do not make every sentence bold.
- Do not over-format simple answers.
- Answer in the same language as the user's question when possible.

ACCURACY RULES:
- Use ONLY the supplied university context.
- Never invent university information.
- Never guess dates, fees, regulations, contacts, requirements or deadlines.
- If the information is not available in the context, say:
  "I couldn't find reliable information about this in the university knowledge base."
- If sources conflict, explain the conflict.
- Do not mention RAG, embeddings, ChromaDB, prompts or internal system details.

Be concise, friendly and professional.
"""

class UniversityRAG:
    def __init__(self):
        self.model = MODEL
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)

        db_path = os.path.join(os.path.dirname(__file__), "vector_db")
        self.client = chromadb.PersistentClient(path=db_path)

        self.collection = self.client.get_or_create_collection(
            name="university_documents",
            metadata={"hnsw:space": "cosine"}
        )

    def _embed(self, texts: List[str]):
        return self.embedder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        ).tolist()

    def _clean_query(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text[:1000]

    def retrieve(self, question: str):
        if self.collection.count() == 0:
            return []

        query_embedding = self._embed([self._clean_query(question)])[0]

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(TOP_K, self.collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        items = []
        for doc, meta, distance in zip(docs, metas, distances):
            # Chroma cosine distance: lower is better.
            score = max(0.0, 1.0 - float(distance))
            items.append({
                "text": doc,
                "metadata": meta or {},
                "score": round(score, 4)
            })

        return items

    def _build_context(self, results):
        blocks = []
        for i, item in enumerate(results, 1):
            m = item["metadata"]
            source = m.get("source", "University knowledge base")
            page = m.get("page")
            title = m.get("title")

            label = source
            if title:
                label = f"{title} | {source}"
            if page:
                label += f" | Page {page}"

            blocks.append(
                f"[SOURCE {i}]\n"
                f"Source: {label}\n"
                f"Relevance: {item['score']}\n"
                f"Content:\n{item['text']}"
            )
        return "\n\n".join(blocks)

    def _call_ollama(self, question, context, history):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Keep only a small recent history to avoid overloading a 1B model.
        for item in history[-4:]:
            role = item.get("role")
            content = item.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({
                    "role": role,
                    "content": content[:1500]
                })

        user_prompt = f"""
UNIVERSITY CONTEXT:
{context}

USER QUESTION:
{question}

Answer using only the university context above.
"""

        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.8,
                "num_ctx": 2048
            }
        }

        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=180
        )
        response.raise_for_status()

        data = response.json()
        return data.get("message", {}).get("content", "").strip()

    def answer(self, question, history=None):
        history = history or []
        results = self.retrieve(question)

        if not results:
            return {
                "answer": "I couldn't find reliable information about this in the university knowledge base.",
                "sources": [],
                "confidence": 0
            }

        # Prevent weak retrieval from reaching the LLM.
        strong = [r for r in results if r["score"] >= MIN_SCORE]

        if not strong:
            return {
                "answer": "I couldn't find reliable information about this in the university knowledge base.",
                "sources": [],
                "confidence": round(results[0]["score"], 4)
            }

        # Keep the context compact for the 1B model.
        strong = strong[:4]
        context = self._build_context(strong)

        answer = self._call_ollama(question, context, history)

        sources = []
        for r in strong:
            m = r["metadata"]
            sources.append({
                "source": m.get("source", "University knowledge base"),
                "title": m.get("title", ""),
                "page": m.get("page", ""),
                "url": m.get("url", ""),
                "score": r["score"]
            })

        return {
            "answer": answer,
            "sources": sources,
            "confidence": round(max(r["score"] for r in strong), 4)
        }
