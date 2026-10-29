"""
Rate limiting middleware using Redis
"""
import asyncio
from typing import Callable
from datetime import datetime

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from app.config import settings


class RateLimiter:
    """Rate limiter using Redis"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "rate_limit"
    
    async def is_rate_limited(self, key: str, limit: int, period: int) -> bool:
        """Check if rate limit exceeded"""
        current = await self.redis.get(f"{self.prefix}:{key}")
        
        if current is None:
            await self.redis.setex(f"{self.prefix}:{key}", period, 1)
            return False
        
        if int(current) >= limit:
            return True
        
        await self.redis.incr(f"{self.prefix}:{key}")
        return False
    
    async def get_remaining(self, key: str, limit: int) -> int:
        """Get remaining requests"""
        current = await self.redis.get(f"{self.prefix}:{key}")
        if current is None:
            return limit
        return max(0, limit - int(current))


def create_rate_limit_middleware(redis_client: redis.Redis):
    """Create rate limiting middleware"""
    
    async def rate_limit_middleware(request: Request, call_next: Callable):
        # Skip rate limiting for health checks
        if request.url.path in ["/api/v1/health", "/", "/api/docs", "/api/openapi.json"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Login rate limit (5 per minute)
        if request.url.path == "/api/v1/auth/login" and request.method == "POST":
            key = f"login:{client_ip}"
            limiter = RateLimiter(redis_client)
            
            if await limiter.is_rate_limited(key, limit=5, period=60):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many login attempts. Please try again later."}
                )
        
        # General rate limit (300 per minute)
        else:
            key = f"general:{client_ip}"
            limiter = RateLimiter(redis_client)
            
            if await limiter.is_rate_limited(key, limit=300, period=60):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded. Please slow down."}
                )
        
        return await call_next(request)
    
    return rate_limit_middleware
