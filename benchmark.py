#!/usr/bin/env python3
"""
benchmark.py — NIRN.Ai Full Request Benchmark (Pure Execution Mode)

Runs a single /api/copilot/draft request and reports ONLY directly measured
execution timings using the X-Performance-Profile header, as well as direct
Ollama server performance.

Zero projections. Zero estimates. Zero theoretical calculations.
"""

import base64
import re
import sys
import time
import httpx

SERVER_BASE = "http://localhost:8000"
OLLAMA_BASE = "http://localhost:11434"
DRAFT_ENDPOINT = "/api/copilot/draft"

BENCHMARK_PAYLOAD = {
    "prompt": (
        "Draft a Government Resolution regarding the regulation of management quota "
        "admissions in private unaided engineering colleges in Maharashtra. "
        "The resolution should specify that management quota shall not exceed 15% of "
        "sanctioned intake, require prior approval from the Commissioner of Technical "
        "Education, mandate transparent merit-based selection, and set penalties for "
        "violations including withdrawal of affiliation."
    ),
    "department": "Higher_and_Technical_Education_Department",
    "language": "english",
}

DIVIDER = "=" * 72

def extract_timing(profile_text: str, label_pattern: str) -> str:
    """Finds a line matching label_pattern and extracts the time value."""
    for line in profile_text.splitlines():
        if re.search(r"^\s*" + label_pattern + r"\s+\.+", line, re.IGNORECASE):
            match = re.search(r"([\d\.]+\s*s)", line)
            if match:
                return match.group(1)
    return "Not Measured"

def extract_all_timings(profile_text: str, label_pattern: str) -> list[str]:
    """Finds all lines matching label_pattern (e.g. for multiple Ollama calls)."""
    results = []
    for line in profile_text.splitlines():
        if re.search(r"^\s*" + label_pattern + r"\s+\.+", line, re.IGNORECASE):
            match = re.search(r"([\d\.]+\s*s)", line)
            if match:
                results.append(match.group(1))
    return results if results else ["Not Measured"]

