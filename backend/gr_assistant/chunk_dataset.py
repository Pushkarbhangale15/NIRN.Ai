from pathlib import Path
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATASET_ROOT = Path("/Users/avomine/VSCode/nirnai/mahGRs-main/GRs")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
)

all_files = list(DATASET_ROOT.rglob("*.txt"))[:100]

chunks_data = []

for file in all_files:
    filename = file.name

    gr_id = filename.split(".")[0]
    department = file.parent.name
    language = "mr" if ".mr." in filename else "en"

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

with open("data/chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunks_data, f, ensure_ascii=False, indent=2)

print("Saved to data/chunks.json")