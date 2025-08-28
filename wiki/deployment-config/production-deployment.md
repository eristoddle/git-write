# Deployment & Configuration

This section covers deploying GitWrite in production environments, from single-server setups to scalable cloud deployments. It includes configuration management, security considerations, monitoring, and maintenance procedures.

## Deployment Overview

GitWrite supports multiple deployment strategies depending on your needs:

1. **Single Server Deployment**: All components on one machine
2. **Containerized Deployment**: Docker-based deployment with orchestration
3. **Cloud-Native Deployment**: Kubernetes with managed services
4. **Serverless Deployment**: Function-based deployment for specific use cases
5. **Hybrid Deployment**: Mix of on-premises and cloud components

## Production Deployment

### Prerequisites

**System Requirements:**
- **CPU**: 2+ cores (4+ recommended for high load)
- **Memory**: 4GB RAM minimum (8GB+ recommended)
- **Storage**: 20GB+ SSD storage
- **Network**: Stable internet connection with HTTPS capability
- **OS**: Ubuntu 20.04+, CentOS 8+, or compatible Linux distribution

**Dependencies:**
- Python 3.10+
- Node.js 18+ (for frontend builds)
- Git 2.20+
- Pandoc (for export functionality)
- SSL certificates for HTTPS
- Reverse proxy (Nginx or Apache)

### Single Server Production Setup

#### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y \
  python3.10 \
  python3.10-venv \
  python3-pip \
  nodejs \
  npm \
  git \
  pandoc \
  nginx \
  certbot \
  python3-certbot-nginx \
  build-essential \
  libgit2-dev

# Create GitWrite user
sudo useradd -r -m -s /bin/bash gitwrite
sudo usermod -aG sudo gitwrite
```

#### 2. Application Setup

```bash
# Switch to GitWrite user
sudo su - gitwrite

# Clone repository
git clone https://github.com/eristoddle/git-write.git
cd git-write

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install poetry
poetry install --no-dev

# Build frontend
cd gitwrite-web
npm ci --production
npm run build
cd ..

