"""
browser_analyzer.py - analyzes browser history from multiple browsers
supports Chrome, Firefox, Edge, Safari, Brave, Opera
extracts: history, downloads, bookmarks, cookies, cache
"""

import sqlite3
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
from collections import defaultdict

# Try to import additional parsing libraries
try:
    import lz4.block
    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False
    print("⚠ lz4 not available - Firefox session restore limited")


class BrowserAnalyzer:
    """analyzes browser artifacts from various browsers"""
    
    # Browser profile locations (relative to user home or AppData)
    BROWSER_PATHS = {
        'chrome': {
            'windows': 'AppData/Local/Google/Chrome/User Data',
            'linux': '.config/google-chrome',
            'darwin': 'Library/Application Support/Google/Chrome'
        },
        'firefox': {
            'windows': 'AppData/Roaming/Mozilla/Firefox/Profiles',
            'linux': '.mozilla/firefox',
            'darwin': 'Library/Application Support/Firefox/Profiles'
        },
        'edge': {
            'windows': 'AppData/Local/Microsoft/Edge/User Data',
            'linux': '.config/microsoft-edge',
            'darwin': 'Library/Application Support/Microsoft Edge'
        },
        'brave': {
            'windows': 'AppData/Local/BraveSoftware/Brave-Browser/User Data',
            'linux': '.config/BraveSoftware/Brave-Browser',
            'darwin': 'Library/Application Support/BraveSoftware/Brave-Browser'
        },
        'safari': {
            'darwin': 'Library/Safari'
        },
        'opera': {
            'windows': 'AppData/Roaming/Opera Software/Opera Stable',
            'linux': '.config/opera',
            'darwin': 'Library/Application Support/com.operasoftware.Opera'
        }
    }
    
    def __init__(self, base_path=None, os_type='windows'):
        """
        base_path: root path to analyze (drive image, user folder, etc.)
        os_type: 'windows', 'linux', or 'darwin'
        """
        self.base_path = Path(base_path) if base_path else Path.home()
        self.os_type = os_type.lower()
        self.detected_browsers = {}
        self.history_entries = []
        self.download_entries = []
        self.bookmark_entries = []
        self.cookie_entries = []
        self.search_history = []
        
    def detect_browsers(self):
        """detect installed browsers and their data locations"""
        print("Detecting browsers...")
        
        for browser_name, paths in self.BROWSER_PATHS.items():
            if self.os_type not in paths:
                continue
            
            browser_path = self.base_path / paths[self.os_type]
            
            if browser_path.exists():
                self.detected_browsers[browser_name] = {
                    'path': browser_path,
                    'profiles': self._find_profiles(browser_path, browser_name)
                }
                print(f"✓ Found {browser_name}: {len(self.detected_browsers[browser_name]['profiles'])} profile(s)")
        
        return self.detected_browsers
    
    def _find_profiles(self, browser_path, browser_name):
        """find all profiles for a browser"""
        profiles = []
        
        if browser_name == 'firefox':
            # Firefox uses profiles.ini
            if (browser_path / 'profiles.ini').exists():
                try:
                    with open(browser_path / 'profiles.ini', 'r') as f:
                        content = f.read()
                        # Parse profiles.ini for profile directories
                        for line in content.split('\n'):
                            if line.startswith('Path='):
                                profile_dir = line.split('=')[1].strip()
                                profile_path = browser_path / profile_dir
                                if profile_path.exists():
                                    profiles.append(profile_path)
                except:
                    pass
            
            # Also check for *.default* directories
            for item in browser_path.glob('*.default*'):
                if item.is_dir() and item not in profiles:
                    profiles.append(item)
        
        elif browser_name == 'safari':
            # Safari stores everything in main directory
            profiles.append(browser_path)
        
        else:
            # Chrome-based browsers use Default, Profile 1, Profile 2, etc.
            for profile_name in ['Default', 'Profile 1', 'Profile 2', 'Profile 3']:
                profile_path = browser_path / profile_name
                if profile_path.exists():
                    profiles.append(profile_path)
        
        return profiles
    
    def analyze_all(self, progress_callback=None):
        """analyze all detected browsers"""
        if not self.detected_browsers:
            self.detect_browsers()
        
        total_browsers = sum(len(info['profiles']) for info in self.detected_browsers.values())
        current = 0
        
        for browser_name, browser_info in self.detected_browsers.items():
            print(f"\nAnalyzing {browser_name}...")
            
            for profile_path in browser_info['profiles']:
                if progress_callback:
                    progress_callback(
                        int((current / total_browsers) * 100),
                        f"Analyzing {browser_name}: {profile_path.name}"
                    )
                
                if browser_name == 'firefox':
                    self._analyze_firefox_profile(profile_path, browser_name)
                elif browser_name == 'safari':
                    self._analyze_safari(profile_path, browser_name)
                else:
                    self._analyze_chromium_profile(profile_path, browser_name)
                
                current += 1
        
        # Extract search queries from URLs
        self._extract_search_queries()
        
        print(f"\n✓ Analysis complete:")
        print(f"  History: {len(self.history_entries)} entries")
        print(f"  Downloads: {len(self.download_entries)} entries")
        print(f"  Bookmarks: {len(self.bookmark_entries)} entries")
        print(f"  Cookies: {len(self.cookie_entries)} entries")
        print(f"  Searches: {len(self.search_history)} queries")
    
    def _analyze_chromium_profile(self, profile_path, browser_name):
        """analyze Chrome/Edge/Brave profile"""
        # History database
        history_db = profile_path / 'History'
        if history_db.exists():
            self._parse_chromium_history(history_db, browser_name, profile_path.name)
        
        # Bookmarks
        bookmarks_file = profile_path / 'Bookmarks'
        if bookmarks_file.exists():
            self._parse_chromium_bookmarks(bookmarks_file, browser_name, profile_path.name)
        
        # Cookies
        cookies_db = profile_path / 'Cookies'
        if cookies_db.exists():
            self._parse_chromium_cookies(cookies_db, browser_name, profile_path.name)
    
    def _parse_chromium_history(self, db_path, browser_name, profile_name):
        """parse Chromium history database"""
        try:
            # Copy database to temp location (may be locked)
            temp_db = self._copy_to_temp(db_path)
            
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            # URLs and visits
            cursor.execute("""
                SELECT 
                    urls.id,
                    urls.url,
                    urls.title,
                    urls.visit_count,
                    urls.typed_count,
                    urls.last_visit_time,
                    visits.visit_time,
                    visits.from_visit
                FROM urls
                LEFT JOIN visits ON urls.id = visits.url
                ORDER BY visits.visit_time DESC
            """)
            
            for row in cursor.fetchall():
                url_id, url, title, visit_count, typed_count, last_visit, visit_time, from_visit = row
                
                # Convert Chrome timestamp (microseconds since 1601-01-01)
                if visit_time:
                    timestamp = self._chrome_time_to_datetime(visit_time)
                else:
                    timestamp = None
                
                self.history_entries.append({
                    'browser': browser_name,
                    'profile': profile_name,
                    'url': url,
                    'title': title or 'Untitled',
                    'visit_count': visit_count,
                    'typed_count': typed_count,
                    'visit_time': timestamp,
                    'from_visit': from_visit,
                    'type': 'history'
                })
            
            # Downloads
            cursor.execute("""
                SELECT 
                    target_path,
                    tab_url,
                    tab_referrer_url,
                    start_time,
                    end_time,
                    total_bytes,
                    received_bytes,
                    state,
                    danger_type
                FROM downloads
                ORDER BY start_time DESC
            """)
            
            for row in cursor.fetchall():
                target, url, referrer, start, end, total_bytes, received, state, danger = row
                
                self.download_entries.append({
                    'browser': browser_name,
                    'profile': profile_name,
                    'target_path': target,
                    'url': url,
                    'referrer': referrer,
                    'start_time': self._chrome_time_to_datetime(start) if start else None,
                    'end_time': self._chrome_time_to_datetime(end) if end else None,
                    'total_bytes': total_bytes,
                    'received_bytes': received,
                    'state': state,
                    'danger': danger,
                    'type': 'download'
                })
            
            conn.close()
            
        except Exception as e:
            print(f"  Error parsing {browser_name} history: {e}")
    
    def _parse_chromium_bookmarks(self, bookmarks_file, browser_name, profile_name):
        """parse Chromium bookmarks JSON"""
        try:
            with open(bookmarks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            def extract_bookmarks(node, folder_path=""):
                if node.get('type') == 'url':
                    self.bookmark_entries.append({
                        'browser': browser_name,
                        'profile': profile_name,
                        'url': node.get('url', ''),
                        'title': node.get('name', 'Untitled'),
                        'date_added': self._chrome_time_to_datetime(int(node.get('date_added', 0))),
                        'folder': folder_path,
                        'type': 'bookmark'
                    })
                elif node.get('type') == 'folder':
                    folder_name = node.get('name', 'Unnamed')
                    new_path = f"{folder_path}/{folder_name}" if folder_path else folder_name
                    for child in node.get('children', []):
                        extract_bookmarks(child, new_path)
            
            # Process bookmark bar and other folders
            roots = data.get('roots', {})
            for root_name, root_data in roots.items():
                if isinstance(root_data, dict):
                    extract_bookmarks(root_data, root_name)
        
        except Exception as e:
            print(f"  Error parsing {browser_name} bookmarks: {e}")
    
    def _parse_chromium_cookies(self, db_path, browser_name, profile_name):
        """parse Chromium cookies database"""
        try:
            temp_db = self._copy_to_temp(db_path)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    host_key,
                    name,
                    value,
                    path,
                    creation_utc,
                    expires_utc,
                    is_secure,
                    is_httponly,
                    last_access_utc
                FROM cookies
                ORDER BY last_access_utc DESC
                LIMIT 5000
            """)
            
            for row in cursor.fetchall():
                host, name, value, path, created, expires, secure, httponly, last_access = row
                
                self.cookie_entries.append({
                    'browser': browser_name,
                    'profile': profile_name,
                    'host': host,
                    'name': name,
                    'value': value[:100] if value else '',  # Truncate for privacy
                    'path': path,
                    'created': self._chrome_time_to_datetime(created) if created else None,
                    'expires': self._chrome_time_to_datetime(expires) if expires else None,
                    'last_access': self._chrome_time_to_datetime(last_access) if last_access else None,
                    'secure': bool(secure),
                    'httponly': bool(httponly),
                    'type': 'cookie'
                })
            
            conn.close()
            
        except Exception as e:
            print(f"  Error parsing {browser_name} cookies: {e}")
    
    def _analyze_firefox_profile(self, profile_path, browser_name):
        """analyze Firefox profile"""
        # History database (places.sqlite)
        places_db = profile_path / 'places.sqlite'
        if places_db.exists():
            self._parse_firefox_places(places_db, browser_name, profile_path.name)
        
        # Bookmarks are also in places.sqlite
        
        # Cookies
        cookies_db = profile_path / 'cookies.sqlite'
        if cookies_db.exists():
            self._parse_firefox_cookies(cookies_db, browser_name, profile_path.name)
    
    def _parse_firefox_places(self, db_path, browser_name, profile_name):
        """parse Firefox places database"""
        try:
            temp_db = self._copy_to_temp(db_path)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            # History
            cursor.execute("""
                SELECT 
                    moz_places.url,
                    moz_places.title,
                    moz_places.visit_count,
                    moz_places.typed,
                    moz_historyvisits.visit_date,
                    moz_historyvisits.from_visit
                FROM moz_places
                LEFT JOIN moz_historyvisits ON moz_places.id = moz_historyvisits.place_id
                ORDER BY moz_historyvisits.visit_date DESC
            """)
            
            for row in cursor.fetchall():
                url, title, visit_count, typed, visit_date, from_visit = row
                
                # Firefox timestamp is microseconds since Unix epoch
                if visit_date:
                    timestamp = datetime.fromtimestamp(visit_date / 1000000)
                else:
                    timestamp = None
                
                self.history_entries.append({
                    'browser': browser_name,
                    'profile': profile_name,
                    'url': url,
                    'title': title or 'Untitled',
                    'visit_count': visit_count,
                    'typed_count': typed,
                    'visit_time': timestamp,
                    'from_visit': from_visit,
                    'type': 'history'
                })
            
            # Bookmarks
            cursor.execute("""
                SELECT 
                    moz_places.url,
                    moz_bookmarks.title,
                    moz_bookmarks.dateAdded,
                    moz_bookmarks.lastModified,
                    moz_bookmarks.parent
                FROM moz_bookmarks
                JOIN moz_places ON moz_bookmarks.fk = moz_places.id
                WHERE moz_bookmarks.type = 1
                ORDER BY moz_bookmarks.dateAdded DESC
            """)
            
            for row in cursor.fetchall():
                url, title, date_added, last_modified, parent = row
                
                self.bookmark_entries.append({
                    'browser': browser_name,
                    'profile': profile_name,
                    'url': url,
                    'title': title or 'Untitled',
                    'date_added': datetime.fromtimestamp(date_added / 1000000) if date_added else None,
                    'last_modified': datetime.fromtimestamp(last_modified / 1000000) if last_modified else None,
                    'folder': str(parent),
                    'type': 'bookmark'
                })
            
            conn.close()
            
        except Exception as e:
            print(f"  Error parsing Firefox places: {e}")
    
    def _parse_firefox_cookies(self, db_path, browser_name, profile_name):
        """parse Firefox cookies database"""
        try:
            temp_db = self._copy_to_temp(db_path)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    host,
                    name,
                    value,
                    path,
                    creationTime,
                    expiry,
                    isSecure,
                    isHttpOnly,
                    lastAccessed
                FROM moz_cookies
                ORDER BY lastAccessed DESC
                LIMIT 5000
            """)
            
            for row in cursor.fetchall():
                host, name, value, path, created, expires, secure, httponly, last_access = row
                
                self.cookie_entries.append({
                    'browser': browser_name,
                    'profile': profile_name,
                    'host': host,
                    'name': name,
                    'value': value[:100] if value else '',
                    'path': path,
                    'created': datetime.fromtimestamp(created / 1000000) if created else None,
                    'expires': datetime.fromtimestamp(expires) if expires else None,
                    'last_access': datetime.fromtimestamp(last_access / 1000000) if last_access else None,
                    'secure': bool(secure),
                    'httponly': bool(httponly),
                    'type': 'cookie'
                })
            
            conn.close()
            
        except Exception as e:
            print(f"  Error parsing Firefox cookies: {e}")
    
    def _analyze_safari(self, safari_path, browser_name):
        """analyze Safari data (macOS only)"""
        # History.db
        history_db = safari_path / 'History.db'
        if history_db.exists():
            self._parse_safari_history(history_db, browser_name)
        
        # Bookmarks.plist (requires plistlib)
        bookmarks_file = safari_path / 'Bookmarks.plist'
        if bookmarks_file.exists():
            self._parse_safari_bookmarks(bookmarks_file, browser_name)
    
    def _parse_safari_history(self, db_path, browser_name):
        """parse Safari history database"""
        try:
            temp_db = self._copy_to_temp(db_path)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    history_items.url,
                    history_items.visit_count,
                    history_visits.visit_time,
                    history_visits.title
                FROM history_items
                LEFT JOIN history_visits ON history_items.id = history_visits.history_item
                ORDER BY history_visits.visit_time DESC
            """)
            
            for row in cursor.fetchall():
                url, visit_count, visit_time, title = row
                
                # Safari uses Core Data timestamp (seconds since 2001-01-01)
                if visit_time:
                    timestamp = datetime(2001, 1, 1) + timedelta(seconds=visit_time)
                else:
                    timestamp = None
                
                self.history_entries.append({
                    'browser': browser_name,
                    'profile': 'Default',
                    'url': url,
                    'title': title or 'Untitled',
                    'visit_count': visit_count,
                    'visit_time': timestamp,
                    'type': 'history'
                })
            
            conn.close()
            
        except Exception as e:
            print(f"  Error parsing Safari history: {e}")
    
    def _parse_safari_bookmarks(self, bookmarks_file, browser_name):
        """parse Safari bookmarks plist"""
        try:
            import plistlib
            
            with open(bookmarks_file, 'rb') as f:
                data = plistlib.load(f)
            
            def extract_bookmarks(node, folder_path=""):
                if node.get('WebBookmarkType') == 'WebBookmarkTypeLeaf':
                    url_string = node.get('URLString', '')
                    if url_string:
                        self.bookmark_entries.append({
                            'browser': browser_name,
                            'profile': 'Default',
                            'url': url_string,
                            'title': node.get('URIDictionary', {}).get('title', 'Untitled'),
                            'folder': folder_path,
                            'type': 'bookmark'
                        })
                elif node.get('WebBookmarkType') == 'WebBookmarkTypeList':
                    folder_name = node.get('Title', 'Unnamed')
                    new_path = f"{folder_path}/{folder_name}" if folder_path else folder_name
                    for child in node.get('Children', []):
                        extract_bookmarks(child, new_path)
            
            if 'Children' in data:
                for child in data['Children']:
                    extract_bookmarks(child)
        
        except Exception as e:
            print(f"  Error parsing Safari bookmarks: {e}")
    
    def _extract_search_queries(self):
        """extract search queries from URLs"""
        search_engines = {
            'google': ['google.com', 'q='],
            'bing': ['bing.com', 'q='],
            'yahoo': ['yahoo.com', 'p='],
            'duckduckgo': ['duckduckgo.com', 'q='],
            'yandex': ['yandex.com', 'text='],
            'baidu': ['baidu.com', 'wd=']
        }
        
        for entry in self.history_entries:
            url = entry.get('url', '')
            
            for engine_name, (domain, param) in search_engines.items():
                if domain in url and param in url:
                    try:
                        # Extract query parameter
                        query_part = url.split(param)[1].split('&')[0]
                        # URL decode
                        from urllib.parse import unquote_plus
                        query = unquote_plus(query_part)
                        
                        self.search_history.append({
                            'browser': entry['browser'],
                            'profile': entry['profile'],
                            'engine': engine_name,
                            'query': query,
                            'timestamp': entry.get('visit_time'),
                            'url': url,
                            'type': 'search'
                        })
                    except:
                        pass
    
    def _chrome_time_to_datetime(self, chrome_time):
        """convert Chrome timestamp to Python datetime"""
        if not chrome_time:
            return None
        try:
            # Chrome uses microseconds since 1601-01-01
            epoch_start = datetime(1601, 1, 1)
            delta = timedelta(microseconds=chrome_time)
            return epoch_start + delta
        except:
            return None
    
    def _copy_to_temp(self, db_path):
        """copy database to temp location to avoid locks"""
        temp_dir = tempfile.gettempdir()
        temp_path = Path(temp_dir) / f"dotty_browser_{db_path.name}"
        shutil.copy2(db_path, temp_path)
        return temp_path
    
    def get_statistics(self):
        """get overall statistics"""
        return {
            'total_browsers': len(self.detected_browsers),
            'total_history': len(self.history_entries),
            'total_downloads': len(self.download_entries),
            'total_bookmarks': len(self.bookmark_entries),
            'total_cookies': len(self.cookie_entries),
            'total_searches': len(self.search_history),
            'browsers': list(self.detected_browsers.keys())
        }
    
    def get_top_sites(self, limit=50):
        """get most visited sites"""
        site_visits = defaultdict(int)
        
        for entry in self.history_entries:
            url = entry.get('url', '')
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                site_visits[domain] += 1
            except:
                pass
        
        return sorted(site_visits.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    def get_timeline_data(self, interval='hour'):
        """get activity timeline data for heatmap"""
        timeline = defaultdict(int)
        
        for entry in self.history_entries:
            timestamp = entry.get('visit_time')
            if timestamp:
                if interval == 'hour':
                    key = timestamp.strftime('%Y-%m-%d %H:00')
                elif interval == 'day':
                    key = timestamp.strftime('%Y-%m-%d')
                elif interval == 'week':
                    key = timestamp.strftime('%Y-W%W')
                elif interval == 'month':
                    key = timestamp.strftime('%Y-%m')
                
                timeline[key] += 1
        
        return dict(sorted(timeline.items()))
    
    def export_to_json(self, output_path):
        """export all browser data to JSON"""
        data = {
            'analysis_time': datetime.now().isoformat(),
            'statistics': self.get_statistics(),
            'browsers': self.detected_browsers,
            'history': self.history_entries,
            'downloads': self.download_entries,
            'bookmarks': self.bookmark_entries,
            'cookies': self.cookie_entries,
            'searches': self.search_history,
            'top_sites': self.get_top_sites()
        }
        
        # Convert Path objects to strings
        def convert_paths(obj):
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_paths(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_paths(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return obj
        
        data = convert_paths(data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"✓ Exported browser data to {output_path}")