import json
import numpy as np
from sentence_transformers import SentenceTransformer

# Load model
model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Load chunks
with open("data/chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

texts = [chunk["text"] for chunk in chunks]

print(f"Generating embeddings for {len(texts)} chunks...")

embeddings = model.encode(
    texts,
    batch_size=32,
    show_progress_bar=True,
    convert_to_numpy=True
)

# Save embeddings
np.save("data/embeddings.npy", embeddings)

print(f"Saved embeddings with shape: {embeddings.shape}")