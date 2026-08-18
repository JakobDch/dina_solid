"""
Workspaces Router

A workspace groups chat sessions. It used to hold uploaded files as well, but
the data now lives in the Solid dataspace, so nothing is stored per workspace
any more and users are never asked to create one.

What remains is the key that conversations are filed under. The interface calls
`/default` on startup and works with whatever comes back.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..db import get_session
from ..models import Workspace, WorkspaceCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspaces"])

DEFAULT_WORKSPACE_TITLE = "My conversations"


@router.get("/default", summary="Get or create the default workspace")
async def get_default_workspace(db: Session = Depends(get_session)) -> Workspace:
    """Return a workspace to file conversations under, creating one if needed.

    Workspaces are an implementation detail now: the interface needs an id to
    attach sessions to, but the user never picks one. Reusing the oldest keeps
    a returning visitor's history in one place instead of scattering it across
    a new workspace per visit.
    """
    existing = db.exec(select(Workspace).order_by(Workspace.created.asc())).first()
    if existing:
        return existing

    workspace = Workspace(title=DEFAULT_WORKSPACE_TITLE)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    logger.info(f"Created the default workspace {workspace.id}")
    return workspace


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
    """Create a workspace."""
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
