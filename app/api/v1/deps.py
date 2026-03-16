
from fastapi import HTTPException, Header


def get_client_id(x_client_id: str = Header(...)):
    if not x_client_id:
        raise HTTPException(status_code=400, detail="Client-ID missing")
    return x_client_id