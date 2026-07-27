from typing import List
import llm
import retrieval
from config import settings

from .models import ConflictReportItem
from .rule_engine import check_deterministic_conflicts
from .llm_verifier import verify_conflict_with_llm

def detect_cross_department_conflicts(body_text: str) -> List[ConflictReportItem]:
    """
    Two-stage pipeline to detect policy, funding, authority, timeline, and operational
    conflicts between the draft GR text and existing GRs in the corpus.
    
    1. Splits the draft GR into clauses.
    2. Retrieves Top-K similar clauses from the vector DB.
    3. Runs Rule Engine for deterministic matches.
    4. Runs LLM Verification Layer for remaining semantic/ambiguous relations.
    """
    clauses = llm.split_into_clauses(body_text)
    if not clauses:
        return []
        
    conflicts: List[ConflictReportItem] = []
    
    # Process each clause to locate conflicts
    for clause in clauses[:settings.MAX_CLAUSES_ANALYSED]:
        # Search for semantically similar candidates across all departments
        candidates = retrieval.search(clause, top_k=settings.CANDIDATES_PER_CLAUSE)
        
        for hit in candidates:
            # Stage 1: Deterministic Rule Engine
            det_conflict = check_deterministic_conflicts(
                draft_clause=clause,
                matched_gr_id=hit.gr_id,
                matched_gr_title=hit.title,
                matched_clause=hit.snippet
            )
            
            if det_conflict:
                conflicts.append(det_conflict)
                continue
                
            # Stage 2: LLM Verification for semantic ambiguity
            llm_conflict = verify_conflict_with_llm(
                draft_clause=clause,
                matched_gr_id=hit.gr_id,
                matched_gr_title=hit.title,
                matched_clause=hit.snippet
            )
            
            if llm_conflict:
                conflicts.append(llm_conflict)
                
    return conflicts