# Copy built frontend to API static directory
cp -r gitwrite-web/dist/* static/
```

#### 3. Configuration

**Environment Configuration (`/home/gitwrite/git-write/.env`):**
```env
# API Configuration
GITWRITE_API_HOST=0.0.0.0
GITWRITE_API_PORT=8000
GITWRITE_API_WORKERS=4

# Security
SECRET_KEY=your-secret-key-here-change-this
JWT_SECRET_KEY=your-jwt-secret-here-change-this
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database (if using external database)
DATABASE_URL=postgresql://user:password@localhost:5432/gitwrite

# Storage
GITWRITE_DATA_DIR=/var/lib/gitwrite
GITWRITE_REPOS_DIR=/var/lib/gitwrite/repositories
GITWRITE_EXPORTS_DIR=/var/lib/gitwrite/exports

# Email (for notifications)
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USER=notifications@your-domain.com
SMTP_PASSWORD=your-smtp-password
SMTP_TLS=true

# External Services
PANDOC_PATH=/usr/bin/pandoc

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/gitwrite/gitwrite.log
```

**GitWrite Configuration (`gitwrite.yaml`):**
```yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 4
  timeout: 300

security:
  secret_key: ${SECRET_KEY}
  jwt_secret: ${JWT_SECRET_KEY}
  allowed_hosts: ${ALLOWED_HOSTS}
  cors_origins:
    - https://your-domain.com
    - https://www.your-domain.com

storage:
  data_directory: ${GITWRITE_DATA_DIR}
  repositories_directory: ${GITWRITE_REPOS_DIR}
  exports_directory: ${GITWRITE_EXPORTS_DIR}
  max_repository_size: 1GB
  max_file_size: 100MB

features:
  collaboration: true
  export: true
  api_access: true
  web_interface: true

limits:
  max_repositories_per_user: 10
  max_collaborators_per_repository: 50
  rate_limit_requests_per_minute: 60

monitoring:
  metrics_enabled: true
  health_check_enabled: true
  prometheus_metrics: true
```

#### 4. Systemd Service

**Service File (`/etc/systemd/system/gitwrite.service`):**
```ini
[Unit]
Description=GitWrite API Server
After=network.target
Wants=network.target

[Service]
Type=exec
User=gitwrite
Group=gitwrite
WorkingDirectory=/home/gitwrite/git-write
Environment=PATH=/home/gitwrite/git-write/venv/bin
EnvironmentFile=/home/gitwrite/git-write/.env
ExecStart=/home/gitwrite/git-write/venv/bin/uvicorn gitwrite_api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --access-log \
  --log-config logging.yaml
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=gitwrite

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/gitwrite /var/log/gitwrite

[Install]
WantedBy=multi-user.target
```

#### 5. Nginx Configuration

**Main Configuration (`/etc/nginx/sites-available/gitwrite`):**
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;

# Upstream backend
upstream gitwrite_backend {
    least_conn;
    server 127.0.0.1:8000 max_fails=3 fail_timeout=30s;
    # Add more servers for load balancing:
    # server 127.0.0.1:8001 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # File upload size limit
    client_max_body_size 100M;

    # Timeout settings
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    # API routes
    location /api/ {
        limit_req zone=api burst=20 nodelay;

        proxy_pass http://gitwrite_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Authentication routes (stricter rate limiting)
    location /api/auth/ {
        limit_req zone=auth burst=10 nodelay;

        proxy_pass http://gitwrite_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files (frontend)
    location / {
        root /home/gitwrite/git-write/static;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Health check
    location /health {
        proxy_pass http://gitwrite_backend;
        access_log off;
    }

    # Monitoring
    location /metrics {
        proxy_pass http://gitwrite_backend;
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        deny all;
    }
}
```

#### 6. SSL Certificate Setup

```bash
# Install SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Test SSL configuration
sudo nginx -t

# Enable and start services
sudo systemctl enable nginx
sudo systemctl enable gitwrite
sudo systemctl start nginx
sudo systemctl start gitwrite

# Verify services are running
sudo systemctl status nginx
sudo systemctl status gitwrite
```

### Containerized Deployment

#### Docker Setup

**Dockerfile (Production):**
```dockerfile
# Multi-stage build for optimization
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
COPY gitwrite-web/package*.json ./
RUN npm ci --only=production

COPY gitwrite-web/ ./
RUN npm run build

# Python backend
FROM python:3.10-slim AS backend

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgit2-dev \
    build-essential \
    pandoc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash gitwrite

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY --chown=gitwrite:gitwrite . .

# Copy built frontend
COPY --from=frontend-build --chown=gitwrite:gitwrite /app/frontend/dist ./static

# Create necessary directories
RUN mkdir -p /var/lib/gitwrite/repositories /var/lib/gitwrite/exports /var/log/gitwrite && \
    chown -R gitwrite:gitwrite /var/lib/gitwrite /var/log/gitwrite

USER gitwrite

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "gitwrite_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Docker Compose (Production):**
```yaml
version: '3.8'

services:
  gitwrite:
    build: .
    container_name: gitwrite-app
    restart: unless-stopped
    environment:
      - GITWRITE_API_HOST=0.0.0.0
      - GITWRITE_API_PORT=8000
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DATABASE_URL=postgresql://gitwrite:${DB_PASSWORD}@postgres:5432/gitwrite
    volumes:
      - gitwrite_data:/var/lib/gitwrite
      - gitwrite_logs:/var/log/gitwrite
    depends_on:
      - postgres
      - redis
    networks:
      - gitwrite_network

  postgres:
    image: postgres:15-alpine
    container_name: gitwrite-db
    restart: unless-stopped
    environment:
      - POSTGRES_DB=gitwrite
      - POSTGRES_USER=gitwrite
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - gitwrite_network

  redis:
    image: redis:7-alpine
    container_name: gitwrite-cache
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - gitwrite_network

  nginx:
    image: nginx:alpine
    container_name: gitwrite-proxy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl/certs:ro
      - nginx_logs:/var/log/nginx
    depends_on:
      - gitwrite
    networks:
      - gitwrite_network

volumes:
  gitwrite_data:
  gitwrite_logs:
  postgres_data:
  redis_data:
  nginx_logs:

networks:
  gitwrite_network:
    driver: bridge
```

#### Kubernetes Deployment

**Namespace (`namespace.yaml`):**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: gitwrite
```

**ConfigMap (`configmap.yaml`):**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gitwrite-config
  namespace: gitwrite
data:
  GITWRITE_API_HOST: "0.0.0.0"
  GITWRITE_API_PORT: "8000"
  LOG_LEVEL: "INFO"
  GITWRITE_DATA_DIR: "/var/lib/gitwrite"
```

**Secrets (`secrets.yaml`):**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: gitwrite-secrets
  namespace: gitwrite
type: Opaque
data:
  SECRET_KEY: <base64-encoded-secret>
  JWT_SECRET_KEY: <base64-encoded-jwt-secret>
  DB_PASSWORD: <base64-encoded-db-password>
```

**Deployment (`deployment.yaml`):**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gitwrite-api
  namespace: gitwrite
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gitwrite-api
  template:
    metadata:
      labels:
        app: gitwrite-api
    spec:
      containers:
      - name: gitwrite
        image: gitwrite/gitwrite:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: gitwrite-config
        - secretRef:
            name: gitwrite-secrets
        volumeMounts:
        - name: gitwrite-data
          mountPath: /var/lib/gitwrite
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
      volumes:
      - name: gitwrite-data
        persistentVolumeClaim:
          claimName: gitwrite-pvc
```

**Service (`service.yaml`):**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: gitwrite-service
  namespace: gitwrite
spec:
  selector:
    app: gitwrite-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

**Ingress (`ingress.yaml`):**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: gitwrite-ingress
  namespace: gitwrite
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: gitwrite-tls
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: gitwrite-service
            port:
              number: 80
```

## Security Configuration

### HTTPS and SSL

**Let's Encrypt Setup:**
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

**Custom SSL Certificate:**
```bash
# Place certificate files
sudo cp your-cert.pem /etc/ssl/certs/gitwrite.pem
sudo cp your-private-key.pem /etc/ssl/private/gitwrite.key

# Set proper permissions
sudo chmod 644 /etc/ssl/certs/gitwrite.pem
sudo chmod 600 /etc/ssl/private/gitwrite.key
```

### Authentication and Authorization

**JWT Configuration:**
```python
# Security settings in configuration
JWT_SETTINGS = {
    'SECRET_KEY': os.environ['JWT_SECRET_KEY'],
    'ALGORITHM': 'HS256',
    'ACCESS_TOKEN_EXPIRE_HOURS': 24,
    'REFRESH_TOKEN_EXPIRE_DAYS': 30,
    'REQUIRE_HTTPS': True,
    'SECURE_COOKIES': True
}
```

**OAuth Integration:**
```python
# OAuth providers configuration
OAUTH_PROVIDERS = {
    'github': {
        'client_id': os.environ['GITHUB_CLIENT_ID'],
        'client_secret': os.environ['GITHUB_CLIENT_SECRET'],
        'scope': 'user:email'
    },
    'google': {
        'client_id': os.environ['GOOGLE_CLIENT_ID'],
        'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
        'scope': 'openid email profile'
    }
}
```

### Firewall Configuration

**UFW Setup (Ubuntu):**
```bash
# Enable firewall
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow specific IPs for admin access
sudo ufw allow from 192.168.1.100 to any port 22

# Check status
sudo ufw status verbose
```

## Monitoring and Logging

### Application Monitoring

**Prometheus Configuration (`prometheus.yml`):**
```yaml
global:
  scrape_interval: 15s

rule_files:
  - "gitwrite_rules.yml"

scrape_configs:
  - job_name: 'gitwrite'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

**Grafana Dashboard:**
```json
{
  "dashboard": {
    "title": "GitWrite Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
          }
        ]
      }
    ]
  }
}
```

### Logging Configuration

**Logging Configuration (`logging.yaml`):**
```yaml
version: 1
disable_existing_loggers: False

formatters:
  detailed:
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  simple:
    format: "%(levelname)s: %(message)s"

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: simple
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: detailed
    filename: /var/log/gitwrite/gitwrite.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

  error_file:
    class: logging.handlers.RotatingFileHandler
    level: ERROR
    formatter: detailed
    filename: /var/log/gitwrite/error.log
    maxBytes: 10485760
    backupCount: 5

loggers:
  gitwrite_api:
    level: INFO
    handlers: [console, file, error_file]
    propagate: False

  gitwrite_core:
    level: INFO
    handlers: [console, file, error_file]
    propagate: False

  uvicorn:
    level: INFO
    handlers: [console, file]
    propagate: False

root:
  level: WARNING
  handlers: [console, file]
```

## Backup and Recovery

### Automated Backup

**Backup Script (`backup.sh`):**
```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/var/backups/gitwrite"
DATA_DIR="/var/lib/gitwrite"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup GitWrite data
echo "Starting GitWrite backup..."
tar -czf "$BACKUP_DIR/gitwrite_data_$DATE.tar.gz" -C "$DATA_DIR" .

# Backup database (if using PostgreSQL)
if command -v pg_dump &> /dev/null; then
    pg_dump -h localhost -U gitwrite gitwrite > "$BACKUP_DIR/database_$DATE.sql"
    gzip "$BACKUP_DIR/database_$DATE.sql"
fi

# Backup configuration
cp /home/gitwrite/git-write/.env "$BACKUP_DIR/config_$DATE.env"
cp /home/gitwrite/git-write/gitwrite.yaml "$BACKUP_DIR/gitwrite_config_$DATE.yaml"

# Clean old backups
find "$BACKUP_DIR" -name "gitwrite_*" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR/gitwrite_data_$DATE.tar.gz"
```

**Cron Job:**
```bash
# Add to crontab
0 2 * * * /usr/local/bin/gitwrite-backup.sh
```

### Disaster Recovery

**Recovery Procedure:**
```bash
# 1. Stop services
sudo systemctl stop gitwrite nginx

# 2. Restore data
cd /var/lib/gitwrite
sudo tar -xzf /var/backups/gitwrite/gitwrite_data_YYYYMMDD_HHMMSS.tar.gz

# 3. Restore database
sudo -u postgres psql
DROP DATABASE IF EXISTS gitwrite;
CREATE DATABASE gitwrite;
\q
gunzip -c /var/backups/gitwrite/database_YYYYMMDD_HHMMSS.sql.gz | sudo -u postgres psql gitwrite

# 4. Restore configuration
cp /var/backups/gitwrite/config_YYYYMMDD_HHMMSS.env /home/gitwrite/git-write/.env
cp /var/backups/gitwrite/gitwrite_config_YYYYMMDD_HHMMSS.yaml /home/gitwrite/git-write/gitwrite.yaml

# 5. Fix permissions
sudo chown -R gitwrite:gitwrite /var/lib/gitwrite
sudo chown gitwrite:gitwrite /home/gitwrite/git-write/.env

# 6. Start services
sudo systemctl start gitwrite nginx

# 7. Verify recovery
curl -f http://localhost/health
```

---

*This deployment guide provides comprehensive instructions for setting up GitWrite in production environments with proper security, monitoring, and backup procedures. Choose the deployment method that best fits your infrastructure and scaling requirements.*