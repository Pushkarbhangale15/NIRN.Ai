"""
Second attempt: IndexIVFPQ gave only ~30% recall even exhaustively (PQ compression too lossy
for this embedding space). Switching to IVF + Scalar Quantization (int8 per-dimension) instead
of Product Quantization -- less aggressive compression (~4x vs PQ's ~32x) but should preserve
much more similarity fidelity since it quantizes each dimension independently rather than
replacing sub-vectors with codebook entries.
"""
import time
import numpy as np
import faiss

t_start = time.time()

print("Loading flat index (mmap mode)...")
t0 = time.time()
index = faiss.read_index("data/index.faiss", faiss.IO_FLAG_MMAP)
print(f"  loaded in {time.time()-t0:.1f}s")

d = index.d
n = index.ntotal
print(f"d={d}  n={n}")

N_BLOCKS = 40
BLOCK_SIZE = 7_500
TRAIN_SIZE = N_BLOCKS * BLOCK_SIZE

print(f"\nReconstructing {TRAIN_SIZE} training vectors from {N_BLOCKS} evenly-spaced blocks...")
t0 = time.time()
starts = np.linspace(0, n - BLOCK_SIZE, N_BLOCKS, dtype=np.int64)
train_blocks = [index.reconstruct_n(int(s), BLOCK_SIZE) for s in starts]
train_vectors = np.concatenate(train_blocks, axis=0)
del train_blocks
print(f"Training set ready: {train_vectors.shape}  ({time.time()-t0:.1f}s)")

NLIST = 4096
quantizer = faiss.IndexFlatIP(d)
ivfsq = faiss.IndexIVFScalarQuantizer(
    quantizer, d, NLIST, faiss.ScalarQuantizer.QT_8bit, faiss.METRIC_INNER_PRODUCT
)

print(f"\nTraining IVF-SQ8 (nlist={NLIST})...")
t0 = time.time()
ivfsq.train(train_vectors)
print(f"Trained in {time.time()-t0:.1f}s")
del train_vectors

BATCH_SIZE = 50_000
print(f"\nAdding all {n} vectors in batches of {BATCH_SIZE}...")
t0 = time.time()
for start in range(0, n, BATCH_SIZE):
    end = min(start + BATCH_SIZE, n)
    batch = index.reconstruct_n(start, end - start)
    ivfsq.add(batch)
    del batch
    if (start // BATCH_SIZE) % 10 == 0:
        print(f"  {end}/{n} ({100*end/n:.1f}%)  {time.time()-t0:.1f}s elapsed")

print(f"\nAdded all vectors in {time.time()-t0:.1f}s")
print(f"ivfsq.ntotal = {ivfsq.ntotal}  (expected {n})")
assert ivfsq.ntotal == n

ivfsq.nprobe = 32

out_path = "data/index_ivfsq.faiss"
faiss.write_index(ivfsq, out_path)

import os
size_mb = os.path.getsize(out_path) / (1024 * 1024)
print(f"\nSaved {out_path}  ({size_mb:.1f} MB, was ~8640 MB)")
print(f"Total conversion time: {time.time()-t_start:.1f}s")
