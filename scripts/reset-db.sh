#!/bin/bash
# ===========================================
# Recipe Finder - Reset Database
# ===========================================
# WARNING: This will delete all data!

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}⚠️  WARNING: This will delete all database data!${NC}"
echo ""
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cancelled.${NC}"
    exit 0
fi

echo -e "${YELLOW}🗑️  Stopping services and removing volumes...${NC}"
docker compose down -v

echo -e "${GREEN}🔄 Restarting services with fresh database...${NC}"
./scripts/start.sh
