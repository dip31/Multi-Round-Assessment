# AI-Driven Multi-Round Assessment Platform

A comprehensive technical assessment platform featuring AI-driven adaptive testing, enterprise-grade proctoring, and real-time performance analytics.

## 🎯 Project Overview

This platform supports multi-stage technical assessments with three types of assessment rounds:

- **Aptitude Round**: Multiple-choice questions with RL-driven difficulty adaptation
- **Coding Round**: Programming challenges with automated code execution and evaluation  
- **Interview Round**: AI-powered behavioral and technical interview sessions

## 🏗️ Architecture

### Backend (FastAPI + PostgreSQL)
- **FastAPI**: Modern, high-performance Python web framework with async/await support
- **PostgreSQL**: Primary relational database with JSONB support for flexible data structures
- **SQLAlchemy**: ORM with async support and connection pooling
- **Alembic**: Database migration management
- **JWT Authentication**: Secure token-based authentication with refresh tokens

### Frontend (React + Vite)
- **React 18**: Modern React with hooks and functional components
- **Vite**: Fast build tool with hot module replacement
- **TailwindCSS**: Utility-first CSS framework with custom themes
- **Axios**: HTTP client with interceptors for API communication
- **React Router**: Client-side routing with protected routes

## 🚀 Core Features

### 1. User Authentication System
- **Secure Registration**: Password hashing with bcrypt
- **JWT Login**: Access and refresh token management
- **Protected Routes**: Role-based access control
- **Session Management**: Automatic token refresh and logout

### 2. AI-Driven Adaptive Testing
- **Reinforcement Learning Engine**: Q-learning algorithm for dynamic difficulty adjustment
- **Real-time Adaptation**: Questions adapt based on user performance
- **Performance Metrics**: Response time, accuracy, streak tracking
- **Learning Analytics**: Detailed RL statistics and progress visualization

### 3. Basic Online Proctoring System
- **Webcam Permission Check**: Requires camera access before test start
- **Tab Switch Detection**: Monitors browser tab switching with violation tracking
- **Fullscreen Enforcement**: Automatic fullscreen mode with exit detection
- **Page Reload Protection**: Warns against page refresh during test
- **Idle Activity Monitoring**: 60-second inactivity detection with alerts
- **Real-time Warnings**: UI notifications for proctoring violations
- **Comprehensive Logging**: Complete audit trail with metadata

### 4. Assessment Management
- **Multi-Round Support**: Aptitude, Coding, and Interview rounds
- **Session Tracking**: Complete assessment lifecycle management
- **Time Management**: 30-minute global timer per session
- **Progress Tracking**: Real-time question completion status

## 📊 Database Schema

### Core Tables
- **users**: User profiles and authentication data
- **assessment_sessions**: Complete assessment attempts
- **assessment_rounds**: Individual rounds within sessions
- **aptitude_questions**: MCQ question bank with difficulty levels
- **aptitude_attempts**: User answer attempts with RL data
- **rl_sessions**: Reinforcement learning state tracking
- **proctoring_events**: Proctoring violation logs with metadata

### Key Relationships
- Users → Assessment Sessions (1:N)
- Sessions → Assessment Rounds (1:N)
- Rounds → Aptitude Attempts (1:N)
- Sessions → Proctoring Events (1:N)

## 🔧 Technical Implementation

### Backend APIs

#### Authentication (`/api/v1/auth`)
- `POST /register` - User registration
- `POST /login` - User authentication
- `POST /refresh` - Token refresh

#### Session Management (`/api/v1/session`)
- `POST /start` - Start new assessment session
- `GET /status` - Get current session status

#### Aptitude Testing (`/api/v1/aptitude`)
- `GET /next-question` - Get next adaptive question
- `POST /submit-answer` - Submit answer with RL adaptation
- `GET /result` - Get comprehensive results with RL metrics

#### Proctoring (`/api/v1/proctoring`)
- `POST /log-event` - Log proctoring violations
- `GET /events/{session_id}` - Retrieve session proctoring events

### Frontend Components

#### Core Pages
- **Login.jsx**: User authentication interface
- **Dashboard.jsx**: Assessment start and management
- **AptitudeTest.jsx**: Main testing interface with proctoring
- **Result.jsx**: Comprehensive results with RL analytics

#### Proctoring Components
- **ProctoringWarning.jsx**: Real-time violation notifications
- **FullscreenPrompt.jsx**: User-friendly fullscreen request
- **useProctoring.js**: Custom hook for proctoring logic

#### Utility Components
- **Navbar.jsx**: Navigation with user state
- **QuestionCard.jsx**: Interactive MCQ display
- **Timer.jsx**: Countdown timer with visual feedback

### Custom Hooks
- **useAuth.js**: Authentication state management
- **useSession.js**: Session lifecycle management
- **useProctoring.js**: Real-time proctoring monitoring
- **useTimer.js**: Countdown timer logic

## 🤖 Reinforcement Learning System

