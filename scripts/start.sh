#!/bin/bash
# ===========================================
# Recipe Finder - Start Script
# ===========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Recipe Finder...${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from .env.example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}📝 Please edit .env with your API keys before continuing.${NC}"
        echo -e "${YELLOW}   Required: YOUTUBE_API_KEY, ANTHROPIC_API_KEY${NC}"
        exit 1
    else
        echo -e "${RED}❌ No .env.example file found. Please create a .env file.${NC}"
        exit 1
    fi
fi

# Check for required environment variables
source .env

if [ -z "$YOUTUBE_API_KEY" ] || [ "$YOUTUBE_API_KEY" = "your-youtube-api-key" ]; then
    echo -e "${RED}❌ YOUTUBE_API_KEY is not set. Please update your .env file.${NC}"
    exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your-anthropic-api-key" ]; then
    echo -e "${RED}❌ ANTHROPIC_API_KEY is not set. Please update your .env file.${NC}"
    exit 1
fi

# Start the services
echo -e "${GREEN}📦 Building and starting containers...${NC}"
docker compose up -d --build

# Wait for services to be healthy
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 5

# Check if database is healthy
MAX_RETRIES=30
RETRY_COUNT=0
until docker compose exec -T db pg_isready -U postgres > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ Database failed to start. Check logs with: docker compose logs db${NC}"
        exit 1
    fi
    echo -e "${YELLOW}⏳ Waiting for database... (${RETRY_COUNT}/${MAX_RETRIES})${NC}"
    sleep 2
done

echo -e "${GREEN}✅ Database is ready!${NC}"

# Print service URLs
echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}🎉 Recipe Finder is running!${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo -e "📱 API:              http://localhost:${API_PORT:-3000}"
echo -e "🔐 Supabase API:     http://localhost:${KONG_HTTP_PORT:-8000}"
echo -e "🎛️  Supabase Studio:  http://localhost:${STUDIO_PORT:-3001}"
echo -e "📧 Email Inbox:      http://localhost:${INBUCKET_PORT:-9000}"
echo ""
echo -e "${YELLOW}Tip: View logs with: docker compose logs -f${NC}"
echo -e "${YELLOW}Tip: Stop with: ./scripts/stop.sh${NC}"
