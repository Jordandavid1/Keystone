"""
KEYSTONE Lineage Directed Acyclic Graph (DAG) Tracking
Supports the 8 canonical relationship types, self-parenting prevention,
cycle detection, and ancestor/descendant BFS graph traversal.
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
    "intermediate"
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
                if p not in visited:
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
                if c not in visited:
                    visited.add(c)
                    descendants.append(c)
                    queue.append(c)
        return descendants

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
                "parent_id": str(e.parent_asset_id),
                "child_id": str(e.child_asset_id),
                "relationship_type": e.relationship_type,
                "job_id": str(e.job_id) if e.job_id else None,
                "created_at": e.created_at.isoformat() if e.created_at else None
            }
            for e in db_edges
        ]

    async def persist_relationship(
        self,
        parent_id: str | uuid.UUID,
        child_id: str | uuid.UUID,
        relationship_type: str,
        job_id: Optional[str | uuid.UUID] = None
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
                metadata_={}
            )
            self.session.add(db_rel)
            await self.session.flush()
            return db_rel
        return None  # type: ignore
