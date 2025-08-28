# Backup & Recovery

Comprehensive backup and disaster recovery strategy for GitWrite, ensuring data protection, business continuity, and rapid recovery from various failure scenarios. This guide covers automated backups, point-in-time recovery, disaster recovery procedures, and data retention policies.

## Backup Strategy Overview

```
GitWrite Backup Architecture
    │
    ├─ Database Backups
    │   ├─ Continuous WAL Archiving
    │   ├─ Daily Full Backups
    │   ├─ Point-in-Time Recovery
    │   └─ Cross-Region Replication
    │
    ├─ Repository Storage Backups
    │   ├─ Git Repository Sync
    │   ├─ Incremental Backups
    │   └─ Remote Mirror Repositories
    │
    ├─ Application Data Backups
    │   ├─ Configuration Files
    │   ├─ Uploaded Files
    │   └─ User Assets
    │
    └─ Infrastructure Backups
        ├─ Container Images
        ├─ Kubernetes Manifests
        └─ Terraform State
```

## Recovery Time Objectives (RTO) & Recovery Point Objectives (RPO)

| Scenario | RTO Target | RPO Target | Business Impact |
|----------|------------|------------|-----------------|
| Database Failure | < 30 minutes | < 5 minutes | Medium |
| Application Server Failure | < 5 minutes | 0 (stateless) | Low |
| Storage Failure | < 2 hours | < 15 minutes | High |
| Complete Data Center Loss | < 4 hours | < 30 minutes | Critical |
| Regional Disaster | < 8 hours | < 1 hour | Critical |

## Database Backup & Recovery

### PostgreSQL Continuous Archiving

```bash
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /backup/wal/%f && cp %p /backup/wal/%f'
max_wal_senders = 3
wal_keep_segments = 64
checkpoint_completion_target = 0.9
```

### Automated Backup Script

```bash
#!/bin/bash
# backup-database.sh

set -e

# Configuration
BACKUP_DIR="/backups/postgres"
S3_BUCKET="gitwrite-backups"
DATABASE_URL="${DATABASE_URL}"
RETENTION_DAYS=30

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="gitwrite_backup_${TIMESTAMP}.sql"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

echo "Starting database backup: ${BACKUP_FILE}"

# Create database dump
pg_dump "${DATABASE_URL}" \
    --verbose \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_PATH}"

# Verify backup integrity
echo "Verifying backup integrity..."
pg_restore --list "${BACKUP_PATH}" > /dev/null

# Compress backup
gzip "${BACKUP_PATH}"
COMPRESSED_FILE="${BACKUP_PATH}.gz"

# Upload to S3
echo "Uploading backup to S3..."
aws s3 cp "${COMPRESSED_FILE}" "s3://${S3_BUCKET}/database/" \
    --storage-class STANDARD_IA

# Upload WAL files
echo "Syncing WAL files..."
aws s3 sync /backup/wal/ "s3://${S3_BUCKET}/wal/" \
    --delete \
    --storage-class STANDARD_IA

# Clean up old local backups
find "${BACKUP_DIR}" -name "*.gz" -mtime +7 -delete

# Clean up old S3 backups
aws s3api list-objects-v2 \
    --bucket "${S3_BUCKET}" \
    --prefix "database/" \
    --query "Contents[?LastModified<='$(date -d "${RETENTION_DAYS} days ago" --iso-8601)'].Key" \
    --output text | xargs -r -n1 aws s3 rm "s3://${S3_BUCKET}/"

echo "Database backup completed successfully"

# Send notification
curl -X POST "${SLACK_WEBHOOK_URL}" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"GitWrite database backup completed: ${BACKUP_FILE}\"}"
```

### Point-in-Time Recovery

