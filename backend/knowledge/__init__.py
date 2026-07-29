"""
knowledge module — Government Knowledge Base service package.

Provides a unified KnowledgeService singleton for terminology, departments,
designations, phrases, and budget heads across the NIRN.Ai backend.
"""

from .loader import KnowledgeBaseLoadError
from .service import KnowledgeService, get_knowledge_service, knowledge_service

__all__ = [
    "KnowledgeService",
    "get_knowledge_service",
    "knowledge_service",
    "KnowledgeBaseLoadError",
]
