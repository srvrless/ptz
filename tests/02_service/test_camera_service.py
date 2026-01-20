
from app.services import camera_service
def test_camera_service_list_cameras():
    cams = camera_service.list_cameras()

    assert "camera1" in cams
    assert cams["camera1"]["host"] == "192.168.0.10"


def test_camera_service_mjpeg_stream(
    patched_camera_manager,
    patched_imencode,
    mock_socket_connection,
):
    gen = camera_service.get_mjpeg_stream(
        "camera1",
        enable_detection=False,
    )

    for _ in range(3):
        chunk = next(gen)
        assert b"--frame" in chunk
        assert b"Content-Type: image/jpeg" in chunk