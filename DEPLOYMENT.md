# Production Deployment Guide

## 🚀 DigitalOcean App Platform Deployment

### Prerequisites
- GitHub account (repo zaten connected)
- DigitalOcean account
- Docker Hub account (optional, for private images)

### Step 1: Push to GitHub
```bash
git add .
git commit -m "Production-ready build"
git push origin main
```

### Step 2: Create App on DigitalOcean
1. Go to DigitalOcean Dashboard
2. Apps → Create App
3. Select your GitHub repository: `chatbot-uni`
4. Branch: `main`
5. Autodeploy: ✅ Enable (so pushing to main triggers deploy)

### Step 3: Configure Environment Variables
In DigitalOcean App Platform console, set:

```env
GOOGLE_API_KEY=<your-gemini-api-key>
ENVIRONMENT=production
LOG_LEVEL=INFO
USE_EMBEDDINGS=true
```

### Step 4: Configure Resources
- **CPU**: 1 vCPU (minimum)
- **Memory**: 1 GB (minimum)
- **Instance count**: 1 (can scale to 3)

### Step 5: Deploy
Click "Create App" → Wait for build & deployment

---

## 🐳 Local Docker Build & Test

### Build Production Image
```bash
docker build -t chatbot-uni:latest -f Dockerfile .
```

### Run Locally
```bash
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY="your-key" \
  -e ENVIRONMENT=production \
  chatbot-uni:latest
```

### Test Health Check
```bash
curl http://localhost:8080/health
# Should return: {"status":"ok","startup_complete":true}
```

---

## 📊 Monitoring & Debugging

### View Logs on DigitalOcean
```
Apps → Your App → Runtime Logs (real-time)
```

### Test API Endpoints
```bash
# Health check
curl https://your-app.ondigitalocean.app/health

# Chat endpoint
curl -X POST https://your-app.ondigitalocean.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "merhaba",
    "session_id": "test-session"
  }'

# Analytics
curl https://your-app.ondigitalocean.app/api/analytics/summary
```

---

## 🔒 Security Best Practices

1. **Environment Variables**: Never commit secrets to git
2. **API Key**: Store GOOGLE_API_KEY in DigitalOcean secrets
3. **CORS**: Configured for production domains
4. **Logging**: All requests logged to SQLite

---

## 📈 Performance Tips

- **Caching**: SQLite for chat history
- **Async Processing**: Background tasks for web scraping
- **Auto-scaling**: Enabled for handling spikes

---

## 🔄 Rollback

If something breaks after deployment:
1. Go to DigitalOcean Apps
2. Deployments tab
3. Select previous working deployment
4. Click "Rollback"

---

## 📝 Environment Differences

### Development (Local)
- Port: 8000
- Hot reload: Enabled
- Volumes: Mounted for live code changes
- `docker-compose up`

### Production (DigitalOcean)
- Port: 8080
- Hot reload: Disabled
- No volumes
- Auto-deployed on `git push main`
