"""
Workspaces Router

A workspace groups the chat sessions of one line of work. It is the unit the
frontend routes on (/workspace/:id) and the key chat sessions are stored under.

Data itself lives in the Solid dataspace, so a workspace carries no files - it
is purely an organisational container.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..db import get_session
from ..models import Workspace, WorkspaceCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspaces"])


@router.get("", summary="List all workspaces")
async def list_workspaces(db: Session = Depends(get_session)) -> List[Workspace]:
    """Return all workspaces, newest first."""
    statement = select(Workspace).order_by(Workspace.created.desc())
    return list(db.exec(statement).all())


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a workspace")
async def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_session),
) -> Workspace:
    """Create a workspace.

    `clone_from_id` is accepted for compatibility with the existing frontend but
    only copies the title and description: there are no workspace-local files to
    duplicate now that data is read from the dataspace.
    """
    workspace = Workspace(title=payload.title, description=payload.description)

    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    logger.info(f"Created workspace {workspace.id} ({workspace.title})")
    return workspace


@router.get("/{workspace_id}", summary="Read a single workspace")
async def get_workspace(workspace_id: str, db: Session = Depends(get_session)) -> Workspace:
    """Return one workspace by id."""
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


@router.delete("/{workspace_id}", summary="Delete a workspace")
async def delete_workspace(workspace_id: str, db: Session = Depends(get_session)):
    """Delete a workspace and, by cascade, its chat sessions."""
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    db.delete(workspace)
    db.commit()

    logger.info(f"Deleted workspace {workspace_id}")
    return {"message": "Workspace deleted", "workspace_id": workspace_id}
