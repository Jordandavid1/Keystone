"""
KEYSTONE Project Router (/v1/projects)
Tenant-isolated project CRUD with soft-deletion filtering.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_tenant_id, get_current_user
from apps.api.src.db.models import User
from apps.api.src.db.session import get_db
from apps.api.src.repositories.projects import ProjectRepository

router = APIRouter(prefix="/v1/projects", tags=["Projects"])


class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None


@router.post("", summary="Create a new workspace project")
async def create_project(
    req: CreateProjectRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    project_repo = ProjectRepository(db, tenant_id=tenant_id)
    project_id = str(uuid.uuid4())
    project = await project_repo.create_project(
        id=project_id,
        name=req.name,
        description=req.description
    )
    return {
        "status": "ok",
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "user_id": project.user_id,
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None
    }


@router.get("", summary="List active projects for current tenant")
async def list_projects(
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    project_repo = ProjectRepository(db, tenant_id=tenant_id)
    projects = await project_repo.get_projects()
    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "user_id": p.user_id,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in projects
        ]
    }


@router.get("/{project_id}", summary="Get project by ID")
async def get_project(
    project_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    project_repo = ProjectRepository(db, tenant_id=tenant_id)
    project = await project_repo.get_project_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or forbidden"
        )
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "user_id": project.user_id,
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None
    }


@router.delete("/{project_id}", summary="Soft-delete project")
async def delete_project(
    project_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    project_repo = ProjectRepository(db, tenant_id=tenant_id)
    deleted = await project_repo.soft_delete_project(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or already deleted"
        )
    return {"status": "ok", "message": "Project soft-deleted successfully"}
