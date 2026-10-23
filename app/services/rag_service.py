"""
RAG (Retrieval-Augmented Generation) Service

Integrates with Groq LLM for:
- Intelligent resume parsing and extraction
- Context-aware question generation based on resume content
- Resume analysis and skill assessment
"""

import json
import logging
import os
import re
import math
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
import json
import logging
from typing import Any, Dict, List, Optional
import hashlib

logger = logging.getLogger(__name__)


class SimpleEmbeddings:
    """Simple TF-IDF based embeddings - no heavy ML dependencies."""
    
    def __init__(self):
        self.vocabulary = {}
        self.idf = {}
        self.document_vectors = []
        self.documents = []
        self.fitted = False
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer - split on non-alphanumeric."""
        # Convert to lowercase and split on non-alphanumeric
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter out very short words and common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs'}
        return [w for w in words if len(w) > 2 and w not in stop_words]
    
    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute term frequency for a document."""
        tf = {}
        total = len(tokens)
        if total == 0:
            return tf
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1.0 / total
        return tf
    
    def fit_transform(self, documents: List[str]):
        """Fit vectorizer and transform documents."""
        self.documents = documents
        self.fitted = True
        
        # Build vocabulary and compute IDF
        doc_count = len(documents)
        df = {}  # document frequency
        
        # First pass: compute document frequency for each term
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                df[token] = df.get(token, 0) + 1
        
        # Compute IDF
        N = len(documents)
        self.idf = {}
        for term, df_count in df.items():
            self.idf[term] = math.log((N + 1) / (df_count + 1)) + 1.0
        
        # Compute TF-IDF vectors for each document
        self.document_vectors = []
        for doc in documents:
            tokens = self._tokenize(doc)
            tf = self._compute_tf(tokens)
            vec = {}
            for term, tf_val in tf.items():
                if term in self.idf:
                    vec[term] = tf_val * self.idf[term]
            self.document_vectors.append(vec)
        
        self.fitted = True
        self.documents = documents
        return self
    
    def transform(self, documents: List[str]):
        """Transform new documents using fitted vectorizer."""
        if not self.fitted:
            return self.fit_transform(documents)
        
        vectors = []
        for doc in documents:
            tokens = self._tokenize(doc)
            tf = self._compute_tf(tokens)
            vec = {}
            for term, tf_val in tf.items():
                if term in self.idf:
                    vec[term] = tf_val * self.idf[term]
            vectors.append(vec)
        return vectors
    
    def similarity_search(self, query: str, top_k: int = 5) -> List[tuple]:
        """Find most similar documents to query."""
        if not self.fitted:
            return []
        
        # Tokenize query
        query_tokens = self._tokenize(query)
        query_tf = {}
        for token in query_tokens:
            query_tf[token] = query_tokens.count(token) / len(query_tokens)
        
        # Compute query vector
        query_vec = {}
        for term, tf_val in query_tf.items():
            if term in self.idf:
                query_vec[term] = query_tf[term] * self.idf.get(term, 1.0)
        
        # Compute cosine similarity with all documents
        similarities = []
        for i, doc_vec in enumerate(self.document_vectors):
            # Compute dot product
            dot_product = sum(query_vec.get(term, 0) * doc_vec.get(term, 0) for term in query_vec)
            
            # Compute magnitudes
            query_mag = math.sqrt(sum(v*v for v in query_vec.values()))
            doc_mag = math.sqrt(sum(v*v for v in self.document_vectors[i].values()))
            
            if query_mag > 0 and doc_mag > 0:
                sim = dot_product / (query_mag * doc_mag)
            else:
                sim = 0
            similarities.append((i, sim))
        
        # Get top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, sim in similarities[:top_k]:
            if sim > 0.05:  # Minimum similarity threshold
                results.append((self.documents[idx], sim))
        
        return results
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer - split on non-alphanumeric."""
        # Convert to lowercase and split on non-alphanumeric
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter out very short words and common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs'}
        return [w for w in words if len(w) > 2 and w not in stop_words]
    
    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute term frequency for a document."""
        tf = {}
        total = len(tokens)
        if total == 0:
            return tf
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1.0 / total
        return tf


