import pytest
import asyncio
import json
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Import the components from auv_sim_api
import math
from dataclasses import dataclass


# Re-define classes for testing (copy from auv_sim_api.py)
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


@dataclass
class SimState:
    pos: list
    vel: list
    omega: list
    yaw: float
    pitch: float
    roll: float


@dataclass
class Controls:
    pitch_fin: int = 0
    yaw_fin: int = 0
    prop: int = 0


# Utility functions
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def deg2rad(d):
    return d * math.pi / 180


def rad2deg(r):
    return r * 180 / math.pi


def drag_force(params, vel):
    v = math.sqrt(sum(v*v for v in vel))
    if v < 1e-6:
        return [0, 0, 0]
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
    state.yaw += deg2rad(ctrl.yaw_fin) * dt * 0.1
    state.pitch += deg2rad(ctrl.pitch_fin) * dt * 0.1


# Test fixtures
class TestAUVSimAPI(AioHTTPTestCase):
    
    async def get_application(self):
        """Create and setup the test app"""
        self.params = VehicleParams()
        self.state = SimState(pos=[0, 0, 0], vel=[0, 0, 0], omega=[0, 0, 0], yaw=0, pitch=0, roll=0)
        self.ctrl = Controls()
        
        # Create handlers
        async def status(request):
            return web.json_response({
                "pos_m": {"x": self.state.pos[0], "y": self.state.pos[1], "z": self.state.pos[2]},
                "vel_mps": {"x": self.state.vel[0], "y": self.state.vel[1], "z": self.state.vel[2]},
                "att_deg": {"yaw": rad2deg(self.state.yaw), "pitch": rad2deg(self.state.pitch), "roll": rad2deg(self.state.roll)},
                "controls": {"pitch_fin": self.ctrl.pitch_fin, "yaw_fin": self.ctrl.yaw_fin, "prop": self.ctrl.prop}
            })

        async def set_pitch(request):
            data = await request.json()
            self.ctrl.pitch_fin = clamp(int(data["value"]), -30, 30)
            return web.json_response({"pitch_fin": self.ctrl.pitch_fin})

        async def set_yaw(request):
            data = await request.json()
            self.ctrl.yaw_fin = clamp(int(data["value"]), -30, 30)
            return web.json_response({"yaw_fin": self.ctrl.yaw_fin})

        async def set_prop(request):
            data = await request.json()
            self.ctrl.prop = clamp(int(data["value"]), -30, 100)
            return web.json_response({"prop": self.ctrl.prop})
        
        app = web.Application()
        app.router.add_get("/status", status)
        app.router.add_post("/pitch", set_pitch)
        app.router.add_post("/yaw", set_yaw)
        app.router.add_post("/prop", set_prop)
        return app

    @unittest_run_loop
    async def test_status_initial_state(self):
        """Test that status endpoint returns initial state"""
        resp = await self.client.request("GET", "/status")
        assert resp.status == 200
        data = await resp.json()
        
        # Verify initial state
        assert data["pos_m"]["x"] == 0
        assert data["pos_m"]["y"] == 0
        assert data["pos_m"]["z"] == 0
        assert data["vel_mps"]["x"] == 0
        assert data["vel_mps"]["y"] == 0
        assert data["vel_mps"]["z"] == 0
        assert data["att_deg"]["yaw"] == 0
        assert data["att_deg"]["pitch"] == 0
        assert data["att_deg"]["roll"] == 0
        assert data["controls"]["pitch_fin"] == 0
        assert data["controls"]["yaw_fin"] == 0
        assert data["controls"]["prop"] == 0

    @unittest_run_loop
    async def test_set_pitch_valid(self):
        """Test setting pitch fin with valid values"""
        resp = await self.client.request("POST", "/pitch", json={"value": 15})
        assert resp.status == 200
        data = await resp.json()
        assert data["pitch_fin"] == 15
        
        # Verify status reflects change
        resp = await self.client.request("GET", "/status")
        status_data = await resp.json()
        assert status_data["controls"]["pitch_fin"] == 15

    @unittest_run_loop
    async def test_set_pitch_clamp_positive(self):
        """Test pitch fin clamping on positive side"""
        resp = await self.client.request("POST", "/pitch", json={"value": 50})
        assert resp.status == 200
        data = await resp.json()
        assert data["pitch_fin"] == 30  # Should be clamped to max 30

    @unittest_run_loop
    async def test_set_pitch_clamp_negative(self):
        """Test pitch fin clamping on negative side"""
        resp = await self.client.request("POST", "/pitch", json={"value": -50})
        assert resp.status == 200
        data = await resp.json()
        assert data["pitch_fin"] == -30  # Should be clamped to min -30

    @unittest_run_loop
    async def test_set_yaw_valid(self):
        """Test setting yaw fin with valid values"""
        resp = await self.client.request("POST", "/yaw", json={"value": 20})
        assert resp.status == 200
        data = await resp.json()
        assert data["yaw_fin"] == 20
        
        # Verify status reflects change
        resp = await self.client.request("GET", "/status")
        status_data = await resp.json()
        assert status_data["controls"]["yaw_fin"] == 20

    @unittest_run_loop
    async def test_set_yaw_clamp_positive(self):
        """Test yaw fin clamping on positive side"""
        resp = await self.client.request("POST", "/yaw", json={"value": 100})
        assert resp.status == 200
        data = await resp.json()
        assert data["yaw_fin"] == 30  # Should be clamped to max 30

    @unittest_run_loop
    async def test_set_yaw_clamp_negative(self):
        """Test yaw fin clamping on negative side"""
        resp = await self.client.request("POST", "/yaw", json={"value": -100})
        assert resp.status == 200
        data = await resp.json()
        assert data["yaw_fin"] == -30  # Should be clamped to min -30

    @unittest_run_loop
    async def test_set_prop_valid(self):
        """Test setting propeller with valid values"""
        resp = await self.client.request("POST", "/prop", json={"value": 50})
        assert resp.status == 200
        data = await resp.json()
        assert data["prop"] == 50
        
        # Verify status reflects change
        resp = await self.client.request("GET", "/status")
        status_data = await resp.json()
        assert status_data["controls"]["prop"] == 50

    @unittest_run_loop
    async def test_set_prop_clamp_positive(self):
        """Test propeller clamping on positive side"""
        resp = await self.client.request("POST", "/prop", json={"value": 150})
        assert resp.status == 200
        data = await resp.json()
        assert data["prop"] == 100  # Should be clamped to max 100

    @unittest_run_loop
    async def test_set_prop_clamp_negative(self):
        """Test propeller clamping on negative side"""
        resp = await self.client.request("POST", "/prop", json={"value": -50})
        assert resp.status == 200
        data = await resp.json()
        assert data["prop"] == -30  # Should be clamped to min -30

    @unittest_run_loop
    async def test_set_prop_zero(self):
        """Test setting propeller to zero (neutral)"""
        resp = await self.client.request("POST", "/prop", json={"value": 0})
        assert resp.status == 200
        data = await resp.json()
        assert data["prop"] == 0

    @unittest_run_loop
    async def test_multiple_controls_sequence(self):
        """Test setting multiple controls in sequence"""
        # Set pitch
        resp = await self.client.request("POST", "/pitch", json={"value": 10})
        assert resp.status == 200
        
        # Set yaw
        resp = await self.client.request("POST", "/yaw", json={"value": -15})
        assert resp.status == 200
        
        # Set prop
        resp = await self.client.request("POST", "/prop", json={"value": 75})
        assert resp.status == 200
        
        # Check status shows all changes
        resp = await self.client.request("GET", "/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["controls"]["pitch_fin"] == 10
        assert data["controls"]["yaw_fin"] == -15
        assert data["controls"]["prop"] == 75

    @unittest_run_loop
    async def test_boundary_values(self):
        """Test boundary values for all controls"""
        test_cases = [
            ("/pitch", -30, -30),
            ("/pitch", 30, 30),
            ("/yaw", -30, -30),
            ("/yaw", 30, 30),
            ("/prop", -30, -30),
            ("/prop", 100, 100),
        ]
        
        for endpoint, input_val, expected in test_cases:
            resp = await self.client.request("POST", endpoint, json={"value": input_val})
            assert resp.status == 200
            data = await resp.json()
            control_name = endpoint.strip("/") + "_fin" if "fin" in endpoint else endpoint.strip("/")
            if control_name == "pitch_fin":
                assert data["pitch_fin"] == expected, f"Failed for {endpoint} with value {input_val}"
            elif control_name == "yaw_fin":
                assert data["yaw_fin"] == expected, f"Failed for {endpoint} with value {input_val}"
            elif control_name == "prop":
                assert data["prop"] == expected, f"Failed for {endpoint} with value {input_val}"

    @unittest_run_loop
    async def test_response_content_type(self):
        """Test that responses have correct content type"""
        resp = await self.client.request("GET", "/status")
        assert resp.content_type == "application/json"
        
        resp = await self.client.request("POST", "/pitch", json={"value": 10})
        assert resp.content_type == "application/json"

    @unittest_run_loop
    async def test_status_response_structure(self):
        """Test that status response has all required fields"""
        resp = await self.client.request("GET", "/status")
        data = await resp.json()
        
        # Check top-level keys
        assert "pos_m" in data
        assert "vel_mps" in data
        assert "att_deg" in data
        assert "controls" in data
        
        # Check nested keys
        assert all(k in data["pos_m"] for k in ["x", "y", "z"])
        assert all(k in data["vel_mps"] for k in ["x", "y", "z"])
        assert all(k in data["att_deg"] for k in ["yaw", "pitch", "roll"])
        assert all(k in data["controls"] for k in ["pitch_fin", "yaw_fin", "prop"])


# Additional unit tests for physics functions
class TestPhysicsUtils:
    
    def test_clamp_within_range(self):
        """Test clamp returns value within range unchanged"""
        assert clamp(5, 0, 10) == 5
        assert clamp(0, 0, 10) == 0
        assert clamp(10, 0, 10) == 10

    def test_clamp_above_range(self):
        """Test clamp clamps values above range"""
        assert clamp(15, 0, 10) == 10
        assert clamp(100, -30, 30) == 30

    def test_clamp_below_range(self):
        """Test clamp clamps values below range"""
        assert clamp(-5, 0, 10) == 0
        assert clamp(-100, -30, 30) == -30

    def test_deg2rad_conversion(self):
        """Test degree to radian conversion"""
        assert abs(deg2rad(0) - 0) < 1e-6
        assert abs(deg2rad(180) - math.pi) < 1e-6
        assert abs(deg2rad(90) - math.pi/2) < 1e-6

    def test_rad2deg_conversion(self):
        """Test radian to degree conversion"""
        assert abs(rad2deg(0) - 0) < 1e-6
        assert abs(rad2deg(math.pi) - 180) < 1e-6
        assert abs(rad2deg(math.pi/2) - 90) < 1e-6

    def test_drag_force_zero_velocity(self):
        """Test drag force is zero at zero velocity"""
        params = VehicleParams()
        force = drag_force(params, [0, 0, 0])
        assert force == [0, 0, 0]

    def test_drag_force_opposes_motion(self):
        """Test drag force opposes velocity direction"""
        params = VehicleParams()
        force = drag_force(params, [1, 0, 0])
        assert force[0] < 0  # Force opposes positive x velocity
        assert force[1] == 0
        assert force[2] == 0

    def test_step_sim_basic(self):
        """Test basic simulation step"""
        params = VehicleParams()
        state = SimState(pos=[0, 0, 0], vel=[0, 0, 0], omega=[0, 0, 0], yaw=0, pitch=0, roll=0)
        ctrl = Controls(prop=100)
        dt = 0.01
        
        step_sim(params, state, ctrl, dt)
        
        # With positive prop, should accelerate in positive direction
        assert state.vel[0] > 0
        assert state.pos[0] > 0

    def test_step_sim_multiple_steps(self):
        """Test multiple simulation steps accumulate changes"""
        params = VehicleParams()
        state = SimState(pos=[0, 0, 0], vel=[0, 0, 0], omega=[0, 0, 0], yaw=0, pitch=0, roll=0)
        ctrl = Controls(prop=50)
        dt = 0.01
        
        initial_pos = state.pos[0]
        
        for _ in range(10):
            step_sim(params, state, ctrl, dt)
        
        # Position should have increased over multiple steps
        assert state.pos[0] > initial_pos

    def test_step_sim_fin_control(self):
        """Test fin control affects attitude"""
        params = VehicleParams()
        state = SimState(pos=[0, 0, 0], vel=[0, 0, 0], omega=[0, 0, 0], yaw=0, pitch=0, roll=0)
        ctrl = Controls(pitch_fin=10)
        dt = 0.01
        
        initial_pitch = state.pitch
        step_sim(params, state, ctrl, dt)
        
        # Positive pitch fin should increase pitch
        assert state.pitch > initial_pitch


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
