# DEPRECATED: embeds queries with paraphrase-multilingual-MiniLM-L12-v2, a different model than
# retrieval.py uses (intfloat/multilingual-e5-base) — incompatible with the real index's vector
# space. Standalone CLI debug script, not imported by the running backend. Do not point this at
# backend/data/index.faiss; safe to delete once confirmed unused.
import faiss
import json
import pickle
from sentence_transformers import SentenceTransformer

# Load embedding model
model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Load FAISS index
index = faiss.read_index("backend/data/index.faiss")

# Load chunk metadata
with open("backend/data/chunks.pkl", "rb") as f:
    chunks = pickle.load(f)

query = input("Ask a question: ")

# Embed the query

query_embedding = model.encode(

    [query],

    convert_to_numpy=True

)

# Normalize query vector

faiss.normalize_L2(query_embedding)

# Search top 5

distances, indices = index.search(query_embedding, k=5)

print("\nTop Results:\n")

for i, idx in enumerate(indices[0]):
    chunk = chunks[idx]

    print("=" * 80)
    print(f"Rank {i+1}")
    print(f"Department : {chunk['department']}")
    print(f"GR ID      : {chunk['gr_id']}")
    print(f"Language   : {chunk['language']}")
    print(f"Chunk ID   : {chunk['chunk_id']}")
    print()
    print(chunk["text"][:700])
    print()