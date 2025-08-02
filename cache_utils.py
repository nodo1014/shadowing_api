"""
Caching utilities for performance optimization
성능 최적화를 위한 캐싱 유틸리티
"""
import json
import hashlib
import logging
from typing import Any, Optional, Callable
from datetime import datetime, timedelta
import redis
import pickle
from functools import wraps

logger = logging.getLogger(__name__)

class CacheManager:
    """캐시 관리 클래스"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, 
                 default_ttl: int = 3600, prefix: str = "cache:"):
        self.redis_client = redis_client
        self.default_ttl = default_ttl
        self.prefix = prefix
        self.local_cache = {}  # 로컬 캐시 (Redis 사용 불가시)
        self.use_redis = redis_client is not None
        
    def _generate_key(self, key: str) -> str:
        """캐시 키 생성"""
        return f"{self.prefix}{key}"
        
    def _hash_key(self, data: Any) -> str:
        """데이터를 해시하여 키 생성"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()
        
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 가져오기"""
        cache_key = self._generate_key(key)
        
        try:
            if self.use_redis:
                value = self.redis_client.get(cache_key)
                if value:
                    return pickle.loads(value)
            else:
                # 로컬 캐시 사용
                if cache_key in self.local_cache:
                    item = self.local_cache[cache_key]
                    if item['expiry'] > datetime.utcnow():
                        return item['value']
                    else:
                        # 만료된 항목 제거
                        del self.local_cache[cache_key]
                        
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            
        return None
        
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """캐시에 값 저장"""
        cache_key = self._generate_key(key)
        ttl = ttl or self.default_ttl
        
        try:
            if self.use_redis:
                serialized = pickle.dumps(value)
                self.redis_client.setex(cache_key, ttl, serialized)
            else:
                # 로컬 캐시 사용
                self.local_cache[cache_key] = {
                    'value': value,
                    'expiry': datetime.utcnow() + timedelta(seconds=ttl)
                }
                # 메모리 관리 - 최대 100개 항목만 유지
                if len(self.local_cache) > 100:
                    self._cleanup_local_cache()
                    
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
            
    def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        cache_key = self._generate_key(key)
        
        try:
            if self.use_redis:
                self.redis_client.delete(cache_key)
            else:
                if cache_key in self.local_cache:
                    del self.local_cache[cache_key]
                    
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
            
    def clear_pattern(self, pattern: str) -> int:
        """패턴과 일치하는 모든 캐시 삭제"""
        count = 0
        
        try:
            if self.use_redis:
                for key in self.redis_client.scan_iter(f"{self.prefix}{pattern}*"):
                    self.redis_client.delete(key)
                    count += 1
            else:
                # 로컬 캐시에서 패턴 매칭
                keys_to_delete = [k for k in self.local_cache.keys() 
                                 if k.startswith(f"{self.prefix}{pattern}")]
                for key in keys_to_delete:
                    del self.local_cache[key]
                    count += 1
                    
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            
        return count
        
    def _cleanup_local_cache(self):
        """로컬 캐시 정리 (만료된 항목 및 오래된 항목 제거)"""
        current_time = datetime.utcnow()
        
        # 만료된 항목 제거
        expired_keys = [k for k, v in self.local_cache.items() 
                       if v['expiry'] <= current_time]
        for key in expired_keys:
            del self.local_cache[key]
            
        # 여전히 100개 이상이면 가장 오래된 항목 제거
        if len(self.local_cache) > 100:
            sorted_items = sorted(self.local_cache.items(), 
                                key=lambda x: x[1]['expiry'])
            for key, _ in sorted_items[:20]:  # 가장 오래된 20개 제거
                del self.local_cache[key]
                

def cached(cache_manager: CacheManager, ttl: Optional[int] = None, 
          key_func: Optional[Callable] = None):
    """캐시 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 기본 키 생성 (함수명 + 인자)
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
                
            # 캐시에서 조회
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__} with key {cache_key}")
                return cached_value
                
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 결과 캐싱
            cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cached result for {func.__name__} with key {cache_key}")
            
            return result
            
        return wrapper
    return decorator
    

# 사용 예시
def create_subtitle_cache_key(subtitle_data: dict, template: str) -> str:
    """자막 데이터를 기반으로 캐시 키 생성"""
    key_data = {
        "text_eng": subtitle_data.get("text_eng", ""),
        "text_kor": subtitle_data.get("text_kor", ""),
        "keywords": subtitle_data.get("keywords", []),
        "template": template
    }
    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()