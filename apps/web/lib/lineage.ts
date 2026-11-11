import { StudioAsset } from './types';

export interface LineageNode {
  asset: StudioAsset;
  depth: number;
  row: number;
}

export interface LineageEdge {
  from: string;
  to: string;
}

export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
  columns: number;
  rows: number;
}

/** Depth-column layout of the asset DAG built from each asset's parentId. */
export function buildLineage(assets: StudioAsset[]): LineageGraph {
  const byId = new Map(assets.map((a) => [a.id, a]));
  const depthCache = new Map<string, number>();

  const depthOf = (asset: StudioAsset, guard = 0): number => {
    if (depthCache.has(asset.id)) return depthCache.get(asset.id)!;
    const parent = asset.parentId ? byId.get(asset.parentId) : undefined;
    const d = parent && guard < 64 ? depthOf(parent, guard + 1) + 1 : 0;
    depthCache.set(asset.id, d);
    return d;
  };

  // Oldest first so roots sit at the top of their column.
  const ordered = [...assets].sort((a, b) => a.createdAt - b.createdAt);
  const rowsPerColumn = new Map<number, number>();
  const nodes: LineageNode[] = ordered.map((asset) => {
    const depth = depthOf(asset);
    const row = rowsPerColumn.get(depth) || 0;
    rowsPerColumn.set(depth, row + 1);
    return { asset, depth, row };
  });

  const edges: LineageEdge[] = ordered
    .filter((a) => a.parentId && byId.has(a.parentId))
    .map((a) => ({ from: a.parentId as string, to: a.id }));

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
