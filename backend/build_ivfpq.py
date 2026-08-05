"""
One-time local conversion: IndexFlatIP (9GB, exact) -> IndexIVFPQ (compressed, approximate).

Root cause being fixed: the flat index doesn't fit comfortably in this machine's 16GB RAM
alongside the embedding model, chunk metadata, and Ollama's gemma3:4b, causing real disk-swap
thrashing on every brute-force search (confirmed via vm_stat: ~2GB swapped in during a single
5s search). IVFPQ shrinks resident memory ~30x and searches only a few clusters instead of
scanning all 2.95M vectors, fixing both the memory pressure and the raw compute cost.

Reconstructs vectors directly from the existing index.faiss -- no re-embedding needed.
"""
import time
import numpy as np
import faiss

t_start = time.time()

print("Loading flat index (mmap mode)...")
t0 = time.time()
try:
    index = faiss.read_index("data/index.faiss", faiss.IO_FLAG_MMAP)
    print(f"  loaded with mmap in {time.time()-t0:.1f}s")
except Exception as e:
    print(f"  mmap load failed ({e}); falling back to normal load")
    index = faiss.read_index("data/index.faiss")
    print(f"  loaded (no mmap) in {time.time()-t0:.1f}s")

d = index.d
n = index.ntotal
print(f"d={d}  n={n}")

# --- Build a training sample from evenly-spaced contiguous blocks across the whole corpus ---
# Vectors were added department-by-department during the merge step, so a sample confined to
# the first N vectors would only cover a few departments. Evenly-spaced blocks give coverage
# across the whole corpus while still using fast reconstruct_n() range calls instead of ~300k
# individual reconstruct() calls.
N_BLOCKS = 40
BLOCK_SIZE = 7_500
TRAIN_SIZE = N_BLOCKS * BLOCK_SIZE

print(f"\nReconstructing {TRAIN_SIZE} training vectors from {N_BLOCKS} evenly-spaced blocks...")
t0 = time.time()
starts = np.linspace(0, n - BLOCK_SIZE, N_BLOCKS, dtype=np.int64)
train_blocks = []
for i, s in enumerate(starts):
    block = index.reconstruct_n(int(s), BLOCK_SIZE)
    train_blocks.append(block)
    if i % 10 == 0:
        print(f"  block {i}/{N_BLOCKS}  ({time.time()-t0:.1f}s elapsed)")
train_vectors = np.concatenate(train_blocks, axis=0)
del train_blocks
print(f"Training set ready: {train_vectors.shape}  ({time.time()-t0:.1f}s)")

# --- Build and train the IVFPQ index ---
NLIST = 4096   # coarse clusters (~4x sqrt(n) for n=2.95M)
M = 96         # PQ subquantizers (768 / 96 = 8 dims each) -> ~96 bytes/vector, ~32x compression
NBITS = 8      # bits per subquantizer code (256 centroids each)

quantizer = faiss.IndexFlatIP(d)
ivfpq = faiss.IndexIVFPQ(quantizer, d, NLIST, M, NBITS, faiss.METRIC_INNER_PRODUCT)

print(f"\nTraining IVFPQ (nlist={NLIST}, m={M}, nbits={NBITS})...")
t0 = time.time()
ivfpq.train(train_vectors)
print(f"Trained in {time.time()-t0:.1f}s")
del train_vectors

# --- Add all vectors in batches (bounds peak memory instead of reconstructing all 9GB at once) ---
BATCH_SIZE = 50_000
print(f"\nAdding all {n} vectors in batches of {BATCH_SIZE}...")
t0 = time.time()
for start in range(0, n, BATCH_SIZE):
    end = min(start + BATCH_SIZE, n)
    batch = index.reconstruct_n(start, end - start)
    ivfpq.add(batch)
    del batch
    if (start // BATCH_SIZE) % 10 == 0:
        elapsed = time.time() - t0
        pct = 100 * end / n
        print(f"  {end}/{n} ({pct:.1f}%)  {elapsed:.1f}s elapsed")

print(f"\nAdded all vectors in {time.time()-t0:.1f}s")
print(f"ivfpq.ntotal = {ivfpq.ntotal}  (expected {n})")
assert ivfpq.ntotal == n, "vector count mismatch after add!"

ivfpq.nprobe = 32  # clusters searched per query -- tunable recall/speed tradeoff

out_path = "data/index_ivfpq.faiss"
faiss.write_index(ivfpq, out_path)
print(f"\nSaved {out_path}")

import os
size_mb = os.path.getsize(out_path) / (1024 * 1024)
print(f"New index size: {size_mb:.1f} MB (was ~8640 MB)")
print(f"\nTotal conversion time: {time.time()-t_start:.1f}s")
