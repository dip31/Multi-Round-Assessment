# Quick Start Guide

## 🚀 Start the Project

### Backend (Port 8000)
```bash
cd Multi-Round-Assesment
uvicorn app.main:app --reload
```

### Frontend (Port 3001)
```bash
cd Multi-Round-Assesment/frontend
npm run dev
```

## 🌐 Access URLs

- **Frontend:** http://localhost:3001
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## 👤 Test User

```
Email: testuser@example.com
Password: testpass123
```

## 📝 Complete Test Flow

1. **Login** → http://localhost:3001/login
2. **Dashboard** → Click "Start Assessment"
3. **Coding Round** → 2 problems, 90 minutes
4. **Write Code** → Use the code editor
5. **Run Code** → Test with visible test cases
6. **Submit** → Submit for full evaluation
7. **End Test** → Appears after all problems submitted
8. **Results** → View final score and statistics

## ✅ What's Fixed

### End Test Button
- Appears when ALL problems are submitted
- Works for both correct and incorrect submissions
- Message: "Submit all problems to end round"

### Result Counting
- Shows total problems (2), not run attempts
- Problems Solved = count of 100% scores
- Run Code attempts are NOT counted

### Code Execution
- Automatic fallback to Mock Judge0 if real Judge0 unavailable
- Works with Python code
- Returns execution results

## 🧪 Test Scripts

```bash
# Test End Test button logic
python scripts/test_end_button_simple.py

# Test result counting
python scripts/test_result_counts.py

# Test code execution
python scripts/test_with_mock_judge0.py

# Diagnose Judge0
python scripts/diagnose_judge0.py
```

## 🔧 Troubleshooting

### Backend Not Starting
```bash
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill process if needed
taskkill /PID <process_id> /F
```

### Frontend Not Starting
```bash
# Remove lock file
cd frontend
Remove-Item -Path ".next\dev\lock" -Force

# Restart
npm run dev
```

### Code Execution Fails
```bash
# Enable Mock Judge0
# Add to .env file:
USE_MOCK_JUDGE0=true

# Restart backend
```

## 📊 Expected Behavior

### Problem Status Colors
- 🟢 **Green** = Accepted (100% score)
- 🟡 **Yellow** = Attempted (submitted but not 100%)
- ⚪ **White** = Not Attempted

### End Test Button
- **Hidden** = Not all problems submitted yet
- **Visible** = All problems submitted (can end test)

### Result Page
- **Total Problems** = 2 (total in test)
- **Problems Solved** = Count of 100% scores
- **Total Score** = Average of best scores

## 📚 Documentation

- **ISSUE_RESOLVED_SUMMARY.md** - Complete issue resolution
- **CODE_EXECUTION_ISSUE_FIXED.md** - Code execution details
- **JUDGE0_ISSUE_REPORT.md** - Judge0 diagnosis
- **QUICK_START.md** - This file

## 🎯 Current Status

✅ Backend running (Port 8000)
✅ Frontend running (Port 3001)
✅ Code execution working
✅ End Test button fixed
✅ Result counting fixed
✅ All features functional

## 💡 Tips

1. Use "Run Code" to test before submitting
2. Submit all problems to see End Test button
3. End Test button appears even if solutions are wrong
4. Result page shows total problems, not run count
5. Mock Judge0 works for Python code testing

## 🆘 Need Help?

Run diagnostics:
```bash
python scripts/diagnose_judge0.py
python scripts/test_with_mock_judge0.py
```

Check logs:
- Backend: Terminal where uvicorn is running
- Frontend: Terminal where npm run dev is running
- Browser: F12 → Console tab

## ✨ Ready to Test!

Go to http://localhost:3001 and start coding! 🚀