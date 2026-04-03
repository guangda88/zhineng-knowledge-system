#!/bin/bash
###############################################################################
# CLIProxyAPI Setup Script for ZhiNeng Knowledge System
#
# This script helps you set up CLIProxyAPI for unified AI services
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "============================================================"
    echo "$1"
    echo "============================================================"
    echo -e "${NC}"
}

# Check if Docker is installed
check_docker() {
    print_header "Checking Prerequisites"

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "Please install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi

    print_success "Docker is installed"

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
        exit 1
    fi

    print_success "Docker Compose is installed"
}

# Setup environment variables
setup_env() {
    print_header "Setting Up Environment Variables"

    ENV_FILE=".env.cliproxyapi"
    TEMPLATE_FILE=".env.cliproxyapi.template"

    if [ -f "$ENV_FILE" ]; then
        print_warning "$ENV_FILE already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing $ENV_FILE"
            return
        fi
    fi

    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_error "Template file not found: $TEMPLATE_FILE"
        exit 1
    fi

    cp "$TEMPLATE_FILE" "$ENV_FILE"
    print_success "Created $ENV_FILE from template"

    print_warning "Please edit $ENV_FILE and add your API keys"
    echo ""
    echo "Required API keys:"
    echo "  - DEEPSEEK_API_KEY (recommended as primary model)"
    echo "  - At least one of: CLAUDE_API_KEY, GEMINI_API_KEY, QWEN_API_KEY"
    echo ""
    echo "Get API keys from:"
    echo "  - DeepSeek: https://platform.deepseek.com/"
    echo "  - Claude: https://console.anthropic.com/"
    echo "  - Gemini: https://aistudio.google.com/app/apikey"
    echo "  - Qwen: https://dashscope.aliyun.com/"
    echo ""

    read -p "Have you added your API keys? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Please add your API keys before proceeding"
        print_info "Edit $ENV_FILE with your favorite editor"
        exit 0
    fi
}

# Verify API keys
verify_api_keys() {
    print_header "Verifying API Keys"

    source .env.cliproxyapi

    if [ -z "$DEEPSEEK_API_KEY" ] || [ "$DEEPSEEK_API_KEY" = "your_deepseek_api_key_here" ]; then
        print_warning "DEEPSEEK_API_KEY is not set"
    else
        print_success "DEEPSEEK_API_KEY is configured"
    fi

    if [ -z "$CLAUDE_API_KEY" ] || [ "$CLAUDE_API_KEY" = "your_claude_api_key_here" ]; then
        print_warning "CLAUDE_API_KEY is not set"
    else
        print_success "CLAUDE_API_KEY is configured"
    fi

    if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
        print_warning "GEMINI_API_KEY is not set"
    else
        print_success "GEMINI_API_KEY is configured"
    fi

    if [ -z "$QWEN_API_KEY" ] || [ "$QWEN_API_KEY" = "your_qwen_api_key_here" ]; then
        print_warning "QWEN_API_KEY is not set"
    else
        print_success "QWEN_API_KEY is configured"
    fi

    # Check if at least one API key is configured
    if [ -z "$DEEPSEEK_API_KEY" ] && [ -z "$CLAUDE_API_KEY" ] && [ -z "$GEMINI_API_KEY" ] && [ -z "$QWEN_API_KEY" ]; then
        print_error "No API keys configured!"
        echo "Please add at least one API key to $ENV_FILE"
        exit 1
    fi

    print_success "At least one API key is configured"
}

# Create necessary directories
create_directories() {
    print_header "Creating Directories"

    mkdir -p config/cliproxyapi
    mkdir -p logs/cliproxyapi

    print_success "Directories created"
}

# Pull Docker image
pull_image() {
    print_header "Pulling CLIProxyAPI Docker Image"

    print_info "Pulling routerforme/cli-proxy-api:latest..."
    docker pull routerforme/cli-proxy-api:latest

    print_success "Docker image pulled"
}

# Start services
start_services() {
    print_header "Starting Services"

    print_info "Starting CLIProxyAPI..."
    docker-compose -f docker-compose.yml -f docker-compose.cli-proxy.yml --env-file .env.cliproxyapi up -d cliproxyapi

    print_success "CLIProxyAPI started"
}

# Wait for service to be healthy
wait_for_service() {
    print_header "Waiting for CLIProxyAPI to be Ready"

    print_info "Waiting up to 60 seconds..."
    for i in {1..60}; do
        if curl -sf http://localhost:8317/health > /dev/null 2>&1; then
            print_success "CLIProxyAPI is ready!"
            return
        fi
        echo -n "."
        sleep 1
    done
    echo ""
    print_error "CLIProxyAPI failed to start within 60 seconds"
    echo "Check logs with: docker logs lingzhi-cliproxyapi"
    exit 1
}

# Test the service
test_service() {
    print_header "Testing CLIProxyAPI"

    print_info "Testing health endpoint..."
    if curl -sf http://localhost:8317/health | jq . > /dev/null 2>&1; then
        print_success "Health endpoint is working"
    else
        print_warning "Health endpoint returned non-JSON response"
    fi

    print_info "Testing models endpoint..."
    if curl -sf http://localhost:8317/v1/models | jq . > /dev/null 2>&1; then
        print_success "Models endpoint is working"
    else
        print_warning "Models endpoint test failed (may need API keys)"
    fi
}

# Print next steps
print_next_steps() {
    print_header "Setup Complete!"

    echo ""
    print_success "CLIProxyAPI is now running"
    echo ""
    echo "📡 Endpoints:"
    echo "  - HTTP API: http://localhost:8317"
    echo "  - OpenAI Compatible: http://localhost:8317/v1"
    echo "  - Health Check: http://localhost:8317/health"
    echo "  - Swagger UI: http://localhost:8317/swagger"
    echo ""
    echo "📚 Documentation:"
    echo "  - Integration Guide: docs/CLIProxyAPI_INTEGRATION_GUIDE.md"
    echo "  - CLIProxyAPI GitHub: https://github.com/router-for-me/CLIProxyAPI"
    echo ""
    echo "🔧 Useful Commands:"
    echo "  - View logs: docker logs -f lingzhi-cliproxyapi"
    echo "  - Stop service: docker-compose -f docker-compose.cli-proxy.yml stop cliproxyapi"
    echo "  - Restart service: docker-compose -f docker-compose.cli-proxy.yml restart cliproxyapi"
    echo ""
    echo "🧪 Test the integration:"
    echo "  python scripts/test_cliproxyapi_integration.py"
    echo ""
}

# Main execution
main() {
    print_header "CLIProxyAPI Setup for ZhiNeng Knowledge System"

    check_docker
    create_directories
    setup_env
    verify_api_keys
    pull_image
    start_services
    wait_for_service
    test_service
    print_next_steps

    echo ""
    print_success "All done! 🎉"
    echo ""
}

# Run main function
main
