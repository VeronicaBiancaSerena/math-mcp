"""NetworkX graph construction with bounded size."""

from __future__ import annotations

from typing import Any

import networkx as nx

from math_mcp.errors import InvalidInput
from math_mcp.schemas import Limits


def build_graph(payload: dict[str, Any], limits: Limits) -> Any:
    """Build a (possibly directed, possibly weighted) graph from a payload."""
    nodes = payload.get("nodes")
    edges = payload.get("edges", [])
    directed = bool(payload.get("directed", False))
    if not isinstance(nodes, list):
        raise InvalidInput("'nodes' must be a list")
    if not isinstance(edges, list):
        raise InvalidInput("'edges' must be a list")
    if len(nodes) > limits.max_graph_nodes:
        raise InvalidInput(f"graph has {len(nodes)} nodes, exceeds limit {limits.max_graph_nodes}")
    if len(edges) > limits.max_graph_edges:
        raise InvalidInput(f"graph has {len(edges)} edges, exceeds limit {limits.max_graph_edges}")

    graph = nx.DiGraph() if directed else nx.Graph()
    graph.add_nodes_from(str(n) for n in nodes)
    for edge in edges:
        if not isinstance(edge, list) or len(edge) < 2:
            raise InvalidInput("each edge must be [u, v] or [u, v, weight]")
        u, v = str(edge[0]), str(edge[1])
        if len(edge) >= 3:
            graph.add_edge(u, v, weight=float(edge[2]))
        else:
            graph.add_edge(u, v)
    return graph
