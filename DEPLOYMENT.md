# ScholarBot Deployment Guide

## Local Development Deployment

### Quick Setup

```bash
# Clone repository
git clone <repo-url>
cd scholarbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add OPENAI_API_KEY=your_key

# Run application
streamlit run app.py
```

## Production Deployment Options

### Option 1: Streamlit Cloud (Recommended for Demo)

#### Prerequisites
- GitHub account
- Streamlit Cloud account (free at share.streamlit.io)
- OpenAI API key

#### Steps

1. **Push code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo>
   git push -u origin main
   ```

2. **Deploy to Streamlit Cloud**
   - Go to https://share.streamlit.io
   - Click "New app"
   - Select your repository
   - Main file: `app.py`
   - Python version: 3.11

3. **Configure Secrets**
   - In Streamlit Cloud dashboard
   - Go to App Settings → Secrets
   - Add:
     ```toml
     OPENAI_API_KEY = "your_openai_api_key"
     PRIMO_PUBLIC_BASE = "https://csu-sb.primo.exlibrisgroup.com/primaws/rest/pub"
     PRIMO_VID = "01CALS_USB:01CALS_USB"
     PRIMO_TAB = "CSUSB_CSU_Articles"
     PRIMO_SCOPE = "CSUSB_CSU_articles"
     PRIMO_INST = "01CALS_USB"
     ```

4. **Deploy**
   - Click "Deploy"
   - Wait for deployment to complete
   - Access your app at: https://[app-name].streamlit.app

### Option 2: Docker Deployment

#### Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

#### Build and Run

```bash
# Build image
docker build -t scholarbot:latest .

# Run container
docker run -d \
  --name scholarbot \
  -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  scholarbot:latest

# Access at http://localhost:8501
```

#### Using Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  scholarbot:
    build: .
    ports:
      - "8501:8501"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PRIMO_PUBLIC_BASE=https://csu-sb.primo.exlibrisgroup.com/primaws/rest/pub
      - PRIMO_VID=01CALS_USB:01CALS_USB
      - PRIMO_TAB=CSUSB_CSU_Articles
      - PRIMO_SCOPE=CSUSB_CSU_articles
      - PRIMO_INST=01CALS_USB
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Run with:
```bash
docker-compose up -d
```

### Option 3: Cloud Platform Deployment

#### AWS Elastic Beanstalk

1. Install EB CLI:
   ```bash
   pip install awsebcli
   ```

2. Initialize EB application:
   ```bash
   eb init -p python-3.11 scholarbot
   ```

3. Create environment:
   ```bash
   eb create scholarbot-env
   ```

4. Set environment variables:
   ```bash
   eb setenv OPENAI_API_KEY=your_key
   ```

5. Deploy:
   ```bash
   eb deploy
   ```

#### Google Cloud Run

1. Build container:
   ```bash
   gcloud builds submit --tag gcr.io/[PROJECT-ID]/scholarbot
   ```

2. Deploy:
   ```bash
   gcloud run deploy scholarbot \
     --image gcr.io/[PROJECT-ID]/scholarbot \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars OPENAI_API_KEY=your_key
   ```

#### Heroku

1. Create `Procfile`:
   ```
   web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
   ```

2. Deploy:
   ```bash
   heroku create scholarbot-app
   heroku config:set OPENAI_API_KEY=your_key
   git push heroku main
   ```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_MODEL` | Model to use | `gpt-4` |
| `OPENAI_TEMPERATURE` | Response creativity | `0.7` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `PRIMO_PUBLIC_BASE` | Library API base URL | See .env.example |
| `PRIMO_VID` | Library VID | See .env.example |
| `PRIMO_TAB` | Library tab | See .env.example |
| `PRIMO_SCOPE` | Library scope | See .env.example |
| `PRIMO_INST` | Library institution | See .env.example |
| `PRIMO_PUBLIC_TIMEOUT` | API timeout (seconds) | `20` |

## Performance Tuning

### For High Traffic

1. **Use GPT-3.5-turbo**:
   ```bash
   OPENAI_MODEL=gpt-3.5-turbo
   ```
   - Faster responses
   - Lower costs
   - Good for most queries

2. **Increase timeout**:
   ```bash
   PRIMO_PUBLIC_TIMEOUT=30
   ```

3. **Use caching** (future enhancement):
   - Cache frequent queries
   - Reduce API calls

### For Better Quality

