"""
layout.py - calculates where to put each node on screen
REFACTORED: Zettelkasten-focused layout with focus mode
- Focus node centered
- 1-hop neighbors in inner ring
- 2-hop neighbors in outer ring
- Cluster by folder and user
"""

import math
import random
from collections import defaultdict


def calculate_positions(graph, width=1600, height=900, focus_node_id=None):
    """
    Main entry point - calculates Zettelkasten-style layout
    
    Args:
        graph: Graph object with files and links
        width: Canvas width
        height: Canvas height
        focus_node_id: Node to center on (auto-select if None)
    """
    if not graph.files:
        return
    
    print("calculating zettelkasten layout...")
    
    # Auto-select focus node if not provided
    if not focus_node_id or focus_node_id not in graph.files:
        focus_node_id = auto_select_focus_node(graph)
    
    # Calculate using zettelkasten layout
    calculate_zettelkasten_layout(graph, focus_node_id, width, height)
    
    print("layout done")


def auto_select_focus_node(graph):
    """
    Auto-select the most interesting node as focus
    
    Priority:
    1. Most connected non-system file
    2. Most recently modified user file
    3. Root folder
    4. First node
    """
    if not graph.files:
        return None
    
    # Find most connected user file
    connection_counts = {}
    for node_id in graph.files.keys():
        count = len([l for l in graph.links if l.source == node_id or l.target == node_id])
        connection_counts[node_id] = count
    
    # Filter to user files only
    user_nodes = [
        node_id for node_id, node in graph.files.items()
        if not node.info.get('is_system_file', False) and not node.is_folder
    ]
    
    if user_nodes:
        # Pick most connected user file
        return max(user_nodes, key=lambda nid: connection_counts.get(nid, 0))
    
    # Fallback: most connected node overall
    if connection_counts:
        return max(connection_counts.keys(), key=lambda nid: connection_counts[nid])
    
    # Last resort: first node
    return list(graph.files.keys())[0]


def calculate_zettelkasten_layout(graph, focus_node_id, width, height):
    """
    Zettelkasten-style radial layout
    - Focus node in center
    - 1-hop neighbors in inner ring (clustered by folder/user)
    - 2-hop neighbors in outer ring (clustered by folder/user)
    - Additional nodes in far ring
    """
    center_x, center_y = width // 2, height // 2
    
    # Find all nodes by hop distance from focus
    node_layers = get_node_layers(graph, focus_node_id, max_hops=3)
    
    # Position focus node at center
    focus_node = graph.files[focus_node_id]
    focus_node.x = center_x
    focus_node.y = center_y
    
    # Define ring radii
    inner_radius = 250
    middle_radius = 500
    outer_radius = 750
    
    # Position 1-hop neighbors in inner ring (clustered)
    if 1 in node_layers and node_layers[1]:
        position_nodes_clustered(
            graph, node_layers[1], center_x, center_y, inner_radius
        )
    
    # Position 2-hop neighbors in middle ring (clustered)
    if 2 in node_layers and node_layers[2]:
        position_nodes_clustered(
            graph, node_layers[2], center_x, center_y, middle_radius
        )
    
    # Position 3-hop and beyond in outer ring
    if 3 in node_layers and node_layers[3]:
        position_nodes_clustered(
            graph, node_layers[3], center_x, center_y, outer_radius
        )


def get_node_layers(graph, start_id, max_hops=3):
    """
    BFS to find nodes by hop distance from start node
    
    Returns:
        dict: {hop_distance: [node_ids]}
    """
    layers = {0: [start_id]}
    visited = {start_id}
    current_layer = [start_id]
    
    for hop in range(1, max_hops + 1):
        next_layer = []
        
        for node_id in current_layer:
            # Find all neighbors
            for link in graph.links:
                neighbor = None
                
                if link.source == node_id and link.target not in visited:
                    neighbor = link.target
                elif link.target == node_id and link.source not in visited:
                    neighbor = link.source
                
                if neighbor and neighbor in graph.files:
                    next_layer.append(neighbor)
                    visited.add(neighbor)
        
        if next_layer:
            layers[hop] = next_layer
            current_layer = next_layer
        else:
            break
    
    return layers


