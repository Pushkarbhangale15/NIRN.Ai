import os
import sys
import subprocess
import shutil

def main():
    print("✓ Checking embeddings...")
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "data")
    
    required_files = ["index.faiss", "chunks.pkl", "metadata.json"]
    missing = [f for f in required_files if not os.path.exists(os.path.join(data_dir, f))]
    
    if not missing:
        print("✓ Backend ready.")
        return

    print("Embedding data not found.")
    print("✓ Downloading embeddings...")
    
    # 1. Ensure gdown is installed
    try:
        import gdown
    except ImportError:
        print("Installing gdown...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])
            import gdown
        except Exception as e:
            print("Unable to download prebuilt embeddings.")
            print("Suggest: python build_embeddings.py to regenerate the embeddings locally.")
            sys.exit(1)

    # 2. Download from Google Drive
    folder_url = "https://drive.google.com/drive/folders/1f__XsLWW8hEV19uNNgkhRVyWIim7dwNB"
    try:
        # Download to data_dir
        os.makedirs(data_dir, exist_ok=True)
        gdown.download_folder(url=folder_url, output=data_dir, quiet=False)
        print("✓ Extracting...")
        
        # Move files from backend/data/data/ to backend/data/
        nested_data_dir = os.path.join(data_dir, "data")
        if os.path.exists(nested_data_dir):
            for file_name in os.listdir(nested_data_dir):
                shutil.move(os.path.join(nested_data_dir, file_name), os.path.join(data_dir, file_name))
            shutil.rmtree(nested_data_dir)
            
        # 3. Build index.faiss and chunks.pkl if missing
        embeddings_path = os.path.join(data_dir, "embeddings.npy")
        chunks_json_path = os.path.join(data_dir, "chunks.json")
        
        if os.path.exists(embeddings_path) and os.path.exists(chunks_json_path):
            import numpy as np
            import faiss
            import json
            import pickle

            index_out = os.path.join(data_dir, "index.faiss")
            chunks_pkl_out = os.path.join(data_dir, "chunks.pkl")

            embeddings = np.load(embeddings_path)
            faiss.normalize_L2(embeddings)
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatIP(dimension)
            index.add(embeddings)
            faiss.write_index(index, index_out)

            with open(chunks_json_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            with open(chunks_pkl_out, "wb") as f:
                pickle.dump(chunks, f)

            # Cleanup large raw source files to save disk space
            os.remove(embeddings_path)
            os.remove(chunks_json_path)

        # Remove extra screen shot if downloaded
        screenshot_path = os.path.join(data_dir, "Screenshot 2026-07-26 at 4.48.58 PM.png")
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)

        # 4. Verification
        print("✓ Verifying...")
        still_missing = [f for f in required_files if not os.path.exists(os.path.join(data_dir, f))]
        if still_missing:
            missing_str = ", ".join(still_missing)
            print(f"Error: Verification failed. Missing files: {missing_str}")
            sys.exit(1)

        print("✓ Backend ready.")
        
    except Exception as e:
        print("Unable to download prebuilt embeddings.")
        print(f"Details: {e}")
        print("Suggest: python build_embeddings.py to regenerate the embeddings locally.")
        sys.exit(1)

if __name__ == "__main__":
    main()
