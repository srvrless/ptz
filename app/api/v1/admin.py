from sqladmin import ModelView

from app.models import Camera, CameraConnection, CameraLocation, CameraPTZ


class CameraAdmin(ModelView, model=Camera):
    """Admin view for Camera model."""

    column_list = [
        Camera.id,
        Camera.name,
        "location_lat",
        "location_lon",
        "location_height",
        "location_rate",
        "ptz_type",
    ]
    form_excluded_columns = [Camera.created_at, Camera.updated_at]
    column_sortable_list = [Camera.id]
    can_create = True
    can_edit = True
    can_delete = True


class CameraConnectionAdmin(ModelView, model=CameraConnection):
    """Admin view for CameraConnection model."""

    column_list = [
        CameraConnection.id,
        "camera_name",
        CameraConnection.host,
        CameraConnection.port,
        CameraConnection.rtsp_url,
        CameraConnection.rtsp_url_ik,
        CameraConnection.username,
        CameraConnection.password,
    ]
    form_excluded_columns = []
    column_sortable_list = [CameraConnection.id]
    can_create = True
    can_edit = True
    can_delete = True


class CameraLocationAdmin(ModelView, model=CameraLocation):
    column_list = [
        CameraLocation.id,
        "camera_name",
        CameraLocation.lat,
        CameraLocation.lon,
        CameraLocation.height,
        CameraLocation.rate,
    ]
    form_excluded_columns = []
    can_create = True
    can_edit = True
    can_delete = True


class CameraPTZAdmin(ModelView, model=CameraPTZ):
    column_list = [
        CameraPTZ.id,
        "camera_name",
        "ptz_type_name",
    ]
    form_excluded_columns = []
    can_create = True
    can_edit = True
    can_delete = True