### Q-Learning Algorithm
- **State Representation**: 5-tuple (difficulty, correct_streak, wrong_streak, avg_response_time_bin, topic_accuracy_bin)
- **Action Space**: {easy, medium, hard} difficulty selection
- **Reward Calculation**: Based on correctness, response time, and streak patterns
- **Exploration Strategy**: Epsilon-greedy with decay

### RL Features
- **Dynamic Difficulty**: Questions adapt based on performance
- **State Building**: Comprehensive user performance analysis
- **Policy Application**: Intelligent difficulty selection
- **Q-Table Management**: Persistent learning across sessions

## 🔒 Security Features

### Authentication & Authorization
- **JWT Tokens**: Secure access and refresh token management
- **Password Security**: Bcrypt hashing with salt
- **Session Ownership**: Users can only access their own data
- **Role-Based Access**: Student and admin role separation

### Proctoring Security
- **Violation Tracking**: Comprehensive event logging
- **Real-time Monitoring**: Active behavior detection
- **Threshold Enforcement**: Automatic violation limits
- **Audit Trail**: Complete proctoring event history

## 📈 Analytics & Reporting

### Performance Metrics
- **Accuracy Tracking**: Question-by-question correctness
- **Response Time Analysis**: Time-based performance metrics
- **Difficulty Progression**: Visual RL adaptation tracking
- **Streak Analysis**: Correct/wrong answer patterns

### RL Analytics
- **Learning Curves**: Q-value progression visualization
- **Reward Distribution**: Performance-based reward analysis
- **State Transitions**: Difficulty adaptation patterns
- **Policy Effectiveness**: RL algorithm performance metrics

## 🛠️ Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Git

### Backend Setup
```bash
# Clone repository
git clone <repository-url>
cd Multi-Round-Assessment

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your database credentials

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Database Setup
```bash
# Create PostgreSQL database
createdb ai_placement_platform

# Run schema setup
psql -d ai_placement_platform -f database/schema.sql

# (Optional) Add sample questions
# See database/sample_data.sql
```

## 🧪 Testing

### Backend Tests
```bash
# Run all tests
pytest tests/

# Run specific test modules
pytest tests/test_auth.py
pytest tests/test_aptitude.py
pytest tests/test_proctoring.py
```

### Frontend Tests
```bash
# Run unit tests
npm test

# Run integration tests
npm run test:e2e
```

### API Testing
```bash
# Test authentication
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'

# Test next question
curl -X GET http://localhost:8000/api/v1/aptitude/next-question \
  -H "Authorization: Bearer <token>"
```

## 📁 Project Structure

```
Multi-Round-Assessment/
├── app/                          # Backend application
│   ├── api/                      # API versioning
│   │   └── v1/                  # API v1 endpoints
│   ├── config/                   # Configuration settings
│   ├── core/                     # Core utilities (auth, security)
│   ├── database/                 # Database configuration
│   ├── middleware/               # Custom middleware
│   ├── models/                   # SQLAlchemy ORM models
│   ├── modules/                  # Feature modules
│   │   ├── aptitude/            # Aptitude testing module
│   │   ├── auth/                # Authentication module
│   │   ├── proctoring/          # Proctoring module
│   │   └── session/             # Session management
│   ├── schemas/                  # Pydantic validation schemas
│   ├── services/                 # Business logic layer
│   └── main.py                   # FastAPI application entry
├── frontend/                     # React frontend
│   ├── public/                   # Static assets
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── hooks/               # Custom hooks
│   │   ├── pages/               # Route components
│   │   ├── services/            # API client services
│   │   └── App.jsx              # Main app component
│   └── package.json
├── database/                     # Database files
│   ├── schema.sql                # Database schema
│   └── sample_data.sql          # Sample data
├── tests/                        # Test files
├── alembic/                      # Database migrations
├── docs/                         # Documentation
└── README.md                     # This file
```

## 🎯 Key Achievements

### ✅ Completed Features
1. **Full Authentication System**: JWT-based secure authentication
2. **Adaptive Testing Engine**: RL-driven difficulty adjustment
3. **Enterprise Proctoring**: 5-feature monitoring system
4. **Real-time Analytics**: Comprehensive performance tracking
5. **Modern Frontend**: Responsive React application
6. **RESTful APIs**: Complete backend API coverage
7. **Database Design**: Optimized PostgreSQL schema
8. **Security Implementation**: Production-ready security

### 🔧 Technical Excellence
- **Clean Architecture**: Modular, scalable design
- **Error Handling**: Comprehensive error management
- **Performance**: Optimized queries and caching
- **Testing**: Unit and integration test coverage
- **Documentation**: Complete API and code documentation
- **CI/CD Ready**: Production deployment ready

## 🚀 Deployment

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/dbname

# JWT Security
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### Production Deployment
```bash
# Build frontend
cd frontend && npm run build

# Start backend with production settings
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# (Optional) Use Docker
docker-compose up -d
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Backend API**: `http://localhost:8000` (Auto-generated docs at `/docs`)
- **Frontend Application**: `http://localhost:5173`
- **Database**: PostgreSQL on `localhost:5432`

---

**Built with ❤️ using FastAPI, React, and Reinforcement Learning**