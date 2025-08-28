# Scaling & Performance

Comprehensive guide to scaling GitWrite for high performance and availability, including horizontal scaling, performance optimization, load balancing, caching strategies, and monitoring. This guide covers everything from small team deployments to enterprise-scale installations.

## Scaling Architecture

```
GitWrite Scaling Architecture
    │
    ├─ Load Balancers
    │   ├─ Application Load Balancer
    │   ├─ WebSocket Load Balancer
    │   └─ CDN (Static Assets)
    │
    ├─ Application Tier
    │   ├─ Backend API Servers (N instances)
    │   ├─ Frontend Servers (N instances)
    │   └─ Background Workers
    │
    ├─ Database Tier
    │   ├─ Primary PostgreSQL
    │   ├─ Read Replicas
    │   └─ Connection Pooling
    │
    ├─ Cache Tier
    │   ├─ Redis Cluster
    │   ├─ Application Cache
    │   └─ CDN Cache
    │
    └─ Storage Tier
        ├─ Git Repository Storage
        ├─ File Upload Storage
        └─ Backup Storage
```

## Performance Targets

### Response Time Goals

| Operation | Target Response Time | Maximum Acceptable |
|-----------|---------------------|-------------------|
| Page Load | < 2 seconds | < 5 seconds |
| API Calls | < 200ms | < 500ms |
| Search | < 1 second | < 3 seconds |
| File Save | < 1 second | < 3 seconds |
| Real-time Updates | < 100ms | < 300ms |

### Throughput Goals

| Metric | Small Team | Medium Org | Enterprise |
|--------|------------|------------|------------|
| Concurrent Users | 10-50 | 100-500 | 1000+ |
| Requests/Second | 100 | 1,000 | 10,000+ |
| File Operations/Hour | 1,000 | 10,000 | 100,000+ |
| Storage Growth | 1GB/month | 10GB/month | 100GB/month |

## Horizontal Scaling

### Application Server Scaling

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  backend:
    image: gitwrite/backend:latest
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
    environment:
      - API_WORKERS=2
      - DATABASE_POOL_SIZE=5
    depends_on:
      - postgres
      - redis

  frontend:
    image: gitwrite/frontend:latest
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 128M
          cpus: '0.25'
    ports:
      - "3000-3001:3000"

  worker:
    image: gitwrite/backend:latest
    deploy:
      replicas: 2
    command: celery worker -A backend.tasks
    depends_on:
      - redis
      - postgres
```

### Kubernetes Scaling

```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gitwrite-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gitwrite-backend
  template:
    metadata:
      labels:
        app: gitwrite-backend
    spec:
      containers:
      - name: backend
        image: gitwrite/backend:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: gitwrite-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: gitwrite-secrets
              key: redis-url

---
apiVersion: v1
kind: Service
metadata:
  name: gitwrite-backend-service
spec:
  selector:
    app: gitwrite-backend
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: gitwrite-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: gitwrite-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Load Balancer Configuration

```nginx
# nginx.conf - Load Balancer
upstream gitwrite_backend {
    least_conn;
    server backend-1:8000 weight=1 max_fails=3 fail_timeout=30s;
    server backend-2:8000 weight=1 max_fails=3 fail_timeout=30s;
    server backend-3:8000 weight=1 max_fails=3 fail_timeout=30s;
}

upstream gitwrite_frontend {
    least_conn;
    server frontend-1:3000 weight=1;
    server frontend-2:3000 weight=1;
}

# WebSocket load balancing
upstream gitwrite_websocket {
    ip_hash;  # Sticky sessions for WebSocket
    server backend-1:8000;
    server backend-2:8000;
    server backend-3:8000;
}

server {
    listen 80;
    server_name gitwrite.com;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # API requests
    location /api/ {
        proxy_pass http://gitwrite_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Health check
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
    }

    # WebSocket connections
    location /ws {
        proxy_pass http://gitwrite_websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }

    # Frontend application
    location / {
        proxy_pass http://gitwrite_frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Static assets with caching
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        proxy_pass http://gitwrite_frontend;
    }
}
```

