#!/bin/bash

# Generate SSL certificates for development
echo "🔐 Generating SSL certificates for development..."

# Create infra-nginx directory if it doesn't exist
mkdir -p infra-nginx

# Generate private key
openssl genrsa -out infra-nginx/private.key 2048

# Generate certificate signing request
openssl req -new -key infra-nginx/private.key -out infra-nginx/cert.csr -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Generate self-signed certificate
openssl x509 -req -days 365 -in infra-nginx/cert.csr -signkey infra-nginx/private.key -out infra-nginx/cert.pem

# Clean up CSR file
rm infra-nginx/cert.csr

echo "✅ SSL certificates generated successfully!"
echo "📁 Files created:"
echo "  - infra-nginx/private.key"
echo "  - infra-nginx/cert.pem"
echo ""
echo "⚠️  Note: These are self-signed certificates for development only."
echo "   For production, use proper SSL certificates from a trusted CA." 