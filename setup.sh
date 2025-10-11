#!/bin/bash

# Agentic RAG Setup Script
# This script helps you set up the Agentic RAG system quickly

set -e  # Exit on error

echo "=================================================="
echo "  Agentic RAG - Automated Setup"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Edit .env and add your API keys!${NC}"
    echo ""
    echo "Required:"
    echo "  - OPENAI_API_KEY (if using OpenAI)"
    echo "  - POSTGRES_PASSWORD (for database)"
    echo ""
    read -p "Press Enter after you've edited .env..."
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker from: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "Please install Docker Compose from: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"
echo ""

# Ask user how they want to run
echo "How would you like to run Agentic RAG?"
echo "1. Docker (Recommended - everything in containers)"
echo "2. Local (Development - requires Python 3.11+)"
echo ""
read -p "Enter choice (1 or 2): " choice

if [ "$choice" == "1" ]; then
    echo ""
    echo "Starting services with Docker Compose..."
    echo ""
    
    # Pull images
    echo "Pulling Docker images..."
    docker-compose pull postgres
    
    # Build custom images
    echo "Building application images..."
    docker-compose build
    
    # Start services
    echo "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    echo ""
    echo "Waiting for services to start..."
    sleep 10
    
    # Check health
    echo ""
    echo "Checking service health..."
    
    # Check postgres
    if docker-compose ps postgres | grep -q "Up"; then
        echo -e "${GREEN}✓ PostgreSQL is running${NC}"
    else
        echo -e "${RED}❌ PostgreSQL failed to start${NC}"
        docker-compose logs postgres
        exit 1
    fi
    
    # Check backend
    if docker-compose ps backend | grep -q "Up"; then
        echo -e "${GREEN}✓ Backend is running${NC}"
    else
        echo -e "${RED}❌ Backend failed to start${NC}"
        docker-compose logs backend
        exit 1
    fi
    
    # Check frontend
    if docker-compose ps frontend | grep -q "Up"; then
        echo -e "${GREEN}✓ Frontend is running${NC}"
    else
        echo -e "${RED}❌ Frontend failed to start${NC}"
        docker-compose logs frontend
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}✅ All services are running!${NC}"
    echo ""
    echo "Access the application:"
    echo "  - Frontend UI:    http://localhost:7860"
    echo "  - Backend API:    http://localhost:8000"
    echo "  - API Docs:       http://localhost:8000/docs"
    echo ""
    echo "Useful commands:"
    echo "  - View logs:      docker-compose logs -f"
    echo "  - Stop services:  docker-compose down"
    echo "  - Restart:        docker-compose restart"
    echo ""

elif [ "$choice" == "2" ]; then
    echo ""
    echo "Setting up for local development..."
    echo ""
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    required_version="3.11"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        echo -e "${RED}❌ Python 3.11+ is required (found $python_version)${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Python $python_version is installed${NC}"
    
    # Install Python dependencies
    echo ""
    echo "Installing Python dependencies..."
    pip install -e .
    
    echo -e "${GREEN}✓ Dependencies installed${NC}"
    
    # Start PostgreSQL in Docker
    echo ""
    echo "Starting PostgreSQL with Docker..."
    docker-compose up -d postgres
    
    sleep 5
    
    if docker-compose ps postgres | grep -q "Up"; then
        echo -e "${GREEN}✓ PostgreSQL is running${NC}"
    else
        echo -e "${RED}❌ PostgreSQL failed to start${NC}"
        docker-compose logs postgres
        exit 1
    fi
    
    # Initialize database
    echo ""
    echo "Initializing database..."
    python scripts/init_db.py
    
    echo ""
    echo -e "${GREEN}✅ Setup complete!${NC}"
    echo ""
    echo "To run the application:"
    echo ""
    echo "  Terminal 1 (Backend):"
    echo "    python -m rag.backend.app"
    echo ""
    echo "  Terminal 2 (Frontend):"
    echo "    python -m rag.frontend.gradio_app"
    echo ""
    echo "Then access:"
    echo "  - Frontend UI:    http://localhost:7860"
    echo "  - Backend API:    http://localhost:8000"
    echo ""

else
    echo -e "${RED}Invalid choice${NC}"
    exit 1
fi

echo ""
echo "=================================================="
echo "  Setup Complete! 🎉"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Open the frontend in your browser"
echo "  2. Upload some documents (PDF, DOCX, images)"
echo "  3. Ask questions in the chat interface"
echo ""
echo "For more information, see:"
echo "  - README.md for full documentation"
echo "  - QUICKSTART.md for getting started guide"
echo "  - ARCHITECTURE.md for system design details"
echo ""
