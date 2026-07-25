from pathlib import Path
import json

DATASET_ROOT = Path("/Users/avomine/VSCode/nirnai/mahGRs-main/GRs")

all_files = list(DATASET_ROOT.rglob("*.txt"))

metadata = []

for file in all_files:
    filename = file.name

    item = {
        "gr_id": filename.split(".")[0],
        "department": file.parent.name,
        "language": "mr" if ".mr." in filename else "en",
        "filename": filename,
        "path": str(file)
    }

    metadata.append(item)

output_path = Path("data") / "metadata.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print(f"Saved {len(metadata)} records to {output_path}")

