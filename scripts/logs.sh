#!/bin/bash
# ===========================================
# Recipe Finder - View Logs
# ===========================================

# Colors for output
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SERVICE=${1:-}

if [ -z "$SERVICE" ]; then
    echo -e "${YELLOW}📋 Showing logs for all services...${NC}"
    echo -e "${YELLOW}Tip: Use './scripts/logs.sh <service>' for specific service${NC}"
    echo -e "${YELLOW}Available: api, db, auth, rest, kong, studio, meta, inbucket${NC}"
    echo ""
    docker compose logs -f
else
    echo -e "${YELLOW}📋 Showing logs for: $SERVICE${NC}"
    docker compose logs -f "$SERVICE"
fi