def position_nodes_clustered(graph, node_ids, cx, cy, radius):
    """
    Position nodes around a circle, clustered by folder and user
    
    Args:
        graph: Graph object
        node_ids: List of node IDs to position
        cx, cy: Center coordinates
        radius: Distance from center
    """
    if not node_ids:
        return
    
    # Group nodes by folder and user
    clusters = defaultdict(list)
    
    for node_id in node_ids:
        node = graph.files.get(node_id)
        if not node:
            continue
        
        # Create cluster key from folder path and owner
        folder_path = str(node.path.parent) if hasattr(node.path, 'parent') else 'root'
        owner = node.info.get('owner_name', 'unknown')
        is_system = node.info.get('is_system_file', False)
        
        cluster_key = f"{folder_path}_{owner}_{'sys' if is_system else 'user'}"
        clusters[cluster_key].append(node_id)
    
    # Calculate positions for each cluster
    cluster_keys = list(clusters.keys())
    num_clusters = len(cluster_keys)
    
    if num_clusters == 0:
        return
    
    # Each cluster gets a slice of the circle
    angle_per_cluster = (2 * math.pi) / num_clusters
    
    for cluster_idx, cluster_key in enumerate(cluster_keys):
        cluster_nodes = clusters[cluster_key]
        
        # Base angle for this cluster
        base_angle = cluster_idx * angle_per_cluster
        
        # Spread nodes within cluster
        if len(cluster_nodes) == 1:
            # Single node - place at cluster center
            angle = base_angle
            node = graph.files[cluster_nodes[0]]
            node.x = cx + radius * math.cos(angle)
            node.y = cy + radius * math.sin(angle)
        else:
            # Multiple nodes - spread them in an arc
            arc_size = angle_per_cluster * 0.8  # Leave some gap between clusters
            
            for i, node_id in enumerate(cluster_nodes):
                # Distribute within the arc
                t = i / max(len(cluster_nodes) - 1, 1)
                angle = base_angle - arc_size/2 + t * arc_size
                
                # Add slight radial variation for visual separation
                node_radius = radius + random.uniform(-30, 30)
                
                node = graph.files[node_id]
                node.x = cx + node_radius * math.cos(angle)
                node.y = cy + node_radius * math.sin(angle)


def position_nodes_in_ring(graph, node_ids, cx, cy, radius):
    """
    Position nodes evenly around a circle (simple version)
    
    Args:
        graph: Graph object
        node_ids: List of node IDs to position
        cx, cy: Center coordinates
        radius: Distance from center
    """
    if not node_ids:
        return
    
    angle_step = (2 * math.pi) / len(node_ids)
    
    for i, node_id in enumerate(node_ids):
        angle = i * angle_step
        node = graph.files.get(node_id)
        if node:
            node.x = cx + radius * math.cos(angle)
            node.y = cy + radius * math.sin(angle)


# ============================================================================
# Legacy force-directed layout (kept for compatibility)
# ============================================================================

def calculate_force_directed_layout(graph, width=800, height=600):
    """
    Original force-directed layout (creates spaghetti)
    Kept for backward compatibility but not recommended
    """
    if not graph.files:
        return
    
    print("calculating force-directed layout...")
    
    # Start with random positions
    for node in graph.files.values():
        node.x = random.uniform(100, width - 100)
        node.y = random.uniform(100, height - 100)
    
    # Physics simulation
    iterations = 200
    for step in range(iterations):
        
        # Repel all nodes from each other
        for node1 in graph.files.values():
            fx, fy = 0, 0
            
            for node2 in graph.files.values():
                if node1.id != node2.id:
                    dx = node1.x - node2.x
                    dy = node1.y - node2.y
                    dist = math.sqrt(dx*dx + dy*dy) or 1
                    
                    # Repulsion force
                    force = 15000 / (dist * dist)
                    fx += (dx / dist) * force
                    fy += (dy / dist) * force
            
            node1.fx = fx
            node1.fy = fy
        
        # Attract connected nodes
        for link in graph.links:
            src = graph.files.get(link.source)
            tgt = graph.files.get(link.target)
            
            if src and tgt:
                dx = tgt.x - src.x
                dy = tgt.y - src.y
                dist = math.sqrt(dx*dx + dy*dy) or 1
                
                # Attraction force
                if link.type == 'parent_folder':
                    force = dist * 0.003
                elif link.type == 'same_folder':
                    force = dist * 0.005
                else:
                    force = dist * 0.008
                    
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                
                src.fx += fx
                src.fy += fy
                tgt.fx -= fx
                tgt.fy -= fy
        
        # Move nodes
        for node in graph.files.values():
            node.x += node.fx * 0.05
            node.y += node.fy * 0.05
            
            # Keep in bounds
            node.x = max(50, min(width - 50, node.x))
            node.y = max(50, min(height - 50, node.y))
    
    print("layout done")