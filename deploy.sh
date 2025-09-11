#!/bin/bash
# GitWrite Deployment Script
# Usage: ./deploy.sh [development|production|test]

set -e

# Default to development if no argument provided
MODE=${1:-development}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if required tools are installed
check_dependencies() {
    print_info "Checking dependencies..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "All dependencies are installed."
}

# Function to setup environment file
setup_environment() {
    print_info "Setting up environment configuration..."
    
    if [ "$MODE" = "production" ]; then
        if [ ! -f .env ]; then
            print_info "Creating production environment file from template..."
            cp .env.production .env
            print_warning "Please edit .env file and update the security settings before deploying to production!"
        fi
    else
        if [ ! -f .env ]; then
            print_info "Creating development environment file from template..."
            cp .env.example .env
        fi
    fi
    
    print_success "Environment configuration ready."
}

# Function to create necessary directories
create_directories() {
    print_info "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p data/repositories
    mkdir -p data/exports
    mkdir -p ssl
    
    print_success "Directories created."
}

# Function to deploy based on mode
deploy() {
    print_info "Deploying GitWrite in ${MODE} mode..."
    
    case $MODE in
        "development")
            print_info "Starting development environment with hot reload..."
            docker-compose --profile development up --build -d
            ;;
        "production")
            print_info "Starting production environment..."
            docker-compose --profile production up --build -d
            ;;
        "test")
            print_info "Starting test environment..."
            docker-compose up --build gitwrite-api
            ;;
        *)
            print_error "Invalid mode: $MODE. Use development, production, or test."
            exit 1
            ;;
    esac
}

# Function to show status
show_status() {
    print_info "Checking service status..."
    docker-compose ps
}

# Function to show logs
show_logs() {
    print_info "Showing service logs..."
    docker-compose logs -f --tail=50
}

# Function to stop services
stop_services() {
    print_info "Stopping GitWrite services..."
    docker-compose down
    print_success "Services stopped."
}

# Function to clean up
cleanup() {
    print_info "Cleaning up Docker resources..."
    docker-compose down -v --remove-orphans
    docker system prune -f
    print_success "Cleanup completed."
}

# Function to backup data
backup_data() {
    print_info "Creating backup of GitWrite data..."
    
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup repositories and exports
    if [ -d "data" ]; then
        cp -r data "$BACKUP_DIR/"
    fi
    
    # Backup environment configuration
    if [ -f ".env" ]; then
        cp .env "$BACKUP_DIR/"
    fi
    
    print_success "Backup created in $BACKUP_DIR"
}

# Function to restore data
restore_data() {
    if [ -z "$2" ]; then
        print_error "Please specify backup directory: ./deploy.sh restore <backup_directory>"
        exit 1
    fi
    
    BACKUP_DIR="$2"
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_error "Backup directory $BACKUP_DIR does not exist."
        exit 1
    fi
    
    print_info "Restoring data from $BACKUP_DIR..."
    
    # Restore data
    if [ -d "$BACKUP_DIR/data" ]; then
        cp -r "$BACKUP_DIR/data" .
    fi
    
    # Restore environment
    if [ -f "$BACKUP_DIR/.env" ]; then
        cp "$BACKUP_DIR/.env" .
    fi
    
    print_success "Data restored from $BACKUP_DIR"
}

# Function to update GitWrite
update() {
    print_info "Updating GitWrite..."
    
    # Pull latest changes (if using git)
    if [ -d ".git" ]; then
        git pull
    fi
    
    # Rebuild and restart services
    docker-compose down
    docker-compose build --no-cache
    deploy
    
    print_success "GitWrite updated successfully."
}

# Function to run tests
run_tests() {
    print_info "Running GitWrite tests..."
    
    # Build test image
    docker-compose build gitwrite-api
    
    # Run tests in container
    docker-compose run --rm gitwrite-api poetry run pytest
    
    print_success "Tests completed."
}

# Function to show help
show_help() {
    echo "GitWrite Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  development     Start development environment (default)"
    echo "  production      Start production environment"
    echo "  test            Start test environment"
    echo "  status          Show service status"
    echo "  logs            Show service logs"
    echo "  stop            Stop all services"
    echo "  cleanup         Stop services and clean up Docker resources"
    echo "  backup          Create backup of data and configuration"
    echo "  restore <dir>   Restore data from backup directory"
    echo "  update          Update GitWrite and restart services"
    echo "  test-run        Run the test suite"
    echo "  help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 development  # Start development environment"
    echo "  $0 production   # Start production environment"
    echo "  $0 backup       # Create backup"
    echo "  $0 restore backup_20231201_120000  # Restore from backup"
}

# Main script logic
main() {
    case ${1:-development} in
        "development"|"production"|"test")
            check_dependencies
            setup_environment
            create_directories
            deploy
            show_status
            print_success "GitWrite is running in $MODE mode!"
            print_info "API available at: http://localhost:8000"
            if [ "$MODE" = "development" ]; then
                print_info "Web app (dev) available at: http://localhost:3001"
            else
                print_info "Web app available at: http://localhost:3000"
            fi
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs
            ;;
        "stop")
            stop_services
            ;;
        "cleanup")
            cleanup
            ;;
        "backup")
            backup_data
            ;;
        "restore")
            restore_data "$@"
            ;;
        "update")
            update
            ;;
        "test-run")
            run_tests
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"