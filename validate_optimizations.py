import asyncio
import os
import sys
import time
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from config import settings
from llm import call_model, detect_conflicts, _cache
import prompts
from schemas import CorpusHit

def measure_ollama():
    try:
        r = httpx.get("http://localhost:11434/api/tags")
        if r.status_code != 200:
            print("Ollama not running or model not found.")
    except Exception:
        print("Ollama not running.")

async def validate():
    print("Validating optimizations...")
    measure_ollama()
    
    draft_prompt_en = prompts.build_draft_prompt("en")
    print(f"\nDraft Prompt length: {len(draft_prompt_en)} chars")
    
    # 1. Benchmark Old Prompts vs New Prompts for Draft
    user_msg = "Draft a GR regarding regulation of management quota admissions in private unaided engineering colleges. Max 15% sanctioned intake."
    
    t0 = time.perf_counter()
    draft_new = call_model(draft_prompt_en, f"Input:\n- User Prompt: {user_msg}\n- Issuing Department: Higher Education\n- Language: en\n- Retrieved Context:\n")
    t1 = time.perf_counter()
    
    print(f"Draft Generation (New): {t1-t0:.2f}s, {len(draft_new)} chars")
    
    # 2. Benchmark Sequential vs Unified Conflicts
    sample_clauses = [
        "Management quota shall not exceed 15% of sanctioned intake.",
        "Prior approval from Commissioner is required.",
        "Merit-based selection is mandatory."
    ]
    candidates = [
        CorpusHit(gr_id="1", title="A", department="Dept", snippet="Management quota is capped at 10%.", score=0.9, source_url=""),
        CorpusHit(gr_id="2", title="B", department="Dept", snippet="Commissioner approval not needed for engineering.", score=0.8, source_url="")
    ] * 3 # 6 candidates total, 2 per clause
    
    settings.USE_UNIFIED_CONFLICT_PROMPT = False
    _cache._cache.clear()
    t0 = time.perf_counter()
    conflicts_seq = detect_conflicts(sample_clauses, candidates, "en")
    t1 = time.perf_counter()
    print(f"Conflict Detection (Sequential): {t1-t0:.2f}s, {len(conflicts_seq)} conflicts")
    
    settings.USE_UNIFIED_CONFLICT_PROMPT = True
    _cache._cache.clear()
    t0 = time.perf_counter()
    conflicts_uni = detect_conflicts(sample_clauses, candidates, "en")
    t1 = time.perf_counter()
    print(f"Conflict Detection (Unified): {t1-t0:.2f}s, {len(conflicts_uni)} conflicts")
    
    # Print comparison
    print("\n--- RESULTS ---")
    print(f"Sequential Conf Count: {len(conflicts_seq)}")
    print(f"Unified Conf Count: {len(conflicts_uni)}")
    
if __name__ == "__main__":
    asyncio.run(validate())
