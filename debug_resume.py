import asyncio
import os
import fitz

def create_dummy_pdf():
    doc = fitz.open()
    page = doc.new_page()
    text = """John Doe
Software Engineer
Skills: Python, Java, React, SQL, FastAPI, Machine Learning.
Projects:
- AI Resume Analyzer: Built an AI resume parser using Python and Groq. Includes NLP.
- Portfolio Website: Developed a personal website using React and Tailwind CSS.
Experience:
- Software Engineer at Tech Corp (2020-2023). Worked on backend APIs in Java and Python.
Education:
- B.S. in Computer Science, State University, 2020."""
    page.insert_text((50, 50), text)
    doc.save("test_resume.pdf")
    doc.close()

async def main():
    create_dummy_pdf()
    
    with open("test_resume.pdf", "rb") as f:
        pdf_bytes = f.read()
    
    from app.services.resume_service import parse_resume
    from app.services.groq_service import GroqService
    from app.config.settings import settings
    
    print("Testing parse_resume...")
    try:
        extracted = parse_resume(pdf_bytes)
        print("Parsed data:", dict(extracted))
        skills = extracted.get("skills", [])
        projects = extracted.get("projects", [])
        
        # In case backend format expects projects as dict: { "name": "description" }
        # wait, the extraction template extracts projects as list of dicts: [ { "name": "...", "description": "...", "technologies": ["...", "..."] } ]
        print("Skills:", skills)
        print("Projects:", projects)
        
        if not skills and not projects:
            print("ERROR: Skills and projects are empty!")
            
    except Exception as e:
        print("parse_resume failed:", e)
        return

    print("\nTesting generate_question_pool...")
    try:
        groq_service = GroqService(settings.GROQ_API_KEY)
        # convert projects to dict if needed?
        # groq_service.generate_question_pool takes skills: List[str], projects: Dict[str, str]
        # But extracted["projects"] is a List[Dict] ...
        
        projects_dict = {}
        if isinstance(projects, list):
            for p in projects:
                if isinstance(p, dict):
                    name = p.get("name", "Unknown Project")
                    desc = p.get("description", "")
                    projects_dict[name] = desc
        else:
            projects_dict = projects

        pool = groq_service.generate_question_pool(
            skills=skills,
            projects=projects_dict,
            count=12
        )
        print("Generated question pool size:", len(pool) if pool else 0)
        if pool:
            print("First question:", pool[0])
            
    except Exception as e:
        print("generate_question_pool failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
