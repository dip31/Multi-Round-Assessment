# Production Setup Guide

## Overview
The AI Recruitment System is designed to seamlessly switch between **simulation mode** (for testing) and **production mode** (real API calls) by simply adding API keys to the `.env` file.

## Quick Production Setup

### 1. Enable Production Mode
```env
# Set this to 'true' to enable real API calls
PRODUCTION_MODE=true
```

### 2. Job Posting APIs

#### LinkedIn Job Posting
```env
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret  
LINKEDIN_ACCESS_TOKEN=your_linkedin_access_token
```
**How to get:** LinkedIn Developer Portal → Create App → Job Posting API access

#### Indeed Job Posting
```env
INDEED_PUBLISHER_ID=your_indeed_publisher_id
INDEED_API_KEY=your_indeed_api_key
```
**How to get:** Indeed Publisher Portal → Apply for API access

#### Naukri Job Posting
```env
NAUKRI_API_KEY=your_naukri_api_key
NAUKRI_CLIENT_ID=your_naukri_client_id
```
**How to get:** Naukri Partner Program → API access request

#### Adzuna (Free Tier Available)
```env
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
ADZUNA_COUNTRY=in
```
**How to get:** https://developer.adzuna.com → Free signup (200 requests/day)

### 3. Candidate Sourcing APIs

#### GitHub (Free with Token)
```env
GITHUB_API_TOKEN=your_github_personal_access_token
```
**How to get:** GitHub Settings → Developer settings → Personal access tokens

#### Stack Overflow (Free Tier Available)
```env
STACKOVERFLOW_API_KEY=your_stackoverflow_api_key
```
**How to get:** https://stackapps.com/apps/oauth/register → Free (10k requests/day with key)

#### LinkedIn Talent Solutions
```env
LINKEDIN_TALENT_API_KEY=your_linkedin_talent_api_key
```
**How to get:** LinkedIn Talent Solutions → API access (Enterprise only)

#### AngelList/Wellfound
```env
ANGELLIST_API_KEY=your_angellist_api_key
```
**How to get:** Wellfound API Program → Apply for access

#### HackerRank (Optional)
```env
HACKERRANK_API_KEY=your_hackerrank_api_key
```
**How to get:** HackerRank for Work → API access

## API Priority & Fallbacks

### Job Posting Priority:
1. **LinkedIn** - Highest reach for professionals
2. **Indeed** - Largest job board
3. **Naukri** - India-specific platform
4. **Adzuna** - Free tier available

### Candidate Sourcing Priority:
1. **GitHub** - Best for developers (free with token)
2. **Stack Overflow** - Technical expertise (free tier)
3. **LinkedIn** - Professional profiles (requires enterprise)
4. **AngelList** - Startup talent

## Testing Your Setup

### 1. Check API Status
```bash
curl http://localhost:8000/api/sourcing/scraping-status
```

### 2. Test Job Posting
1. Create a job via dashboard
2. Generate JD with AI
3. Post to platforms - check for real URLs vs simulated

### 3. Test Candidate Scraping
1. Use the Profile Scraper tab
2. Search for skills like "Python, React"
3. Check if real profiles are returned vs simulated

## Production Checklist

- [ ] Set `PRODUCTION_MODE=true`
- [ ] Add at least one job posting API key
- [ ] Add at least one candidate sourcing API key  
- [ ] Test job posting flow
- [ ] Test candidate scraping flow
- [ ] Set up RabbitMQ for Phase 3 integration
- [ ] Configure PostgreSQL for production database
- [ ] Set up proper JWT secrets
- [ ] Configure S3 for file storage (optional)

## Cost Estimates

### Free Tier Options:
- **Adzuna**: 200 job posts/day
- **GitHub**: 5000 API calls/hour with token
- **Stack Overflow**: 10,000 API calls/day with key

### Paid APIs:
- **LinkedIn Job Posting**: ~$200-500/month
- **Indeed API**: Contact for pricing
- **Naukri API**: Contact for pricing
- **LinkedIn Talent Solutions**: Enterprise pricing

## Monitoring & Limits

The system automatically:
- ✅ Detects available API credentials
- ✅ Falls back to simulation if credentials missing
- ✅ Handles rate limits gracefully
- ✅ Logs all API calls for monitoring
- ✅ Shows production/simulation status in responses

## Support

For API access issues:
1. Check the specific platform's developer documentation
2. Ensure your API keys have the correct permissions
3. Monitor rate limits in the application logs
4. Use the `/api/system/health` endpoint to check system status

The system is designed to work partially - you can enable just LinkedIn posting or just GitHub scraping, and other platforms will continue to simulate until you add their credentials.