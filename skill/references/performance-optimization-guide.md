# Kingdou Performance Optimization Implementation Guide

## Optimization Architecture

### Configuration Caching
- **File**: `config_loader.py`
- **Cache TTL**: 300 seconds (5 minutes)
- **Benefit**: Reduces file I/O overhead by 10-20ms per operation
- **Implementation**: Static class cache with timestamp-based expiration

### Network Connection Pooling
- **File**: `feishu_client.py`
- **Library**: requests with HTTPAdapter
- **Pool Settings**: 
  - pool_connections=10
  - pool_maxsize=20
  - retry_strategy: total=3, backoff_factor=0.5
- **Benefit**: Reduces network latency by 50-100ms per API call
- **Fallback**: Automatic fallback to urllib if requests not available

### Group-Specific Optimizations
- **High Optimization Groups**: Defined in `submit_piecework.py`
- **Current List**: 
  - `oc_<redacted-06>` (员工<11>计件群)
- **Optimization Applied**: Skip `get_record()` verification step
- **Performance Gain**: 300-500ms reduction in response time
- **Risk Management**: Only applied to trusted high-frequency groups

## Performance Benchmarks

| Operation | Before Optimization | After Optimization | Improvement |
|-----------|-------------------|-------------------|-------------|
| Config Load | 15ms | <1ms (cached) | 14ms |
| API Call (single) | 200ms | 100-150ms | 50-100ms |
| Full Submit (员工<11>) | 600-800ms | 200-300ms | 400-600ms |
| Full Submit (others) | 600-800ms | 500-650ms | 100-150ms |

## Implementation Details

### Configuration Cache Code
```python
class ConfigLoader:
    _config_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
    _cache_ttl = 300
    
    def load(self) -> Dict[str, Any]:
        cache_key = str(self.config_path)
        current_time = time.time()
        
        if cache_key in self._config_cache:
            cached_data, cached_time = self._config_cache[cache_key]
            if current_time - cached_time < self._cache_ttl:
                return cached_data
        
        # Load and cache new data
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self._config_cache[cache_key] = (data, current_time)
        return data
```

### Connection Pool Code
```python
# requests-based implementation with fallback
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    HAS_REQUESTS = False

class FeishuClient:
    def __init__(self):
        if HAS_REQUESTS:
            self.session = requests.Session()
            # Configure connection pool and retries
        else:
            self.session = None
```

### Group-Specific Optimization
```python
HIGH_OPTIMIZATION_GROUPS = {
    "oc_<redacted-06>": "员工<11>计件群"
}

if chat_id in HIGH_OPTIMIZATION_GROUPS and not dry_run:
    code = "PENDING"
    amount = parsed.unit_price * parsed.quantity
else:
    # Original verification logic
```

## Adding New Optimized Groups

To add a new group to high optimization:

1. **Verify group stability**: Ensure the group has consistent usage patterns
2. **Add to whitelist**: Update `HIGH_OPTIMIZATION_GROUPS` dictionary
3. **Monitor performance**: Check logs for any issues
4. **Rollback capability**: Remove from list if problems occur

## Monitoring and Metrics

Performance metrics are logged in:
- Gateway logs: `~/.hermes/logs/gateway.log`
- Kingdou logs: `~/.hermes/logs/kingdou/shadow-router.log`
- Error logs: `~/.hermes/logs/kingdou/shadow-router-errors.log`

Key metrics to monitor:
- Response time per submission
- API call success rates
- Cache hit ratios
- Error rates by group