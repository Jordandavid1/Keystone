"""
KEYSTONE Lineage Directed Acyclic Graph (DAG) Tracking
Supports the 9 canonical relationship types, self-parenting prevention,
cycle detection, cross-modal `depicts` persona edges, and ancestor/descendant BFS graph traversal.
"""

from __future__ import annotations

import collections
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import AssetRelationship

VALID_RELATIONSHIPS: List[str] = [
    "source",
    "edit",
    "variation",
    "animation",
    "upscale",
    "reference",
    "selected-final",
    "intermediate",
    "depicts",
]


class LineageDAG:
    """Lineage DAG tracker with strict acyclicity invariants."""

    VALID_RELATIONSHIPS = VALID_RELATIONSHIPS

    def __init__(self, session: Optional[AsyncSession] = None) -> None:
        self.session = session
        self.edges: List[Dict[str, Any]] = []

    def has_path(self, start: str, target: str, visited: Optional[Set[str]] = None) -> bool:
        """Determines if a directed path exists from start to target."""
        if start == target:
            return True
        if visited is None:
            visited = set()
        visited.add(start)

        nexts = [e["child_id"] for e in self.edges if e["parent_id"] == start]
        for n in nexts:
            if n not in visited:
                if self.has_path(n, target, visited):
                    return True
        return False

    def add_relationship(
        self,
        parent_id: str | uuid.UUID,
        child_id: str | uuid.UUID,
        relationship_type: str,
        job_id: Optional[str | uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Inserts a directed relationship edge parent -> child.
        Raises:
            ValueError: SELF_REFERENTIAL_LINEAGE if parent_id == child_id
            ValueError: INVALID_RELATIONSHIP_TYPE if type is unsupported
            ValueError: CYCLE_DETECTED if edge would form a directed cycle
        """
        p_id = str(parent_id)
        c_id = str(child_id)
        j_id = str(job_id) if job_id is not None else None

        if p_id == c_id:
            raise ValueError("SELF_REFERENTIAL_LINEAGE: An asset cannot be its own parent")

        if relationship_type not in VALID_RELATIONSHIPS:
            raise ValueError(f"INVALID_RELATIONSHIP_TYPE: '{relationship_type}' is not supported")

        # Cycle check: would adding p_id -> c_id create a path from c_id to p_id?
        if self.has_path(c_id, p_id):
            raise ValueError("CYCLE_DETECTED: Adding this relationship creates a directed cycle in lineage DAG")

        edge = {
            "id": str(uuid.uuid4()),
            "parent_id": p_id,
            "child_id": c_id,
            "relationship_type": relationship_type,
            "job_id": j_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.edges.append(edge)
        return edge

    def get_ancestors(self, asset_id: str | uuid.UUID) -> List[str]:
        """Traverses DAG upstream to return all ancestor asset IDs."""
        a_id = str(asset_id)
        ancestors: List[str] = []
        queue = collections.deque([a_id])
        visited = {a_id}

        while queue:
            cur = queue.popleft()
            parents = [e["parent_id"] for e in self.edges if e["child_id"] == cur]
            for p in parents:
                if p is not None and p not in visited:
                    visited.add(p)
                    ancestors.append(p)
                    queue.append(p)
        return ancestors

    def get_descendants(self, asset_id: str | uuid.UUID) -> List[str]:
        """Traverses DAG downstream to return all derived descendant asset IDs."""
        a_id = str(asset_id)
        descendants: List[str] = []
        queue = collections.deque([a_id])
        visited = {a_id}

        while queue:
            cur = queue.popleft()
            children = [e["child_id"] for e in self.edges if e["parent_id"] == cur]
            for c in children:
                if c is not None and c not in visited:
                    visited.add(c)
                    descendants.append(c)
                    queue.append(c)
        return descendants

    def get_depicts(self, asset_id: str | uuid.UUID) -> List[Dict[str, Any]]:
        """Returns `depicts` persona lineage edges targeting this asset."""
        a_id = str(asset_id)
        return [
            {
                "id": e.get("id"),
                "persona_id": e.get("persona_id"),
                "persona_version": e.get("persona_version"),
                "mature": bool(e.get("mature", False)),
                "job_id": e.get("job_id"),
                "created_at": e.get("created_at"),
            }
            for e in self.edges
            if e.get("child_id") == a_id and e.get("relationship_type") == "depicts"
        ]

    # Async Database Integration Methods
    async def load_from_db(self) -> None:
        """Loads all edges from database into memory graph."""
        if not self.session:
            return
        stmt = select(AssetRelationship)
        res = await self.session.execute(stmt)
        db_edges = res.scalars().all()
        self.edges = [
            {
                "id": str(e.id),
                "parent_id": str(e.parent_asset_id) if e.parent_asset_id else None,
                "child_id": str(e.child_asset_id) if e.child_asset_id else None,
                "relationship_type": e.relationship_type,
                "job_id": str(e.job_id) if e.job_id else None,
                "persona_id": str(e.persona_id) if e.persona_id else None,
                "persona_version": e.persona_version,
                "mature": bool(getattr(e, "mature", False)),
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in db_edges
        ]

    async def persist_relationship(
        self,
        parent_id: str | uuid.UUID,
        child_id: str | uuid.UUID,
        relationship_type: str,
        job_id: Optional[str | uuid.UUID] = None,
        mature: bool = False,
    ) -> AssetRelationship:
        """Validates acyclicity and persists edge to database."""
        if self.session:
            await self.load_from_db()
        edge_dict = self.add_relationship(parent_id, child_id, relationship_type, job_id)
        if self.session:
            db_rel = AssetRelationship(
                id=edge_dict["id"],
                parent_asset_id=edge_dict["parent_id"],
                child_asset_id=edge_dict["child_id"],
                relationship_type=edge_dict["relationship_type"],
                job_id=edge_dict["job_id"],
                mature=bool(mature),
            )
            self.session.add(db_rel)
            await self.session.flush()
            return db_rel
        return None  # type: ignore

    async def persist_depicts_edge(
        self,
        child_asset_id: str | uuid.UUID,
        persona_id: str | uuid.UUID,
        persona_version: int = 1,
        job_id: Optional[str | uuid.UUID] = None,
        mature: bool = False,
    ) -> AssetRelationship:
        """Persist a cross-modal `depicts(persona_id, persona_version)` edge for an output asset."""
        edge_id = str(uuid.uuid4())
        c_id = str(child_asset_id)
        p_id = str(persona_id)
        j_id = str(job_id) if job_id is not None else None
        p_ver = int(persona_version or 1)
        is_mature = bool(mature)

        self.edges.append(
            {
                "id": edge_id,
                "parent_id": None,
                "child_id": c_id,
                "relationship_type": "depicts",
                "job_id": j_id,
                "persona_id": p_id,
                "persona_version": p_ver,
                "mature": is_mature,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if not self.session:
            return None  # type: ignore

        db_rel = AssetRelationship(
            id=edge_id,
            parent_asset_id=None,
            child_asset_id=c_id,
            relationship_type="depicts",
            job_id=j_id,
            persona_id=p_id,
            persona_version=p_ver,
            mature=is_mature,
        )
        self.session.add(db_rel)
        await self.session.flush()
        return db_rel


async def persist_depicts_edge(
    session: AsyncSession,
    child_asset_id: str | uuid.UUID,
    persona_id: str | uuid.UUID,
    persona_version: int = 1,
    job_id: Optional[str | uuid.UUID] = None,
    mature: bool = False,
) -> AssetRelationship:
    """Async DB helper to persist a `depicts` lineage edge for a persona-bearing asset."""
    dag = LineageDAG(session=session)
    return await dag.persist_depicts_edge(
        child_asset_id=child_asset_id,
        persona_id=persona_id,
        persona_version=persona_version,
        job_id=job_id,
        mature=mature,
    )
