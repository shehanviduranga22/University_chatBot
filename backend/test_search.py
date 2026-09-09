import os
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "vector_db"

COLLECTION_NAME = "university_documents"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

print("Loading embedding model...")

model = SentenceTransformer(EMBEDDING_MODEL)

print("Embedding model loaded.")


# ============================================================
# CONNECT TO CHROMADB
# ============================================================

print(f"Vector DB path: {DB_PATH}")

client = chromadb.PersistentClient(
    path=str(DB_PATH)
)


# ============================================================
# CHECK COLLECTION
# ============================================================

print(f"Loading collection: {COLLECTION_NAME}")

try:
    collection = client.get_collection(
        name=COLLECTION_NAME
    )

except Exception as e:
    print("\nERROR: Could not load ChromaDB collection.")
    print(e)

    print("\nAvailable collections:")

    collections = client.list_collections()

    if collections:
        for c in collections:
            print(" -", c.name)
    else:
        print("No collections found.")

    raise SystemExit(1)


print("Collection loaded successfully.")
print("Total documents:", collection.count())


# ============================================================
# QUERY
# ============================================================

query = "Who is the Dean of the Faculty of Applied Sciences?"

print("\nQuery:")
print(query)


# ============================================================
# CREATE QUERY EMBEDDING
# ============================================================

embedding = model.encode(
    [query],
    normalize_embeddings=True
).tolist()


# ============================================================
# SEARCH
# ============================================================

TOP_K = 10

results = collection.query(
    query_embeddings=embedding,
    n_results=TOP_K,
    include=[
        "documents",
        "metadatas",
        "distances"
    ]
)


# ============================================================
# DISPLAY RESULTS
# ============================================================

print("\n")
print("=" * 70)
print("SEARCH RESULTS")
print("=" * 70)


documents = results.get("documents", [[]])[0]
metadatas = results.get("metadatas", [[]])[0]
distances = results.get("distances", [[]])[0]


if not documents:
    print("\nNo results found.")
    raise SystemExit(0)


for i, doc in enumerate(documents):

    print("\n" + "-" * 70)
    print(f"RESULT {i + 1}")
    print("-" * 70)

    distance = distances[i] if i < len(distances) else None
    metadata = metadatas[i] if i < len(metadatas) else {}

    print(f"Distance : {distance}")
    print(f"Source   : {metadata.get('source', 'Unknown')}")
    print(f"Page     : {metadata.get('page', 'Unknown')}")
    print(f"Title    : {metadata.get('title', 'Unknown')}")

    print("\nContent:")
    print(doc[:1500])


print("\n" + "=" * 70)
print("SEARCH COMPLETE")
print("=" * 70)