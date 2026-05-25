"""
Resume parsing service for extracting skills and projects from PDF files.

Uses LlamaIndex with Groq LLM for intelligent resume parsing and analysis.
Provides both structure extracted data and generates adaptive interview questions
based on the candidate's skills and experience.
"""

import json
import logging
from typing import Dict, List

from config import *
from services.rag_service import RAGOrchestrator

logger = logging.getLogger(__name__)

# Initialize RAG orchestrator (singleton)
_rag_orchestrator = None

def get_rag_orchestrator() -> RAGOrchestrator:
    """Get or initialize the RAG orchestrator."""
    global _rag_orchestrator
    if _rag_orchestrator is None:
        _rag_orchestrator = RAGOrchestrator(
            groq_api_key=GROQ_API_KEY,
            openai_api_key=None
        )
    return _rag_orchestrator

def parse_resume(file_bytes: bytes) -> Dict[str, any]:
    """
    Parse a PDF resume file and extract structured information.
    
    Uses LlamaIndex with Groq LLM to intelligently extract:
    - Skills and technical competencies
    - Projects with descriptions and technologies
    - Work experience and roles
    - Educational background
    - Professional summary
    
    Args:
        file_bytes: Raw PDF file bytes in memory
        
    Returns:
        Dictionary with:
        - 'skills': List of extracted skills
        - 'projects': List of projects with details
        - 'experience': List of work experience
        - 'education': Educational background
        - 'summary': Professional summary
        - 'full_content': Complete extracted text
        
    Side Effects:
        Deletes file_bytes after extraction (memory cleanup).
    """
    try:
        rag = get_rag_orchestrator()
        extracted_data = rag.parse_resume(file_bytes)
        return extracted_data
        
    except Exception as e:
        logger.error(f"Resume parsing failed: {str(e)}")
        return {
            "skills": [],
            "projects": [],
            "experience": [],
            "education": [],
            "summary": "",
            "full_content": ""
        }
    finally:
        # Clean up memory
        if file_bytes:
            del file_bytes


def generate_interview_questions(
    resume_data: Dict,
    count: int = 12,
    difficulty: str = "medium"
) -> List[Dict]:
    """
    Generate adaptive interview questions based on resume content.
    
    Uses RAG to create questions tailored to the candidate's background,
    skills, and experience level.
    
    Args:
        resume_data: Output from parse_resume()
        count: Number of questions to generate
        difficulty: Question difficulty (easy, medium, hard)
        
    Returns:
        List of question objects with metadata
    """
    try:
        rag = get_rag_orchestrator()
        questions = rag.generate_questions(resume_data, count=count, difficulty=difficulty)
        return questions
        
    except Exception as e:
        logger.error(f"Question generation failed: {str(e)}")
        return []

