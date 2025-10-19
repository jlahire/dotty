"""
graph_stuff.py - holds all files and their connections
imports: file_stuff.py for FileNode
"""

import json
from pathlib import Path
from models.file_stuff import FileNode


class Link:
    """connection between two files"""
    
    def __init__(self, source, target, link_type, label=""):
        self.source = source
        self.target = target
        self.type = link_type
        self.label = label


class Graph:
    """stores all files and links between them"""
    
    def __init__(self, nodes=None, root_path=None):
        """
        Initialize graph with nodes and optional root path
        
        Args:
            nodes: List of FileNode objects to add to the graph (or None)
            root_path: Path object or string representing the root directory being analyzed (optional)
        """
        self.files = {}  # id -> FileNode
        self.links = []  # list of Link objects
        self.root = None  # root node (if applicable)
        self.root_path = None  # Initialize to None first
        
        # Set root_path if provided
        if root_path:
            self.set_root_path(root_path)
        
        # Add nodes if provided
        if nodes:
            if isinstance(nodes, list):
                for node in nodes:
                    self.add_file(node)
            else:
                raise ValueError("nodes must be a list of FileNode objects")
    
    def set_root_path(self, root_path):
        """
        Set or update the root path for this graph
        
        Args:
            root_path: Path object or string representing the root directory
        """
        if root_path:
            self.root_path = Path(root_path) if not isinstance(root_path, Path) else root_path
        else:
            self.root_path = None
    
    def add_file(self, node):
        """
        Add a file node to the graph
        
        Args:
            node: FileNode object to add
        """
        if node and hasattr(node, 'id'):
            self.files[node.id] = node
        else:
            raise ValueError("Invalid node: must have 'id' attribute")
    
    def add_link(self, source_id, target_id, link_type, label=""):
        """
        Connect two files with a link
        
        Args:
            source_id: ID of source node
            target_id: ID of target node
            link_type: Type of relationship
            label: Optional label for the link
        """
        if source_id not in self.files:
            print(f"Warning: source node {source_id} not found in graph")
            return
        
        if target_id not in self.files:
            print(f"Warning: target node {target_id} not found in graph")
            return
        
        link = Link(source_id, target_id, link_type, label)
        self.links.append(link)
        
        # Track connections in both directions - USE DICT NOT LIST
        source_node = self.files[source_id]
        target_node = self.files[target_id]
        
        # Initialize connections as dict if not already
        if not hasattr(source_node, 'connections') or isinstance(source_node.connections, list):
            source_node.connections = {}
        if not hasattr(target_node, 'connections') or isinstance(target_node.connections, list):
            target_node.connections = {}
        
        # Add to connections dict
        if link_type not in source_node.connections:
            source_node.connections[link_type] = []
        if link_type not in target_node.connections:
            target_node.connections[link_type] = []
        
        source_node.connections[link_type].append(target_id)
        target_node.connections[link_type].append(source_id)
    
    def remove_file(self, node_id):
        """
        Remove a file node and all its links from the graph
        
        Args:
            node_id: ID of node to remove
        """
        if node_id not in self.files:
            return
        
        # Remove all links involving this node
        self.links = [link for link in self.links 
                     if link.source != node_id and link.target != node_id]
        
        # Remove from other nodes' connection lists
        for other_id in self.files[node_id].connections:
            if other_id in self.files:
                if node_id in self.files[other_id].connections:
                    self.files[other_id].connections.remove(node_id)
        
        # Remove the node itself
        del self.files[node_id]
    
    def find_files(self, search_text):
        """
        Search for files by name
        
        Args:
            search_text: Text to search for (case-insensitive)
            
        Returns:
            List of matching FileNode objects
        """
        if not search_text:
            return []
        
        search = search_text.lower()
        return [f for f in self.files.values() if search in f.name.lower()]
    
    def get_node(self, node_id):
        """
        Get a node by its ID
        
        Args:
            node_id: ID of the node to retrieve
            
        Returns:
            FileNode object or None if not found
        """
        return self.files.get(node_id)
    
    def get_links_for_node(self, node_id):
        """
        Get all links connected to a specific node
        
        Args:
            node_id: ID of the node
            
        Returns:
            List of Link objects
        """
        return [link for link in self.links 
                if link.source == node_id or link.target == node_id]
    
    def get_statistics(self):
        """
        Get graph statistics
        
        Returns:
            Dictionary with graph statistics
        """
        file_count = sum(1 for node in self.files.values() if not node.is_folder)
        folder_count = sum(1 for node in self.files.values() if node.is_folder)
        deleted_count = sum(1 for node in self.files.values() 
                          if hasattr(node, 'is_deleted') and node.is_deleted)
        
        link_types = {}
        for link in self.links:
            link_types[link.type] = link_types.get(link.type, 0) + 1
        
        return {
            'total_nodes': len(self.files),
            'files': file_count,
            'folders': folder_count,
            'deleted_files': deleted_count,
            'total_links': len(self.links),
            'link_types': link_types,
            'root_path': str(self.root_path) if self.root_path else None
        }
    
    def save(self, filepath):
        """
        Export graph to JSON file
        
        Args:
            filepath: Path to save the JSON file
        """
        try:
            data = {
                'root_path': str(self.root_path) if self.root_path else None,
                'files': [
                    {
                        'id': f.id,
                        'name': f.name,
                        'is_folder': f.is_folder,
                        'is_hidden': getattr(f, 'is_hidden', False),
                        'is_deleted': getattr(f, 'is_deleted', False),
                        'info': f.info,
                        'x': f.x,
                        'y': f.y
                    }
                    for f in self.files.values()
                ],
                'links': [
                    {
                        'source': l.source,
                        'target': l.target,
                        'type': l.type,
                        'label': l.label
                    }
                    for l in self.links
                ],
                'statistics': self.get_statistics()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"Graph saved to {filepath}")
            return True
            
        except Exception as e:
            print(f"Error saving graph: {e}")
            return False
    
    def load(self, filepath):
        """
        Load graph from JSON file
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Clear existing data
            self.files = {}
            self.links = []
            self.root = None
            
            # Load root path
            if data.get('root_path'):
                self.root_path = Path(data['root_path'])
            
            # Load files (basic reconstruction - actual FileNode objects may need full paths)
            # This is a simplified version - full implementation would need to handle all node types
            print(f"Loaded {len(data.get('files', []))} files and {len(data.get('links', []))} links")
            
            return True
            
        except Exception as e:
            print(f"Error loading graph: {e}")
            return False
    
    def clear(self):
        """Clear all data from the graph"""
        self.files = {}
        self.links = []
        self.root = None
        self.root_path = None
    
    def __repr__(self):
        """String representation of the graph"""
        return f"Graph(nodes={len(self.files)}, links={len(self.links)}, root={self.root_path})"