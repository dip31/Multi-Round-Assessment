# Interview Interface Setup Guide

## Overview

The AI Interview system has two parts:
1. **Admin Dashboard** (FastAPI) - Running on http://localhost:8000
2. **Candidate Interview Interface** (React) - Runs on http://localhost:5173

## Quick Start

### 1. Start the Backend (Already Running)
Your FastAPI backend is already running on port 8000 with all the interview APIs integrated.

### 2. Start the React Interview Frontend

Open a new terminal and run:

```bash
cd Multi-Round-Assessment-interview-round/frontend
npm install  # Only needed first time
npm run dev
```

This will start the React app on http://localhost:5173

### 3. Access the Interview

**Option A: From Admin Dashboard**
1. Go to http://localhost:8000
2. Click on "Stage 6: Interview" tab
3. Click "Open Candidate Interview Interface"

**Option B: Direct Access**
- Go directly to http://localhost:5173/interview

## Interview Flow

### For Candidates:
1. **Login/Register** at http://localhost:5173/login
2. **Upload Resume** at http://localhost:5173/resume-upload
3. **Start Interview** at http://localhost:5173/interview
4. **View Report** after completion

### Interview Features:
- ✅ AI-powered video interview
- ✅ Speech-to-text transcription (Groq Whisper)
- ✅ Text-to-speech responses (Sarvam.ai)
- ✅ Real-time behavioral monitoring
- ✅ RL-driven difficulty adaptation
- ✅ Smart follow-up questions
- ✅ 10-turn interview (5 HR + 5 Technical)

## API Endpoints

All interview APIs are available at http://localhost:8000/api/interview/*

- `POST /api/interview/resume/upload` - Upload resume
- `POST /api/interview/session/start` - Start interview
- `GET /api/interview/session/{id}/next` - Get first question
- `POST /api/interview/session/{id}/respond` - Submit answer
- `POST /api/interview/stt` - Speech-to-text
- `POST /api/interview/tts` - Text-to-speech
- `GET /api/interview/session/{id}/report` - Get report

## Configuration

### Required API Keys (in .env):
```env
GROQ_API_KEY=your-groq-api-key-here
SARVAM_API_KEY=your-sarvam-api-key-here  # Optional for TTS
REDIS_URL=redis://localhost:6379/0  # Optional for caching
```

### Optional: Redis for Caching
```bash
docker run -d -p 6379:6379 redis:alpine
```

## Troubleshooting

### React App Won't Start
```bash
cd Multi-Round-Assessment-interview-round/frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Interview API Errors
- Check that backend is running on port 8000
- Check GROQ_API_KEY is set in .env
- Check browser console for errors

### Audio Not Working
- Allow microphone permissions in browser
- SARVAM_API_KEY is optional - interview works without TTS
- Check browser console for audio errors

### CORS Errors
The backend is already configured to allow CORS from the React app.

## Testing the Interview

### Quick Test Flow:
1. Start both servers (backend + React)
2. Go to http://localhost:5173/login
3. Register a test account
4. Upload a sample resume (PDF)
5. Start the interview
6. Click "Start Speaking" and answer questions
7. Complete all 10 turns
8. View your interview report

### Sample Test Account:
You can create any account - no email verification required.

## Architecture

```
┌─────────────────────────────────────────┐
│   Admin Dashboard (Port 8000)           │
│   - Stage 1-5: Existing stages          │
│   - Stage 6: Interview management       │
│   - Stage 7: Evaluation & reports       │
└─────────────────────────────────────────┘
                    │
                    │ API Calls
                    ▼
┌─────────────────────────────────────────┐
│   FastAPI Backend (Port 8000)           │
│   - /api/interview/* endpoints          │
│   - Database (SQLite)                   │
│   - Groq API (STT)                      │
│   - Sarvam API (TTS)                    │
└─────────────────────────────────────────┘
                    │
                    │ API Calls
                    ▼
┌─────────────────────────────────────────┐
│   React Interview UI (Port 5173)        │
│   - Candidate login/register            │
│   - Resume upload                       │
│   - Live interview interface            │
│   - Interview reports                   │
└─────────────────────────────────────────┘
```

## Next Steps

1. ✅ Backend is running with interview APIs
2. ✅ Frontend code is in Multi-Round-Assessment-interview-round/frontend
3. 🔄 Start the React app: `cd Multi-Round-Assessment-interview-round/frontend && npm run dev`
4. 🎤 Take a test interview at http://localhost:5173/interview

## Production Deployment

For production, you'll need to:
1. Build the React app: `npm run build`
2. Serve the built files from FastAPI or a CDN
3. Update API URLs in the React app
4. Set up proper authentication
5. Configure HTTPS for both apps

## Support

The interview system is fully integrated and ready to use. Both the admin dashboard and candidate interface are working together through the unified API.
