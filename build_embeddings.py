import os
import sys
import json
import pickle
import numpy as np
import faiss
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

def main():
    workspace_root = os.path.dirname(os.path.abspath(__file__))
    dataset_root = Path(workspace_root) / "mahGRs-main" / "GRs"
    data_dir = os.path.join(workspace_root, "backend", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    if not dataset_root.exists():
        print(f"Error: Local dataset not found at {dataset_root}")
        sys.exit(1)
        
    print("✓ Chunking dataset...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    all_files = list(dataset_root.rglob("*.txt"))
    
    chunks_data = []
    metadata = []
    for file in all_files:
        filename = file.name
        gr_id = filename.split(".")[0]
        department = file.parent.name
        language = "mr" if ".mr." in filename else "en"
        
        # Build metadata list
        metadata.append({
            "gr_id": gr_id,
            "department": department,
            "language": language,
            "filename": filename,
            "path": str(file)
        })

        try:
            with open(file, "r", encoding="utf-8") as f:
                text = f.read()
            chunks = splitter.split_text(text)
            for idx, chunk in enumerate(chunks):
                chunks_data.append({
                    "gr_id": gr_id,
                    "department": department,
                    "language": language,
                    "chunk_id": idx,
                    "text": chunk
                })
        except Exception as e:
            print(f"Skipping {filename}: {e}")
            
    print(f"Created {len(chunks_data)} chunks.")
    
    # Save metadata.json
    metadata_path = os.path.join(data_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved metadata to {metadata_path}")
        
    print("✓ Generating embeddings (this may take some time)...")
    model = SentenceTransformer("intfloat/multilingual-e5-base")
    texts = ["passage: " + chunk["text"] for chunk in chunks_data]
    
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True)
    
    print("✓ Building FAISS index...")
    faiss.normalize_L2(embeddings)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    
    # Save index.faiss and chunks.pkl to backend/data/
    index_out = os.path.join(data_dir, "index.faiss")
    chunks_pkl_out = os.path.join(data_dir, "chunks.pkl")
    
    faiss.write_index(index, index_out)
    with open(chunks_pkl_out, "wb") as f:
        pickle.dump(chunks_data, f)
        
    print("✓ Embedding regeneration complete. Backend ready.")

if __name__ == "__main__":
    main()