## Database Scaling

### Read Replica Configuration

```python
# backend/database/scaling.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import random

class DatabaseManager:
    """Manage primary and read replica connections."""

    def __init__(self, primary_url: str, replica_urls: list):
        self.primary_engine = create_engine(
            primary_url,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True
        )

        self.replica_engines = [
            create_engine(
                url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            for url in replica_urls
        ]

        self.PrimarySession = sessionmaker(bind=self.primary_engine)
        self.ReplicaSessions = [
            sessionmaker(bind=engine)
            for engine in self.replica_engines
        ]

    @contextmanager
    def get_write_session(self):
        """Get session for write operations."""
        session = self.PrimarySession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def get_read_session(self):
        """Get session for read operations."""
        if not self.replica_engines:
            # Fall back to primary if no replicas
            session = self.PrimarySession()
        else:
            # Round-robin or random selection of replica
            replica_session = random.choice(self.ReplicaSessions)
            session = replica_session()

        try:
            yield session
        finally:
            session.close()

# Usage in services
class RepositoryService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_repositories(self, user_id: str):
        """Read operation - use replica."""
        with self.db_manager.get_read_session() as session:
            return session.query(Repository).filter_by(owner_id=user_id).all()

    def create_repository(self, repo_data: dict):
        """Write operation - use primary."""
        with self.db_manager.get_write_session() as session:
            repo = Repository(**repo_data)
            session.add(repo)
            return repo
```

### Connection Pooling

```python
# backend/database/pool.py
from sqlalchemy.pool import QueuePool
import psycopg2.pool

class OptimizedConnectionPool:
    """Optimized database connection pooling."""

    def __init__(self, database_url: str, min_connections: int = 5, max_connections: int = 20):
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            min_connections,
            max_connections,
            database_url,
            # Connection optimization
            options="-c default_transaction_isolation=read committed"
        )

    def get_connection(self):
        """Get connection from pool."""
        return self.pool.getconn()

    def return_connection(self, conn):
        """Return connection to pool."""
        self.pool.putconn(conn)

    def close_all_connections(self):
        """Close all connections."""
        self.pool.closeall()

# SQLAlchemy engine optimization
def create_optimized_engine(database_url: str):
    """Create optimized SQLAlchemy engine."""
    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections every hour
        echo=False,
        connect_args={
            "options": "-c timezone=utc",
            "application_name": "gitwrite",
        }
    )
```

## Caching Strategy

### Redis Cluster Setup

```yaml
# redis-cluster.yml
version: '3.8'

services:
  redis-node-1:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes
    ports:
      - "7001:6379"
    volumes:
      - redis-1-data:/data

  redis-node-2:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes
    ports:
      - "7002:6379"
    volumes:
      - redis-2-data:/data

  redis-node-3:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes
    ports:
      - "7003:6379"
    volumes:
      - redis-3-data:/data

volumes:
  redis-1-data:
  redis-2-data:
  redis-3-data:
```

### Application Caching

```python
# backend/cache/manager.py
import redis
import json
import pickle
from typing import Any, Optional
from functools import wraps

class CacheManager:
    """Centralized cache management."""

    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url, decode_responses=False)
        self.json_redis = redis.from_url(redis_url, decode_responses=True)

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            data = self.redis_client.get(key)
            if data:
                return pickle.loads(data)
        except Exception:
            return None
        return None

    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set value in cache."""
        try:
            data = pickle.dumps(value)
            return self.redis_client.setex(key, expire, data)
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        return bool(self.redis_client.delete(key))

    def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value from cache."""
        try:
            data = self.json_redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            return None
        return None

    def set_json(self, key: str, value: dict, expire: int = 3600) -> bool:
        """Set JSON value in cache."""
        try:
            data = json.dumps(value)
            return self.json_redis.setex(key, expire, data)
        except Exception:
            return False

# Cache decorators
def cache_result(key_pattern: str, expire: int = 3600):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_pattern.format(*args, **kwargs)

            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, expire)
            return result

        return wrapper
    return decorator

# Usage examples
@cache_result("repositories:user:{0}", expire=300)
def get_user_repositories(user_id: str):
    """Get user repositories with caching."""
    # Database query here
    pass

@cache_result("file:content:{0}:{1}", expire=600)
def get_file_content(repo_id: str, file_path: str):
    """Get file content with caching."""
    # File system access here
    pass
```

