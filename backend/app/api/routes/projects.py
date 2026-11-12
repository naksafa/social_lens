import uuid

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_project_service
from app.schemas.project import ProjectCreate, ProjectListItem, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, service: ProjectService = Depends(get_project_service)) -> ProjectRead:
    return ProjectRead.model_validate(service.create(data))


@router.get("", response_model=list[ProjectListItem])
def list_projects(service: ProjectService = Depends(get_project_service)) -> list[ProjectListItem]:
    return service.list_projects()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, service: ProjectService = Depends(get_project_service)) -> ProjectRead:
    return ProjectRead.model_validate(service.get(project_id))


@router.put("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return ProjectRead.model_validate(service.update(project_id, data))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, service: ProjectService = Depends(get_project_service)) -> Response:
    service.delete(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
