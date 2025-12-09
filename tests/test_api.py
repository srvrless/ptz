# tests/test_api.py
from typing import Any, Dict


def test_get_cameras(client, auth_header):
    resp = client.get("/api/cameras", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert "camera1" in data
    assert "camera2" in data


def test_ptz_move_endpoint(client, auth_header):
    payload = {
        "lat": 55.0,
        "lon": 37.0,
        "height": 5.0,
        "zoom": 0.5,
        "radar_id": 1,
    }
    resp = client.post("/api/ptz/camera1/move/", json=payload, headers=auth_header)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "ok"
    assert "azimut" in data
    assert isinstance(data["azimut"], (int, float))

# tests/test_api.py

# tests/test_api.py

def test_stream_endpoint(client, auth_header, monkeypatch):
    from app.api.v1 import deps as deps_module

    class DummyCameraService:
        @staticmethod
        def get_mjpeg_stream(camera_id: str, enable_detection: bool = True):
            # Делаем конечный генератор: пару фреймов и конец
            for _ in range(3):
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\nxxx\r\n"

    # подменяем зависимость, которую FastAPI инжектит в endpoint
    monkeypatch.setattr(deps_module, "get_camera_service", lambda: DummyCameraService())

    resp = client.get("/api/stream/camera1/", headers=auth_header)
    assert resp.status_code == 200

    body = resp.content
    assert b"--frame" in body
