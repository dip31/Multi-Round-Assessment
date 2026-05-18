# Frontend Troubleshooting Guide

## Issue: Page is Loading but Not Showing Content

### Current Status
- ✅ Frontend server is running on http://localhost:3000
- ✅ Server responds with 200 OK
- ✅ Page content is being served (47KB)
- ✅ No compilation errors in terminal

### Possible Causes & Solutions

#### 1. Browser Cache Issue
**Solution**: Hard refresh the page
- **Windows/Linux**: `Ctrl + Shift + R` or `Ctrl + F5`
- **Mac**: `Cmd + Shift + R`

#### 2. JavaScript Not Loading
**Solution**: Check browser console
1. Open browser DevTools: `F12` or `Right-click → Inspect`
2. Go to "Console" tab
3. Look for any red error messages
4. Share the errors if you see any

#### 3. CSS Not Loading
**Solution**: Check Network tab
1. Open DevTools (`F12`)
2. Go to "Network" tab
3. Refresh the page
4. Look for any failed requests (red status codes)

#### 4. Port Conflict
**Solution**: Try a different port
```bash
cd frontend
PORT=3001 npm run dev
```
Then open http://localhost:3001

#### 5. Node Modules Issue
**Solution**: Reinstall dependencies
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run dev
```

### Quick Diagnostic Steps

#### Step 1: Check if Server is Running
```powershell
curl -UseBasicParsing http://localhost:3000
```
Expected: Should return HTML content

#### Step 2: Check Process
```powershell
netstat -ano | Select-String ":3000"
```
Expected: Should show LISTENING on port 3000

#### Step 3: View Server Logs
Check the terminal where `npm run dev` is running for any errors

#### Step 4: Test API Connection
```powershell
curl -UseBasicParsing http://localhost:8000/health
```
Expected: `{"status":"ok"}`

### Common Error Messages & Fixes

#### "Module not found"
```bash
cd frontend
npm install
```

#### "Port 3000 is already in use"
```bash
# Kill the process
Stop-Process -Id <PID> -Force
# Or use a different port
PORT=3001 npm run dev
```

#### "Cannot find module '@/components/...'"
Check if the file exists and the import path is correct

### Browser-Specific Issues

#### Chrome/Edge
1. Clear cache: `Ctrl + Shift + Delete`
2. Disable extensions temporarily
3. Try Incognito mode: `Ctrl + Shift + N`

#### Firefox
1. Clear cache: `Ctrl + Shift + Delete`
2. Try Private window: `Ctrl + Shift + P`

### Still Not Working?

#### Try This:
1. Stop the frontend server (`Ctrl + C` in terminal)
2. Clear the build cache:
   ```bash
   cd frontend
   rm -rf .next
   ```
3. Restart the server:
   ```bash
   npm run dev
   ```
4. Hard refresh the browser: `Ctrl + Shift + R`

#### Check These:
- [ ] Is the backend running? (http://localhost:8000/health)
- [ ] Is the frontend server running? (check terminal)
- [ ] Are there any errors in the browser console? (F12)
- [ ] Are there any errors in the terminal?
- [ ] Did you try a hard refresh? (Ctrl + Shift + R)
- [ ] Did you try a different browser?

### Get More Information

#### View Full Page Source
```powershell
curl -UseBasicParsing http://localhost:3000/login | Select-Object -ExpandProperty Content | Out-File page.html
```
Then open `page.html` in a text editor to see what's being served

#### Check What's Running
```powershell
Get-Process node | Select-Object Id, ProcessName, StartTime
```

### Contact Information
If the issue persists, provide:
1. Browser console errors (F12 → Console tab)
2. Network tab errors (F12 → Network tab)
3. Terminal output from `npm run dev`
4. Screenshot of what you see in the browser
