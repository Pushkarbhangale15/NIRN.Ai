import pickle
from collections import Counter

with open("vector_db/chunks.pkl", "rb") as f:
    chunks = pickle.load(f)

dept_counts = Counter(chunk.get("department", "Unknown") for chunk in chunks)

print("Total chunks:", len(chunks))
print("Departments:", len(dept_counts))

for dept, count in dept_counts.items():
    print(f"{dept}: {count}")