from pathlib import Path

DATASET_ROOT = Path("/Users/avomine/VSCode/nirnai/mahGRs-main/GRs")

all_files = list(DATASET_ROOT.rglob("*.txt"))

sample = all_files[0]

# Department
department = sample.parent.name

# Filename
filename = sample.name

# Language (mr or en)
language = "mr" if ".mr." in filename else "en"

# GR ID
gr_id = filename.split(".")[0]

print("Department :", department)
print("Language   :", language)
print("GR ID      :", gr_id)
print("Filename   :", filename)
print("Full Path  :", sample)