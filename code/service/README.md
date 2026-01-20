# AUV Simulator API Service

Backend API for the AUV Simulator with production-grade security features.

## Key Features

✓ **Localhost ready** - Simple HTTP setup for local testing and demos
✓ **Production security** - Full WAF protection with input validation, rate limiting, security headers
✓ **Clean REST API** - Simple JSON endpoints for status and control
✓ **Modular design** - Can be deployed independently or with the web UI
✓ **Comprehensive testing** - 25 regression tests covering all endpoints and physics
✓ **Automatic retries** - Paired with client library that handles transient issues

## Security Protections

The API includes exceptional WAF (Web Application Firewall) protections:

### Rate Limiting
- 300 requests per minute per IP
- Automatic 5-minute IP blocking on violations
- Sliding window request tracking

### Input Validation
- **SQL Injection Detection** - Blocks SQL keywords and operators
- **XSS Prevention** - Detects and blocks script tags, event handlers
- **Path Traversal Prevention** - Blocks `../` and encoded traversal attempts
- **Command Injection Prevention** - Blocks shell commands and process substitution
- **Payload Size Limits** - Maximum 1KB per payload, 10KB per request

### Request Filtering
- **Suspicious User-Agent Blocking** - Detects attack tools (sqlmap, nikto, burp, etc.)
- **Forbidden Header Detection** - Blocks header injection attempts
- **Request Size Limits** - Rejects oversized payloads

### Security Headers
- `X-Content-Type-Options: nosniff` - Prevents MIME sniffing
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-XSS-Protection: 1; mode=block` - Browser XSS filter
- `Strict-Transport-Security` - Forces HTTPS (1 year)
- `Content-Security-Policy: default-src 'none'` - Strict CSP
- `Referrer-Policy: no-referrer` - Privacy protection

### Audit Logging
All security events logged with:
- Attack type detected
- Source IP address
- Timestamp
- Request details for forensics

## API Endpoints

All endpoints available at `http://localhost:8080` by default.

### GET /status
Returns current vehicle state and telemetry.

**Response:**
```json
{
  "pos_m": {"x": 0.0, "y": 0.0, "z": 0.0},
  "vel_mps": {"x": 0.0, "y": 0.0, "z": 0.0},
  "att_deg": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
  "controls": {"pitch_fin": 0, "yaw_fin": 0, "prop": 0}
}
```

### POST /pitch
Set horizontal fin angle.

**Request:**
```json
{"value": 15}  // -30 to 30 degrees
```

**Response:**
```json
{"pitch_fin": 15}
```

### POST /yaw
Set vertical fin angle.

**Request:**
```json
{"value": -10}  // -30 to 30 degrees
```

**Response:**
```json
{"yaw_fin": -10}
```

### POST /prop
Set propeller throttle.

**Request:**
```json
{"value": 50}  // -30 to 100 percent
```

**Response:**
```json
{"prop": 50}
```

## Quick Start

### Prerequisites
- Python 3.11+
- Dependencies: `aiohttp`, `pytest` (for testing)

### Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install aiohttp pytest
```

### Running the API

```bash
python auv_sim_api.py
```

Output:
```
INFO:WAF:AUV Sim API running on :8080 with WAF protection enabled
```

The API will start on `http://localhost:8080`

### Running Tests

```bash
pytest test_auv_sim_api.py -v
```

All 25 regression tests should pass.

## Development

### Physics Model

- Vehicle mass: 500 kg
- Buoyancy model with drag forces
- Fin-based attitude control (pitch/yaw)
- Propeller-based surge thrust
- Simple 6-DOF simulation step

### Testing Coverage

- API endpoint testing (all 4 endpoints)
- Control value clamping (boundary conditions)
- Physics calculations (drag, forces, attitude)
- Integration tests (multiple control sequences)
- Response validation (structure, types, content)

## Customization

### Changing API Port

Edit `auv_sim_api.py` and modify the TCP site creation:
```python
site = web.TCPSite(runner, "0.0.0.0", 9000)  # Change 8080 to desired port
```

### Adjusting Rate Limits

Edit `auv_sim_api.py`:
```python
rate_limiter = RateLimiter(requests_per_minute=600)  # Increase limit
```

### Disabling Security Features (NOT RECOMMENDED)

To remove specific security checks, edit the `waf_middleware` function. This is strongly discouraged for production use.

## Performance Notes

- Status polling interval: 100ms default (adjustable in client config)
- Request timeout: 5 seconds default
- Simulation step: 20ms (50 Hz physics)
- Supports concurrent requests with per-IP rate limiting

## Troubleshooting

### "Rate limit exceeded" Error
- Default limit is 300 requests/minute
- Wait 5 minutes for automatic unblock or restart the API
- Increase limit in code if needed for testing

### Connection Refused
- Verify API is running: `python auv_sim_api.py`
- Check port 8080 is available: `lsof -i :8080`
- Try different port if 8080 is in use

### Slow Responses
- Check network latency
- Monitor terminal logs for WAF issues
- Increase `statusPollInterval` in client config if polling too aggressively

## License

Licensed under the PolyForm Noncommercial License 1.0.0.
See LICENSE.md and COMMERCIAL.md for details.

Commercial use requires a separate license.
Contact: m.oger@roitsystems.ca
