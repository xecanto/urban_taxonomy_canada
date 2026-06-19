import geopandas as gpd
import momepy

roads = gpd.read_file('../data/roads.gpkg')
graph = momepy.gdf_to_nx(roads)

import networkx as nx
import matplotlib.pyplot as plt

pos = {node: node for node in graph.nodes()}

plt.figure(figsize=(100, 100))
nx.draw(
    graph,
    pos=pos,
    node_size=1,
    width=0.5,
    with_labels=False
)
plt.savefig("road_network.png", dpi=300)
plt.show()