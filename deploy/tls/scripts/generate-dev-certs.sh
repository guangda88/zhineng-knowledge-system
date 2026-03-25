#!/bin/bash
# Development Certificate Generation Script
# ======================================

# This script generates self-signed SSL certificates for development/testing.
# DO NOT use these certificates in production!

set -e

# Configuration
CERT_DIR="$(dirname "$0")/../../certs/dev"
DOMAIN="dev.zhineng.local"
VALID_DAYS=365
RSA_BITS=2048
COUNTRY="CN"
STATE="Beijing"
LOCALITY="Beijing"
ORGANIZATION="ZBOX AI"
ORGANIZATIONAL_UNIT="Development"
COMMON_NAME="$DOMAIN"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Development Certificate Generator${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Create certificate directory
echo "Creating certificate directory..."
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

# Remove old certificates
echo "Removing old certificates..."
rm -f *.pem *.key *.crt *.csr

# Generate private key
echo -e "${YELLOW}Generating private key ($RSA_BITS bits)...${NC}"
openssl genrsa -out server.key $RSA_BITS
chmod 600 server.key

# Generate certificate signing request (CSR)
echo -e "${YELLOW}Generating CSR...${NC}"
openssl req -new -key server.key -out server.csr -subj "/C=$COUNTRY/ST=$STATE/L=$LOCALITY/O=$ORGANIZATION/OU=$ORGANIZATIONAL_UNIT/CN=$COMMON_NAME"

# Generate self-signed certificate
echo -e "${YELLOW}Generating self-signed certificate (valid for $VALID_DAYS days)...${NC}"
openssl x509 -req -days $VALID_DAYS -in server.csr -signkey server.key -out server.crt

# Generate full chain (self-signed, so same as certificate)
cp server.crt fullchain.pem

# Convert to PEM format
openssl x509 -in server.crt -outform PEM -out server.pem

# Set permissions
chmod 644 server.crt server.pem fullchain.pem
chmod 600 server.key

# Show certificate information
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Certificate Information${NC}"
echo -e "${GREEN}========================================${NC}"
openssl x509 -in server.crt -noout -text | grep -A 2 "Subject:"
openssl x509 -in server.crt -noout -text | grep "Not After"
echo ""

# Success message
echo -e "${GREEN}✓ Certificates generated successfully!${NC}"
echo ""
echo -e "${YELLOW}Certificate files:${NC}"
echo "  - server.crt     (Certificate)"
echo "  - server.key     (Private Key)"
echo "  - server.pem     (PEM format)"
echo "  - fullchain.pem  (Full Chain)"
echo ""
echo -e "${YELLOW}Certificate directory:${NC}"
echo "  $CERT_DIR"
echo ""
echo -e "${RED}WARNING: These are self-signed certificates for development only!${NC}"
echo -e "${RED}         DO NOT use in production!${NC}"
echo ""

# Update instructions
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Next Steps${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "1. Add to /etc/hosts (if testing locally):"
echo -e "   ${YELLOW}127.0.0.1 $DOMAIN${NC}"
echo ""
echo "2. Trust the certificate in your browser:"
echo -e "   ${YELLOW}open $CERT_DIR/server.crt${NC}"
echo ""
echo "3. Update backend configuration:"
echo -e "   ${YELLOW}UVICORN_SSL_CERTFILE=$CERT_DIR/server.pem${NC}"
echo -e "   ${YELLOW}UVICORN_SSL_KEYFILE=$CERT_DIR/server.key${NC}"
echo ""
echo "4. Update Nginx configuration:"
echo -e "   ${YELLOW}ssl_certificate $CERT_DIR/fullchain.pem;${NC}"
echo -e "   ${YELLOW}ssl_certificate_key $CERT_DIR/server.key;${NC}"
echo ""
echo -e "${GREEN}Done!${NC}"
