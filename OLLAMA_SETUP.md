# Ollama Setup for Local LLM Resume Parsing

## Quick Setup

### 1. Install Ollama
```bash
# Windows (PowerShell as Administrator)
winget install Ollama.Ollama

# Or download from: https://ollama.com/download
```

### 2. Start Ollama Service
```bash
# Start Ollama (runs on http://localhost:11434)
ollama serve
```

### 3. Pull the Model
```bash
# Download the lightweight Llama 3.2 3B model (2GB)
ollama pull llama3.2:3b
```

### 4. Test the Setup
```bash
# Test if model is working
ollama run llama3.2:3b "Hello, how are you?"
```

## Alternative Models

If `llama3.2:3b` doesn't work well, try:
```bash
# Smaller model (1.7GB)
ollama pull llama3.2:1b

# Larger, more capable model (4.7GB)  
ollama pull llama3.1:8b
```

## Verify Setup
- Ollama API: http://localhost:11434
- Check models: `ollama list`
- Check status: `ollama ps`

## Resume Parsing Flow
1. Upload resume → LlamaIndex + Ollama (primary)
2. If Ollama fails → Direct Ollama API (fallback)
3. If all fails → Regex parsing (final fallback)

The system will automatically detect when Ollama is available and use it for parsing.