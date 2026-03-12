class TestDetectorAPI:
    """
    Раньше здесь тестировался `/api/cameras`, но в проекте больше нет DB/UoW и
    отдельного cameras-endpoint.

    Проверяем живой endpoint, который существует в текущем приложении:
    `/api/detector/status`.
    """

    def test_get_detector_status_success(self, client_with_mocks, auth_header):
        client, mocks = client_with_mocks
        mocks["detector_manager"].get_current_mode.return_value = None
        mocks["detector_manager"].get_available_modes.return_value = {
            "optical": {"available": True, "weights_path": "optical.pt"},
            "thermal": {"available": True, "weights_path": "thermal.pt"},
        }

        response = client.get("/api/detector/status", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"current_mode", "available_modes"}
        assert isinstance(data["available_modes"], dict)
