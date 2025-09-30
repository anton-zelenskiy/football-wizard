# 🔒 Mini App Security Implementation

This guide explains the comprehensive security measures implemented for your Telegram Mini App API.

## 🛡️ Security Layers Implemented

### 1. **Telegram WebApp Authentication**
- **HMAC-based validation** of Telegram WebApp init data
- **Cryptographic verification** using your bot token
- **Timestamp validation** (auth data expires after 24 hours)
- **User identity verification** from Telegram

### 2. **Rate Limiting**
- **Per-user rate limiting** (100 requests per hour per user)
- **IP-based rate limiting** (60 requests per minute per IP)
- **Automatic IP blocking** for suspicious activity
- **Graceful degradation** with user-friendly error messages

### 3. **Request Validation**
- **Origin header validation** (only Telegram domains allowed)
- **User-Agent validation** (Telegram WebApp signatures)
- **Request timeout protection** (30 seconds max)
- **Malicious request detection**

### 4. **Security Headers**
- **X-Content-Type-Options**: Prevents MIME type sniffing
- **X-Frame-Options**: Prevents clickjacking
- **X-XSS-Protection**: XSS attack prevention
- **Referrer-Policy**: Controls referrer information

## 🔧 Implementation Details

### Authentication Flow

```python
# 1. Client sends request with Telegram WebApp init data
Authorization: Bearer <telegram_init_data>

# 2. Server validates the init data
def validate_telegram_webapp_data(init_data: str, bot_token: str):
    # Parse and validate hash using HMAC-SHA256
    # Check timestamp (24-hour expiry)
    # Return authenticated user data
```

### Rate Limiting

```python
# Per-user limits
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW = 3600   # 1 hour in seconds

# Per-IP limits
MAX_REQUESTS_PER_MINUTE = 60
```

### Security Middleware

```python
# Applied to all Mini App routes
app.add_middleware(SecurityMiddleware, max_requests_per_minute=60)
app.add_middleware(MiniAppSecurityMiddleware)
```

## 🚨 Security Features

### ✅ **What's Protected:**

1. **API Endpoints** - All Mini App endpoints require authentication
2. **User Data** - Only authenticated Telegram users can access data
3. **Rate Limiting** - Prevents abuse and DoS attacks
4. **Request Validation** - Blocks malicious requests
5. **IP Blocking** - Automatic blocking of suspicious IPs
6. **Logging** - Comprehensive security event logging

### ✅ **What's NOT Protected:**

1. **HTML Interface** - The Mini App HTML page is publicly accessible (by design)
2. **Static Assets** - CSS/JS files are served without authentication
3. **Health Checks** - Basic health endpoints remain public

## 🔍 Security Monitoring

### Logged Events:
- **Authentication attempts** (success/failure)
- **Rate limit violations**
- **Suspicious User-Agent/Origin**
- **IP blocking events**
- **API access patterns**

### Example Log Entries:
```
INFO: Mini App API access: user_id=12345, ip=192.168.1.1, username=john_doe
WARNING: Rate limit exceeded for IP 192.168.1.1
WARNING: Suspicious User-Agent: curl/7.68.0
WARNING: Blocked IP 192.168.1.1 for 300 seconds
```

## 🚀 Usage Examples

### Secure API Call (from Mini App):
```javascript
// Get Telegram WebApp init data
const initData = window.Telegram.WebApp.initData;

// Make authenticated request
const response = await fetch('/football/api/v1/mini-app/betting-opportunities', {
    headers: {
        'Authorization': `Bearer ${initData}`,
        'Content-Type': 'application/json'
    }
});
```

### Error Handling:
```javascript
if (response.status === 401) {
    // Authentication failed - restart Mini App
    throw new Error('Authentication failed. Please restart the Mini App.');
} else if (response.status === 429) {
    // Rate limit exceeded
    throw new Error('Rate limit exceeded. Please try again later.');
}
```

## ⚙️ Configuration

### Environment Variables:
```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
BASE_HOST=https://your-domain.com

# Optional (with defaults)
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600
MAX_REQUESTS_PER_MINUTE=60
```

### Security Settings:
```python
class SecurityConfig:
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600
    REQUEST_TIMEOUT: int = 30
```

## 🧪 Testing Security

### Test Authentication:
```bash
# This should fail (no auth)
curl https://your-domain.com/football/api/v1/mini-app/betting-opportunities

# This should fail (invalid auth)
curl -H "Authorization: Bearer invalid_data" \
     https://your-domain.com/football/api/v1/mini-app/betting-opportunities
```

### Test Rate Limiting:
```bash
# Make multiple requests quickly to trigger rate limiting
for i in {1..70}; do
  curl https://your-domain.com/football/api/v1/mini-app/betting-opportunities
done
```

## 🚨 Security Best Practices

### ✅ **Do:**
- Keep your bot token secure
- Monitor security logs regularly
- Use HTTPS in production
- Update dependencies regularly
- Implement additional monitoring if needed

### ❌ **Don't:**
- Share your bot token
- Disable authentication for "testing"
- Ignore security warnings in logs
- Use HTTP in production
- Skip rate limiting

## 🔧 Troubleshooting

### Common Issues:

1. **"Authentication failed" errors:**
   - Check that bot token is correctly set
   - Verify Mini App is opened from Telegram
   - Ensure init data is being passed correctly

2. **"Rate limit exceeded" errors:**
   - Normal behavior for excessive requests
   - Wait for rate limit window to reset
   - Check if legitimate users are affected

3. **"Invalid origin" errors:**
   - Ensure Mini App is opened from Telegram
   - Check CORS configuration
   - Verify domain configuration

### Debug Mode:
```python
# Enable debug logging
import logging
logging.getLogger("app.api.security").setLevel(logging.DEBUG)
```

## 📊 Security Metrics

### Monitor These Metrics:
- **Authentication success rate**
- **Rate limit violations per hour**
- **Blocked IPs per day**
- **Suspicious requests per hour**
- **Average response time**

### Alert Thresholds:
- **>10% authentication failures**
- **>100 rate limit violations per hour**
- **>50 blocked IPs per day**
- **>1000 suspicious requests per hour**

## 🚀 Production Deployment

### Security Checklist:
- [ ] HTTPS enabled
- [ ] Bot token secured
- [ ] Rate limiting configured
- [ ] Security headers enabled
- [ ] Logging configured
- [ ] Monitoring setup
- [ ] Error handling tested
- [ ] Authentication tested

### Recommended Additional Security:
- **WAF (Web Application Firewall)**
- **DDoS protection**
- **SSL/TLS certificate monitoring**
- **Regular security audits**
- **Automated vulnerability scanning**

---

**🔒 Your Mini App API is now secure!** The implementation provides multiple layers of protection while maintaining a smooth user experience for legitimate Telegram users.
