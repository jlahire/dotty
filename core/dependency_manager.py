"""
dependency_manager.py - Centralized dependency checking and management

This module provides a single place to check all dependencies, show their status,
and provide clear installation instructions. Replace scattered dependency checks
throughout the codebase with this centralized system.
"""

import sys
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum


class DependencyCategory(Enum):
    """Categories of dependencies"""
    CORE = "Core (Required for basic functionality)"
    FORENSIC = "Forensic Analysis"
    MEMORY = "Memory Dump Analysis"
    ISO = "ISO Image Analysis"
    BROWSER = "Browser History Analysis"
    EMAIL = "Email Analysis"
    DEVICE = "Device Capture"
    OPTIONAL = "Optional Features"


@dataclass
class Dependency:
    """Represents a single dependency"""
    name: str
    import_name: str
    pip_package: str
    category: DependencyCategory
    description: str
    install_command: str
    alternative: Optional[str] = None
    documentation_url: Optional[str] = None
    
    def check(self) -> bool:
        """Check if dependency is available"""
        try:
            __import__(self.import_name)
            return True
        except ImportError:
            return False
    
    def get_install_instructions(self) -> str:
        """Get formatted installation instructions"""
        instructions = [
            f"Package: {self.name}",
            f"Purpose: {self.description}",
            f"",
            f"Install with:",
            f"  {self.install_command}",
        ]
        
        if self.alternative:
            instructions.extend([
                f"",
                f"Alternative:",
                f"  {self.alternative}"
            ])
        
        if self.documentation_url:
            instructions.extend([
                f"",
                f"Documentation:",
                f"  {self.documentation_url}"
            ])
        
        return "\n".join(instructions)


