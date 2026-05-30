"""Graph algorithm operations backed by NetworkX (deterministic, exact)."""

from __future__ import annotations

from typing import Any

import networkx as nx

from math_mcp.backends.networkx_backend import build_graph
from math_mcp.errors import InvalidInput, UnsupportedOperation
from math_mcp.tools.base import Ctx, Outcome, object_result, verification_result
from math_mcp.tools.dispatch import handler


def _graph(ctx: Ctx) -> Any:
    return build_graph(ctx.payload, ctx.limits)


@handler("graph_compute", "is_connected")
def is_connected(ctx: Ctx) -> Outcome:
    graph = _graph(ctx)
    if graph.number_of_nodes() == 0:
        raise InvalidInput("connectivity is undefined for an empty graph")
    connected = nx.is_weakly_connected(graph) if graph.is_directed() else nx.is_connected(graph)
    return verification_result(
        status="success",
        certainty="exact",
        method="backend",
        backend="networkx",
        result={"connected": bool(connected)},
    )


@handler("graph_compute", "connected_components")
def connected_components(ctx: Ctx) -> Outcome:
    graph = _graph(ctx)
    gen = (
        nx.weakly_connected_components(graph)
        if graph.is_directed()
        else nx.connected_components(graph)
    )
    components = [sorted(component) for component in gen]
    return object_result(components, certainty="exact", method="backend", backend="networkx")


@handler("graph_compute", "shortest_path")
def shortest_path(ctx: Ctx) -> Outcome:
    graph = _graph(ctx)
    source, target = str(ctx.require("source")), str(ctx.require("target"))
    if source not in graph or target not in graph:
        raise InvalidInput("source and target must be nodes in the graph")
    try:
        path = nx.shortest_path(graph, source, target)
        result = {"path": path, "length": len(path) - 1, "reachable": True}
    except nx.NetworkXNoPath:
        result = {"path": None, "reachable": False}
    return object_result(result, certainty="exact", method="backend", backend="networkx")


@handler("graph_compute", "has_cycle")
def has_cycle(ctx: Ctx) -> Outcome:
    graph = _graph(ctx)
    if graph.is_directed():
        cyclic = not nx.is_directed_acyclic_graph(graph)
    else:
        cyclic = len(nx.cycle_basis(graph)) > 0
    return verification_result(
        status="success",
        certainty="exact",
        method="backend",
        backend="networkx",
        result={"has_cycle": bool(cyclic)},
    )


@handler("graph_compute", "topological_sort")
def topological_sort(ctx: Ctx) -> Outcome:
    graph = _graph(ctx)
    if not graph.is_directed():
        raise UnsupportedOperation("topological_sort requires a directed graph")
    if not nx.is_directed_acyclic_graph(graph):
        raise InvalidInput("topological_sort requires an acyclic graph")
    return object_result(
        list(nx.topological_sort(graph)), certainty="exact", method="backend", backend="networkx"
    )


@handler("graph_compute", "maximum_matching")
def maximum_matching(ctx: Ctx) -> Outcome:
    graph = _graph(ctx)
    if graph.is_directed():
        raise UnsupportedOperation("maximum_matching requires an undirected graph")
    matching = nx.max_weight_matching(graph, maxcardinality=True)
    edges = [sorted(pair) for pair in matching]
    return object_result(
        {"matching": edges, "size": len(edges)},
        certainty="exact",
        method="backend",
        backend="networkx",
    )


@handler("graph_compute", "minimum_spanning_tree")
def minimum_spanning_tree(ctx: Ctx) -> Outcome:
    graph = _graph(ctx)
    if graph.is_directed():
        raise UnsupportedOperation("minimum_spanning_tree requires an undirected graph")
    tree = nx.minimum_spanning_tree(graph)
    edges = [[u, v, tree[u][v].get("weight", 1.0)] for u, v in tree.edges()]
    total = sum(w for *_uv, w in edges)
    return object_result(
        {"edges": edges, "total_weight": total},
        certainty="exact",
        method="backend",
        backend="networkx",
    )
