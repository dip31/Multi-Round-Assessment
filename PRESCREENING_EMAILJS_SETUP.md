# Prescreening & Email Configuration Guide

## Overview
The system has been updated with the following changes:
1. **Fixed Prescreening Questions** - 6 standard questions used by default
2. **Gemini AI Chatbot** - Optional AI-powered chatbot (disabled by default)
3. **EmailJS Integration** - Free email service replacing SendGrid

---

## Fixed Prescreening Questions

When `CHATBOT_ENABLED=false` (default), the system uses these 6 fixed questions:

1. What motivated you to apply for this position at our company?
2. Describe your most relevant work experience for this role.
3. What are your key technical skills and how have you applied them?
4. How do you handle tight deadlines and pressure in a work environment?
5. What are your salary expectations for this position?
6. When would you be available to start if selected?

---

## Gemini AI Chatbot Configuration

To enable AI-powered dynamic question generation:

### Step 1: Get Gemini API Key
1. Visit: https://makersuite.google.com/app/apikey
2. Create a new API key
3. Copy the key

### Step 2: Update .env file
```env
CHATBOT_ENABLED=true
GEMINI_API_KEY=your-gemini-api-key-here
```

### Step 3: Install Dependencies
```bash
pip install google-generativeai
```

When enabled, Gemini will generate custom questions based on the job description.

---

## EmailJS Configuration

EmailJS is a free service that allows sending emails without a backend server.

### Step 1: Create EmailJS Account
1. Visit: https://www.emailjs.com/
2. Sign up for a free account (200 emails/month)

### Step 2: Add Email Service
1. Go to "Email Services" in dashboard
2. Click "Add New Service"
3. Choose your email provider (Gmail, Outlook, etc.)
4. Follow the setup instructions
5. Copy the **Service ID**

### Step 3: Create Email Template
1. Go to "Email Templates" in dashboard
2. Click "Create New Template"
3. Use this template structure:

**Subject:** `{{subject}}`

**Content:**
```
Hi {{to_name}},

{{message}}

{{chatbot_url}}

Best regards,
{{company_name}} Recruitment Team

---
Unsubscribe: {{unsubscribe_url}}
```

4. Copy the **Template ID**

### Step 4: Get API Keys
1. Go to "Account" → "General"
2. Copy your **Public Key**
3. Go to "Account" → "Security"
4. Generate and copy your **Private Key**

### Step 5: Update .env file
```env
EMAILJS_SERVICE_ID=service_xxxxxxx
EMAILJS_TEMPLATE_ID=template_xxxxxxx
EMAILJS_PUBLIC_KEY=your_public_key
EMAILJS_PRIVATE_KEY=your_private_key
COMPANY_NAME=Your Company Name
```

---

## Testing the Setup

### Test Fixed Questions
1. Start the system: `python main.py`
2. Create a job posting
3. Upload a resume
4. System will automatically:
   - Parse resume
   - Score candidate
   - Send outreach email (if EmailJS configured)
   - Create prescreening session with 6 fixed questions

### Test Gemini Chatbot
1. Set `CHATBOT_ENABLED=true` in .env
2. Add your `GEMINI_API_KEY`
3. Restart the system
4. Questions will now be dynamically generated based on job description

### Test EmailJS
1. Configure all EmailJS variables in .env
2. Trigger an outreach email via API or automatic flow
3. Check recipient's inbox
4. Check EmailJS dashboard for delivery status

---

## API Endpoints

### Trigger Outreach Email
```bash
POST /api/outreach/send
{
  "candidate_id": "candidate-uuid",
  "job_id": "job-uuid"
}
```

### Create Prescreening Session
```bash
POST /api/prescreening/sessions
{
  "candidate_id": "candidate-uuid",
  "job_id": "job-uuid"
}
```

### Get Prescreening Questions
```bash
POST /api/prescreening/start
{
  "token": "session-token"
}
```

### Submit Answer
```bash
POST /api/prescreening/answer
{
  "token": "session-token",
  "question_index": 0,
  "answer": "Your answer here"
}
```

---

## Troubleshooting

### EmailJS Not Sending
- Check API keys are correct
- Verify template ID matches
- Check EmailJS dashboard for errors
- Ensure you haven't exceeded free tier limit (200/month)

### Gemini Not Working
- Verify API key is valid
- Check you have Gemini API access enabled
- Ensure `google-generativeai` package is installed
- System will fallback to fixed questions if Gemini fails

### Questions Not Appearing
- Check `CHATBOT_ENABLED` setting
- Verify prescreening session was created
- Check logs for errors: `python main.py`

---

## Cost Comparison

| Service | Free Tier | Paid Plans |
|---------|-----------|------------|
| EmailJS | 200 emails/month | $15/month for 1000 emails |
| Gemini API | Free tier available | Pay per use |
| SendGrid (old) | 100 emails/day | $15/month for 40k emails |

---

## Next Steps

1. Configure EmailJS for outreach emails
2. Test with fixed questions first
3. Once comfortable, enable Gemini chatbot
4. Monitor email delivery in EmailJS dashboard
5. Review candidate responses in the system

---

## Support

For issues or questions:
- EmailJS Docs: https://www.emailjs.com/docs/
- Gemini API Docs: https://ai.google.dev/docs
- System Logs: Check console output when running `python main.py`
