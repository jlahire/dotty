"""
linker.py - figures out how files relate to each other
imports: graph_stuff.py for Graph
"""
from collections import defaultdict
from pathlib import Path


def link_to_parent_folder(graph):
    """connect files to their parent directories"""
    # find all directories
    directories = {node.id: node for node in graph.files.values() if node.is_folder}
    
    # -@jlahire
    # link each file to its parent directory
    for node in graph.files.values():
        if not node.is_folder:
            parent_path = node.path.parent
            # find the directory node
            for dir_id, dir_node in directories.items():
                if dir_node.path == parent_path:
                    graph.add_link(node.id, dir_id, 'parent_folder', dir_node.name)
                    break


def link_by_extension(graph):
    """connect files with same extension"""
    by_ext = defaultdict(list)
    
    # group files by extension
    for file_id, node in graph.files.items():
        if not node.is_folder:
            ext = node.info.get('extension', '')
            if ext:
                by_ext[ext].append(file_id)
    
    # -@jlahire
    # connect files in same group
    for ext, file_ids in by_ext.items():
        if len(file_ids) > 1:
            for i in range(len(file_ids)):
                for j in range(i + 1, len(file_ids)):
                    graph.add_link(file_ids[i], file_ids[j], 'same_ext', ext)


def link_by_folder(graph):
    """connect files in same folder"""
    by_folder = defaultdict(list)
    
    for file_id, node in graph.files.items():
        if not node.is_folder:
            folder = str(node.path.parent)
            by_folder[folder].append(file_id)
    
    for folder, file_ids in by_folder.items():
        if len(file_ids) > 1:
            folder_name = Path(folder).name
            for i in range(len(file_ids)):
                for j in range(i + 1, len(file_ids)):
                    graph.add_link(file_ids[i], file_ids[j], 'same_folder', folder_name)


def link_by_date(graph):
    """connect files modified on same day"""
    by_date = defaultdict(list)
    
    for file_id, node in graph.files.items():
        if not node.is_folder:
            date = node.info.get('modified', '')[:10]  # just the date part
            if date:
                by_date[date].append(file_id)
    
    # -@jlahire
    for date, file_ids in by_date.items():
        if len(file_ids) > 1:
            for i in range(len(file_ids)):
                for j in range(i + 1, len(file_ids)):
                    graph.add_link(file_ids[i], file_ids[j], 'same_date', date)


def create_all_links(graph):
    """run all linking functions"""
    print("creating links...")
    link_to_parent_folder(graph)
    link_by_extension(graph)
    link_by_folder(graph)
    link_by_date(graph)
    print(f"created {len(graph.links)} links")
