@echo off
cd /d "D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend"
rmdir /s /q node_modules\.vite 2>nul
rmdir /s /q dist 2>nul
npm run dev