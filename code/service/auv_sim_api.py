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
    data = await request.json()
    ctrl.pitch_fin = clamp(int(data["value"]), -30, 30)
    return web.json_response({"pitch_fin":ctrl.pitch_fin})

async def set_yaw(request):
    data = await request.json()
    ctrl.yaw_fin = clamp(int(data["value"]), -30, 30)
    return web.json_response({"yaw_fin":ctrl.yaw_fin})

async def set_prop(request):
    data = await request.json()
    ctrl.prop = clamp(int(data["value"]), -30, 100)
    return web.json_response({"prop":ctrl.prop})

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

app = web.Application()
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
    print("AUV Sim running on :8080")

asyncio.run(start())