### CDN Configuration

```yaml
# cloudfront-config.yml
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  GitWriteCDN:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Origins:
        - DomainName: gitwrite-app.s3.amazonaws.com
          Id: S3Origin
          S3OriginConfig:
            OriginAccessIdentity: !Sub 'origin-access-identity/cloudfront/${CloudFrontOAI}'
        - DomainName: api.gitwrite.com
          Id: APIOrigin
          CustomOriginConfig:
            HTTPPort: 443
            OriginProtocolPolicy: https-only

        DefaultCacheBehavior:
          TargetOriginId: S3Origin
          ViewerProtocolPolicy: redirect-to-https
          CachePolicyId: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad  # Managed caching optimized
          Compress: true

        CacheBehaviors:
        - PathPattern: '/api/*'
          TargetOriginId: APIOrigin
          ViewerProtocolPolicy: https-only
          CachePolicyId: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad
          TTL: 0  # No caching for API

        - PathPattern: '/static/*'
          TargetOriginId: S3Origin
          ViewerProtocolPolicy: https-only
          CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6  # Managed caching optimized for static
          Compress: true
```

## Performance Optimization

### Database Query Optimization

```python
# backend/database/optimization.py
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import text

class OptimizedQueries:
    """Database query optimizations."""

    @staticmethod
    def get_repositories_with_stats(session, user_id: str):
        """Optimized repository query with stats."""
        return session.query(Repository).options(
            joinedload(Repository.owner),
            selectinload(Repository.collaborators)
        ).filter(
            Repository.owner_id == user_id
        ).order_by(Repository.updated_at.desc()).all()

    @staticmethod
    def get_file_tree_optimized(session, repo_id: str):
        """Optimized file tree query."""
        # Use raw SQL for complex queries
        query = text("""
            WITH RECURSIVE file_tree AS (
                SELECT id, path, name, parent_path, 0 as level
                FROM repository_files
                WHERE repository_id = :repo_id AND parent_path IS NULL

                UNION ALL

                SELECT rf.id, rf.path, rf.name, rf.parent_path, ft.level + 1
                FROM repository_files rf
                JOIN file_tree ft ON rf.parent_path = ft.path
                WHERE rf.repository_id = :repo_id
            )
            SELECT * FROM file_tree ORDER BY level, name
        """)

        return session.execute(query, {"repo_id": repo_id}).fetchall()

    @staticmethod
    def bulk_update_file_stats(session, file_updates: list):
        """Bulk update file statistics."""
        session.bulk_update_mappings(RepositoryFile, file_updates)
        session.commit()

# Index creation for performance
CREATE_INDEXES = [
    "CREATE INDEX CONCURRENTLY idx_repositories_owner_updated ON repositories(owner_id, updated_at DESC)",
    "CREATE INDEX CONCURRENTLY idx_files_repo_path ON repository_files(repository_id, path)",
    "CREATE INDEX CONCURRENTLY idx_commits_repo_created ON commits(repository_id, created_at DESC)",
    "CREATE INDEX CONCURRENTLY idx_annotations_file_position ON annotations(file_path, line_start)",
]
```

### Application Performance