class RAGOrchestrator:
    """Orchestrates RAG pipeline for resume analysis and question generation."""
    
    def __init__(
        self, 
        groq_api_key: str, 
        openai_api_key: Optional[str] = None,
        persist_dir: str = "./chroma_db",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        Initialize RAG orchestrator with LLM and embeddings.
        
        Args:
            groq_api_key: Groq API key for LLM
            openai_api_key: Optional OpenAI API key (not used for embeddings now)
            persist_dir: Directory to persist vector database
            embedding_model: Not used - kept for compatibility
        """
        # Use Groq client directly (avoid llama_index transformers dependency)
        from groq import Groq
        
        self.groq_client = Groq(api_key=groq_api_key)
        self.model = "openai/gpt-oss-120b"
        
        # Simple TF-IDF based embeddings (no heavy ML dependencies)
        self.embeddings = SimpleEmbeddings()
        
        self.index = None
        self.embeddings_index = None
        
        logger.info("RAG Orchestrator initialized with TF-IDF embeddings")

    def _complete(self, prompt: str, temperature: float = 0.3, max_tokens: int = 2000) -> str:
        """Call Groq LLM for completion."""
        from groq import Groq
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content or ""
    
    def parse_resume(self, file_bytes: bytes) -> Dict[str, Any]:
        """
        Parse PDF resume using PyMuPDF and extract structured information.
        """
        try:
            # Extract text from PDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            full_text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                full_text += str(page.get_text())
            doc.close()
            
            # Use Groq to extract structured information
            extraction_prompt = """
            Analyze this resume and extract the following information in JSON format:
            {
                "skills": ["skill1", "skill2", ...],
                "projects": [
                    {"name": "project name", "description": "brief description", "technologies": ["tech1", "tech2"]},
                    ...
                ],
                "experience": [
                    {"position": "title", "company": "name", "duration": "period", "description": "summary"},
                    ...
                ],
                "education": [
                    {"degree": "type", "institution": "name", "field": "field of study"},
                    ...
                ],
                "summary": "brief professional summary"
            }
            
            Resume Content:
            {resume_text}
            
            Return ONLY valid JSON, no additional text.
            """.format(resume_text=full_text[:8000])
            
            response_text = self._complete(extraction_prompt)
            
            # Clean up response text
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON response
            try:
                extracted_data = json.loads(cleaned_text)
            except json.JSONDecodeError:
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
    
    def _fallback_extraction(self, text: str) -> Dict[str, Any]:
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
        Build vector index from resume content for semantic search.
        
        Args:
            resume_text: Full resume text content
        """
        try:
            # Simple text splitter - no llama_index dependency
            chunks = self._split_text(resume_text, chunk_size=512, overlap=50)
            
            # Filter out very short chunks
            chunks = [c for c in chunks if len(c.strip()) > 50]
            
            if chunks:
                self.embeddings.fit_transform(chunks)
                logger.info(f"Built TF-IDF index with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Failed to build resume index: {str(e)}")
    
    def _split_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        if overlap >= chunk_size:
            overlap = chunk_size - 1
            
        chunks = []
        start = 0
        text_len = len(text)
        max_chunks = 1000  # Safety limit
        
        while start < len(text) and len(chunks) < max_chunks:
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            
            next_start = end - overlap
            if next_start <= start:  # Prevent infinite loop
                start = end
            else:
                start = next_start
                
            if start >= len(text):
                break
        
        return chunks


    def build_index_from_resume_data(self, resume_data: Dict[str, Any]) -> None:
        """
        Build vector index from extracted resume data.
        
        Args:
            resume_data: Parsed resume data from parse_resume()
        """
        # Combine all relevant text from resume data
        text_parts = []
        
        if resume_data.get("skills"):
            text_parts.append("Skills: " + ", ".join(resume_data["skills"]))
        
        if resume_data.get("projects"):
            for proj in resume_data["projects"]:
                if isinstance(proj, dict):
                    text_parts.append(f"Project: {proj.get('name', '')} - {proj.get('description', '')} Technologies: {', '.join(proj.get('technologies', []))}")
        
        if resume_data.get("experience"):
            for exp in resume_data["experience"]:
                if isinstance(exp, dict):
                    text_parts.append(f"Experience: {exp.get('position', '')} at {exp.get('company', '')} - {exp.get('description', '')}")
        
        if resume_data.get("education"):
            for edu in resume_data["education"]:
                if isinstance(edu, dict):
                    text_parts.append(f"Education: {edu.get('degree', '')} from {edu.get('institution', '')} in {edu.get('field', '')}")
        
        if resume_data.get("summary"):
            text_parts.append(f"Summary: {resume_data['summary']}")
        
        full_text = "\n\n".join(text_parts)
        
        if full_text.strip():
            self.build_resume_index(full_text)
        else:
            logger.warning("No text content to build index from")
    
    def _semantic_search(self, query: str, top_k: int = 5) -> List[str]:
        """
        Perform semantic search on resume index.
        
        Args:
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            List of relevant text chunks
        """
        if not self.embeddings.fitted:
            logger.warning("Embeddings not fitted for semantic search")
            return []
        
        try:
            results = self.embeddings.similarity_search(query, top_k=top_k)
            
            results_text = [doc for doc, score in results]
            
            logger.info(f"Semantic search returned {len(results)} chunks for query: {query[:50]}")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            return []
    
    def generate_questions(
        self,
        resume_data: Dict,
        count: int = 12,
        difficulty: str = "medium"
    ) -> List[Dict]:
        """
        Generate interview questions using RAG - retrieve relevant chunks first,
        then generate questions based on relevant context.
        """
        try:
            # Build index from resume data if not already built
            if not self.embeddings.fitted:
                self.build_index_from_resume_data(resume_data)
            
            # Generate search queries based on resume data
            search_queries = self._generate_search_queries(resume_data, difficulty)
            
            # Retrieve relevant chunks for each query
            all_chunks = []
            for query in search_queries:
                chunks = self._semantic_search(query, top_k=3)
                all_chunks.extend(chunks)
            
            # Deduplicate chunks
            unique_chunks = list(dict.fromkeys(all_chunks))
            context = "\n\n---\n\n".join(unique_chunks[:10])  # Limit context size
            
            # If no chunks retrieved, fall back to full resume content
            if not unique_chunks:
                full_content = resume_data.get("full_content", "")
                context = full_content[:5000] if full_content else ""
            
            # Create prompt with retrieved context
            question_prompt = f"""
            Based on the candidate's resume context, generate {count} interview questions 
            with difficulty level: {difficulty}.
            
            Retrieved Resume Context (most relevant sections):
            {context}
            
            Candidate Profile Summary:
            - Skills: {', '.join(resume_data.get('skills', [])[:20])}
            - Summary: {resume_data.get('summary', '')[:300]}
            
            Generate questions that:
            1. Are relevant to their specific skills and experience
            2. Assess technical knowledge and problem-solving
            3. Include behavioral and situational questions
            4. Match the specified difficulty level: {difficulty}
            
            Return as JSON array of objects with fields:
            {{"question": "text", "difficulty": "level", "topic": "category", "type": "technical|behavioral|situational"}}
            """
            
            response_text = self._complete(question_prompt, temperature=0.4)
            
            try:
                questions = json.loads(response_text)
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
    
    def _generate_search_queries(self, resume_data: Dict, difficulty: str) -> List[str]:
        """Generate search queries based on resume data for semantic search."""
        queries = []
        
        # Skills-based queries
        skills = resume_data.get("skills", [])
        if skills:
            top_skills = skills[:10]
            queries.append(f"Technical questions about {' '.join(skills[:5])}")
            queries.append(f"Experience with {' '.join(skills[:5])}")
        
        # Project-based queries
        projects = resume_data.get("projects", [])
        if projects:
            for proj in projects[:3]:
                if isinstance(proj, dict) and proj.get("name"):
                    queries.append(f"Project experience with {proj.get('name', '')}")
        
        # Experience-based queries
        experience = resume_data.get("experience", [])
        if experience:
            for exp in experience[:2]:
                if isinstance(exp, dict) and exp.get("position"):
                    queries.append(f"Experience as {exp.get('position', '')}")
        
        # Difficulty-specific queries
        if difficulty == "hard":
            queries.append("Advanced technical challenges system design architecture")
            queries.append("Complex problem solving debugging optimization")
        elif difficulty == "medium":
            queries.append("Technical implementation best practices")
            queries.append("Code review debugging problem solving")
        else:
            queries.append("Basic technical concepts fundamentals")
            queries.append("Learning ability growth potential")
        
        return queries[:8]  # Limit number of queries
    
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
        if not self.embeddings.fitted:
            return "Resume index not initialized. Please build index first."
        
        try:
            chunks = self._semantic_search(query, top_k=5)
            if not chunks:
                return "No relevant information found in resume."
            
            context = "\n\n".join(chunks[:5])
            
            query_prompt = f"""
            Based on the following resume excerpts, answer the query.
            
            Context:
            {context}
            
            Query: {query}
            
            Answer concisely based only on the provided context.
            """
            
            return self._complete(query_prompt, temperature=0.2, max_tokens=500)
            
        except Exception as e:
            logger.error(f"Resume query failed: {str(e)}")
            return f"Error querying resume: {str(e)}"


def get_rag_orchestrator(groq_api_key: str, openai_api_key: Optional[str] = None) -> RAGOrchestrator:
    """Factory function to create RAG orchestrator."""
    return RAGOrchestrator(groq_api_key=groq_api_key, openai_api_key=openai_api_key)