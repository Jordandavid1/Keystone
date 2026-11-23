import { StudioAsset } from './types';

export interface LineageNode {
  asset: StudioAsset;
  depth: number;
  row: number;
}

export interface LineageEdge {
  from: string;
  to: string;
  relationshipType?: string;
}

export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
  columns: number;
  rows: number;
}

/** Depth-column layout of the asset DAG built from each asset's parentId and hydrated server edges. */
export function buildLineage(assets: StudioAsset[], extraEdges: LineageEdge[] = []): LineageGraph {
  const byId = new Map(assets.map((a) => [a.id, a]));
  const parentByChild = new Map<string, string>();
  const edgeMap = new Map<string, LineageEdge>();

  for (const a of assets) {
    if (a.parentId && byId.has(a.parentId) && a.parentId !== a.id) {
      parentByChild.set(a.id, a.parentId);
      edgeMap.set(`${a.parentId}->${a.id}`, { from: a.parentId, to: a.id });
    }
  }
  for (const e of extraEdges) {
    if (e.from && e.to && e.from !== e.to && byId.has(e.from) && byId.has(e.to)) {
      if (!parentByChild.has(e.to)) parentByChild.set(e.to, e.from);
      edgeMap.set(`${e.from}->${e.to}`, e);
    }
  }

  const depthCache = new Map<string, number>();

  const depthOf = (assetId: string, guard = 0): number => {
    if (depthCache.has(assetId)) return depthCache.get(assetId)!;
    const pId = parentByChild.get(assetId);
    const d = pId && byId.has(pId) && guard < 64 ? depthOf(pId, guard + 1) + 1 : 0;
    depthCache.set(assetId, d);
    return d;
  };

  // Oldest first so roots sit at the top of their column.
  const ordered = [...assets].sort((a, b) => a.createdAt - b.createdAt);
  const rowsPerColumn = new Map<number, number>();
  const nodes: LineageNode[] = ordered.map((asset) => {
    const depth = depthOf(asset.id);
    const row = rowsPerColumn.get(depth) || 0;
    rowsPerColumn.set(depth, row + 1);
    return { asset, depth, row };
  });

  const edges = Array.from(edgeMap.values());
  const columns = nodes.reduce((m, n) => Math.max(m, n.depth + 1), 0);
  const rows = Array.from(rowsPerColumn.values()).reduce((m, r) => Math.max(m, r), 0);
  return { nodes, edges, columns, rows };
}

/** Local ancestor chain of an asset (nearest first). */
export function ancestorsOf(assetId: string, assets: StudioAsset[]): string[] {
  const byId = new Map(assets.map((a) => [a.id, a]));
  const chain: string[] = [];
  let cur = byId.get(assetId);
  let guard = 0;
  while (cur && cur.parentId && guard < 64) {
    chain.push(cur.parentId);
    cur = byId.get(cur.parentId);
    guard += 1;
  }
  return chain;
}

export function descendantsOf(assetId: string, assets: StudioAsset[]): string[] {
  const out: string[] = [];
  const queue = [assetId];
  while (queue.length) {
    const cur = queue.shift()!;
    for (const a of assets) {
      if (a.parentId === cur && !out.includes(a.id)) {
        out.push(a.id);
        queue.push(a.id);
      }
    }
  }
  return out;
}