1. **Use GPT-4**:
   ```bash
   OPENAI_MODEL=gpt-4
   ```
   - Better understanding
   - More accurate parameter extraction
   - Better conversation flow

2. **Adjust temperature**:
   ```bash
   OPENAI_TEMPERATURE=0.5  # More focused
   # or
   OPENAI_TEMPERATURE=0.9  # More creative
   ```

## Monitoring

### Application Logs

```bash
# Streamlit logs (local)
tail -f ~/.streamlit/logs/streamlit.log

# Docker logs
docker logs scholarbot -f

# Streamlit Cloud logs
# Available in dashboard under "Manage app" → "Logs"
```

### Health Checks

```bash
# Check application health
curl http://localhost:8501/_stcore/health

# Expected response: 200 OK
```

### Metrics to Monitor

- Response time per query
- API error rate
- Memory usage
- Number of active sessions
- Tool call success rate

## Security Best Practices

### API Key Security

1. **Never commit .env file**
   - Already in .gitignore
   - Use environment variables in production

2. **Rotate keys regularly**
   - Change OpenAI API key periodically
   - Update in deployment platform

3. **Use secrets management**
   - AWS Secrets Manager
   - Google Secret Manager
   - Azure Key Vault

### Network Security

1. **Use HTTPS**
   - Streamlit Cloud provides HTTPS automatically
   - Configure SSL/TLS for custom deployments

2. **Rate limiting** (future enhancement)
   - Limit requests per user
   - Prevent abuse

3. **Authentication** (future enhancement)
   - Add login system
   - Restrict access

## Troubleshooting

### Common Issues

#### 1. "Module not found" errors
```bash
# Solution: Reinstall dependencies
pip install -r requirements.txt
```

#### 2. Slow responses
```bash
# Solution: Use faster model
OPENAI_MODEL=gpt-3.5-turbo
```

#### 3. API timeout errors
```bash
# Solution: Increase timeout
PRIMO_PUBLIC_TIMEOUT=30
```

#### 4. Memory issues
```bash
# Solution: Clear conversation more frequently
# Or limit message history length
```

### Debug Mode

Enable detailed logging:
```bash
LOG_LEVEL=DEBUG streamlit run app.py
```

## Scaling

### Horizontal Scaling

For high traffic:

1. **Load Balancer**:
   - Deploy multiple instances
   - Use nginx or cloud load balancer
   - Session stickiness for conversation continuity

2. **Database for State**:
   - Replace MemorySaver with Redis
   - Share state across instances
   - Enable true horizontal scaling

### Vertical Scaling

For better performance:

1. **Increase resources**:
   - More CPU for LLM processing
   - More memory for conversation state
   - Faster network for API calls

## Cost Optimization

### OpenAI API Costs

| Model | Cost per 1K tokens |
|-------|-------------------|
| GPT-4 | ~$0.03 (input) / $0.06 (output) |
| GPT-3.5-turbo | ~$0.0015 (input) / $0.002 (output) |

### Strategies to Reduce Costs

1. **Use GPT-3.5-turbo** for most queries
2. **Limit conversation history** length
3. **Cache frequent queries**
4. **Set max_tokens** appropriately
5. **Monitor usage** regularly

## Backup and Recovery

### Conversation Data

Currently in-memory only (lost on restart)

Future enhancements:
- Export conversation history
- Backup to cloud storage
- Restore from backups

### Application Code

- Use version control (Git)
- Tag releases
- Maintain changelog

## Maintenance

### Regular Tasks

- [ ] Update dependencies monthly
- [ ] Review logs weekly
- [ ] Monitor API costs
- [ ] Test new OpenAI models
- [ ] Update documentation
- [ ] Collect user feedback

### Updates

```bash
# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart application
# (method depends on deployment platform)
```

## Support

### Getting Help

1. Check logs for errors
2. Review documentation
3. Search GitHub issues
4. Contact maintainers

### Reporting Issues

Include:
- Error message
- Steps to reproduce
- Environment details
- Logs (sanitized)

---

**Deployment Checklist**

- [ ] Code pushed to repository
- [ ] Environment variables configured
- [ ] API keys secured
- [ ] Application tested locally
- [ ] Deployment platform selected
- [ ] Application deployed
- [ ] Health check verified
- [ ] Monitoring configured
- [ ] Documentation updated
- [ ] Team notified

Good luck with your deployment! 🚀
