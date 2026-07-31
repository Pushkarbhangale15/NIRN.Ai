"""
profiler.py — Lightweight request-scoped performance timer for NIRN.Ai.

Enabled by setting PROFILE_PERFORMANCE=True (or "1" / "yes") in the
environment or .env file.  When disabled every call is a no-op so there
is zero runtime overhead in production.

Usage
-----
from profiler import perf, PROFILING_ENABLED

with perf("My Stage"):
    do_work()

# Nested stages
with perf("Outer Stage"):
    with perf("Inner Stage"):
        do_inner()

# Print the report at the end of a request
perf.report()
perf.reset()       # clear for the next request

Design notes
------------
* Uses time.perf_counter() — the highest-resolution timer available on
  the host platform.
* Thread-safe via a threading.local() slot so concurrent requests do not
  mix their timings.
* The singleton `perf` object is process-wide; callers on different
  threads each get their own private span stack and span list.
* When PROFILING_ENABLED is False, __enter__/__exit__ and report() are
  all true no-ops — no string formatting, no dict allocation.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager
from typing import Dict, List, Optional


# -----------------------------------------------------------------------
# Feature flag — check at import time, once.
# -----------------------------------------------------------------------

def _flag(name: str, default: bool = False) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off", ""):
        return default
    return default


PROFILING_ENABLED: bool = _flag("PROFILE_PERFORMANCE", default=False)


# -----------------------------------------------------------------------
# Span — one named timing entry
# -----------------------------------------------------------------------

class _Span:
    __slots__ = ("name", "parent", "start", "end", "children", "meta")

    def __init__(self, name: str, parent: Optional["_Span"]):
        self.name = name
        self.parent: Optional["_Span"] = parent
        self.start: float = time.perf_counter()
        self.end: float = 0.0
        self.children: List["_Span"] = []
        self.meta: Dict[str, object] = {}

    def stop(self) -> None:
        self.end = time.perf_counter()

    @property
    def elapsed(self) -> float:
        if self.end == 0.0:
            return time.perf_counter() - self.start
        return self.end - self.start

    def add_meta(self, **kwargs) -> None:
        self.meta.update(kwargs)


import contextvars

# -----------------------------------------------------------------------
# Context-local state (supports Starlette run_in_threadpool)
# -----------------------------------------------------------------------

_root_var = contextvars.ContextVar("profiler_root", default=None)
_stack_var = contextvars.ContextVar("profiler_stack", default=None)
_spans_var = contextvars.ContextVar("profiler_spans", default=None)


def _get_root() -> Optional[_Span]:
    return _root_var.get()


def _get_stack() -> List[_Span]:
    s = _stack_var.get()
    if s is None:
        s = []
        _stack_var.set(s)
    return s


def _get_spans() -> List[_Span]:
    s = _spans_var.get()
    if s is None:
        s = []
        _spans_var.set(s)
    return s


# -----------------------------------------------------------------------
# Context-manager interface
# -----------------------------------------------------------------------

class _PerfContext:
    """
    Context-manager that records a named timing span and nests correctly
    inside any currently active span on the same thread.

    This is a no-op when PROFILING_ENABLED is False.
    """

    def __init__(self, name: str):
        self.name = name
        self._span: Optional[_Span] = None

    def __enter__(self) -> "_PerfContext":
        if not PROFILING_ENABLED:
            return self
        stack = _get_stack()
        parent = stack[-1] if stack else None
        span = _Span(self.name, parent)
        if parent is not None:
            parent.children.append(span)
        else:
            # root-level span — store as the request root
            _root_var.set(span)
        stack.append(span)
        _get_spans().append(span)
        self._span = span
        return self

    def __exit__(self, *_) -> None:
        if not PROFILING_ENABLED or self._span is None:
            return
        self._span.stop()
        _get_stack().pop()

    def meta(self, **kwargs) -> None:
        """Attach arbitrary metadata to this span (e.g. clause count)."""
        if PROFILING_ENABLED and self._span is not None:
            self._span.add_meta(**kwargs)


# -----------------------------------------------------------------------
# Singleton helper that also exposes reset() and report()
# -----------------------------------------------------------------------

class _Profiler:
    """
    Process-wide profiler singleton.

    Use as a context manager::

        with perf("Stage Name"):
            ...

    Or call directly::

        ctx = perf("Stage Name")
        ctx.__enter__()
        ...
        ctx.__exit__(None, None, None)

    Print the report and clear state between requests::

        perf.report()
        perf.reset()
    """

    def __call__(self, name: str) -> _PerfContext:
        return _PerfContext(name)

    def inject(self, name: str, duration_s: float, **meta) -> None:
        """Inject a completed span into the current active span (or root)."""
        if not PROFILING_ENABLED:
            return
        stack = _get_stack()
        parent = stack[-1] if stack else None
        span = _Span(name, parent)
        span.end = span.start + duration_s
        if parent is not None:
            parent.children.append(span)
        else:
            if _root_var.get() is None:
                _root_var.set(span)
        _get_spans().append(span)
        if meta:
            span.add_meta(**meta)

    def current_meta(self, **kwargs) -> None:
        """Attach arbitrary metadata to the CURRENT active span on the stack."""
        if not PROFILING_ENABLED:
            return
        stack = _get_stack()
        if stack:
            stack[-1].add_meta(**kwargs)

    # ----------------------------------------------------------------
    # get_all_meta(), get_report_string() and report()
    # ----------------------------------------------------------------

    def get_all_meta(self) -> List[Dict[str, Any]]:
        """Extract all metadata dicts from the tree, in order."""
        root = _get_root()
        if not root:
            return []
            
        out = []
        def _traverse(s: _Span):
            if s.meta:
                out.append(s.meta)
            for c in s.children:
                _traverse(c)
                
        _traverse(root)
        return out

    def get_report_string(self) -> str:
        """Returns the formatted report as a string, or empty if disabled."""
        if not PROFILING_ENABLED:
            return ""

        root = _get_root()
        all_spans = _get_spans()

        lines = []
        lines.append("")
        lines.append("=" * 52)
        lines.append("========== REQUEST PROFILE ==========")
        lines.append("=" * 52)

        if root is None:
            lines.append("  (no spans recorded)")
        else:
            self._render_span(root, lines, depth=0)

        lines.append("-" * 52)

        # BONUS summary
        llm_spans = [s for s in all_spans if s.name.startswith("Ollama Call")]
        embed_spans = [s for s in all_spans if s.name == "SentenceTransformer encode"]
        faiss_spans = [s for s in all_spans if s.name == "FAISS search"]
        rule_spans = [s for s in all_spans if s.name.startswith("Rule Engine")]
        clause_metas = [s.meta for s in all_spans if s.name.startswith("Clause")]

        if llm_spans or embed_spans:
            lines.append("")
            lines.append("  --- BONUS STATISTICS ---")

        if clause_metas:
            n_clauses = len(clause_metas)
            total_candidates = sum(int(m.get("candidates", 0)) for m in clause_metas)
            lines.append(f"  Clauses analysed  ......... {n_clauses}")
            lines.append(f"  Candidates retrieved ...... {total_candidates}")

        if llm_spans:
            llm_times = [s.elapsed for s in llm_spans]
            lines.append(f"  LLM calls total ........... {len(llm_times)}")
            lines.append(f"  Average LLM time .......... {sum(llm_times)/len(llm_times):.2f} s")
            lines.append(f"  Fastest LLM call .......... {min(llm_times):.2f} s")
            lines.append(f"  Slowest LLM call .......... {max(llm_times):.2f} s")

        if embed_spans:
            embed_times = [s.elapsed for s in embed_spans]
            lines.append(f"  Average embed time ........ {sum(embed_times)/len(embed_times):.2f} s")

        if faiss_spans:
            faiss_times = [s.elapsed for s in faiss_spans]
            lines.append(f"  Average FAISS time ........ {sum(faiss_times)/len(faiss_times):.4f} s")

        if rule_spans:
            rule_times = [s.elapsed for s in rule_spans]
            lines.append(f"  Average rule-engine time .. {sum(rule_times)/len(rule_times):.4f} s")

        lines.append("")
        lines.append("-" * 52)
        if root is not None:
            total = root.elapsed
            lines.append(f"  TOTAL REQUEST ............. {total:>7.3f} s")
        lines.append("=" * 52)
        lines.append("")
        return "\n".join(lines)

    def report(self) -> None:
        """Prints the report to stderr."""
        report_str = self.get_report_string()
        if report_str:
            print(report_str, file=sys.stderr, flush=True)

    # ----------------------------------------------------------------
    # reset()
    # ----------------------------------------------------------------

    def reset(self) -> None:
        if not PROFILING_ENABLED:
            return
        _root_var.set(None)
        _stack_var.set([])
        _spans_var.set([])

    # ----------------------------------------------------------------
    # render tree
    # ----------------------------------------------------------------

    def _render_span(self, span: _Span, lines: list, depth: int) -> None:
        indent = "    " * depth
        label = span.name
        elapsed = span.elapsed
        # Dot leader fills to column 42 minus indent and label length
        label_col = 40 - len(indent)
        dots = "." * max(1, label_col - len(label))
        lines.append(f"  {indent}{label} {dots} {elapsed:>7.3f} s")
        
        for child in span.children:
            self._render_span(child, lines, depth + 1)


# -----------------------------------------------------------------------
# Public singleton
# -----------------------------------------------------------------------

perf: _Profiler = _Profiler()
