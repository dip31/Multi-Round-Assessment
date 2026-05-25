# AI Recruitment Multi-Agent System

A complete 10-stage autonomous recruitment pipeline with AI-powered agents for job posting, candidate sourcing, screening, interviews, offers, and onboarding.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Node.js 18+ (for interview frontend)

### 1. Start Infrastructure Services

```bash
# Start all infrastructure services
docker-compose up -d postgres rabbitmq redis

# Or start individually:
# docker-compose up -d postgres    # PostgreSQL database
# docker-compose up -d rabbitmq    # Message broker  
# docker-compose up -d redis       # Cache (optional)

# Verify services are running
docker ps
```

**Service Status:**
- PostgreSQL: http://localhost:5432 (recruitment/recruitment_user/recruitment_pass)
- RabbitMQ Management: http://localhost:15672 (recruitment/recruitment_queue)
- Redis: http://localhost:6379

### 2. Setup Python Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys (GROQ_API_KEY required)

# Optional: Switch to PostgreSQL (default is SQLite)
# Uncomment DATABASE_URL in .env:
# DATABASE_URL=postgresql+asyncpg://recruitment_user:recruitment_pass@localhost:5432/recruitment
```

### 3. Start Backend Services

```bash
# Start main recruitment system (port 8000)
python main.py
```

Wait for startup messages:
```
✅ Stages 8, 9, 10 autonomous agents started
🚀 AI Recruitment System started
📊 Dashboard: http://localhost:8000
```

### 4. Start Interview Frontend (Optional)

```bash
# Navigate to interview frontend
cd interview-frontend

# Install dependencies (first time only)
npm install

# Start React app (port 5173)
npm run dev
```

### 5. Create Sample Data

```bash
# In a new terminal, create test data
python create_simple_sample_data.py
```

## � Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Main Dashboard** | http://localhost:8000 | Complete recruitment pipeline (10 stages) |
| **Interview App** | http://localhost:5173 | Candidate-facing AI interview interface |
| **API Documentation** | http://localhost:8000/docs | FastAPI interactive docs |
| **PostgreSQL** | localhost:5432 | Database (recruitment/recruitment_user) |
| **RabbitMQ Management** | http://localhost:15672 | Event bus monitoring (recruitment/recruitment_queue) |
| **Redis** | localhost:6379 | Cache service |

## 🎯 System Status

**✅ Working Stages (76.9%):**
- Stage 1: Job Requisition & Posting
- Stage 2: Candidate Sourcing  
- Stage 3: Screening & Shortlisting
- Stage 4: Outreach
- Stage 5: Prescreening
- Stage 7: Evaluation
- Stage 8: Offer Management

**⚠️ Known Issues:**
- Stage 6: Interview (SQL compatibility)
- Stage 9: Onboarding (SQL compatibility) 
- Stage 10: Analytics (SQL compatibility)

## 🔧 Health Check

```bash
# Test all system components
python system_health_check.py
```

## 📁 Project Structure

```
├── main.py                 # Main FastAPI application
├── config.py              # Configuration settings
├── .env                   # Environment variables
├── docker-compose.yml     # Infrastructure services
├── data/                  # SQLite database
├── frontend/              # Admin dashboard
├── interview-frontend/    # React interview app
├── intake/               # Stage 1: Job requisition
├── sourcing/             # Stage 2: Candidate sourcing
├── screening/            # Stage 3: Screening
├── outreach/             # Stage 4: Outreach
├── prescreening/         # Stage 5: Prescreening
├── interview/            # Stage 6: AI Interview
├── evaluation/           # Stage 7: Evaluation
├── offer/                # Stage 8: Offer management
├── onboarding/           # Stage 9: Onboarding
├── analytics/            # Stage 10: Analytics
└── shared/               # Common utilities
```

## 🛠️ Troubleshooting

**Container Issues:**
```bash
# If you get network conflicts or container name conflicts:
docker-compose down
docker network prune -f
docker rm -f recruitment-rabbitmq recruitment-postgres recruitment-redis

# Then restart services
docker-compose up -d postgres rabbitmq redis

# Check service logs
docker-compose logs postgres
docker-compose logs rabbitmq
docker-compose logs redis

# Reset all data
docker-compose down -v
docker-compose up -d
```

**Database Issues:**
```bash
# SQLite (default)
rm data/recruitment.db
python main.py  # Will recreate tables

# PostgreSQL 
docker-compose restart postgres
```

**Port Conflicts:**
- PostgreSQL: 5432
- RabbitMQ: 5672, 15672  
- Redis: 6379
- Main app: 8000
- Interview app: 5173

## 📧 Email Configuration

For production email sending, add to `.env`:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=hr@yourcompany.com
FROM_NAME=HR Team
```

## 🎉 Demo Workflow

1. **View Dashboard**: http://localhost:8000
2. **Check Sample Data**: Navigate through Stage 1-8 tabs
3. **Test Offers**: Click "Accept Offer" in Stage 8
4. **Monitor Events**: Check RabbitMQ management UI
5. **Try Interview**: Visit http://localhost:5173 (if running)

---

**Status**: 76.9% Complete | **Last Updated**: April 2026