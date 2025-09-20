#!/bin/bash

# Twin Boss Agent Setup Script
# Safe and secure setup without exposing credentials

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check for required tools
check_requirements() {
    log "Checking system requirements..."
    
    command -v docker >/dev/null 2>&1 || error "Docker is required but not installed"
    command -v docker-compose >/dev/null 2>&1 || error "Docker Compose is required but not installed"
    command -v python3 >/dev/null 2>&1 || error "Python 3 is required but not installed"
    command -v node >/dev/null 2>&1 || error "Node.js is required but not installed"
    command -v npm >/dev/null 2>&1 || error "npm is required but not installed"
    
    log "All requirements met ✓"
}

# Setup directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p data logs ssl web
    chmod 755 data logs ssl web
    
    log "Directories created ✓"
}

# Setup environment
setup_environment() {
    log "Setting up environment configuration..."
    
    if [ ! -f .env ]; then
        if [ -f .env.template ]; then
            cp .env.template .env
            warn "Created .env from template. Please edit with your actual values."
        else
            error "No .env.template found. Cannot create environment file."
        fi
    else
        log "Environment file already exists ✓"
    fi
}

# Install dependencies
install_dependencies() {
    log "Installing Node.js dependencies..."
    npm install
    
    log "Setting up Python environment..."
    if [ ! -d .venv ]; then
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    pip install -r api/requirements.txt
    
    log "Dependencies installed ✓"
}

# Build and start services
start_services() {
    log "Building and starting services..."
    
    # Create data directory if it doesn't exist
    mkdir -p data
    
    # Start with docker-compose
    docker-compose up -d --build
    
    log "Services started ✓"
    log "API available at: http://localhost:8011"
    log "Web interface at: http://localhost:8080"
    log "Web content at: http://localhost/web/"
}

# Health check
health_check() {
    log "Performing health check..."
    
    sleep 5  # Wait for services to start
    
    # Check API health
    if curl -s http://localhost:8011/health >/dev/null; then
        log "API health check passed ✓"
    else
        warn "API health check failed"
    fi
    
    # Check web service
    if curl -s http://localhost:8080 >/dev/null; then
        log "Web service health check passed ✓"
    else
        warn "Web service health check failed"
    fi
}

# Main setup function
main() {
    log "Starting Twin Boss Agent setup..."
    
    check_requirements
    setup_directories
    setup_environment
    install_dependencies
    start_services
    health_check
    
    log "Setup complete! 🎉"
    log ""
    log "Access points:"
    log "- Main Console: http://localhost:8080"
    log "- API Documentation: http://localhost:8011/docs"
    log "- Fundraiser Page: http://localhost/web/fundraiser.html"
    log "- Kickstarter Page: http://localhost/web/kickstarter.html"
    log ""
    log "To stop services: docker-compose down"
    log "To view logs: docker-compose logs -f"
    log ""
    log "Remember to edit .env with your actual API keys and configuration!"
}

# Run main function
main "$@"