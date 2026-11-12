from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.project_service import ProjectService


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)