```bash
#!/bin/bash
# restore-database.sh

set -e

# Configuration
BACKUP_DIR="/backups/postgres"
S3_BUCKET="gitwrite-backups"
RESTORE_TARGET="${1:-latest}"  # timestamp or 'latest'

echo "Starting database restore to: ${RESTORE_TARGET}"

# Stop application services
echo "Stopping application services..."
docker-compose down backend worker

# Create recovery directory
RECOVERY_DIR="/tmp/postgres_recovery"
mkdir -p "${RECOVERY_DIR}"

if [ "${RESTORE_TARGET}" = "latest" ]; then
    # Get latest backup
    LATEST_BACKUP=$(aws s3 ls "s3://${S3_BUCKET}/database/" --recursive | sort | tail -n 1 | awk '{print $4}')
    echo "Using latest backup: ${LATEST_BACKUP}"
else
    # Find backup closest to target time
    LATEST_BACKUP=$(aws s3 ls "s3://${S3_BUCKET}/database/" --recursive | \
        awk -v target="${RESTORE_TARGET}" '$1 <= target {backup=$4} END {print backup}')
    echo "Using backup: ${LATEST_BACKUP}"
fi

# Download backup
echo "Downloading backup..."
aws s3 cp "s3://${S3_BUCKET}/${LATEST_BACKUP}" "${RECOVERY_DIR}/"

# Download WAL files
echo "Downloading WAL files..."
aws s3 sync "s3://${S3_BUCKET}/wal/" "${RECOVERY_DIR}/wal/"

# Stop PostgreSQL
systemctl stop postgresql

# Backup current data directory
mv /var/lib/postgresql/14/main /var/lib/postgresql/14/main.backup.$(date +%s)

# Create new data directory
mkdir -p /var/lib/postgresql/14/main
chown postgres:postgres /var/lib/postgresql/14/main

# Restore base backup
echo "Restoring base backup..."
cd /var/lib/postgresql/14/main
sudo -u postgres pg_basebackup -D . -Ft -z -P -h localhost

# Configure recovery
cat > /var/lib/postgresql/14/main/recovery.conf << EOF
restore_command = 'cp ${RECOVERY_DIR}/wal/%f %p'
recovery_target_time = '${RESTORE_TARGET}'
recovery_target_inclusive = true
EOF

# Set permissions
chown postgres:postgres /var/lib/postgresql/14/main/recovery.conf

# Start PostgreSQL for recovery
echo "Starting PostgreSQL for recovery..."
systemctl start postgresql

# Monitor recovery progress
echo "Monitoring recovery progress..."
while [ -f /var/lib/postgresql/14/main/recovery.conf ]; do
    echo "Recovery in progress..."
    sleep 10
done

echo "Database recovery completed"

# Verify database integrity
echo "Verifying database integrity..."
sudo -u postgres psql -d gitwrite -c "SELECT COUNT(*) FROM repositories;"

# Start application services
echo "Starting application services..."
docker-compose up -d backend worker

echo "Database restore completed successfully"
```

## Repository Storage Backup

### Git Repository Synchronization

```python
# backup/git_backup.py
import os
import subprocess
import boto3
from pathlib import Path
from datetime import datetime
import logging

class GitRepositoryBackup:
    """Backup Git repositories to multiple locations."""

    def __init__(self, source_path: str, backup_configs: dict):
        self.source_path = Path(source_path)
        self.backup_configs = backup_configs
        self.logger = logging.getLogger(__name__)

    def backup_all_repositories(self):
        """Backup all repositories."""
        for repo_dir in self.source_path.iterdir():
            if repo_dir.is_dir() and (repo_dir / '.git').exists():
                self.backup_repository(repo_dir)

    def backup_repository(self, repo_path: Path):
        """Backup individual repository."""
        repo_name = repo_path.name
        self.logger.info(f"Backing up repository: {repo_name}")

        try:
            # Create bundle backup
            bundle_path = self._create_bundle(repo_path)

            # Upload to S3
            if 's3' in self.backup_configs:
                self._upload_to_s3(bundle_path, repo_name)

            # Mirror to remote Git
            if 'git_mirror' in self.backup_configs:
                self._mirror_to_remote(repo_path, repo_name)

            # Local backup
            if 'local' in self.backup_configs:
                self._copy_to_local(repo_path, repo_name)

        except Exception as e:
            self.logger.error(f"Failed to backup {repo_name}: {e}")

    def _create_bundle(self, repo_path: Path) -> Path:
        """Create Git bundle for backup."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        bundle_name = f"{repo_path.name}_{timestamp}.bundle"
        bundle_path = Path("/tmp") / bundle_name

        # Create bundle with all refs
        subprocess.run([
            'git', '-C', str(repo_path),
            'bundle', 'create', str(bundle_path),
            '--all'
        ], check=True)

        return bundle_path

    def _upload_to_s3(self, bundle_path: Path, repo_name: str):
        """Upload bundle to S3."""
        s3_config = self.backup_configs['s3']
        s3_client = boto3.client('s3')

        s3_key = f"repositories/{repo_name}/{bundle_path.name}"

        s3_client.upload_file(
            str(bundle_path),
            s3_config['bucket'],
            s3_key,
            ExtraArgs={'StorageClass': 'STANDARD_IA'}
        )

        self.logger.info(f"Uploaded {bundle_path.name} to S3")

    def _mirror_to_remote(self, repo_path: Path, repo_name: str):
        """Mirror repository to remote Git service."""
        git_config = self.backup_configs['git_mirror']
        remote_url = f"{git_config['base_url']}/{repo_name}.git"

        # Add remote if not exists
        try:
            subprocess.run([
                'git', '-C', str(repo_path),
                'remote', 'add', 'backup', remote_url
            ], check=False)
        except:
            pass

        # Push all branches and tags
        subprocess.run([
            'git', '-C', str(repo_path),
            'push', 'backup', '--all'
        ], check=True)

        subprocess.run([
            'git', '-C', str(repo_path),
            'push', 'backup', '--tags'
        ], check=True)

    def _copy_to_local(self, repo_path: Path, repo_name: str):
        """Copy repository to local backup location."""
        local_config = self.backup_configs['local']
        backup_dir = Path(local_config['path']) / repo_name

        # Create backup directory
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Clone or update backup
        if (backup_dir / '.git').exists():
            subprocess.run([
                'git', '-C', str(backup_dir),
                'fetch', '--all'
            ], check=True)
        else:
            subprocess.run([
                'git', 'clone', '--mirror',
                str(repo_path), str(backup_dir)
            ], check=True)

# Backup configuration
BACKUP_CONFIG = {
    's3': {
        'bucket': 'gitwrite-repo-backups',
        'region': 'us-east-1'
    },
    'git_mirror': {
        'base_url': 'https://backup-git.example.com'
    },
    'local': {
        'path': '/backup/repositories'
    }
}

# Run backup
if __name__ == "__main__":
    backup = GitRepositoryBackup(
        source_path="/data/repositories",
        backup_configs=BACKUP_CONFIG
    )
    backup.backup_all_repositories()
```