```python
# backend/performance/optimization.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from functools import wraps

def async_timing(func):
    """Decorator to measure async function execution time."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return wrapper

class PerformanceOptimizer:
    """Performance optimization utilities."""

    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=4)

    async def parallel_file_processing(self, files: list):
        """Process multiple files in parallel."""
        loop = asyncio.get_event_loop()

        tasks = [
            loop.run_in_executor(
                self.thread_pool,
                self._process_single_file,
                file_path
            )
            for file_path in files
        ]

        return await asyncio.gather(*tasks)

    def _process_single_file(self, file_path: str):
        """Process a single file (CPU-intensive operation)."""
        # File processing logic here
        pass

# Memory optimization
class MemoryOptimizer:
    """Memory usage optimization."""

    @staticmethod
    def stream_large_file(file_path: str, chunk_size: int = 8192):
        """Stream large file to avoid memory issues."""
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    @staticmethod
    def paginate_query(query, page_size: int = 1000):
        """Paginate database query for large datasets."""
        offset = 0
        while True:
            results = query.offset(offset).limit(page_size).all()
            if not results:
                break
            yield results
            offset += page_size
```

## Monitoring and Metrics

### Performance Monitoring

```python
# backend/monitoring/performance.py
import time
import psutil
from prometheus_client import Counter, Histogram, Gauge
from functools import wraps

# Prometheus metrics
REQUEST_COUNT = Counter('gitwrite_requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('gitwrite_request_duration_seconds', 'Request duration')
ACTIVE_USERS = Gauge('gitwrite_active_users', 'Number of active users')
DATABASE_CONNECTIONS = Gauge('gitwrite_db_connections', 'Database connections')

def monitor_performance(func):
    """Decorator to monitor function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start_time
            REQUEST_DURATION.observe(duration)

            if duration > 1.0:  # Log slow operations
                print(f"Slow operation: {func.__name__} took {duration:.2f}s")

    return wrapper

class SystemMonitor:
    """System resource monitoring."""

    def __init__(self):
        self.process = psutil.Process()

    def get_system_metrics(self):
        """Get current system metrics."""
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'process_memory': self.process.memory_info().rss / 1024 / 1024,  # MB
            'process_cpu': self.process.cpu_percent(),
            'open_files': len(self.process.open_files()),
            'connections': len(self.process.connections()),
        }

    def check_resource_limits(self):
        """Check if resources are near limits."""
        metrics = self.get_system_metrics()
        warnings = []

        if metrics['memory_percent'] > 80:
            warnings.append(f"High memory usage: {metrics['memory_percent']:.1f}%")

        if metrics['cpu_percent'] > 80:
            warnings.append(f"High CPU usage: {metrics['cpu_percent']:.1f}%")

        if metrics['disk_usage'] > 90:
            warnings.append(f"High disk usage: {metrics['disk_usage']:.1f}%")

        return warnings

# Health check endpoint
@app.get("/health/performance")
async def performance_health():
    """Performance health check endpoint."""
    monitor = SystemMonitor()
    metrics = monitor.get_system_metrics()
    warnings = monitor.check_resource_limits()

    return {
        "status": "healthy" if not warnings else "degraded",
        "metrics": metrics,
        "warnings": warnings,
        "timestamp": time.time()
    }
```

### Load Testing

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between
import random

class GitWriteUser(HttpUser):
    """Load testing user behavior."""

    wait_time = between(1, 3)

    def on_start(self):
        """Login when user starts."""
        response = self.client.post("/auth/login", json={
            "email": f"test{random.randint(1, 1000)}@example.com",
            "password": "testpassword"
        })

        if response.status_code == 200:
            token = response.json()["access_token"]
            self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(3)
    def view_repositories(self):
        """View user repositories."""
        self.client.get("/repositories")

    @task(2)
    def view_repository(self):
        """View specific repository."""
        self.client.get("/repositories/test-repo")

    @task(1)
    def save_file(self):
        """Save file content."""
        self.client.post("/repositories/test-repo/save", json={
            "file_path": "test.md",
            "content": f"# Test Content\n\nRandom number: {random.randint(1, 1000)}",
            "message": "Load test update"
        })

    @task(1)
    def search_content(self):
        """Search repository content."""
        self.client.get("/repositories/test-repo/search?q=test")
```

---

*GitWrite's scaling and performance architecture provides comprehensive solutions for handling growth from small teams to enterprise deployments. The system includes horizontal scaling, database optimization, caching strategies, and performance monitoring to ensure consistent performance under any load.*