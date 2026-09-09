import os
import re
import shutil
from pathlib import Path

import chromadb
import pymupdf
from sentence_transformers import SentenceTransformer

BASE = Path(__file__).parent
DOCUMENTS = BASE / "documents"
DB = BASE / "vector_db"

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

embedder = SentenceTransformer(EMBEDDING_MODEL)

client = chromadb.PersistentClient(path=str(DB))
collection = client.get_or_create_collection(
    name="university_documents",
    metadata={"hnsw:space": "cosine"}
)

def clean_text(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def chunk_text(text):
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(words):
            break

        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks

def process_pdf(path):
    doc = pymupdf.open(path)
    all_chunks = []

    for page_index, page in enumerate(doc):
        text = clean_text(page.get_text("text"))
        if not text:
            continue

        for chunk in chunk_text(text):
            all_chunks.append({
                "text": chunk,
                "metadata": {
                    "source": path.name,
                    "page": page_index + 1,
                    "title": path.stem,
                    "type": "pdf"
                }
            })

    doc.close()
    return all_chunks

def main():
    DOCUMENTS.mkdir(exist_ok=True)

    pdfs = list(DOCUMENTS.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in backend/documents/")
        print("Add university PDFs and run this script again.")
        return

    print(f"Found {len(pdfs)} PDF files.")

    # Rebuild the collection for a clean knowledge base.
    try:
        client.delete_collection("university_documents")
    except Exception:
        pass

    global collection
    collection = client.get_or_create_collection(
        name="university_documents",
        metadata={"hnsw:space": "cosine"}
    )

    all_items = []
    for pdf in pdfs:
        print(f"Processing: {pdf.name}")
        all_items.extend(process_pdf(pdf))

    print(f"Created {len(all_items)} chunks.")

    batch_size = 64

    for i in range(0, len(all_items), batch_size):
        batch = all_items[i:i + batch_size]
        texts = [x["text"] for x in batch]
        embeddings = embedder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        ).tolist()

        ids = [f"pdf_{i+j}" for j in range(len(batch))]

        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=[x["metadata"] for x in batch]
        )

        print(f"Indexed {min(i + batch_size, len(all_items))}/{len(all_items)}")

    print("\nDone.")
    print("Vector database:", DB)
    print("Total chunks:", collection.count())

if __name__ == "__main__":
    main()
