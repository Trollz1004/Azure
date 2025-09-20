# Azure - Twin Boss Agent

This repository hosts the Twin Boss Agent self-hosted stack with enhanced AI automation and business integration capabilities.

## Features

- **AI-Powered Business Automation**: Intelligent agents for customer service, content generation, and workflow management
- **Real-time Analytics**: Live dashboards and performance monitoring
- **Privacy Compliance**: GDPR-compliant data export and deletion tools
- **Marketing Automation**: AI-generated campaigns and content
- **Secure Configuration**: Environment-based secrets management
- **Docker Support**: Full containerization with Docker Compose
- **CI/CD Pipeline**: Automated testing and deployment via GitHub Actions

## Quick Start

### Option 1: Automated Setup (Recommended)
```bash
# Clone the repository
git clone https://github.com/Trollz1004/Azure.git
cd Azure

# Run the setup script
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Setup
1. **Install Dependencies**:
   ```bash
   npm install
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r api/requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.template .env
   # Edit .env with your API keys and configuration
   ```

3. **Start Services**:
   ```bash
   # Development mode
   npm start & 
   cd api && uvicorn app:app --host 0.0.0.0 --port 8011 --reload
   
   # Production mode with Docker
   docker-compose up -d
   ```

## Access Points

- **Main Console**: http://localhost:8080
- **API Documentation**: http://localhost:8011/docs
- **Fundraiser Page**: http://localhost/web/fundraiser.html
- **Kickstarter Page**: http://localhost/web/kickstarter.html
- **API Health**: http://localhost:8011/health

## API Endpoints

### Core Agent Features
- `POST /agents/twin/execute` - Execute AI agent queries
- `POST /agents/create` - Create new agent instances
- `POST /fundraising/deploy` - Deploy fundraising campaigns
- `POST /business/integrate` - Business system integration
- `POST /admin/automate` - Administrative automation
- `GET /previews/stream` - Real-time event stream (SSE)

### Enhanced AI Features
- `POST /ai/generate` - AI content generation
- `POST /marketing/create` - Marketing campaign creation
- `GET /analytics/dashboard` - Analytics and metrics
- `POST /automation/workflow` - Workflow automation
- `POST /privacy/request` - Privacy compliance requests

### Configuration & Management
- `GET /health` - Service health check
- `GET /config` - System configuration
- `POST /domains/host` - Domain management

## Configuration

### Environment Variables
```bash
# API Keys (required for AI features)
OPENAI_API_KEY=your-openai-key
GEMINI_API_KEY=your-gemini-key
STABILITY_API_KEY=your-stability-key
HUGGINGFACE_TOKEN=your-hf-token

# Service Configuration
LOCAL_API_KEY=local-dev-key-123
API_BASE=http://127.0.0.1:8011
NODE_ENV=development

# Business Configuration
EMAIL_MAIN=your-email@example.com
DOMAIN_MAIN=your-domain.com

# GitHub Integration (for deployment)
GITHUB_PAT=your-github-token
GITHUB_USERNAME=your-username

# Cloudflare (optional)
CLOUDFLARE_API_TOKEN=your-cloudflare-token
```

### Docker Configuration
The application includes Docker Compose setup with:
- **API Service**: Python FastAPI backend
- **Web Service**: Node.js frontend  
- **Nginx**: Reverse proxy and static content
- **Redis**: Caching and session storage

## Deployment

### Website Deployment
Deploy your website to GitHub Pages:
```powershell
# PowerShell
pwsh -File deploy-website.ps1

# Bash
python3 ai_automation.py
```

### Production Deployment
```bash
# Build and start production containers
docker-compose -f docker-compose.yml up -d

# Monitor logs
docker-compose logs -f

# Scale services
docker-compose up -d --scale twinboss_api=3
```

## Security Features

- **API Key Authentication**: All endpoints protected with configurable API keys
- **Environment-based Secrets**: No hardcoded credentials in source code
- **Rate Limiting**: Nginx-based request throttling
- **Security Headers**: HTTPS, CSP, and other security headers
- **Privacy Compliance**: GDPR-compliant data handling

## Development

### Running Tests
```bash
# Python API tests
cd api && python -m pytest tests/

# Node.js tests
npm test

# AI automation tests
python ai_automation.py
```

### Code Quality
```bash
# Python linting
flake8 api/ --max-line-length=127

# Python formatting
black api/ *.py

# Security scanning
docker run --rm -v $(pwd):/app aquasecurity/trivy fs /app
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Server    │    │   AI Services   │
│   (Node.js)     │◄──►│   (FastAPI)     │◄──►│   (OpenAI/etc)  │
│   Port 8080     │    │   Port 8011     │    │   External APIs │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx Proxy   │    │   Redis Cache   │    │   File Storage  │
│   Port 80/443   │    │   Port 6379     │    │   ./data/       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes and test thoroughly
4. Submit a pull request with detailed description

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Documentation**: Check the API docs at `/docs` endpoint
- **Issues**: Report bugs via GitHub Issues
- **Security**: Report security issues privately to the maintainers

---

**Note**: This system includes powerful AI automation capabilities. Always configure proper API keys and review generated content before use in production environments.