class DependencyManager:
    """Manages all application dependencies"""
    
    # Define all dependencies
    DEPENDENCIES = [
        # Core dependencies (tkinter is usually bundled with Python)
        Dependency(
            name="Pillow",
            import_name="PIL",
            pip_package="pillow",
            category=DependencyCategory.CORE,
            description="Image processing for file previews",
            install_command="pip install pillow",
            documentation_url="https://pillow.readthedocs.io/"
        ),
        
        # Forensic analysis
        Dependency(
            name="pytsk3",
            import_name="pytsk3",
            pip_package="pytsk3",
            category=DependencyCategory.FORENSIC,
            description="Forensic toolkit for DD/RAW images",
            install_command="pip install pytsk3",
            alternative="On Windows, may require Visual C++ Build Tools",
            documentation_url="https://github.com/py4n6/pytsk"
        ),
        
        Dependency(
            name="dissect.target",
            import_name="dissect.target",
            pip_package="dissect.target",
            category=DependencyCategory.FORENSIC,
            description="E01 forensic image support (pure Python)",
            install_command="pip install dissect.target dissect.evidence",
            documentation_url="https://github.com/fox-it/dissect"
        ),
        
        # Memory analysis
        Dependency(
            name="volatility3",
            import_name="volatility3",
            pip_package="volatility3",
            category=DependencyCategory.MEMORY,
            description="Memory forensics framework",
            install_command="pip install volatility3",
            documentation_url="https://github.com/volatilityfoundation/volatility3"
        ),
        
        # ISO analysis
        Dependency(
            name="pycdlib",
            import_name="pycdlib",
            pip_package="pycdlib",
            category=DependencyCategory.ISO,
            description="ISO 9660 filesystem reading",
            install_command="pip install pycdlib",
            documentation_url="https://clalancette.github.io/pycdlib/"
        ),
        
        # Browser analysis
        Dependency(
            name="lz4",
            import_name="lz4.block",
            pip_package="lz4",
            category=DependencyCategory.BROWSER,
            description="Firefox session restore decompression",
            install_command="pip install lz4",
            documentation_url="https://python-lz4.readthedocs.io/"
        ),
        
        # Email analysis
        Dependency(
            name="pypff",
            import_name="pypff",
            pip_package="pypff",
            category=DependencyCategory.EMAIL,
            description="PST/OST file parsing (Outlook)",
            install_command="pip install pypff",
            alternative="May require compilation. See: https://github.com/libyal/libpff",
            documentation_url="https://github.com/libyal/libpff"
        ),
        
        # Device operations
        Dependency(
            name="psutil",
            import_name="psutil",
            pip_package="psutil",
            category=DependencyCategory.DEVICE,
            description="System and device information",
            install_command="pip install psutil",
            documentation_url="https://psutil.readthedocs.io/"
        ),
        
        Dependency(
            name="paramiko",
            import_name="paramiko",
            pip_package="paramiko",
            category=DependencyCategory.DEVICE,
            description="SSH connection for remote capture",
            install_command="pip install paramiko",
            documentation_url="https://www.paramiko.org/"
        ),
        
        # Optional features
        Dependency(
            name="pdf2image",
            import_name="pdf2image",
            pip_package="pdf2image",
            category=DependencyCategory.OPTIONAL,
            description="PDF preview in file viewer",
            install_command="pip install pdf2image",
            alternative="Also requires poppler-utils system package",
            documentation_url="https://github.com/Belval/pdf2image"
        ),
    ]
    
    def __init__(self):
        self.status = {}
        self._check_all()
    
    def _check_all(self):
        """Check status of all dependencies"""
        for dep in self.DEPENDENCIES:
            self.status[dep.name] = {
                'available': dep.check(),
                'dependency': dep
            }
    
    def is_available(self, name: str) -> bool:
        """Check if a specific dependency is available"""
        return self.status.get(name, {}).get('available', False)
    
    def get_missing_dependencies(self, category: Optional[DependencyCategory] = None) -> List[Dependency]:
        """Get list of missing dependencies, optionally filtered by category"""
        missing = []
        for name, info in self.status.items():
            dep = info['dependency']
            if not info['available']:
                if category is None or dep.category == category:
                    missing.append(dep)
        return missing
    
    def get_available_dependencies(self, category: Optional[DependencyCategory] = None) -> List[Dependency]:
        """Get list of available dependencies, optionally filtered by category"""
        available = []
        for name, info in self.status.items():
            dep = info['dependency']
            if info['available']:
                if category is None or dep.category == category:
                    available.append(dep)
        return available
    
    def get_status_report(self) -> str:
        """Generate a comprehensive status report"""
        lines = []
        lines.append("="*70)
        lines.append("DOTTY DEPENDENCY STATUS REPORT")
        lines.append("="*70)
        lines.append("")
        
        # Group by category
        for category in DependencyCategory:
            deps_in_category = [
                (name, info) for name, info in self.status.items()
                if info['dependency'].category == category
            ]
            
            if not deps_in_category:
                continue
            
            lines.append(f"{category.value}")
            lines.append("-" * 70)
            
            for name, info in deps_in_category:
                dep = info['dependency']
                status = "✓ INSTALLED" if info['available'] else "✗ MISSING"
                lines.append(f"  [{status}] {name}")
                lines.append(f"      {dep.description}")
                
                if not info['available']:
                    lines.append(f"      Install: {dep.install_command}")
                
                lines.append("")
            
            lines.append("")
        
        # Summary
        total = len(self.status)
        available = sum(1 for info in self.status.values() if info['available'])
        missing = total - available
        
        lines.append("="*70)
        lines.append(f"SUMMARY: {available}/{total} dependencies available ({missing} missing)")
        lines.append("="*70)
        
        return "\n".join(lines)
    
    def get_install_script(self, missing_only: bool = True) -> str:
        """Generate a pip install script for missing dependencies"""
        if missing_only:
            deps = self.get_missing_dependencies()
        else:
            deps = [info['dependency'] for info in self.status.values()]
        
        if not deps:
            return "# All dependencies are already installed!"
        
        lines = [
            "#!/bin/bash",
            "# Dotty Dependency Installation Script",
            "# Run this script to install missing dependencies",
            "",
            "echo 'Installing Dotty dependencies...'",
            ""
        ]
        
        for dep in deps:
            lines.append(f"# {dep.name} - {dep.description}")
            lines.append(f"pip install {dep.pip_package}")
            if dep.alternative:
                lines.append(f"# Note: {dep.alternative}")
            lines.append("")
        
        lines.append("echo 'Installation complete!'")
        
        return "\n".join(lines)
    
    def check_feature_requirements(self, feature: str) -> Dict[str, any]:
        """
        Check if all requirements for a specific feature are met
        
        Returns:
            dict with 'available', 'missing', and 'message' keys
        """
        feature_requirements = {
            'forensic': [DependencyCategory.FORENSIC],
            'memory': [DependencyCategory.MEMORY],
            'iso': [DependencyCategory.ISO],
            'browser': [DependencyCategory.BROWSER],
            'email': [DependencyCategory.EMAIL],
            'device': [DependencyCategory.DEVICE],
        }
        
        if feature not in feature_requirements:
            return {
                'available': False,
                'missing': [],
                'message': f"Unknown feature: {feature}"
            }
        
        required_categories = feature_requirements[feature]
        missing = []
        
        for category in required_categories:
            missing.extend(self.get_missing_dependencies(category))
        
        if not missing:
            return {
                'available': True,
                'missing': [],
                'message': f"{feature.capitalize()} analysis is available"
            }
        
        message_lines = [
            f"{feature.capitalize()} analysis requires additional dependencies:",
            ""
        ]
        
        for dep in missing:
            message_lines.append(f"  • {dep.name}")
            message_lines.append(f"    Install: {dep.install_command}")
            message_lines.append("")
        
        return {
            'available': False,
            'missing': missing,
            'message': "\n".join(message_lines)
        }
    
    def install_dependency(self, name: str) -> bool:
        """
        Attempt to install a dependency using pip
        
        Returns:
            True if installation successful, False otherwise
        """
        if name not in self.status:
            print(f"Unknown dependency: {name}")
            return False
        
        dep = self.status[name]['dependency']
        
        print(f"Installing {dep.name}...")
        print(f"Command: pip install {dep.pip_package}")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", dep.pip_package],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                print(f"✓ Successfully installed {dep.name}")
                # Re-check availability
                self.status[name]['available'] = dep.check()
                return True
            else:
                print(f"✗ Failed to install {dep.name}")
                print(f"Error: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"✗ Error installing {dep.name}: {e}")
            return False
    
    def generate_requirements_txt(self, filename: str = "requirements.txt"):
        """Generate a requirements.txt file"""
        with open(filename, 'w') as f:
            f.write("# Dotty Dependencies\n")
            f.write("# Install with: pip install -r requirements.txt\n\n")
            
            for category in DependencyCategory:
                deps = [
                    info['dependency'] for info in self.status.values()
                    if info['dependency'].category == category
                ]
                
                if deps:
                    f.write(f"# {category.value}\n")
                    for dep in deps:
                        f.write(f"{dep.pip_package}\n")
                    f.write("\n")
        
        print(f"Generated {filename}")


# Global instance
_dependency_manager = None

def get_dependency_manager() -> DependencyManager:
    """Get the global dependency manager instance"""
    global _dependency_manager
    if _dependency_manager is None:
        _dependency_manager = DependencyManager()
    return _dependency_manager


# Convenience functions
def is_available(name: str) -> bool:
    """Check if a dependency is available"""
    return get_dependency_manager().is_available(name)


def check_feature(feature: str) -> Dict:
    """Check if a feature's dependencies are met"""
    return get_dependency_manager().check_feature_requirements(feature)


def print_status():
    """Print dependency status report"""
    print(get_dependency_manager().get_status_report())


def generate_install_script(output_file: str = "install_dependencies.sh"):
    """Generate installation script for missing dependencies"""
    script = get_dependency_manager().get_install_script()
    with open(output_file, 'w') as f:
        f.write(script)
    print(f"Generated {output_file}")


# Main execution for testing
if __name__ == '__main__':
    print("Checking Dotty dependencies...\n")
    dm = get_dependency_manager()
    print(dm.get_status_report())
    
    # Generate files
    print("\nGenerating helper files...")
    dm.generate_requirements_txt()
    generate_install_script()
    
    print("\nDone! Check requirements.txt and install_dependencies.sh")