### Automated Repository Backup

```bash
#!/bin/bash
# backup-repositories.sh

set -e

SOURCE_DIR="/data/repositories"
BACKUP_DIR="/backup/repositories"
S3_BUCKET="gitwrite-repo-backups"

echo "Starting repository backup..."

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Backup each repository
for repo_dir in "${SOURCE_DIR}"/*; do
    if [ -d "${repo_dir}/.git" ]; then
        repo_name=$(basename "${repo_dir}")
        echo "Backing up repository: ${repo_name}"

        # Create incremental backup
        rsync -av --delete \
            "${repo_dir}/" \
            "${BACKUP_DIR}/${repo_name}/"

        # Create bundle for offsite backup
        cd "${repo_dir}"
        git bundle create "/tmp/${repo_name}.bundle" --all

        # Upload bundle to S3
        aws s3 cp "/tmp/${repo_name}.bundle" \
            "s3://${S3_BUCKET}/${repo_name}/" \
            --storage-class GLACIER

        # Clean up
        rm "/tmp/${repo_name}.bundle"
    fi
done

echo "Repository backup completed"
```

## Application Data Backup

### File Upload Backup

```python
# backup/file_backup.py
import os
import shutil
from pathlib import Path
import boto3
from datetime import datetime

class FileBackupManager:
    """Backup uploaded files and user assets."""

    def __init__(self, upload_dir: str, s3_bucket: str):
        self.upload_dir = Path(upload_dir)
        self.s3_bucket = s3_bucket
        self.s3_client = boto3.client('s3')

    def backup_uploads(self):
        """Backup all uploaded files."""
        for user_dir in self.upload_dir.iterdir():
            if user_dir.is_dir():
                self._backup_user_files(user_dir)

    def _backup_user_files(self, user_dir: Path):
        """Backup files for specific user."""
        user_id = user_dir.name

        for file_path in user_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(self.upload_dir)
                s3_key = f"uploads/{relative_path}"

                # Check if file needs backup
                if self._needs_backup(file_path, s3_key):
                    self._upload_file(file_path, s3_key)

    def _needs_backup(self, local_path: Path, s3_key: str) -> bool:
        """Check if file needs to be backed up."""
        try:
            # Get S3 object metadata
            response = self.s3_client.head_object(
                Bucket=self.s3_bucket,
                Key=s3_key
            )

            # Compare modification times
            s3_modified = response['LastModified'].timestamp()
            local_modified = local_path.stat().st_mtime

            return local_modified > s3_modified

        except self.s3_client.exceptions.NoSuchKey:
            # File doesn't exist in S3
            return True
        except Exception:
            # Error checking, backup to be safe
            return True

    def _upload_file(self, file_path: Path, s3_key: str):
        """Upload file to S3."""
        self.s3_client.upload_file(
            str(file_path),
            self.s3_bucket,
            s3_key,
            ExtraArgs={
                'StorageClass': 'STANDARD_IA',
                'ServerSideEncryption': 'AES256'
            }
        )
```

