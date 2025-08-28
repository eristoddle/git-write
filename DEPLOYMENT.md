# GitWrite Development and Deployment Guide

This guide covers setting up GitWrite for development and deploying it to production.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- Node.js 18+ (for local frontend development)
- Python 3.10+ (for local API development)

### Development Setup

1. **Clone and Setup Environment**
   ```bash
   git clone <repository-url>
   cd git-write
   cp .env.example .env
   ```

2. **Start Development Environment**
   ```bash
   ./deploy.sh development
   ```

3. **Access Services**
   - API: http://localhost:8000
   - Web App (Dev): http://localhost:3001
   - API Documentation: http://localhost:8000/docs

## Deployment Options

### Development Environment

**Purpose**: Local development with hot reload and debugging

**Services**:
- GitWrite API with development settings
- Frontend with hot reload
- Shared volumes for code changes

**Command**:
```bash
./deploy.sh development
```

**Features**:
- Hot reload for both frontend and backend
- Debug logging enabled
- Development database (SQLite)
- Accessible on localhost

### Production Environment

**Purpose**: Production deployment with optimized performance and security

**Services**:
- GitWrite API (optimized build)
- Frontend (production build with Nginx)
- PostgreSQL database
- Redis for caching
- Nginx reverse proxy

**Command**:
```bash
./deploy.sh production
```

**Features**:
- Production-optimized builds
- Security headers and HTTPS support
- Database persistence
- Health checks and auto-restart
- Resource optimization

## Configuration

### Environment Variables

#### Core Settings
- `GITWRITE_ENV`: Environment mode (development/production)
- `GITWRITE_SECRET_KEY`: Secret key for authentication (CHANGE IN PRODUCTION!)
- `GITWRITE_API_HOST`: API host binding
- `GITWRITE_API_PORT`: API port

#### Storage Settings
- `GITWRITE_REPO_PATH`: Path for Git repositories
- `GITWRITE_EXPORT_PATH`: Path for exported files
- `GITWRITE_LOG_LEVEL`: Logging level (debug/info/warning/error)

#### Database Settings (Production)
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password

#### Security Settings
- `GITWRITE_CORS_ORIGINS`: Allowed CORS origins
- `GITWRITE_USE_SSL`: Enable SSL/TLS
- `GITWRITE_SSL_CERT_PATH`: SSL certificate path
- `GITWRITE_SSL_KEY_PATH`: SSL private key path

### Environment Files

- `.env.example`: Development template
- `.env.production`: Production template
- `.env`: Your local configuration (create from template)

## Available Commands

### Deployment Script (`./deploy.sh`)

| Command | Description |
|---------|-------------|
| `development` | Start development environment (default) |
| `production` | Start production environment |
| `test` | Start test environment |
| `status` | Show service status |
| `logs` | Show service logs |
| `stop` | Stop all services |
| `cleanup` | Stop services and clean up Docker resources |
| `backup` | Create backup of data and configuration |
| `restore <dir>` | Restore data from backup directory |
| `update` | Update GitWrite and restart services |
| `test-run` | Run the test suite |
| `help` | Show help message |

### Development Commands

```bash
# Start development environment
./deploy.sh development

# View logs
./deploy.sh logs

# Stop services
./deploy.sh stop

# Run tests
./deploy.sh test-run

# Check status
./deploy.sh status
```

### Production Commands

```bash
# Deploy to production
./deploy.sh production

# Create backup
./deploy.sh backup

# Update GitWrite
./deploy.sh update

# Restore from backup
./deploy.sh restore backup_20231201_120000
```

## Data Management

### Backup and Restore

**Create Backup**:
```bash
./deploy.sh backup
```

This creates a timestamped backup directory containing:
- All Git repositories
- Exported files
- Environment configuration

**Restore from Backup**:
```bash
./deploy.sh restore backup_20231201_120000
```

### Data Persistence

**Development**: Data is stored in Docker volumes and local directories.

**Production**: Data is stored in named Docker volumes with backup capabilities.

**Important Directories**:
- `data/repositories/`: Git repositories
- `data/exports/`: Exported files
- `logs/`: Application logs

## Local Development (Without Docker)

### Backend (API)

