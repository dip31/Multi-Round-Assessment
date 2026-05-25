"""
Central configuration for the AI Recruitment System.
Loads from environment variables with sensible defaults for development.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)

# ── Database ───────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DB_DIR}/recruitment.db")

# ── Groq API ──────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── JWT Auth ───────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# ── Storage ────────────────────────────────────────────
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")  # "local" or "s3"
S3_BUCKET = os.getenv("S3_BUCKET", "recruitment-resumes")
S3_REGION = os.getenv("S3_REGION", "ap-south-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# ── RabbitMQ (production) ──────────────────────────────
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# ── Rate Limits ────────────────────────────────────────
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# ── LlamaIndex ─────────────────────────────────────────
LLAMA_INDEX_CHUNK_SIZE = 1024
LLAMA_INDEX_CHUNK_OVERLAP = 200

# ── Production Mode Toggle ─────────────────────────────
PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "false").lower() == "true"

# ── Job Posting APIs ───────────────────────────────────
# LinkedIn (2024 simpleJobPostings API)
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_COMPANY_ID = os.getenv("LINKEDIN_COMPANY_ID", "")  # Get from LinkedIn company page

# Indeed (2024 GraphQL Job Sync API)
INDEED_API_KEY = os.getenv("INDEED_API_KEY", "")  # OAuth access token
INDEED_EMPLOYER_ID = os.getenv("INDEED_EMPLOYER_ID", "")  # Your employer ID

# Naukri (Manual posting only - no public API)
# Visit https://recruit.naukri.com/ for manual job posting

# Adzuna API (job aggregator - used for job posting research, NOT candidate sourcing)
# Note: Adzuna is a job board aggregator, it doesn't have candidate profiles
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "in")  # in=India, gb=UK, us=US
ADZUNA_FEED_URL = os.getenv("ADZUNA_FEED_URL", "")
COMPANY_CAREERS_BASE_URL = os.getenv("COMPANY_CAREERS_BASE_URL", "http://localhost:8000/careers")

# ── Candidate Sourcing APIs ────────────────────────────
# LinkedIn Talent Solutions
LINKEDIN_TALENT_API_KEY = os.getenv("LINKEDIN_TALENT_API_KEY", "")

# GitHub (developer profiles)
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN", "")

# Stack Overflow (developer profiles, optional, 300/day without key)
STACKOVERFLOW_API_KEY = os.getenv("STACKOVERFLOW_API_KEY", "")

# AngelList/Wellfound (startup talent)
ANGELLIST_API_KEY = os.getenv("ANGELLIST_API_KEY", "")

# ── HackerRank
HACKERRANK_API_KEY = os.getenv("HACKERRANK_API_KEY", "")

# ── Stage 4 & 5 Configuration ────────────────────────────────────────────────
# EmailJS (free email service)
EMAILJS_SERVICE_ID = os.getenv("EMAILJS_SERVICE_ID", "")
EMAILJS_TEMPLATE_ID = os.getenv("EMAILJS_TEMPLATE_ID", "")
EMAILJS_PUBLIC_KEY = os.getenv("EMAILJS_PUBLIC_KEY", "")
EMAILJS_PRIVATE_KEY = os.getenv("EMAILJS_PRIVATE_KEY", "")

# Company Info
COMPANY_NAME = os.getenv("COMPANY_NAME", "Our Company")
SCREENING_BASE_URL = os.getenv("SCREENING_BASE_URL", "http://localhost:8001/chatbot")
TALENT_POOL_BASE_URL = os.getenv("TALENT_POOL_BASE_URL", "http://localhost:8000/talent-pool")
HR_ADMIN_EMAIL = os.getenv("HR_ADMIN_EMAIL", "hr@company.com")

# Chatbot Configuration
CHATBOT_ENABLED = os.getenv("CHATBOT_ENABLED", "false").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# SpringVerify BGV
SPRINGVERIFY_API_KEY = os.getenv("SPRINGVERIFY_API_KEY", "")
BGV_MOCK = os.getenv("BGV_MOCK", "true").lower() == "true"

# ── Stage 6 & 7 Configuration (Interview & Evaluation) ────────────────────────
# Sarvam.ai TTS API
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

# Redis for caching (interview questions, TTS)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Interview Configuration
INTERVIEW_TOTAL_TURNS = int(os.getenv("INTERVIEW_TOTAL_TURNS", "10"))
INTERVIEW_HR_PHASE_TURNS = int(os.getenv("INTERVIEW_HR_PHASE_TURNS", "5"))

# ── Stage 8, 9, 10 Configuration (Offer, Onboarding, Analytics) ───────────────
# Local storage directories (replaces AWS S3)
OFFERS_DIR = BASE_DIR / "output" / "offers"
OFFERS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = BASE_DIR / "output" / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
PROVISIONING_DIR = BASE_DIR / "output" / "provisioning"
PROVISIONING_DIR.mkdir(parents=True, exist_ok=True)

# SMTP Email Configuration (for offer letters, onboarding)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
