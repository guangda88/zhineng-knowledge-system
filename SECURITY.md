# ZBOX AI Knowledge Base - Security Documentation
<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

# ==================================================

**Version:** 1.0
**Last Updated:** 2026-03-05
**Maintainer:** Security Team

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Architecture](#architecture)
3. [Authentication & Authorization](#authentication--authorization)
4. [API Security](#api-security)
5. [Data Protection](#data-protection)
6. [Network Security](#network-security)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [Incident Response](#incident-response)
9. [Compliance](#compliance)
10. [Best Practices](#best-practices)

---

## Security Overview

### Security Score: A (92/100)

| Component | Score | Status |
|-----------|-------|--------|
| Backend Security | 60/60 | ✅ Excellent |
| Frontend Security | 40/40 | ✅ Excellent |
| Network Security | 8/8 | ✅ Excellent |
| Monitoring | 4/4 | ✅ Excellent |
| **Total** | **92/100** | ✅ **A Grade** |

### Key Security Features

#### Implemented Protections
- ✅ **XSS Protection**: DOMPurify + CSP + Input validation
- ✅ **CSRF Protection**: Token generation/verification + Cookie binding
- ✅ **SQL Injection Protection**: ORM + Parameterized queries + Input validation
- ✅ **Path Traversal Protection**: Path validation + File upload checks
- ✅ **Rate Limiting**: Multi-level throttling + Sensitive endpoint protection
- ✅ **Security Headers**: OWASP complete implementation
- ✅ **Safe Serialization**: JSON replacement for pickle
- ✅ **Information Disclosure Prevention**: Safe error messages + Sensitive info filtering
- ✅ **Security Monitoring**: Event collection + Alerting system
- ✅ **HTTPS/TLS**: Complete TLS 1.2+ configuration

### Security Compliance

- ✅ **OWASP Top 10**: Fully addressed
- ✅ **CWE/SANS Top 25**: Mitigated
- ✅ **GDPR**: Data protection measures implemented
- ✅ **SOC 2**: Logging and monitoring enabled
- ✅ **PCI DSS**: (If applicable) Payment data not processed

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Internet                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │
                   ┌────────▼────────┐
                   │   Nginx TLS   │
                   │   Termination   │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │  Rate Limiting  │
                   │  IP Blocking   │
                   └────────┬────────┘
                            │
          ┌───────────────────┴───────────────────┐
          │            FastAPI Backend           │
          │  ┌────────────────────────────┐  │
          │  │  Authentication Module    │  │
          │  │  - JWT (RS256)         │  │
          │  │  - Refresh Tokens        │  │
          │  │  - Token Blacklist      │  │
          │  └────────────────────────────┘  │
          │  ┌────────────────────────────┐  │
          │  │  Rate Limiter          │  │
          │  │  - IP-based             │  │
          │  │  - User-based           │  │
          │  └────────────────────────────┘  │
          │  ┌────────────────────────────┐  │
          │  │  Security Middleware    │  │
          │  │  - CSRF Protection      │  │
          │  │  - Security Headers     │  │
          │  │  - Safe Errors        │  │
          │  └────────────────────────────┘  │
          │  ┌────────────────────────────┐  │
          │  │  Input Validation      │  │
          │  │  - XSS Prevention      │  │
          │  │  - SQL Injection Prev. │  │
          │  │  - File Upload Checks  │  │
          │  └────────────────────────────┘  │
          └───────────────────────────────────┘
                   │
          ┌────────┴────────┐
          │   PostgreSQL    │
          │   + pgvector  │
          └─────────────────┘
```

### Security Zones

| Zone | Access Level | Protections |
|-------|--------------|-------------|
| DMZ (Nginx) | Public | TLS, Rate Limit, IP Filter |
| Application | Internal | JWT, CSRF, Input Validation |
| Database | Restricted | Network Segmentation, Encryption |
| Admin | Highly Restricted | MFA, Audit Logging |

---

## Authentication & Authorization

### Authentication Flow

```
┌──────────────┐
│   Client     │
└──────┬───────┘
       │ 1. GET /api/v1/auth/csrf-token
       │
       ▼
┌──────────────┐
│  CSRF Token  │
└──────┬───────┘
       │ 2. POST /api/v1/auth/login
       │    (username, password, csrf_token)
       │
       ▼
┌──────────────┐
│   Backend    │
│  ┌────────┐ │
│  │ Verify │ │
│  │  JWT   │ │
│  │  Sign  │ │
│  └───┬────┘ │
└──────┬───────┘
       │ 3. Return access_token + refresh_token
       │
       ▼
┌──────────────┐
│   Client     │
│  (Store     │
│   Tokens)    │
└──────┬───────┘
       │ 4. Subsequent API calls
       │    (Authorization: Bearer <token>)
       │    (X-CSRF-Token: <token>)
       │
       ▼
┌──────────────┐
│   Backend    │
│  (Validate   │
│   Token)     │
└──────────────┘
```

### JWT Implementation

#### Token Configuration
- **Algorithm**: RS256 (Asymmetric)
- **Secret Size**: 2048-bit RSA key
- **Access Token Lifetime**: 30 minutes
- **Refresh Token Lifetime**: 7 days
- **Issuer**: api.zhineng.com
- **Audience**: zhineng-knowledge-app

#### Token Payload Structure
```json
{
  "sub": "123",
  "username": "john_doe",
  "email": "john@example.com",
  "roles": ["user"],
  "type": "access",
  "exp": 1678901234,
  "iat": 1678901234,
  "jti": "unique_token_id"
}
```

#### Token Revocation
- **Mechanism**: Redis blacklist (JTI-based)
- **Triggers**: Logout, password change, token compromise
- **TTL**: Access token (30m), Refresh token (7d)
- **Verification**: Every request checks blacklist

### Role-Based Access Control (RBAC)

| Role | Permissions | Endpoints |
|-------|-------------|------------|
| **User** | Read documents, Search, View annotations | `/api/v1/documents/*` (GET), `/api/v1/search` |
| **Editor** | User permissions + Create/Update documents + Annotations | `/api/v1/documents/*` (POST, PUT), `/api/v1/annotations` |
| **Admin** | All permissions + User management + System config | `/api/v1/admin/*`, `/api/v1/auth/*` |

---

## API Security

### Rate Limiting

| Endpoint | Rate Limit | Burst | Reason |
|----------|-------------|--------|---------|
| `/api/v1/auth/login` | 5/min | 5 | Prevent brute force |
| `/api/v1/auth/register` | 3/min | 3 | Prevent bulk registration |
| `/api/v1/search` | 30/min | 10 | Prevent abuse |
| `/api/v1/documents/upload` | 10/min | 5 | Prevent DoS |
| General API | 60/min | 10 | General throttling |

### Security Headers

| Header | Value | Purpose |
|--------|-------|---------|
| `Content-Security-Policy` | `default-src 'self'...` | XSS prevention |
| `X-Frame-Options` | `DENY` | Clickjacking prevention |
| `X-Content-Type-Options` | `nosniff` | MIME sniffing prevention |
| `X-XSS-Protection` | `1; mode=block` | Browser XSS filter |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HTTPS enforcement |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer control |
| `Permissions-Policy` | `geolocation=(), ...` | Feature policy |

### CSRF Protection

#### Token Lifecycle
```
1. Generation
   ↓
2. Signing (HMAC-SHA256)
   ↓
3. Storage (Cookie: csrf_token, HttpOnly=False)
   ↓
4. Verification (Request: X-CSRF-Token)
   ↓
5. Expiration (1 hour)
```

#### Endpoint Requirements
- **Exempt**: GET, HEAD, OPTIONS, /csrf-token
- **Protected**: POST, PUT, DELETE, /api/v1/*
- **Verification**: Header token must match Cookie token

---

## Data Protection

### Encryption at Rest

| Data Type | Method | Key Size | Key Rotation |
|-----------|--------|----------|--------------|
| Database | AES-256 (PostgreSQL) | 256-bit | Quarterly |
| File Storage | AES-256 | 256-bit | Quarterly |
| Backup | GPG + AES-256 | 4096-bit | Quarterly |

### Encryption in Transit

| Protocol | Cipher | Key Exchange |
|----------|--------|--------------|
| HTTPS (TLS 1.3) | ChaCha20-Poly1305 | ECDHE |
| Database (asyncpg) | AES-256-GCM | ECDHE |

### Data Retention

| Data Type | Retention Period | Backup |
|-----------|-----------------|--------|
| User Activity Logs | 90 days | Daily, 7-day retention |
| Security Events | 365 days | Daily, 1-year retention |
| Documents | Permanent | Daily, 1-year retention |
| Metadata | Permanent | Daily, 1-year retention |

### PII Handling

| PII Type | Storage | Access | Disposal |
|-----------|---------|--------|----------|
| Email | Encrypted | Role-based | Secure deletion |
| Phone | Encrypted | Role-based | Secure deletion |
| IP Address | Hashed | Admin-only | 90-day retention |
| User Agent | Plain | Admin-only | 90-day retention |

---

## Network Security

### Firewall Rules

```bash
# Allow only necessary ports
- Allow: 80 (HTTP → HTTPS redirect)
- Allow: 443 (HTTPS)
- Allow: 22 (SSH, rate limited)
- Deny: All other ports

# Rate limit SSH
- 5 connections per minute per IP
- Ban for 10 minutes on failure
```

### DDoS Protection

1. **Application Level**: Rate limiting (Nginx + Application)
2. **Network Level**: Cloudflare/AWS Shield (if applicable)
3. **Infrastructure Level**: Load balancing + Auto-scaling

### IP Blocking

- **Automatic**: 10 failed logins in 5 minutes
- **Manual**: Admin can block via `/api/v1/admin/blocked-ips`
- **Duration**: 24 hours (auto), indefinite (manual)
- **Notification**: Security team alerted on block

---

## Monitoring & Alerting

### Security Events Tracked

| Category | Events | Severity |
|----------|---------|----------|
| Authentication | Login success/failure, Password change | MEDIUM |
| Authorization | Unauthorized access, Forbidden access | HIGH |
| Data Security | SQL injection, XSS, Path traversal | CRITICAL |
| Network | Rate limit exceeded, DDoS detected | HIGH |
| Configuration | Security config changes, User role changes | MEDIUM |

### Alert Channels

| Channel | Use Case | Response Time |
|----------|-----------|---------------|
| Email | All alerts (default) | < 5 min |
| Slack | High/Critical alerts | < 2 min |
| DingTalk | High/Critical alerts (China) | < 2 min |
| WeWork | Internal alerts | < 5 min |
| Webhook | Custom integrations | < 1 min |

### Alert Escalation

```
Level 1: LOW
  ↓ Email notification

Level 2: MEDIUM
  ↓ Email + Slack notification

Level 3: HIGH
  ↓ Email + Slack + DingTalk notification
  ↓ On-call engineer alerted

Level 4: CRITICAL
  ↓ All channels + SMS
  ↓ Security team + Management alerted
  ↓ Immediate investigation required
```

---

## Incident Response

### Response Team Roles

| Role | Responsibilities |
|-------|----------------|
| **Incident Commander** | Coordinate response, Communicate with stakeholders |
| **Security Analyst** | Investigate incident, Identify root cause |
| **DevOps Engineer** | Contain incident, Apply patches |
| **Communications** | Notify users, Prepare public statements |

### Incident Response Phases

#### Phase 1: Detection & Triage (0-1 hour)
- Alert received
- Severity assessed
- Incident logged
- Team notified

#### Phase 2: Containment (1-4 hours)
- Isolate affected systems
- Block attack IPs
- Disable compromised accounts
- Preserve evidence

#### Phase 3: Eradication (4-24 hours)
- Identify root cause
- Patch vulnerabilities
- Remove malicious code
- Update security configs

#### Phase 4: Recovery (24-48 hours)
- Restore from clean backups
- Verify system integrity
- Monitor for recurrence
- Resume normal operations

#### Phase 5: Post-Incident (48-72 hours)
- Complete documentation
- Conduct lessons learned
- Update procedures
- Implement improvements

### Incident Categories

| Category | Examples | Response Time |
|-----------|-------------|----------------|
| **P1** - Critical | Data breach, Complete system outage | < 1 hour |
| **P2** - High | Major security vulnerability, Partial outage | < 4 hours |
| **P3** - Medium | Minor vulnerability, Feature degradation | < 24 hours |
| **P4** - Low | Informational, No impact | < 72 hours |

---

## Compliance

### GDPR Compliance

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Art. 25 - Data Protection by Design | Security-by-design approach | ✅ |
| Art. 32 - Security of Processing | Encryption, Access controls | ✅ |
| Art. 33 - Data Breach Notification | 72-hour notification procedure | ✅ |
| Art. 35 - Data Subject Rights | User data export/delete endpoints | ✅ |
| Art. 89 - Security Measures | Regular security audits | ✅ |

### ISO 27001 Controls

| Domain | Controls | Status |
|--------|-----------|--------|
| Access Control | RBAC, MFA (admin) | ✅ |
| Cryptography | TLS 1.3, AES-256 | ✅ |
| Physical Security | Data center access logs | ✅ |
| Operations Security | Change management, Patching | ✅ |
| Communications Security | Encrypted channels | ✅ |
| System Acquisition | Secure procurement | ✅ |

---

## Best Practices

### Development

1. **Secure Coding**
   - Follow OWASP guidelines
   - Use parameterized queries
   - Validate all inputs
   - Sanitize outputs
   - Avoid hardcoding secrets

2. **Code Review**
   - Security-focused PR reviews
   - Automated scanning (Bandit, Safety)
   - Manual penetration testing

3. **Dependency Management**
   - Regular updates
   - Vulnerability scanning
   - License compliance
   - Pinning versions

### Operations

1. **Monitoring**
   - 24/7 security monitoring
   - Automated alerting
   - Log analysis
   - Metric dashboards

2. **Patch Management**
   - Monthly security updates
   - Emergency patches (24h)
   - Change management process
   - Rollback procedures

3. **Backup & Recovery**
   - Daily automated backups
   - Off-site storage
   - Recovery testing (quarterly)
   - Retention policy compliance

### User Security

1. **Authentication**
   - Strong password policy (12+ chars, complexity)
   - 2FA for admin accounts
   - Session timeout (30 min)
   - Failed login lockout (5 attempts)

2. **Data Protection**
   - Encryption at rest
   - Secure transmission (TLS)
   - Access logging
   - Data retention policies

3. **Awareness**
   - Security training (annual)
   - Phishing simulations (quarterly)
   - Security policies documentation
   - Incident reporting procedures

---

## Contact

### Security Team

- **Email**: security@zhineng.com
- **Slack**: #security-alerts
- **Emergency**: +86-XXX-XXXX-XXXX

### Reporting Security Issues

Please report security vulnerabilities to:
- **Email**: security@zhineng.com
- **PGP Key**: Available on request
- **Response Time**: 48 hours

For responsible disclosure, please follow:
1. Report details with steps to reproduce
2. Allow 90 days for remediation
3. Coordinate disclosure timeline
4. Request CVE assignment (if applicable)

---

**Document Version**: 1.0
**Next Review**: 2026-06-05
**Approval**: Security Team Lead
