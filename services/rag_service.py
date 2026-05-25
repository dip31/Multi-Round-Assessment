"""
RAG (Retrieval-Augmented Generation) Service

Integrates LlamaIndex with Groq LLM for:
- Intelligent resume parsing and extraction
- Context-aware question generation based on resume content
- Resume analysis and skill assessment
"""

import json
import logging
from typing import Dict, List, Optional

from llama_index.core import Document, VectorStoreIndex, PromptTemplate
from llama_index.llms.groq import Groq

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """Orchestrates RAG pipeline for resume analysis and question generation."""
    
    def __init__(self, groq_api_key: str, openai_api_key: Optional[str] = None):
        """
        Initialize RAG orchestrator with LLM and embeddings.
        
        Args:
            groq_api_key: Groq API key for LLM
            openai_api_key: Optional OpenAI API key for embeddings (defaults to local)
        """
        self.groq_llm = Groq(api_key=groq_api_key, model="llama-3.3-70b-versatile")
        
        # Try to use OpenAI embeddings, fall back to local if not available
        try:
            if openai_api_key:
                try:
                    from llama_index.embeddings.openai import OpenAIEmbedding
                    self.embed_model = OpenAIEmbedding(api_key=openai_api_key)
                except ImportError:
                    logger.warning("OpenAI embeddings not available, using HuggingFace")
                    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
                    self.embed_model = HuggingFaceEmbedding(
                        model_name="sentence-transformers/all-MiniLM-L6-v2"
                    )
            else:
                from llama_index.embeddings.huggingface import HuggingFaceEmbedding
                self.embed_model = HuggingFaceEmbedding(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
        except Exception as e:
            logger.warning(f"Embedding model init failed: {str(e)}, using local fallback")
            try:
                from llama_index.embeddings.huggingface import HuggingFaceEmbedding
                self.embed_model = HuggingFaceEmbedding(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
            except Exception as e2:
                logger.error(f"Failed to load any embedding model: {str(e2)}")
                raise
        
        self.index = None
        self.query_engine = None
    
    def parse_resume(self, file_bytes: bytes) -> Dict[str, any]:
        """
        Parse PDF resume using LlamaIndex document parsing.
        
        Args:
            file_bytes: PDF file content as bytes
            
        Returns:
            Dictionary with extracted information:
            - skills: List of identified skills
            - projects: List of projects with descriptions
            - experience: Work experience summary
            - education: Educational background
            - full_content: Complete parsed text
        """
        try:
            # Extract text from PDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            full_text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                full_text += page.get_text()
            doc.close()
            
            # Create LlamaIndex document
            document = Document(text=full_text)
            
            # Use Groq to extract structured information
            extraction_prompt = PromptTemplate("""
            Analyze this resume and extract the following information in JSON format:
            {{
                "skills": ["skill1", "skill2", ...],
                "projects": [
                    {{"name": "project name", "description": "brief description", "technologies": ["tech1", "tech2"]}},
                    ...
                ],
                "experience": [
                    {{"position": "title", "company": "name", "duration": "period", "description": "summary"}},
                    ...
                ],
                "education": [
                    {{"degree": "type", "institution": "name", "field": "field of study"}},
                    ...
                ],
                "summary": "brief professional summary"
            }}
            
            Resume Content:
            {resume_text}
            
            Return ONLY valid JSON, no additional text.
            """)
            
            response = self.groq_llm.complete(
                extraction_prompt.format(resume_text=full_text)
            )
            
            # Parse JSON response
            try:
                extracted_data = json.loads(response.text)
            except json.JSONDecodeError:
                # If JSON parsing fails, use fallback extraction
                extracted_data = self._fallback_extraction(full_text)
            
            extracted_data["full_content"] = full_text
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
    
    def _fallback_extraction(self, text: str) -> Dict:
        """Fallback extraction using simple keyword matching."""
        skill_keywords = {
            "Python", "Java", "React", "FastAPI", "SQL", "Machine Learning",
            "Django", "Node.js", "TensorFlow", "Docker", "AWS", "Git",
            "JavaScript", "TypeScript", "PostgreSQL", "MongoDB", "C++",
            "Flask", "Kubernetes", "Redis", "REST API", "Data Structures",
            "Algorithms", "Computer Vision", "NLP", "Deep Learning"
        }
        
        found_skills = [skill for skill in skill_keywords if skill.lower() in text.lower()]
        
        return {
            "skills": found_skills,
            "projects": [],
            "experience": [],
            "education": [],
            "summary": text[:200] + "..." if len(text) > 200 else text,
        }
    
    def build_resume_index(self, resume_text: str) -> None:
        """
        Build vector index for resume content for RAG queries.
        
        Args:
            resume_text: Full resume text content
        """
        try:
            # Create document for indexing
            document = Document(text=resume_text)
            
            # Build vector index
            self.index = VectorStoreIndex.from_documents(
                [document],
                embed_model=self.embed_model,
            )
            
            # Create query engine with Groq LLM
            self.query_engine = self.index.as_query_engine(llm=self.groq_llm)
            
        except Exception as e:
            logger.error(f"Failed to build resume index: {str(e)}")
            self.index = None
            self.query_engine = None
    
    def generate_questions(
        self,
        resume_data: Dict,
        count: int = 12,
        difficulty: str = "medium"
    ) -> List[Dict]:
        """
        Generate interview questions based on resume content using RAG.
        
        Args:
            resume_data: Extracted resume data from parse_resume()
            count: Number of questions to generate (default 12)
            difficulty: Question difficulty level (easy, medium, hard)
            
        Returns:
            List of generated questions with metadata
        """
        try:
            # Build index from resume
            self.build_resume_index(resume_data.get("full_content", ""))
            
            # Create prompt for question generation
            question_prompt = f"""
            Based on the candidate's resume, generate {count} interview questions 
            with difficulty level: {difficulty}.
            
            Candidate Profile:
            - Skills: {', '.join(resume_data.get('skills', []))}
            - Projects: {json.dumps(resume_data.get('projects', []), indent=2)}
            - Experience: {json.dumps(resume_data.get('experience', []), indent=2)}
            - Summary: {resume_data.get('summary', '')}
            
            Generate questions that:
            1. Are relevant to their specific skills and experience
            2. Assess technical knowledge and problem-solving
            3. Include behavioral and situational questions
            4. Match the specified difficulty level
            
            Return as JSON array of objects with fields:
            {{"question": "text", "difficulty": "level", "topic": "category", "type": "technical|behavioral|situational"}}
            """
            
            response = self.groq_llm.complete(question_prompt)
            
            try:
                questions = json.loads(response.text)
                # Ensure questions have required fields
                validated_questions = []
                for q in questions:
                    if isinstance(q, dict) and "question" in q:
                        validated_questions.append({
                            "question": q.get("question", ""),
                            "difficulty": q.get("difficulty", difficulty),
                            "topic": q.get("topic", "General"),
                            "type": q.get("type", "technical")
                        })
                return validated_questions[:count]
            except json.JSONDecodeError:
                logger.warning("Failed to parse generated questions, returning defaults")
                return self._generate_default_questions(resume_data, count)
            
        except Exception as e:
            logger.error(f"Question generation failed: {str(e)}")
            return self._generate_default_questions(resume_data, count)
    
    def _generate_default_questions(self, resume_data: Dict, count: int) -> List[Dict]:
        """Generate default questions as fallback."""
        skills = resume_data.get("skills", [])
        
        default_questions = [
            {"question": f"Tell me about your experience with {skills[0] if skills else 'your technical skills'}", 
             "difficulty": "easy", "topic": "Experience", "type": "behavioral"},
            {"question": "Describe a challenging project you've worked on and how you overcame obstacles",
             "difficulty": "medium", "topic": "Problem Solving", "type": "behavioral"},
            {"question": "How do you approach learning new technologies?",
             "difficulty": "medium", "topic": "Learning", "type": "behavioral"},
            {"question": "Explain your understanding of software design principles",
             "difficulty": "hard", "topic": "Technical", "type": "technical"},
        ]
        
        return default_questions[:count]
    
    def query_resume(self, query: str) -> str:
        """
        Query the resume index for specific information.
        
        Args:
            query: Natural language query about the resume
            
        Returns:
            Response from the resume based on the query
        """
        if not self.query_engine:
            return "Resume index not initialized"
        
        try:
            response = self.query_engine.query(query)
            return str(response)
        except Exception as e:
            logger.error(f"Resume query failed: {str(e)}")
            return f"Error querying resume: {str(e)}"

