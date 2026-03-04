const HORIZONTAL_GAP = 320;
const VERTICAL_GAP = 140;

interface BuildLayoutInput {
  nodeIdsInOrder: string[];
  adjacency: Map<string, string[]>;
  entryNodeId: string | null;
}

interface BuildLayoutResult {
  positions: Map<string, { x: number; y: number }>;
  reachableNodeIds: Set<string>;
}

export const buildWorkflowLayout = ({
  nodeIdsInOrder,
  adjacency,
  entryNodeId,
}: BuildLayoutInput): BuildLayoutResult => {
  const nodeIdSet = new Set(nodeIdsInOrder);
  const reachableNodeIds = new Set<string>();
  const levelById = new Map<string, number>();

  if (entryNodeId && nodeIdSet.has(entryNodeId)) {
    const queue: string[] = [entryNodeId];
    levelById.set(entryNodeId, 0);
    reachableNodeIds.add(entryNodeId);

    for (let index = 0; index < queue.length; index += 1) {
      const current = queue[index];
      const currentLevel = levelById.get(current) ?? 0;
      const targets = adjacency.get(current) ?? [];

      for (const target of targets) {
        if (!nodeIdSet.has(target) || levelById.has(target)) {
          continue;
        }
        levelById.set(target, currentLevel + 1);
        reachableNodeIds.add(target);
        queue.push(target);
      }
    }
  }

  const maxReachableLevel =
    levelById.size > 0
      ? Math.max(...Array.from(levelById.values()))
      : 0;
  const orphanLevel = levelById.size > 0 ? maxReachableLevel + 1 : 0;
  const rowByLevel = new Map<number, number>();
  const positions = new Map<string, { x: number; y: number }>();

  nodeIdsInOrder.forEach((nodeId) => {
    const level = levelById.get(nodeId) ?? orphanLevel;
    const row = rowByLevel.get(level) ?? 0;
    rowByLevel.set(level, row + 1);
    positions.set(nodeId, {
      x: level * HORIZONTAL_GAP,
      y: row * VERTICAL_GAP,
    });
  });

  return {
    positions,
    reachableNodeIds,
  };
};
