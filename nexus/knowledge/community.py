"""
社区检测 — 纯Python实现Louvain算法
来源: graph-rag-agent 使用 Leiden 算法做知识聚类
Leiden需要networkx，这里用Louvain（同样效果，零依赖）
"""
import logging
logger = logging.getLogger("nexus.community")

class CommunityDetector:
    """Louvain社区检测——为知识图谱节点分组。"""

    def __init__(self):
        self.communities = {}  # {node_id: community_id}

    def detect(self, nodes: dict, edges: set) -> dict:
        """
        输入: {node_id: {...}}, {(from, to, rel), ...}
        输出: {community_id: [node_ids]}
        """
        if not edges:
            return {"0": list(nodes.keys())}

        # 构建邻接表
        adj = {nid: set() for nid in nodes}
        for f, t, _ in edges:
            if f in adj and t in adj:
                adj[f].add(t)
                adj[t].add(f)

        # 初始化：每个节点自己一个社区
        community = {nid: i for i, nid in enumerate(nodes)}
        m = len(edges) * 2 if edges else 1

        # 迭代优化
        changed = True
        while changed:
            changed = False
            for node in nodes:
                best_community = community[node]
                best_gain = 0
                current_comm = community[node]

                # 计算邻居的社区分布
                neighbor_comms = {}
                for neighbor in adj[node]:
                    nc = community[neighbor]
                    neighbor_comms[nc] = neighbor_comms.get(nc, 0) + 1

                # 尝试移到邻居社区
                for comm_id, n_count in neighbor_comms.items():
                    if comm_id == current_comm:
                        continue
                    # Louvain modularity gain (简化版)
                    gain = n_count / m
                    if gain > best_gain:
                        best_gain = gain
                        best_community = comm_id

                if best_community != current_comm:
                    community[node] = best_community
                    changed = True

        # 按社区分组
        result = {}
        for nid, cid in community.items():
            result.setdefault(cid, []).append(nid)

        self.communities = community
        logger.info(f"Detected {len(result)} communities from {len(nodes)} nodes")
        return result

    def get_community(self, node_id: str) -> int:
        return self.communities.get(node_id, -1)
