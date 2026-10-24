"""Fetch a small walking network once; gameplay itself never calls Overpass."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

import networkx as nx
import osmnx as ox
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.chase import Arena
from src.chase_maps import MAP_PATH, split_long_edges


def main():
    query = '''[out:xml][timeout:25];
    (way["highway"]["highway"!~"motorway|trunk|construction|proposed"]
    ["access"!~"private|no"]["foot"!="no"](21.032,105.847,21.038,105.853););(._;>;);out body;'''
    failures = []
    providers = (
        ("https://api.openstreetmap.org/api/0.6/map", {"bbox": "105.847,21.032,105.853,21.038"}),
        ("https://overpass-api.de/api/interpreter", {"data": query}),
        ("https://overpass.private.coffee/api/interpreter", {"data": query}),
    )
    for endpoint, params in providers:
        try:
            response = requests.get(endpoint, params=params, timeout=30,
                                    headers={"User-Agent": "HanoiCourseworkChase/1.0"})
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
            for element in list(root):
                tags = {t.attrib["k"]: t.attrib["v"] for t in element.findall("tag")}
                if element.tag == "relation" or (element.tag == "way" and (
                    not tags.get("highway") or tags.get("highway") in
                    {"motorway", "motorway_link", "trunk", "trunk_link", "construction", "proposed"}
                    or tags.get("foot") == "no" or tags.get("access") in {"no", "private"})):
                    root.remove(element)
            with TemporaryDirectory() as directory:
                xml_path = Path(directory) / "streets.osm"
                ElementTree.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)
                graph = ox.graph_from_xml(xml_path, bidirectional=True, simplify=True,
                                          retain_all=False)
            graph = split_long_edges(graph)
            if len(graph) > 600:
                center_x, center_y = 105.850, 21.035
                selected = sorted(graph, key=lambda n: (graph.nodes[n]["x"] - center_x) ** 2
                                  + (graph.nodes[n]["y"] - center_y) ** 2)[:600]
                graph = graph.subgraph(selected).copy()
            component = max(nx.strongly_connected_components(graph), key=len)
            graph = graph.subgraph(component).copy()
            graph.graph.update(source="OpenStreetMap / Overpass — khu phố cổ Hà Nội",
                               retrieved_utc=datetime.now(timezone.utc).isoformat(),
                               attribution="© OpenStreetMap contributors, ODbL 1.0",
                               query_bbox="105.847,21.032,105.853,21.038; capped at 600 nodes",
                               movement_model="Walking simulation; bidirectional; endpoint capture")
            arena = Arena(graph)
            MAP_PATH.parent.mkdir(exist_ok=True)
            temporary = MAP_PATH.with_suffix(".tmp.graphml")
            ox.save_graphml(arena.graph, temporary)
            temporary.replace(MAP_PATH)
            print(f"Saved {MAP_PATH}: {len(graph)} nodes / {graph.number_of_edges()} edges")
            return
        except (requests.RequestException, ValueError, ElementTree.ParseError, nx.NetworkXException) as exc:
            failures.append(f"{endpoint}: {exc}")
    raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
