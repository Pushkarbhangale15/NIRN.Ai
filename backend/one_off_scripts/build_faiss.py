# DEPRECATED: reads from stale relative paths (data/embeddings.npy, data/chunks.json) that no
# longer match the pipeline. The FAISS index is now built by kaggle/build_gr_index.ipynb from the
# full mahGRs corpus. Not imported by the running backend — safe to delete once confirmed unused.
# Moved here (backend/one_off_scripts/) from backend/gr_assistant/ — see this folder's README.md.
import json
import pickle
import numpy as np
import faiss

# Load embeddings
embeddings = np.load("data/embeddings.npy")

print("Embedding Shape:", embeddings.shape)


# Normalize embeddings for cosine similarity
faiss.normalize_L2(embeddings)

# Create FAISS index using Inner Product
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)

# Add vectors
index.add(embeddings)

print("Vectors in Index:", index.ntotal)

# Save index
faiss.write_index(index, "backend/data/index.faiss")

# Save metadata (chunks)
with open("data/chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

with open("backend/data/chunks.pkl", "wb") as f:
    pickle.dump(chunks, f)

print("FAISS index saved.")
print("Chunk metadata saved.")