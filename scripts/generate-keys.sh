#!/bin/bash
# ===========================================
# Recipe Finder - Generate Supabase Keys
# ===========================================
# This script generates JWT keys for Supabase
# Based on your JWT_SECRET

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔑 Supabase Key Generator${NC}"
echo ""

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ jq is required but not installed.${NC}"
    echo -e "   Install with: sudo apt-get install jq (Linux) or brew install jq (Mac)"
    exit 1
fi

# Check if openssl is installed
if ! command -v openssl &> /dev/null; then
    echo -e "${RED}❌ openssl is required but not installed.${NC}"
    exit 1
fi

# Generate or use existing JWT_SECRET
if [ -z "$1" ]; then
    JWT_SECRET=$(openssl rand -base64 32)
    echo -e "${YELLOW}Generated new JWT_SECRET${NC}"
else
    JWT_SECRET="$1"
    echo -e "${YELLOW}Using provided JWT_SECRET${NC}"
fi

# JWT Header
HEADER=$(echo -n '{"alg":"HS256","typ":"JWT"}' | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')

# Anon key payload (expires in 2050)
ANON_PAYLOAD=$(echo -n '{"iss":"supabase","role":"anon","iat":'"$(date +%s)"',"exp":2524608000}' | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')

# Service role payload (expires in 2050)
SERVICE_PAYLOAD=$(echo -n '{"iss":"supabase","role":"service_role","iat":'"$(date +%s)"',"exp":2524608000}' | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')

# Generate signatures
ANON_SIGNATURE=$(echo -n "${HEADER}.${ANON_PAYLOAD}" | openssl dgst -sha256 -hmac "${JWT_SECRET}" -binary | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')
SERVICE_SIGNATURE=$(echo -n "${HEADER}.${SERVICE_PAYLOAD}" | openssl dgst -sha256 -hmac "${JWT_SECRET}" -binary | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')

# Compose tokens
ANON_KEY="${HEADER}.${ANON_PAYLOAD}.${ANON_SIGNATURE}"
SERVICE_KEY="${HEADER}.${SERVICE_PAYLOAD}.${SERVICE_SIGNATURE}"

echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}Generated Keys${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo -e "${YELLOW}Add these to your .env file:${NC}"
echo ""
echo "JWT_SECRET=${JWT_SECRET}"
echo ""
echo "ANON_KEY=${ANON_KEY}"
echo ""
echo "SERVICE_ROLE_KEY=${SERVICE_KEY}"
echo ""
echo -e "${GREEN}=============================================${NC}"
