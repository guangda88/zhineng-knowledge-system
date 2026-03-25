# TLS/HTTPS Configuration
# ===========================================

# This directory contains TLS/HTTPS configuration for production deployment.

## Quick Start
# ------------

### 1. Generate Self-Signed Certificates (Development)
```bash
cd scripts
./generate-dev-certs.sh
```

### 2. Request Production Certificates (Let's Encrypt)
```bash
# Install certbot
apt-get install certbot

# Obtain certificate
certbot certonly --webroot -w /var/www/html \
  -d api.zhineng.com -d www.zhineng.com

# Certificates will be in /etc/letsencrypt/live/api.zhineng.com/
```

### 3. Configure Nginx
```bash
cp nginx/https.conf /etc/nginx/sites-available/zhineng-api
ln -s /etc/nginx/sites-available/zhineng-api /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 4. Configure Backend (Gunicorn/Uvicorn)
```bash
# Update .env
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000

# Run with SSL (behind Nginx proxy)
uvicorn main:app --host 0.0.0.0 --port 8000
```

## File Structure
# -------------

```
tls/
├── nginx/
│   ├── https.conf           # Production Nginx HTTPS config
│   ├── dev-https.conf      # Development HTTPS config (self-signed)
│   └── ssl-params.conf     # SSL best practices
├── scripts/
│   ├── generate-dev-certs.sh # Generate self-signed certificates
│   └── generate-csr.sh       # Generate CSR for production certs
└── certs/
    ├── README.md            # Certificate management guide
    └── .gitkeep           # Placeholder (don't commit actual certs)
```

## Security Best Practices
# ----------------------

### 1. Certificate Management
- Use strong cipher suites (TLS 1.2+)
- Rotate certificates annually
- Monitor certificate expiration
- Use certificate transparency logs

### 2. SSL Configuration
- Enable HSTS (HTTP Strict Transport Security)
- Use OCSP Stapling
- Disable weak protocols (SSLv3, TLS 1.0, TLS 1.1)
- Prefer ECDHE key exchange
- Use strong ciphers (AES-GCM, ChaCha20-Poly1305)

### 3. Forward Secrecy
- Ensure proper `X-Forwarded-*` headers
- Set `X-Forwarded-Proto: https` behind TLS terminator
- Validate upstream certificates

### 4. Session Security
- Use `Secure` flag on cookies
- Set `HttpOnly` on sensitive cookies
- Use `SameSite=Strict` or `SameSite=Lax`

## Monitoring
# ----------

### Certificate Expiration Monitoring
```bash
# Check certificate expiration
echo | openssl x509 -enddate -noout -in /path/to/cert.pem

# Monitor with Nagios/Zabbix
# Add check for < 30 days expiration warning
```

### SSL Labs Testing
```bash
# Test SSL configuration
curl https://www.ssllabs.com/ssltest/analyze.html?d=api.zhineng.com

# Aim for A+ grade
```

## Troubleshooting
# --------------

### Issue: Mixed Content Errors
**Solution**: Ensure all resources load via HTTPS
- Update hardcoded URLs
- Use protocol-relative URLs (`//cdn.example.com`)
- Configure CSP to allow HTTPS only

### Issue: Certificate Chain Incomplete
**Solution**: Include intermediate certificates
```nginx
ssl_certificate /etc/letsencrypt/live/domain/fullchain.pem;
```

### Issue: HSTS Preload Rejected
**Solution**: Ensure HSTS header is correct
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

### Issue: OCSP Stapling Fails
**Solution**: Configure OCSP responder correctly
```nginx
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /path/to/chain.pem;
resolver 8.8.8.8 8.8.4.4 valid=300s;
```

## References
# ----------

- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [SSL Labs Best Practices](https://www.ssllabs.com/projects/ssl-best-practices/)
- [OWASP Transport Layer Protection](https://owasp.org/www-project-cheatsheets/Transport_Layer_Protection_Cheat_Sheet)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