### Configuration Backup

```bash
#!/bin/bash
# backup-configs.sh

CONFIG_BACKUP_DIR="/backup/configs"
S3_BUCKET="gitwrite-config-backups"

echo "Backing up configuration files..."

# Create backup directory
mkdir -p "${CONFIG_BACKUP_DIR}"

# Backup environment files
cp .env* "${CONFIG_BACKUP_DIR}/"

# Backup Docker configurations
cp docker-compose*.yml "${CONFIG_BACKUP_DIR}/"

# Backup Kubernetes manifests
if [ -d "k8s" ]; then
    cp -r k8s/ "${CONFIG_BACKUP_DIR}/"
fi

# Backup Terraform state
if [ -f "terraform.tfstate" ]; then
    cp terraform.tfstate "${CONFIG_BACKUP_DIR}/"
fi

# Create timestamped archive
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="gitwrite_configs_${TIMESTAMP}.tar.gz"

tar -czf "/tmp/${ARCHIVE_NAME}" -C "${CONFIG_BACKUP_DIR}" .

# Upload to S3
aws s3 cp "/tmp/${ARCHIVE_NAME}" "s3://${S3_BUCKET}/"

# Clean up
rm "/tmp/${ARCHIVE_NAME}"

echo "Configuration backup completed"
```

## Disaster Recovery Procedures

### Database Recovery Procedures

```bash
#!/bin/bash
# disaster-recovery.sh

set -e

RECOVERY_TYPE="${1:-full}"  # full, partial, point-in-time
RECOVERY_TARGET="${2:-latest}"

echo "Starting disaster recovery: ${RECOVERY_TYPE}"

case "${RECOVERY_TYPE}" in
    "full")
        echo "Performing full system recovery..."

        # Restore database
        ./restore-database.sh "${RECOVERY_TARGET}"

        # Restore repositories
        ./restore-repositories.sh

        # Restore uploaded files
        ./restore-uploads.sh

        # Restore configuration
        ./restore-configs.sh
        ;;

    "database")
        echo "Performing database-only recovery..."
        ./restore-database.sh "${RECOVERY_TARGET}"
        ;;

    "repositories")
        echo "Performing repository recovery..."
        ./restore-repositories.sh
        ;;

    *)
        echo "Unknown recovery type: ${RECOVERY_TYPE}"
        exit 1
        ;;
esac

echo "Disaster recovery completed"
```

### Recovery Validation

```python
# recovery/validation.py
import psycopg2
import requests
from pathlib import Path

class RecoveryValidator:
    """Validate system after recovery."""

    def __init__(self, config):
        self.config = config
        self.results = []

    def validate_recovery(self):
        """Run all validation checks."""
        self.check_database()
        self.check_repositories()
        self.check_application()
        self.check_data_integrity()

        return self.results

    def check_database(self):
        """Validate database connectivity and data."""
        try:
            conn = psycopg2.connect(self.config['database_url'])
            cursor = conn.cursor()

            # Check basic connectivity
            cursor.execute("SELECT 1")

            # Check table counts
            cursor.execute("SELECT COUNT(*) FROM repositories")
            repo_count = cursor.fetchone()[0]

            self.results.append({
                'check': 'database',
                'status': 'pass',
                'details': f'{repo_count} repositories found'
            })

            conn.close()

        except Exception as e:
            self.results.append({
                'check': 'database',
                'status': 'fail',
                'error': str(e)
            })

    def check_repositories(self):
        """Validate Git repositories."""
        repo_dir = Path(self.config['git_storage_path'])

        if not repo_dir.exists():
            self.results.append({
                'check': 'repositories',
                'status': 'fail',
                'error': 'Repository directory does not exist'
            })
            return

        valid_repos = 0
        for repo_path in repo_dir.iterdir():
            if repo_path.is_dir() and (repo_path / '.git').exists():
                valid_repos += 1

        self.results.append({
            'check': 'repositories',
            'status': 'pass',
            'details': f'{valid_repos} valid repositories found'
        })

    def check_application(self):
        """Validate application endpoints."""
        try:
            response = requests.get(f"{self.config['api_url']}/health")

            if response.status_code == 200:
                self.results.append({
                    'check': 'application',
                    'status': 'pass',
                    'details': 'Health endpoint responding'
                })
            else:
                self.results.append({
                    'check': 'application',
                    'status': 'fail',
                    'error': f'Health endpoint returned {response.status_code}'
                })

        except Exception as e:
            self.results.append({
                'check': 'application',
                'status': 'fail',
                'error': str(e)
            })

    def check_data_integrity(self):
        """Validate data integrity."""
        # Check for data consistency between database and filesystem
        # This is application-specific validation
        pass
```

