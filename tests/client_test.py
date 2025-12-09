import time
import requests

API_URL = "http://127.0.0.1:8000"
TOKEN = "scebob"  # твой APP_TOKEN из .env


def call_api(method, endpoint, json=None):
    url = f"{API_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        r = requests.request(method, url, json=json, headers=headers, timeout=5)
        print(f"[{method}] {endpoint} → {r.status_code}")
        print("Response:", r.text)
        return r
    except Exception as e:
        print(f"[ERROR] API call failed: {method} {endpoint}: {e}")
        return None


def test_camera(camera_id: str):
    print(f"\n==============================")
    print(f"   TESTING CAMERA: {camera_id}")
    print(f"==============================\n")

    # 1. Absolute move
    print("[STEP] move → absolute positioning")
    call_api(
        "POST",
        f"/api/ptz/{camera_id}/move/",
        json={
            "lat": 70.0,         # тестовые координаты
            "lon": 70.0,
            "height": 12.0,
            "zoom": 0.2,
            "radar_id": 1
        }
    )
    time.sleep(4)

    # 2. Continuous move
    print("[STEP] continuous move → x=0.5 y=0.0")
    call_api(
        "POST",
        f"/api/ptz/{camera_id}/continuous_move/",
        json={"x": 1, "y": 1, "zoom": 0.0}
    )
    time.sleep(2)

    # 3. Stop
    print("[STEP] stop")
    call_api("POST", f"/api/ptz/{camera_id}/stop/")
    time.sleep(1)

    # 4. Second continuous move
    print("[STEP] continuous move #2 → x=-0.3 y=0.3")
    call_api(
        "POST",
        f"/api/ptz/{camera_id}/continuous_move/",
        json={"x": -0.7, "y": -1, "zoom": 0.0}
    )
    time.sleep(1)

    # 5. Stop again
    print("[STEP] stop again")
    call_api("POST", f"/api/ptz/{camera_id}/stop/")
    time.sleep(1)

    print(f"\n=== DONE {camera_id} ===\n")


def main():
    print("=== Starting PTZ API Test ===")
    for cam_id in ("camera1", "camera2"):
        test_camera(cam_id)

    print("=== TEST COMPLETE ===")


if __name__ == "__main__":
    main()
