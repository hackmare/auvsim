# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright © 2026 Morgane Oger
#
# Licensed under the PolyForm Noncommercial License 1.0.0
# Commercial use requires a separate license.
# See LICENSE.md and COMMERCIAL.md

# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright © 2026 Morgane Oger
#
# Licensed under the PolyForm Noncommercial License 1.0.0
# Commercial use requires a separate license.
# See LICENSE.md and COMMERCIAL.md

import math
import asyncio
from dataclasses import dataclass
from aiohttp import web
import logging
import re
import time
from collections import defaultdict
from typing import Optional, Dict
from datetime import datetime, timedelta

# Setup logging for security events
logging.basicConfig(level=logging.INFO)
security_logger = logging.getLogger("WAF")

# =============================
# WAF - Rate Limiting & Tracking
# =============================

class RateLimiter:
    """Rate limiter with IP-based tracking"""
    def __init__(self, requests_per_minute=300, window_seconds=60):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)
        self.blocked_ips: Dict[str, float] = {}

    def is_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked"""
        if ip in self.blocked_ips:
            if time.time() - self.blocked_ips[ip] < 300:  # 5 min block
                return True
            del self.blocked_ips[ip]
        return False

    def check_rate_limit(self, ip: str) -> bool:
        """Check if request exceeds rate limit"""
        now = time.time()
        
        # Clean old requests outside window
        self.requests[ip] = [t for t in self.requests[ip] 
                             if now - t < self.window_seconds]
        
        if len(self.requests[ip]) >= self.requests_per_minute:
            security_logger.warning(f"Rate limit exceeded for IP: {ip}")
            self.blocked_ips[ip] = now
            return False
        
        self.requests[ip].append(now)
        return True

rate_limiter = RateLimiter(requests_per_minute=300)

# =============================
# WAF - Input Validation
# =============================

class InputValidator:
    """Comprehensive input validation"""
    
    # Regex patterns for attack detection
    SQL_INJECTION_PATTERN = re.compile(
        r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|SCRIPT|JAVASCRIPT|EVAL)\b)|"
        r"(--|;|\'|\"|\*|\/\*|\*\/|xp_|sp_)",
        re.IGNORECASE
    )
    
    XSS_PATTERN = re.compile(
        r"(<script|javascript:|onerror=|onload=|onclick=|eval\(|expression\(|<iframe|<object|<embed)",
        re.IGNORECASE
    )
    
    PATH_TRAVERSAL_PATTERN = re.compile(r"(\.\./|\.\.\\|%2e%2e)")
    
    COMMAND_INJECTION_PATTERN = re.compile(
        r"(;\s*cat|;\s*rm|;\s*ls|`|sh\s+-c|bash\s+-c|\$\(|\|\||&&|\||&)",
        re.IGNORECASE
    )

    @staticmethod
    def validate_json_input(data: dict, max_size: int = 1024) -> tuple[bool, Optional[str]]:
        """Validate JSON input for attacks"""
        if not isinstance(data, dict):
            return False, "Invalid JSON structure"
        
        # Check size
        import sys
        if sys.getsizeof(str(data)) > max_size:
            security_logger.warning(f"Payload exceeds max size: {sys.getsizeof(str(data))} bytes")
            return False, "Payload too large"
        
        # Check for suspicious patterns
        data_str = str(data).lower()
        
        if InputValidator.SQL_INJECTION_PATTERN.search(data_str):
            security_logger.warning(f"SQL injection attempt detected: {data}")
            return False, "Invalid characters detected"
        
        if InputValidator.XSS_PATTERN.search(data_str):
            security_logger.warning(f"XSS attempt detected: {data}")
            return False, "Invalid characters detected"
        
        if InputValidator.PATH_TRAVERSAL_PATTERN.search(data_str):
            security_logger.warning(f"Path traversal attempt detected: {data}")
            return False, "Invalid characters detected"
        
        if InputValidator.COMMAND_INJECTION_PATTERN.search(data_str):
            security_logger.warning(f"Command injection attempt detected: {data}")
            return False, "Invalid characters detected"
        
        return True, None

    @staticmethod
    def validate_numeric_input(value: any, min_val: float, max_val: float) -> tuple[bool, Optional[str]]:
        """Validate numeric input"""
        try:
            num = int(value) if isinstance(value, (int, str)) else float(value)
            if not (min_val <= num <= max_val):
                return False, f"Value must be between {min_val} and {max_val}"
            return True, None
        except (ValueError, TypeError):
            return False, "Invalid numeric value"

validator = InputValidator()

# =============================
# WAF - Request Filtering
# =============================

class RequestFilter:
    """Filter suspicious requests"""
    
    # Suspicious User-Agents
    SUSPICIOUS_USER_AGENTS = [
        'sqlmap', 'nikto', 'nmap', 'nessus', 'masscan',
        'burp', 'zaproxy', 'metasploit', 'curl', 'wget'
    ]
    
    # Forbidden headers
    FORBIDDEN_HEADERS = {'x-forwarded-for', 'x-real-ip', 'x-originating-ip'}

    @staticmethod
    def check_user_agent(user_agent: Optional[str]) -> bool:
        """Check for suspicious User-Agent"""
        if not user_agent:
            return True
        
        ua_lower = user_agent.lower()
        for suspicious_ua in RequestFilter.SUSPICIOUS_USER_AGENTS:
            if suspicious_ua in ua_lower:
                security_logger.warning(f"Suspicious User-Agent detected: {user_agent}")
                return False
        return True

    @staticmethod
    def check_headers(headers: dict) -> bool:
        """Check for suspicious headers"""
        for forbidden in RequestFilter.FORBIDDEN_HEADERS:
            if forbidden in headers:
                security_logger.warning(f"Forbidden header detected: {forbidden}")
                return False
        return True

    @staticmethod
    def check_request_size(content_length: Optional[str]) -> bool:
        """Check request size"""
        MAX_CONTENT_LENGTH = 10 * 1024  # 10 KB
        
        if content_length:
            try:
                size = int(content_length)
                if size > MAX_CONTENT_LENGTH:
                    security_logger.warning(f"Request too large: {size} bytes")
                    return False
            except ValueError:
                return False
        return True

request_filter = RequestFilter()

# =============================
# WAF - Middleware
# ================================

@web.middleware
async def waf_middleware(request: web.Request, handler):
    """WAF middleware for all requests"""
    
    client_ip = request.remote or "unknown"
    
    # Check if IP is rate-limited
    if rate_limiter.is_blocked(client_ip):
        security_logger.error(f"Blocked request from rate-limited IP: {client_ip}")
        return web.json_response(
            {"error": "Too many requests"},
            status=429
        )
    
    # Check rate limit
    if not rate_limiter.check_rate_limit(client_ip):
        security_logger.error(f"Rate limit exceeded for IP: {client_ip}")
        return web.json_response(
            {"error": "Too many requests"},
            status=429
        )
    
    # Check User-Agent
    user_agent = request.headers.get('User-Agent', '')
    if not request_filter.check_user_agent(user_agent):
        security_logger.error(f"Blocked suspicious User-Agent from {client_ip}: {user_agent}")
        return web.json_response(
            {"error": "Forbidden"},
            status=403
        )
    
    # Check headers
    if not request_filter.check_headers(dict(request.headers)):
        security_logger.error(f"Blocked request with forbidden headers from {client_ip}")
        return web.json_response(
            {"error": "Forbidden"},
            status=403
        )
    
    # Check request size
    content_length = request.headers.get('Content-Length')
    if not request_filter.check_request_size(content_length):
        security_logger.error(f"Request too large from {client_ip}")
        return web.json_response(
            {"error": "Payload too large"},
            status=413
        )
    
    # Log request
    security_logger.info(f"Request from {client_ip}: {request.method} {request.path}")
    
    try:
        response = await handler(request)
    except Exception as e:
        security_logger.error(f"Error processing request from {client_ip}: {str(e)}")
        return web.json_response(
            {"error": "Internal server error"},
            status=500
        )
    
    # Add security headers to response
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'none'"
    response.headers['Referrer-Policy'] = 'no-referrer'
    
    return response

# -----------------------------
# Utilities
# -----------------------------

def clamp(x, lo, hi): return max(lo, min(hi, x))
def deg2rad(d): return d * math.pi / 180
def rad2deg(r): return r * 180 / math.pi

# -----------------------------
# Vehicle Parameters
# -----------------------------

@dataclass
class VehicleParams:
    mass: float = 500.0
    Ixx: float = 90.0
    Iyy: float = 260.0
    Izz: float = 260.0
    rho: float = 1025.0
    Cd: float = 0.1
    area_ref: float = math.pi * (0.4572/2)**2
    thrust_max: float = 9000.0
    fin_area: float = 0.0207
    fin_lift_slope: float = 3.5
    fin_x: float = -1.8

# -----------------------------
# State
# -----------------------------

@dataclass
class SimState:
    pos: list
    vel: list
    omega: list
    yaw: float
    pitch: float
    roll: float

# -----------------------------
# Controls
# -----------------------------

@dataclass
class Controls:
    pitch_fin: int = 0
    yaw_fin: int = 0
    prop: int = 0

# -----------------------------
# Core Physics
# -----------------------------

def drag_force(params, vel):
    v = math.sqrt(sum(v*v for v in vel))
    if v < 1e-6:
        return [0,0,0]
    k = 0.5 * params.rho * params.Cd * params.area_ref
    return [-k*v*vel[0], -k*v*vel[1], -k*v*vel[2]]

def step_sim(params, state, ctrl, dt):
    Fx = params.thrust_max * (ctrl.prop / 100.0)
    Fd = drag_force(params, state.vel)

    ax = (Fx + Fd[0]) / params.mass
    ay = Fd[1] / params.mass
    az = Fd[2] / params.mass

    state.vel[0] += ax * dt
    state.vel[1] += ay * dt
    state.vel[2] += az * dt

    state.pos[0] += state.vel[0] * dt
    state.pos[1] += state.vel[1] * dt
    state.pos[2] += state.vel[2] * dt

    # Simple yaw/pitch from fins
    state.yaw   += deg2rad(ctrl.yaw_fin)   * dt * 0.1
    state.pitch += deg2rad(ctrl.pitch_fin) * dt * 0.1

# -----------------------------
# Web API
# -----------------------------

params = VehicleParams()
state = SimState(pos=[0,0,0], vel=[0,0,0], omega=[0,0,0], yaw=0, pitch=0, roll=0)
ctrl = Controls()

async def status(request):
    return web.json_response({
        "pos_m": {"x":state.pos[0], "y":state.pos[1], "z":state.pos[2]},
        "vel_mps": {"x":state.vel[0], "y":state.vel[1], "z":state.vel[2]},
        "att_deg": {"yaw":rad2deg(state.yaw), "pitch":rad2deg(state.pitch), "roll":rad2deg(state.roll)},
        "controls": {"pitch_fin":ctrl.pitch_fin, "yaw_fin":ctrl.yaw_fin, "prop":ctrl.prop}
    })

async def set_pitch(request):
    try:
        data = await request.json()
        
        # Validate input
        is_valid, error_msg = validator.validate_json_input(data)
        if not is_valid:
            security_logger.warning(f"Invalid pitch input from {request.remote}: {error_msg}")
            return web.json_response({"error": error_msg}, status=400)
        
        # Validate value field exists and is numeric
        if "value" not in data:
            return web.json_response({"error": "Missing 'value' field"}, status=400)
        
        is_valid, error_msg = validator.validate_numeric_input(data["value"], -50, 50)
        if not is_valid:
            security_logger.warning(f"Invalid pitch value from {request.remote}: {error_msg}")
            return web.json_response({"error": error_msg}, status=400)
        
        ctrl.pitch_fin = clamp(int(data["value"]), -30, 30)
        security_logger.info(f"Pitch set to {ctrl.pitch_fin} from {request.remote}")
        return web.json_response({"pitch_fin": ctrl.pitch_fin})
    except Exception as e:
        security_logger.error(f"Error setting pitch: {str(e)}")
        return web.json_response({"error": "Invalid request"}, status=400)

async def set_yaw(request):
    try:
        data = await request.json()
        
        # Validate input
        is_valid, error_msg = validator.validate_json_input(data)
        if not is_valid:
            security_logger.warning(f"Invalid yaw input from {request.remote}: {error_msg}")
            return web.json_response({"error": error_msg}, status=400)
        
        # Validate value field exists and is numeric
        if "value" not in data:
            return web.json_response({"error": "Missing 'value' field"}, status=400)
        
        is_valid, error_msg = validator.validate_numeric_input(data["value"], -50, 50)
        if not is_valid:
            security_logger.warning(f"Invalid yaw value from {request.remote}: {error_msg}")
            return web.json_response({"error": error_msg}, status=400)
        
        ctrl.yaw_fin = clamp(int(data["value"]), -30, 30)
        security_logger.info(f"Yaw set to {ctrl.yaw_fin} from {request.remote}")
        return web.json_response({"yaw_fin": ctrl.yaw_fin})
    except Exception as e:
        security_logger.error(f"Error setting yaw: {str(e)}")
        return web.json_response({"error": "Invalid request"}, status=400)

async def set_prop(request):
    try:
        data = await request.json()
        
        # Validate input
        is_valid, error_msg = validator.validate_json_input(data)
        if not is_valid:
            security_logger.warning(f"Invalid prop input from {request.remote}: {error_msg}")
            return web.json_response({"error": error_msg}, status=400)
        
        # Validate value field exists and is numeric
        if "value" not in data:
            return web.json_response({"error": "Missing 'value' field"}, status=400)
        
        is_valid, error_msg = validator.validate_numeric_input(data["value"], -50, 150)
        if not is_valid:
            security_logger.warning(f"Invalid prop value from {request.remote}: {error_msg}")
            return web.json_response({"error": error_msg}, status=400)
        
        ctrl.prop = clamp(int(data["value"]), -30, 100)
        security_logger.info(f"Prop set to {ctrl.prop} from {request.remote}")
        return web.json_response({"prop": ctrl.prop})
    except Exception as e:
        security_logger.error(f"Error setting prop: {str(e)}")
        return web.json_response({"error": "Invalid request"}, status=400)

# -----------------------------
# Simulation Loop
# -----------------------------

async def sim_loop():
    dt = 0.02
    while True:
        step_sim(params, state, ctrl, dt)
        await asyncio.sleep(dt)

# -----------------------------
# App Setup
# -----------------------------

app = web.Application(middlewares=[waf_middleware])
app.router.add_get("/status", status)
app.router.add_post("/pitch", set_pitch)
app.router.add_post("/yaw", set_yaw)
app.router.add_post("/prop", set_prop)

async def start():
    asyncio.create_task(sim_loop())
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    security_logger.info("AUV Sim API running on :8080 with WAF protection enabled")

asyncio.run(start())