## Backup Monitoring and Alerts

### Backup Monitoring Script

```python
# monitoring/backup_monitor.py
import boto3
import datetime
import smtplib
from email.mime.text import MimeText

class BackupMonitor:
    """Monitor backup health and send alerts."""

    def __init__(self, config):
        self.config = config
        self.s3_client = boto3.client('s3')

    def check_backup_health(self):
        """Check all backup types."""
        issues = []

        # Check database backups
        db_issues = self._check_database_backups()
        issues.extend(db_issues)

        # Check repository backups
        repo_issues = self._check_repository_backups()
        issues.extend(repo_issues)

        if issues:
            self._send_alert(issues)

        return issues

    def _check_database_backups(self):
        """Check database backup freshness."""
        issues = []

        try:
            # List recent backups
            response = self.s3_client.list_objects_v2(
                Bucket=self.config['s3_bucket'],
                Prefix='database/',
                MaxKeys=1
            )

            if 'Contents' not in response:
                issues.append("No database backups found")
                return issues

            # Check if latest backup is recent
            latest_backup = response['Contents'][0]
            backup_time = latest_backup['LastModified']
            age_hours = (datetime.datetime.now(backup_time.tzinfo) - backup_time).total_seconds() / 3600

            if age_hours > 25:  # Daily backups, allow 1 hour grace
                issues.append(f"Database backup is {age_hours:.1f} hours old")

        except Exception as e:
            issues.append(f"Error checking database backups: {e}")

        return issues

    def _send_alert(self, issues):
        """Send alert email."""
        subject = "GitWrite Backup Alert"
        body = "Backup issues detected:\n\n" + "\n".join(f"- {issue}" for issue in issues)

        msg = MimeText(body)
        msg['Subject'] = subject
        msg['From'] = self.config['alert_from']
        msg['To'] = self.config['alert_to']

        with smtplib.SMTP(self.config['smtp_host']) as server:
            server.send_message(msg)
```

### Backup Health Dashboard

```bash
#!/bin/bash
# backup-health.sh

echo "=== GitWrite Backup Health Report ==="
echo "Generated: $(date)"
echo

# Check database backups
echo "Database Backups:"
LATEST_DB_BACKUP=$(aws s3 ls s3://gitwrite-backups/database/ --recursive | sort | tail -n 1)
if [ -n "$LATEST_DB_BACKUP" ]; then
    echo "  ✓ Latest: $(echo $LATEST_DB_BACKUP | awk '{print $1, $2}')"
else
    echo "  ✗ No database backups found"
fi

# Check repository backups
echo "Repository Backups:"
REPO_COUNT=$(aws s3 ls s3://gitwrite-repo-backups/ | wc -l)
echo "  ✓ Repositories backed up: $REPO_COUNT"

# Check backup sizes
echo "Backup Storage Usage:"
DB_SIZE=$(aws s3 ls s3://gitwrite-backups/database/ --recursive --summarize | grep "Total Size" | awk '{print $3}')
REPO_SIZE=$(aws s3 ls s3://gitwrite-repo-backups/ --recursive --summarize | grep "Total Size" | awk '{print $3}')
echo "  Database backups: ${DB_SIZE} bytes"
echo "  Repository backups: ${REPO_SIZE} bytes"

echo
echo "=== End Report ==="
```

---

*GitWrite's backup and recovery system provides comprehensive data protection with automated backups, point-in-time recovery, and disaster recovery procedures. The system ensures business continuity through multiple backup strategies, monitoring, and validated recovery procedures.*