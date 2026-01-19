from typing import Annotated

from fastapi import Depends

from app.utils.uow import InterfaceUnitOfWork, UnitOfWork

UOWDep = Annotated[InterfaceUnitOfWork, Depends(UnitOfWork)]