def profile_ollama_direct():
    """Bypasses FastAPI entirely and measures raw Ollama performance."""
    print("\n" + DIVIDER)
    print("  DIRECT OLLAMA BENCHMARK (Optional)")
    print(DIVIDER)
    
    prompt = "Explain the architecture of a Retrieval Augmented Generation system."
    payload = {
        "model": "gemma3:4b",  # Typical dev fallback or local model
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    
    print("  [Sending direct HTTP POST to localhost:11434...]")
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
    except httpx.ConnectError:
        print("  ERROR: Ollama is not running on localhost:11434")
        return
    t1 = time.perf_counter()
    
    if resp.status_code != 200:
        print(f"  ERROR: Direct Ollama call failed: {resp.status_code}")
        return
        
    d = resp.json()
    total_time = t1 - t0
    
    p_eval_dur = d.get("prompt_eval_duration", 0)
    eval_dur = d.get("eval_duration", 0)
    p_eval_cnt = d.get("prompt_eval_count", 0)
    eval_cnt = d.get("eval_count", 0)
    
    p_tps = round(p_eval_cnt / (p_eval_dur / 1e9), 1) if p_eval_dur > 0 else 0
    e_tps = round(eval_cnt / (eval_dur / 1e9), 1) if eval_dur > 0 else 0
    
    print(f"  Total Wall Clock     : {total_time:.3f} s")
    print(f"  Reported Load Time   : {d.get('load_duration', 0) / 1e9:.3f} s")
    print(f"  Prompt Eval Time     : {p_eval_dur / 1e9:.3f} s  ({p_tps} tokens/s)")
    print(f"  Decode Time          : {eval_dur / 1e9:.3f} s  ({e_tps} tokens/s)")
    print(f"  Reported Total Time  : {d.get('total_duration', 0) / 1e9:.3f} s")
    print(f"  Prompt Tokens        : {p_eval_cnt}")
    print(f"  Generated Tokens     : {eval_cnt}")

def main():
    print(DIVIDER)
    print("  NIRN.Ai — PURE EXECUTION TIMING REPORT")
    print(f"  Generated: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(DIVIDER)

    print("\n  [Authenticating as admin...]")
    try:
        with httpx.Client(timeout=300.0) as client:
            auth_res = client.post(
                SERVER_BASE + "/api/auth/login",
                json={"login_id": "admin", "password": "admin123"},
                headers={"Content-Type": "application/json"}
            )
            auth_res.raise_for_status()
            token = auth_res.json()["access_token"]
            
            print("  [Sending benchmark request to server...]")
            t0 = time.perf_counter()
            response = client.post(
                SERVER_BASE + DRAFT_ENDPOINT,
                json=BENCHMARK_PAYLOAD,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
            )
            t1 = time.perf_counter()
    except httpx.ConnectError:
        print("  ERROR: Server is not running at", SERVER_BASE)
        return
    except Exception as e:
        print(f"  ERROR: Request failed: {e}")
        return
    
    if response.status_code != 200:
        print(f"  ERROR: Server returned {response.status_code}")
        print(f"  {response.text[:500]}")
        return

    payload = response.json()
    profile_b64 = response.headers.get("X-Performance-Profile", "")
    
    if not profile_b64:
        print("  ERROR: X-Performance-Profile header missing.")
        print("  Ensure PROFILE_PERFORMANCE=True in the backend .env file.")
        return

    profile_text = base64.b64decode(profile_b64).decode("utf-8")
    
    # Prompt size measurements directly from local text
    chars = len(BENCHMARK_PAYLOAD["prompt"])
    words = len(BENCHMARK_PAYLOAD["prompt"].split())
    bytes_size = len(BENCHMARK_PAYLOAD["prompt"].encode("utf-8"))
    
    print("\n" + DIVIDER)
    print("  0. INPUT STATISTICS (Actual Measurements)")
    print(DIVIDER)
    print(f"  Prompt Char Count    : {chars}")
    print(f"  Prompt Word Count    : {words}")
    print(f"  Prompt Byte Size     : {bytes_size}")
    print(f"  Prompt Token Count   : Not Measured") # Measured via raw Ollama metadata

    print("\n" + DIVIDER)
    print("  1. DRAFT GENERATION (Actual Measurements)")
    print(DIVIDER)
    print(f"  Prompt Construction  : {extract_timing(profile_text, 'Prompt Construction')}")
    print(f"  Ollama HTTP Request  : {extract_timing(profile_text, 'Ollama HTTP Roundtrip')}")
    print(f"  Response Parsing     : {extract_timing(profile_text, 'Response Parsing')}")
    print(f"  TOTAL Draft Gen      : {extract_timing(profile_text, 'Draft Generation')}")

    print("\n" + DIVIDER)
    print("  2. CONFLICT DETECTION (Actual Measurements)")
    print(DIVIDER)
    print(f"  Clause Splitting     : {extract_timing(profile_text, 'Split Clauses')}")
    print(f"  Batch Embedding      : {extract_timing(profile_text, 'Batch Embedding')}")
    print(f"  FAISS Search         : {extract_timing(profile_text, 'FAISS Search')}")
    
    # Unified Workflow paths vs Sequential paths
    if "Unified Ollama Call" in profile_text:
        print(f"  Prompt Construction  : {extract_timing(profile_text, 'Prompt Build')}")
        print(f"  Unified Ollama Call  : {extract_timing(profile_text, 'Unified Ollama Call')}")
        print(f"  JSON Parsing         : {extract_timing(profile_text, 'Ollama JSON Parsing')}")
        print(f"  Confidence Filtering : {extract_timing(profile_text, 'Confidence Filtering')}")
    else:
        # Sequential
        print(f"  Prompt Construction  : {extract_timing(profile_text, 'Prompt Build')}")
        ollama_calls = extract_all_timings(profile_text, r"Ollama Call \[\d+\]")
        for i, t in enumerate(ollama_calls, 1):
            if t != "Not Measured":
                print(f"  Ollama Call [{i}]      : {t}")
            else:
                print(f"  Ollama Calls         : Not Measured")
        
        print(f"  JSON Parsing         : {extract_timing(profile_text, 'Ollama JSON Parsing')}")
        print(f"  Confidence Filtering : {extract_timing(profile_text, 'Confidence Filter')}")
        
    print(f"  TOTAL Conflict Det.  : {extract_timing(profile_text, 'Conflict Detection')}")

    print("\n" + DIVIDER)
    print("  3. DATABASE PERSISTENCE (Actual Measurements)")
    print(DIVIDER)
    print(f"  Draft Insert         : {extract_timing(profile_text, 'Draft Insert')}")
    print(f"  Reference Insert     : {extract_timing(profile_text, 'Reference Insert')}")
    print(f"  Conflict Insert      : {extract_timing(profile_text, 'Conflict Insert')}")
    print(f"  TOTAL Database       : {extract_timing(profile_text, 'Database')}")

    print("\n" + DIVIDER)
    print("  4. RAW OLLAMA METRICS (Actual Measurements)")
    print(DIVIDER)
    
    metrics_b64 = response.headers.get("X-NIRN-Metrics", "")
    if metrics_b64:
        import json
        metrics_json = base64.b64decode(metrics_b64).decode("utf-8")
        payload = json.loads(metrics_json)
        
        if payload.get("version") != 1:
            print(f"  ERROR: Unsupported metrics version {payload.get('version')}")
        else:
            meta_list = payload.get("calls", [])
            call_idx = 1
            for m in meta_list:
                if "model" not in m and "prompt_tokens" not in m:
                    continue # Skip spans that have meta but aren't LLM metrics
                print(f"  [LLM Call {call_idx}]")
                print(f"    Purpose              : {m.get('purpose', 'Not Measured')}")
                print(f"    Model                : {m.get('model', 'Not Measured')}")
                print(f"    Prompt Tokens        : {m.get('prompt_tokens', 'Not Measured')}")
                print(f"    Generated Tokens     : {m.get('generated_tokens', 'Not Measured')}")
                print(f"    Load Duration        : {m.get('load_duration', 'Not Measured')}")
                print(f"    Prompt Eval Duration : {m.get('prompt_eval_duration', 'Not Measured')}")
                print(f"    Decode Duration      : {m.get('decode_duration', 'Not Measured')}")
                print(f"    Total Duration       : {m.get('total_duration', 'Not Measured')}")
                print(f"    Prefill Tokens/sec   : {m.get('prefill_tps', 'Not Measured')}")
                print(f"    Decode Tokens/sec    : {m.get('decode_tps', 'Not Measured')}")
                print()
                call_idx += 1
                
            if call_idx == 1:
                print("  No raw LLM metrics found in profile.")
    else:
        print("  ERROR: X-NIRN-Metrics header missing.")

    print("\n" + DIVIDER)
    print("  5. TOTAL REQUEST (Actual Measurements)")
    print(DIVIDER)
    print(f"  Client Round-Trip    : {t1 - t0:.3f} s")
    print(f"  Server TOTAL REQUEST : {extract_timing(profile_text, 'TOTAL REQUEST')}")
    print(DIVIDER)
    
    # Run direct optional benchmark
    profile_ollama_direct()
    
    print("\n  Raw Server Profiler Output:")
    print(profile_text)

if __name__ == "__main__":
    main()
