"""
git_analyzer.py - analyze git repositories
uses git commands to find deleted files and history
"""

import subprocess
from pathlib import Path
from datetime import datetime


class GitAnalyzer:
    """analyzes git repositories for deleted files and history"""
    
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path)
        self.is_git_repo = self.check_git_repo()
        self.deleted_files = {}
        self.file_history = {}
    
    def check_git_repo(self):
        """check if directory is a git repository"""
        git_dir = self.repo_path / '.git'
        return git_dir.exists() and git_dir.is_dir()
    
    def analyze(self):
        """run full git analysis"""
        if not self.is_git_repo:
            print("not a git repository")
            return
        
        print("analyzing git repository...")
        self.find_deleted_files()
        self.get_file_history()
        print(f"found {len(self.deleted_files)} deleted files")
    
    def find_deleted_files(self):
        """find all deleted files in git history"""
        try:
            # -@jlahire
            # git log with deleted files
            cmd = [
                'git', '-C', str(self.repo_path),
                'log', '--diff-filter=D', '--summary',
                '--pretty=format:%H|%aI|%an|%s'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return
            
            # FIX: Use actual newline instead of escaped string
            lines = result.stdout.split('\n')
            current_commit = None
            current_date = None
            current_author = None
            current_message = None
            
            for line in lines:
                line = line.strip()
                
                # parse commit info
                if '|' in line and not line.startswith('delete'):
                    parts = line.split('|')
                    if len(parts) >= 4:
                        current_commit = parts[0]
                        current_date = parts[1]
                        current_author = parts[2]
                        current_message = parts[3]
                
                # parse deleted file
                elif line.startswith('delete mode'):
                    # format: "delete mode 100644 path/to/file.txt"
                    parts = line.split()
                    if len(parts) >= 4:
                        file_path = ' '.join(parts[3:])
                        
                        if file_path not in self.deleted_files:
                            self.deleted_files[file_path] = {
                                'path': file_path,
                                'deleted_commit': current_commit,
                                'deleted_date': current_date,
                                'deleted_by': current_author,
                                'commit_message': current_message,
                                'name': Path(file_path).name
                            }
        
        except subprocess.TimeoutExpired:
            print("git command timeout")
        except Exception as e:
            print(f"error finding deleted files: {e}")
    
    def get_file_history(self):
        """get git history for existing files"""
        try:
            # get all tracked files
            cmd = ['git', '-C', str(self.repo_path), 'ls-files']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return
            
            # FIX: Use actual newline instead of escaped string
            tracked_files = result.stdout.strip().split('\n')
            
            # -@jlahire
            # get history for each file (limit to avoid slowdown)
            for file_path in tracked_files[:100]:  # limit to first 100 files
                if not file_path:
                    continue
                
                self.file_history[file_path] = self.get_single_file_history(file_path)
        
        except Exception as e:
            print(f"error getting file history: {e}")
    
    def get_single_file_history(self, file_path):
        """get git history for a single file"""
        try:
            cmd = [
                'git', '-C', str(self.repo_path),
                'log', '--follow', '--pretty=format:%H|%aI|%an|%s',
                '--', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                return []
            
            history = []
            # FIX: Use actual newline instead of escaped string
            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                
                parts = line.split('|')
                if len(parts) >= 4:
                    history.append({
                        'commit': parts[0],
                        'date': parts[1],
                        'author': parts[2],
                        'message': parts[3]
                    })
            
            return history
        
        except Exception as e:
            return []
    
    def get_file_git_info(self, file_path):
        """get git info for a specific file"""
        # check if file is deleted
        if file_path in self.deleted_files:
            return self.deleted_files[file_path]
        
        # check if file has history
        if file_path in self.file_history:
            history = self.file_history[file_path]
            if history:
                return {
                    'tracked': True,
                    'commits': len(history),
                    'last_commit': history[0] if history else None,
                    'first_commit': history[-1] if history else None,
                    'history': history[:5]  # last 5 commits
                }
        
        return None
    
    def get_timeline_data(self, interval='day'):
        """get git commit activity timeline for heatmap"""
        from collections import defaultdict
        
        timeline = defaultdict(lambda: {'commits': 0, 'authors': set(), 'files': set()})
        
        # Process file history commits
        for file_path, history in self.file_history.items():
            for commit in history:
                try:
                    timestamp = datetime.fromisoformat(commit['date'])
                    
                    if interval == 'hour':
                        key = timestamp.strftime('%Y-%m-%d %H:00')
                    elif interval == 'day':
                        key = timestamp.strftime('%Y-%m-%d')
                    elif interval == 'week':
                        key = timestamp.strftime('%Y-W%W')
                    elif interval == 'month':
                        key = timestamp.strftime('%Y-%m')
                    
                    timeline[key]['commits'] += 1
                    timeline[key]['authors'].add(commit['author'])
                    timeline[key]['files'].add(file_path)
                except:
                    pass
        
        # Process deleted files
        for file_path, git_info in self.deleted_files.items():
            try:
                timestamp = datetime.fromisoformat(git_info['deleted_date'])
                
                if interval == 'hour':
                    key = timestamp.strftime('%Y-%m-%d %H:00')
                elif interval == 'day':
                    key = timestamp.strftime('%Y-%m-%d')
                elif interval == 'week':
                    key = timestamp.strftime('%Y-W%W')
                elif interval == 'month':
                    key = timestamp.strftime('%Y-%m')
                
                timeline[key]['commits'] += 1
                timeline[key]['authors'].add(git_info['deleted_by'])
                timeline[key]['files'].add(file_path)
            except:
                pass
        
        # Convert to simpler format for heatmap (just commit counts)
        result = {}
        for key, data in timeline.items():
            result[key] = data['commits']
        
        return dict(sorted(result.items()))
    
    def get_commit_statistics(self):
        """get overall git statistics"""
        all_commits = []
        authors = set()
        
        # Collect all commits from file history
        for history in self.file_history.values():
            for commit in history:
                all_commits.append(commit)
                authors.add(commit['author'])
        
        # Add deleted file commits
        for git_info in self.deleted_files.values():
            authors.add(git_info['deleted_by'])
        
        # Count commits by author
        from collections import defaultdict
        author_commits = defaultdict(int)
        
        for commit in all_commits:
            author_commits[commit['author']] += 1
        
        return {
            'total_commits': len(all_commits),
            'total_authors': len(authors),
            'total_tracked_files': len(self.file_history),
            'total_deleted_files': len(self.deleted_files),
            'top_authors': sorted(author_commits.items(), key=lambda x: x[1], reverse=True)[:10]
        }