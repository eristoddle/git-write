# GitWrite Deployment Guide

*Production Setup and Configuration*

## Table of Contents
1. [Overview](#overview)
2. [Development Setup](#development-setup)
3. [Production Deployment](#production-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Environment Configuration](#environment-configuration)
6. [Security Considerations](#security-considerations)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)

## Overview

GitWrite consists of multiple components:
- **Core Engine**: Python library for Git operations
- **REST API**: FastAPI server (Python)
- **Web Interface**: React/TypeScript frontend
- **CLI Tool**: Command-line interface
- **SDK**: TypeScript/JavaScript client library

### System Requirements

#### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 20GB (plus space for repositories)
- **OS**: Linux (Ubuntu 20.04+), macOS, Windows 10+

#### Recommended for Production
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 100GB+ SSD
- **OS**: Ubuntu 22.04 LTS or CentOS 8+

#### Software Dependencies
- Python 3.10+
- Node.js 16+
- Git 2.30+
- PostgreSQL 12+ (optional, for production user management)
- Nginx (for production web serving)

## Development Setup

### Quick Start
```bash
# Clone repository
git clone <gitwrite-repo-url>
cd git-write

# Install Python dependencies
pip install poetry
poetry install

# Install Node.js dependencies
cd gitwrite-web
npm install
cd ../gitwrite-sdk
npm install && npm run build
cd ..

# Start development servers
# Terminal 1: API Server
poetry run uvicorn gitwrite_api.main:app --reload --port 8000

# Terminal 2: Web Interface
cd gitwrite-web
npm run dev
```

### Environment Setup
Create environment files:

**.env** (project root):
```bash
# API Configuration
GITWRITE_SECRET_KEY=your-secret-key-here
GITWRITE_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Repository Storage
GITWRITE_REPOS_PATH=/path/to/repositories

# CORS Origins
GITWRITE_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:5174

# Database (optional)
DATABASE_URL=sqlite:///./gitwrite.db
```

**gitwrite-web/.env**:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Production Deployment

### Architecture Overview
```
[Internet] → [Load Balancer] → [Reverse Proxy (Nginx)]
                                      ↓
                              [API Server (FastAPI)]
                                      ↓
                              [File System (Git Repos)]
                                      ↓
                              [Database (PostgreSQL)]
```

### Step-by-Step Production Setup

#### 1. Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3.10 python3.10-venv python3.10-dev \
  nodejs npm git nginx postgresql postgresql-contrib \
  build-essential libgit2-dev pkg-config

# Create application user
sudo useradd -m -s /bin/bash gitwrite
sudo mkdir -p /opt/gitwrite
sudo chown gitwrite:gitwrite /opt/gitwrite
```

#### 2. Application Installation
```bash
# Switch to gitwrite user
sudo su - gitwrite

# Clone and setup application
cd /opt/gitwrite
git clone <gitwrite-repo-url> .

# Install Python dependencies
python3.10 -m pip install poetry
poetry install --only=production

# Build web interface
cd gitwrite-web
npm ci --production
npm run build

# Build SDK
cd ../gitwrite-sdk
npm ci --production
npm run build
```

#### 3. Database Setup (PostgreSQL)
```bash
# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE gitwrite;
CREATE USER gitwrite WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE gitwrite TO gitwrite;
\q
EOF
```

#### 4. Configuration Files

**/opt/gitwrite/.env**:
```bash
# Production API Configuration
GITWRITE_SECRET_KEY=your-very-secure-secret-key-at-least-32-characters
GITWRITE_ACCESS_TOKEN_EXPIRE_MINUTES=480

# Repository Storage
GITWRITE_REPOS_PATH=/opt/gitwrite/repositories

# Database
DATABASE_URL=postgresql://gitwrite:secure_password_here@localhost/gitwrite

# CORS Origins (adjust for your domain)
GITWRITE_ALLOWED_ORIGINS=https://yourapp.com,https://www.yourapp.com

# Security
GITWRITE_ENVIRONMENT=production
```

#### 5. Systemd Service Setup

**/etc/systemd/system/gitwrite-api.service**:
```ini
[Unit]
Description=GitWrite API Server
After=network.target postgresql.service

[Service]
Type=simple
User=gitwrite
Group=gitwrite
WorkingDirectory=/opt/gitwrite
Environment=PATH=/opt/gitwrite/.venv/bin
ExecStart=/opt/gitwrite/.venv/bin/uvicorn gitwrite_api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable gitwrite-api
sudo systemctl start gitwrite-api
```

#### 6. Nginx Configuration

**/etc/nginx/sites-available/gitwrite**:
```nginx
server {
    listen 80;
    server_name yourapp.com www.yourapp.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourapp.com www.yourapp.com;

    # SSL Configuration (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourapp.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Web interface (static files)
    location / {
        root /opt/gitwrite/gitwrite-web/dist;
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeouts for large operations
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # File upload size limits
    client_max_body_size 50M;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/gitwrite /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 7. SSL Certificate (Let's Encrypt)
```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourapp.com -d www.yourapp.com

# Test renewal
sudo certbot renew --dry-run
```

## Docker Deployment

### Dockerfile (API)
```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgit2-dev \
    pkg-config \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -s /bin/bash gitwrite

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only=production

# Copy application code
COPY . .
RUN chown -R gitwrite:gitwrite /app

# Switch to app user
USER gitwrite

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Start application
CMD ["uvicorn", "gitwrite_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose
**docker-compose.yml**:
```yaml
version: '3.8'

services:
  # Database
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: gitwrite
      POSTGRES_USER: gitwrite
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  # API Server
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://gitwrite:${DB_PASSWORD}@postgres:5432/gitwrite
      - GITWRITE_SECRET_KEY=${SECRET_KEY}
      - GITWRITE_REPOS_PATH=/app/repositories
    volumes:
      - ./repositories:/app/repositories
    depends_on:
      - postgres
    restart: unless-stopped

  # Web Interface
  web:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./gitwrite-web/dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl/certs:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
```

**.env.docker**:
```bash
DB_PASSWORD=secure_random_password_here
SECRET_KEY=your-very-secure-secret-key-at-least-32-characters
```

### Docker Deployment Commands
```bash
# Build and start services
docker-compose --env-file .env.docker up -d

# View logs
docker-compose logs -f

# Update application
docker-compose build --no-cache
docker-compose up -d

# Backup database
docker-compose exec postgres pg_dump -U gitwrite gitwrite > backup.sql
```

## Environment Configuration

### Environment Variables

#### API Server
```bash
# Required
GITWRITE_SECRET_KEY=          # JWT signing key (32+ characters)
GITWRITE_REPOS_PATH=          # Path to store repositories

# Optional
GITWRITE_ACCESS_TOKEN_EXPIRE_MINUTES=30    # Token expiration
GITWRITE_ALLOWED_ORIGINS=                  # CORS origins
GITWRITE_ENVIRONMENT=development           # Environment mode
DATABASE_URL=                              # Database connection string
```

#### Web Interface
```bash
# Required
VITE_API_BASE_URL=            # API server URL

# Optional
VITE_APP_TITLE=GitWrite       # Application title
VITE_ENABLE_ANALYTICS=false   # Analytics tracking
```

### Configuration Validation
Create a configuration checker:

**scripts/check-config.py**:
```python
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def check_config():
    """Validate GitWrite configuration"""
    errors = []
    
    # Check required environment variables
    required_vars = [
        'GITWRITE_SECRET_KEY',
        'GITWRITE_REPOS_PATH'
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required environment variable: {var}")
    
    # Check secret key strength
    secret_key = os.getenv('GITWRITE_SECRET_KEY', '')
    if len(secret_key) < 32:
        errors.append("GITWRITE_SECRET_KEY must be at least 32 characters")
    
    # Check repository path
    repos_path = os.getenv('GITWRITE_REPOS_PATH')
    if repos_path:
        if not Path(repos_path).exists():
            errors.append(f"Repository path does not exist: {repos_path}")
        elif not os.access(repos_path, os.W_OK):
            errors.append(f"Repository path is not writable: {repos_path}")
    
    # Report results
    if errors:
        print("❌ Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ Configuration is valid")

if __name__ == "__main__":
    check_config()
```

## Security Considerations

### API Security
1. **Strong Secret Keys**: Use cryptographically secure random keys
2. **HTTPS Only**: Force SSL/TLS in production
3. **CORS Configuration**: Restrict origins to your domains
4. **Input Validation**: All inputs are validated by Pydantic models
5. **SQL Injection**: Use ORM/parameterized queries only

### File System Security
```bash
# Set proper permissions
sudo chown -R gitwrite:gitwrite /opt/gitwrite/repositories
sudo chmod -R 750 /opt/gitwrite/repositories

# Use AppArmor/SELinux for additional sandboxing
```

### Database Security
```sql
-- Limit user permissions
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE gitwrite TO gitwrite;
GRANT USAGE ON SCHEMA public TO gitwrite;
GRANT CREATE ON SCHEMA public TO gitwrite;
```

### Network Security
```bash
# Firewall configuration (UFW)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Close API port to external access
sudo ufw deny 8000/tcp
```

## Monitoring and Maintenance

### Health Checks
Create monitoring endpoints:

**health.py**:
```python
from fastapi import APIRouter
import psutil
from pathlib import Path
import os

router = APIRouter()

@router.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "disk_usage": psutil.disk_usage("/").percent,
        "memory_usage": psutil.virtual_memory().percent,
        "repos_path_exists": Path(os.getenv("GITWRITE_REPOS_PATH", "/tmp")).exists()
    }
```

### Log Management
Configure log rotation:

**/etc/logrotate.d/gitwrite**:
```
/var/log/gitwrite/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 gitwrite gitwrite
    postrotate
        systemctl reload gitwrite-api
    endscript
}
```

### Backup Strategy
```bash
#!/bin/bash
# backup-gitwrite.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/gitwrite"
REPOS_PATH="/opt/gitwrite/repositories"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup repositories
tar -czf "$BACKUP_DIR/repos_$DATE.tar.gz" -C "$REPOS_PATH" .

# Backup database
pg_dump -U gitwrite gitwrite > "$BACKUP_DIR/database_$DATE.sql"

# Clean old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.sql" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### Performance Monitoring
Use tools like:
- **Prometheus + Grafana**: Metrics and dashboards
- **htop/top**: Real-time system monitoring
- **pg_stat_activity**: Database performance
- **nginx access logs**: Web traffic analysis

## Troubleshooting

### Common Issues

#### API Server Won't Start
```bash
# Check logs
sudo journalctl -u gitwrite-api -f

# Common causes:
# 1. Port already in use
sudo ss -tlnp | grep :8000

# 2. Permission issues
sudo chown -R gitwrite:gitwrite /opt/gitwrite

# 3. Missing dependencies
poetry install
```

#### Database Connection Errors
```bash
# Test database connection
psql postgresql://gitwrite:password@localhost/gitwrite

# Check PostgreSQL status
sudo systemctl status postgresql

# Reset database if needed
sudo -u postgres dropdb gitwrite
sudo -u postgres createdb gitwrite
```

#### File Permission Issues
```bash
# Fix repository permissions
sudo chown -R gitwrite:gitwrite /opt/gitwrite/repositories
sudo chmod -R 755 /opt/gitwrite/repositories

# Check disk space
df -h
```

#### Web Interface Not Loading
```bash
# Check nginx status
sudo systemctl status nginx

# Test nginx configuration
sudo nginx -t

# Check if files exist
ls -la /opt/gitwrite/gitwrite-web/dist/

# Rebuild if needed
cd /opt/gitwrite/gitwrite-web
npm run build
```

### Performance Issues

#### High Memory Usage
- Monitor Git repository sizes
- Implement repository archiving for old projects
- Increase swap space if needed

#### Slow API Responses
- Check database query performance
- Monitor disk I/O (SSD recommended)
- Implement Redis caching for frequent queries

#### High CPU Usage
- Monitor for runaway Git processes
- Implement operation timeouts
- Consider horizontal scaling

### Recovery Procedures

#### Restore from Backup
```bash
# Stop services
sudo systemctl stop gitwrite-api nginx

# Restore repositories
tar -xzf repos_backup.tar.gz -C /opt/gitwrite/repositories/

# Restore database
psql -U gitwrite gitwrite < database_backup.sql

# Restart services
sudo systemctl start gitwrite-api nginx
```

#### Disaster Recovery
1. **Off-site Backups**: Regular sync to cloud storage
2. **Documentation**: Keep deployment docs updated
3. **Testing**: Regular disaster recovery drills
4. **Monitoring**: 24/7 uptime monitoring

### Support and Updates

#### Updating GitWrite
```bash
# Pull latest changes
cd /opt/gitwrite
git pull origin main

# Update dependencies
poetry install
cd gitwrite-web && npm ci && npm run build

# Restart services
sudo systemctl restart gitwrite-api
sudo systemctl reload nginx
```

#### Getting Support
- Check logs first: API server, nginx, system logs
- Review configuration with validation script
- Monitor system resources (CPU, memory, disk)
- Keep backups current before making changes

---

This deployment guide covers development setup through production deployment. Choose the approach that best fits your infrastructure and security requirements.