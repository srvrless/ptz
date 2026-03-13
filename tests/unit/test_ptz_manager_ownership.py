from fastapi import HTTPException

from app.core.ptz.manager import PTZCameraManager


def test_assert_owner_no_selection_returns_409():
    mgr = PTZCameraManager()
    try:
        mgr.assert_owner(camera_id=1, client_id="c1")
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 409


def test_assert_owner_other_client_returns_423():
    mgr = PTZCameraManager()
    mgr.set_owner(camera_id=1, client_id="c1")
    try:
        mgr.assert_owner(camera_id=1, client_id="c2")
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 423


def test_clear_owner_other_client_returns_423():
    mgr = PTZCameraManager()
    mgr.set_owner(camera_id=1, client_id="c1")
    try:
        mgr.clear_owner(camera_id=1, client_id="c2")
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 423