1. **Install Dependencies**
   ```bash
   pip install poetry
   poetry install
   ```

2. **Run API**
   ```bash
   poetry run uvicorn gitwrite_api.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Run Tests**
   ```bash
   poetry run pytest
   ```

### Frontend

1. **Install Dependencies**
   ```bash
   cd gitwrite-web
   npm install
   ```

2. **Start Development Server**
   ```bash
   npm run dev
   ```

3. **Build for Production**
   ```bash
   npm run build
   ```

### CLI Tool

1. **Install in Development Mode**
   ```bash
   poetry install
   ```

2. **Run CLI**
   ```bash
   poetry run python gitwrite_cli/main.py --help
   ```

## Monitoring and Logs

### Health Checks

- API: `http://localhost:8000/health`
- Web: Available through Docker health checks

### Logs

**View All Logs**:
```bash
./deploy.sh logs
```

**View Specific Service**:
```bash
docker-compose logs -f gitwrite-api
docker-compose logs -f gitwrite-web
```

**Log Files** (if file logging is enabled):
- `logs/gitwrite-api.log`
- `logs/gitwrite-web.log`

## Security Considerations

### Development

- Uses default secret keys (acceptable for development)
- Debug mode enabled
- CORS allows all origins
- No SSL/TLS required

### Production

**IMPORTANT**: Before deploying to production:

1. **Change Secret Key**
   ```bash
   # Generate a secure secret key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Update Database Passwords**
   - Change `POSTGRES_PASSWORD` to a secure password
   - Use environment-specific configurations

3. **Configure SSL/TLS**
   - Obtain SSL certificates
   - Configure Nginx for HTTPS
   - Update `GITWRITE_USE_SSL=true`

4. **Set Proper CORS Origins**
   - Set `GITWRITE_CORS_ORIGINS` to your domain
   - Remove wildcard origins

5. **Review Environment Variables**
   - Disable debug mode
   - Set appropriate log levels
   - Configure proper paths

## Troubleshooting

### Common Issues

**Port Already in Use**:
```bash
# Check what's using the port
lsof -i :8000
# Or change the port in .env file
API_PORT=8001
```

**Permission Denied**:
```bash
# Make sure Docker daemon is running
sudo systemctl start docker
# Or restart Docker Desktop
```

**Build Failures**:
```bash
# Clean build
./deploy.sh cleanup
./deploy.sh development
```

**Database Connection Issues**:
```bash
# Check database service
docker-compose ps postgres
# Reset database
docker-compose down -v
./deploy.sh production
```

### Debug Mode

**Enable Debug Logging**:
```bash
# In .env file
GITWRITE_LOG_LEVEL=debug
GITWRITE_DEBUG=true
```

**Access Container for Debugging**:
```bash
# API container
docker-compose exec gitwrite-api bash

# Database container
docker-compose exec postgres psql -U gitwrite
```

## Updates and Maintenance

### Updating GitWrite

1. **Backup Data**
   ```bash
   ./deploy.sh backup
   ```

2. **Update Code**
   ```bash
   git pull origin main
   ```

3. **Update and Restart**
   ```bash
   ./deploy.sh update
   ```

### Updating Dependencies

**Python Dependencies**:
```bash
poetry update
```

**Node.js Dependencies**:
```bash
cd gitwrite-web
npm update
```

### Database Migrations

If database schema changes are introduced:

```bash
# Run migrations (when implemented)
docker-compose exec gitwrite-api python -m alembic upgrade head
```

## Performance Optimization

### Production Optimizations

1. **Resource Limits** (in docker-compose.yml):
   ```yaml
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: '0.5'
   ```

2. **Nginx Caching**:
   - Static file caching configured
   - Gzip compression enabled
   - Security headers added

3. **Database Optimization**:
   - Connection pooling
   - Query optimization
   - Index creation

### Scaling

**Horizontal Scaling**:
- Multiple API instances behind load balancer
- Redis for session storage
- External database

**Vertical Scaling**:
- Increase container resources
- Optimize query performance
- Enable caching

## Support

For issues and questions:
- Check the troubleshooting section
- Review logs: `./deploy.sh logs`
- Check service status: `./deploy.sh status`
- Create an issue in the repository