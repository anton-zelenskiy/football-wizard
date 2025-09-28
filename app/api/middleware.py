"""
Security middleware for Mini App API
"""

import time
from typing import Dict, Set

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for Mini App API"""
    
    def __init__(self, app, max_requests_per_minute: int = 60):
        super().__init__(app)
        self.max_requests_per_minute = max_requests_per_minute
        self.requests: Dict[str, list] = {}  # {ip: [timestamps]}
        self.blocked_ips: Set[str] = set()
        self.blocked_until: Dict[str, float] = {}  # {ip: unblock_timestamp}
    
    async def dispatch(self, request: Request, call_next):
        # Check if IP is blocked
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        if client_ip in self.blocked_ips:
            if current_time < self.blocked_until.get(client_ip, 0):
                logger.warning(f"Blocked IP {client_ip} attempted access")
                return Response(
                    content="IP blocked due to suspicious activity",
                    status_code=403
                )
            else:
                # Unblock IP
                self.blocked_ips.discard(client_ip)
                self.blocked_until.pop(client_ip, None)
        
        # Rate limiting
        if not self._is_rate_limited(client_ip, current_time):
            logger.warning(f"Rate limit exceeded for IP {client_ip}")
            self._block_ip(client_ip, current_time, 300)  # Block for 5 minutes
            return Response(
                content="Rate limit exceeded",
                status_code=429
            )
        
        # Log request
        logger.info(f"Mini App request: {request.method} {request.url} from {client_ip}")
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else 'unknown'
    
    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Check if IP is within rate limits"""
        # Clean old requests
        if client_ip in self.requests:
            self.requests[client_ip] = [
                timestamp for timestamp in self.requests[client_ip]
                if current_time - timestamp < 60  # Last minute
            ]
        else:
            self.requests[client_ip] = []
        
        # Check if under limit
        if len(self.requests[client_ip]) >= self.max_requests_per_minute:
            return False
        
        # Add current request
        self.requests[client_ip].append(current_time)
        return True
    
    def _block_ip(self, client_ip: str, current_time: float, duration: int):
        """Block IP for specified duration"""
        self.blocked_ips.add(client_ip)
        self.blocked_until[client_ip] = current_time + duration
        logger.warning(f"Blocked IP {client_ip} for {duration} seconds")


class MiniAppSecurityMiddleware(BaseHTTPMiddleware):
    """Mini App specific security middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.allowed_origins = {
            'https://web.telegram.org',
            'https://telegram.org',
            'https://t.me'
        }
    
    async def dispatch(self, request: Request, call_next):
        # Only apply to Mini App routes
        if not request.url.path.startswith('/football/api/v1/mini-app/'):
            return await call_next(request)
        
        # Check Origin header
        origin = request.headers.get('Origin', '')
        if origin and not any(allowed in origin for allowed in self.allowed_origins):
            logger.warning(f"Suspicious origin: {origin}")
            return Response(
                content="Invalid origin",
                status_code=403
            )
        
        # Check for Telegram WebApp headers
        user_agent = request.headers.get('User-Agent', '').lower()
        if not any(keyword in user_agent for keyword in ['telegram', 'webapp', 'mini-app']):
            logger.warning(f"Suspicious User-Agent: {user_agent}")
            # Don't block, but log for monitoring
        
        return await call_next(request)
