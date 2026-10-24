"""Extract only complete XML elements; truncation is accepted only explicitly."""
import argparse
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

import networkx as nx
import osmnx as ox
from shapely import wkt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.chase import Arena, Rules
from src.chase_maps import MAP_PATH, scenario, split_long_edges


def extract_graphml(path, bbox, allow_truncated=False):
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    keys = {}
    west, south, east, north = bbox
    truncated = False
    try:
        for _, element in ET.iterparse(path, events=("end",)):
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "key":
                keys[element.attrib["id"]] = element.attrib.get("attr.name")
            elif tag in {"node", "edge"}:
                data = {keys.get(child.attrib.get("key")): child.text for child in element}
                if tag == "node":
                    x, y = float(data["x"]), float(data["y"])
                    if west <= x <= east and south <= y <= north:
                        graph.add_node(int(element.attrib["id"]), x=x, y=y)
                else:
                    u, v = int(element.attrib["source"]), int(element.attrib["target"])
                    if u in graph and v in graph:
                        attrs = {"length": float(data["length"])}
                        if data.get("geometry"):
                            attrs["geometry"] = wkt.loads(data["geometry"])
                        graph.add_edge(u, v, **attrs)
                        graph.add_edge(v, u, **attrs)
                element.clear()
    except ET.ParseError:
        if not allow_truncated:
            raise
        truncated = True
    if graph.number_of_edges() == 0:
        raise ValueError("Không có cạnh đầy đủ trong vùng trích xuất.")
    graph = graph.subgraph(max(nx.strongly_connected_components(graph), key=len)).copy()
    graph = split_long_edges(graph)
    if len(graph) > 600:
        cx, cy = (west + east) / 2, (south + north) / 2
        nodes = sorted(graph, key=lambda n: (graph.nodes[n]["x"] - cx) ** 2
                       + (graph.nodes[n]["y"] - cy) ** 2)[:600]
        graph = graph.subgraph(nodes).copy()
        graph = graph.subgraph(max(nx.strongly_connected_components(graph), key=len)).copy()
    graph.graph.update(source="Phố cổ Hà Nội · geometry OSM từ graph ô tô cục bộ",
                       attribution="© OpenStreetMap contributors, ODbL 1.0",
                       partial_source=str(truncated), source_file=path.name,
                       query_bbox=",".join(map(str, bbox)),
                       movement_model="Game: bidirectional road subset; not a complete walking network")
    return graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("graphml", type=Path)
    parser.add_argument("--allow-truncated", action="store_true")
    parser.add_argument("--output", type=Path, default=MAP_PATH)
    args = parser.parse_args()
    graph = extract_graphml(args.graphml, (105.843, 21.028, 105.859, 21.042), args.allow_truncated)
    arena = Arena(graph)
    for seed in range(20):
        scenario(arena, Rules(), seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp.graphml")
    ox.save_graphml(graph, temporary)
    temporary.replace(args.output)
    print(f"Saved {len(graph)} nodes / {graph.number_of_edges()} edges; partial_source={graph.graph['partial_source']}")


if __name__ == "__main__":
    main()
