#!/bin/bash
# ===========================================
# Recipe Finder - Stop Script
# ===========================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 Stopping Recipe Finder...${NC}"

# Stop and remove containers
docker compose down

echo -e "${GREEN}✅ All services stopped.${NC}"
echo ""
echo -e "${YELLOW}Tip: To also remove volumes (database data), run:${NC}"
echo -e "     docker compose down -v"
