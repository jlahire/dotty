"""
device_capture.py - captures forensic images and RAM from various devices
supports USB connections, network connections, and local execution
"""

import subprocess
import platform
import socket
import os
from pathlib import Path
from datetime import datetime
import json

# Try to import device-specific libraries
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠ psutil not available - limited device detection")

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    print("⚠ paramiko not available - no SSH support")


class DeviceCapture:
    """handles device detection and capture operations"""
    
    DEVICE_TYPES = {
        'windows': 'Windows PC',
        'linux': 'Linux System',
        'darwin': 'macOS',
        'android': 'Android Device',
        'ios': 'iOS Device',
        'iot': 'IoT Device',
        'vm': 'Virtual Machine',
        'cloud': 'Cloud Instance'
    }
    
    CAPTURE_METHODS = {
        'usb': 'USB Connection',
        'network': 'Network/SSH',
        'local': 'Local Execution',
        'adb': 'Android Debug Bridge',
        'libimobiledevice': 'iOS USB Tools'
    }
    
    def __init__(self):
        self.detected_devices = []
        self.current_os = platform.system().lower()
        
    def detect_local_system(self):
        """detect information about the local system"""
        info = {
            'type': 'local',
            'os': platform.system(),
            'os_version': platform.version(),
            'architecture': platform.machine(),
            'hostname': socket.gethostname(),
            'method': 'local',
            'available': True
        }
        
        # Check if running in VM
        info['is_vm'] = self._detect_vm()
        
        # Get memory info
        if PSUTIL_AVAILABLE:
            mem = psutil.virtual_memory()
            info['total_ram'] = mem.total
            info['available_ram'] = mem.available
            
            # Get disk info
            partitions = psutil.disk_partitions()
            info['drives'] = []
            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    info['drives'].append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free
                    })
                except:
                    pass
        
        return info
    
    def _detect_vm(self):
        """detect if system is a virtual machine"""
        # Check common VM indicators
        vm_indicators = [
            'vmware', 'virtualbox', 'qemu', 'kvm', 'xen',
            'hyper-v', 'parallels', 'virtual'
        ]
        
        system_info = platform.platform().lower()
        
        for indicator in vm_indicators:
            if indicator in system_info:
                return True
        
        # Check for VM-specific files/directories
        if self.current_os == 'linux':
            vm_files = [
                '/sys/class/dmi/id/product_name',
                '/sys/class/dmi/id/sys_vendor'
            ]
            for vm_file in vm_files:
                try:
                    with open(vm_file, 'r') as f:
                        content = f.read().lower()
                        for indicator in vm_indicators:
                            if indicator in content:
                                return True
                except:
                    pass
        
        return False
    
    def detect_usb_devices(self):
        """detect USB-connected devices"""
        devices = []
        
        # Detect Android devices via ADB
        android_devices = self._detect_android_adb()
        devices.extend(android_devices)
        
        # Detect iOS devices via libimobiledevice
        ios_devices = self._detect_ios_devices()
        devices.extend(ios_devices)
        
        # Detect USB storage devices
        usb_storage = self._detect_usb_storage()
        devices.extend(usb_storage)
        
        return devices
    
    def _detect_android_adb(self):
        """detect Android devices via ADB"""
        devices = []
        
        try:
            # Check if adb is available
            result = subprocess.run(['adb', 'devices'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                
                for line in lines:
                    if line.strip() and '\tdevice' in line:
                        device_id = line.split('\t')[0]
                        
                        # Get device info
                        model_result = subprocess.run(
                            ['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
                            capture_output=True, text=True, timeout=5
                        )
                        model = model_result.stdout.strip() if model_result.returncode == 0 else 'Unknown'
                        
                        android_version = subprocess.run(
                            ['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'],
                            capture_output=True, text=True, timeout=5
                        )
                        version = android_version.stdout.strip() if android_version.returncode == 0 else 'Unknown'
                        
                        devices.append({
                            'type': 'android',
                            'id': device_id,
                            'model': model,
                            'os_version': f'Android {version}',
                            'method': 'adb',
                            'available': True,
                            'capabilities': ['disk_image', 'ram_capture', 'logical_backup']
                        })
        except FileNotFoundError:
            print("⚠ ADB not found - Android device detection disabled")
        except Exception as e:
            print(f"⚠ Error detecting Android devices: {e}")
        
        return devices
    
    def _detect_ios_devices(self):
        """detect iOS devices via libimobiledevice"""
        devices = []
        
        try:
            # Check if idevice_id is available
            result = subprocess.run(['idevice_id', '-l'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                device_ids = result.stdout.strip().split('\n')
                
                for device_id in device_ids:
                    if device_id.strip():
                        # Get device info
                        info_result = subprocess.run(
                            ['ideviceinfo', '-u', device_id, '-k', 'ProductType'],
                            capture_output=True, text=True, timeout=5
                        )
                        model = info_result.stdout.strip() if info_result.returncode == 0 else 'Unknown'
                        
                        version_result = subprocess.run(
                            ['ideviceinfo', '-u', device_id, '-k', 'ProductVersion'],
                            capture_output=True, text=True, timeout=5
                        )
                        version = version_result.stdout.strip() if version_result.returncode == 0 else 'Unknown'
                        
                        devices.append({
                            'type': 'ios',
                            'id': device_id,
                            'model': model,
                            'os_version': f'iOS {version}',
                            'method': 'libimobiledevice',
                            'available': True,
                            'capabilities': ['logical_backup', 'file_system']
                        })
        except FileNotFoundError:
            print("⚠ libimobiledevice not found - iOS device detection disabled")
        except Exception as e:
            print(f"⚠ Error detecting iOS devices: {e}")
        
        return devices
    
    def _detect_usb_storage(self):
        """detect USB storage devices"""
        devices = []
        
        if PSUTIL_AVAILABLE:
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                # Try to identify USB devices (basic heuristic)
                if 'removable' in partition.opts.lower() or \
                   '/media/' in partition.mountpoint or \
                   '/mnt/usb' in partition.mountpoint:
                    
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        
                        devices.append({
                            'type': 'usb_storage',
                            'device': partition.device,
                            'mountpoint': partition.mountpoint,
                            'fstype': partition.fstype,
                            'total': usage.total,
                            'method': 'usb',
                            'available': True,
                            'capabilities': ['disk_image', 'file_copy']
                        })
                    except:
                        pass
        
        return devices
    
    def detect_network_devices(self, ip_range=None):
        """detect devices on network (simplified)"""
        # This is a placeholder for network scanning
        # Real implementation would use nmap or similar
        devices = []
        
        print("⚠ Network device detection not fully implemented")
        print("  Use SSH connection option for remote devices")
        
        return devices
    
    def capture_ram_local(self, output_path, progress_callback=None):
        """capture RAM from local system"""
        if progress_callback:
            progress_callback(0, "preparing RAM capture...")
        
        print(f"Capturing RAM to: {output_path}")
        
        os_type = platform.system().lower()
        
        try:
            if os_type == 'linux':
                return self._capture_ram_linux(output_path, progress_callback)
            elif os_type == 'windows':
                return self._capture_ram_windows(output_path, progress_callback)
            elif os_type == 'darwin':
                return self._capture_ram_macos(output_path, progress_callback)
            else:
                return False, f"RAM capture not supported on {os_type}"
        
        except Exception as e:
            return False, f"RAM capture failed: {e}"
    
    def _capture_ram_linux(self, output_path, progress_callback):
        """capture RAM on Linux using LiME or dd"""
        # Try using LiME (Linux Memory Extractor) kernel module
        # If not available, fall back to /dev/mem or /proc/kcore
        
        if progress_callback:
            progress_callback(10, "checking for LiME module...")
        
        # Check if LiME is loaded
        lime_check = subprocess.run(['lsmod'], capture_output=True, text=True)
        if 'lime' in lime_check.stdout:
            if progress_callback:
                progress_callback(20, "using LiME for RAM capture...")
            
            # Use LiME
            cmd = f"sudo insmod lime.ko 'path={output_path} format=raw'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, "RAM captured successfully with LiME"
        
        # Fallback: try copying /proc/kcore
        if progress_callback:
            progress_callback(30, "using /proc/kcore fallback...")
        
        try:
            result = subprocess.run(
                ['sudo', 'dd', f'if=/proc/kcore', f'of={output_path}', 'bs=1M'],
                capture_output=True, text=True, timeout=300
            )
            
            if result.returncode == 0:
                return True, "RAM captured from /proc/kcore"
            else:
                return False, "Failed to capture RAM - may need root privileges"
        except subprocess.TimeoutExpired:
            return False, "RAM capture timed out"
    
    def _capture_ram_windows(self, output_path, progress_callback):
        """capture RAM on Windows using various tools"""
        if progress_callback:
            progress_callback(10, "checking for RAM capture tools...")
        
        # Try common Windows memory capture tools
        tools = [
            ('winpmem', ['winpmem_mini_x64.exe', output_path]),
            ('DumpIt', ['DumpIt.exe', '/OUTPUT', output_path]),
            ('FTK Imager', ['ftkimager', '--mem', output_path])
        ]
        
        for tool_name, cmd in tools:
            try:
                if progress_callback:
                    progress_callback(20, f"trying {tool_name}...")
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0 and Path(output_path).exists():
                    return True, f"RAM captured with {tool_name}"
            except FileNotFoundError:
                continue
            except Exception as e:
                continue
        
        return False, "No RAM capture tool found (need winpmem, DumpIt, or FTK Imager)"
    
    def _capture_ram_macos(self, output_path, progress_callback):
        """capture RAM on macOS"""
        if progress_callback:
            progress_callback(10, "checking macOS RAM capture...")
        
        # macOS RAM capture requires special tools or kernel extensions
        # Try using osxpmem if available
        try:
            result = subprocess.run(
                ['sudo', 'osxpmem', '-o', output_path],
                capture_output=True, text=True, timeout=300
            )
            
            if result.returncode == 0:
                return True, "RAM captured with osxpmem"
        except FileNotFoundError:
            pass
        
        return False, "RAM capture requires osxpmem tool"
    
    def capture_disk_image_local(self, source_drive, output_path, progress_callback=None):
        """create forensic disk image of local drive"""
        if progress_callback:
            progress_callback(0, "preparing disk image...")
        
        print(f"Creating disk image: {source_drive} -> {output_path}")
        
        os_type = platform.system().lower()
        
        try:
            if os_type in ['linux', 'darwin']:
                return self._capture_disk_dd(source_drive, output_path, progress_callback)
            elif os_type == 'windows':
                return self._capture_disk_windows(source_drive, output_path, progress_callback)
        except Exception as e:
            return False, f"Disk capture failed: {e}"
    
    def _capture_disk_dd(self, source, output, progress_callback):
        """capture disk using dd"""
        if progress_callback:
            progress_callback(10, "starting dd capture...")
        
        # Use dd with status=progress if available
        cmd = [
            'sudo', 'dd',
            f'if={source}',
            f'of={output}',
            'bs=4M',
            'conv=noerror,sync',
            'status=progress'
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor progress
            while True:
                output_line = process.stderr.readline()
                if output_line == '' and process.poll() is not None:
                    break
                
                if output_line and progress_callback:
                    # Parse dd output for progress
                    if 'bytes' in output_line:
                        progress_callback(50, "capturing disk...")
            
            returncode = process.wait()
            
            if returncode == 0:
                return True, "Disk image created successfully"
            else:
                return False, "Disk capture failed"
                
        except Exception as e:
            return False, f"Error during capture: {e}"
    
    def _capture_disk_windows(self, source, output, progress_callback):
        """capture disk on Windows"""
        # Try FTK Imager or other Windows imaging tools
        tools = [
            ('FTK Imager', ['ftkimager', source, output, '--e01']),
        ]
        
        for tool_name, cmd in tools:
            try:
                if progress_callback:
                    progress_callback(10, f"using {tool_name}...")
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    return True, f"Disk imaged with {tool_name}"
            except FileNotFoundError:
                continue
        
        return False, "No imaging tool found (need FTK Imager)"
    
    def get_capture_info(self):
        """get information about capture capabilities"""
        info = {
            'local_os': self.current_os,
            'ram_capture_supported': True,
            'disk_capture_supported': True,
            'required_tools': []
        }
        
        os_type = platform.system().lower()
        
        if os_type == 'linux':
            info['required_tools'] = ['dd', 'LiME (optional)', 'adb (for Android)', 'libimobiledevice (for iOS)']
        elif os_type == 'windows':
            info['required_tools'] = ['winpmem/DumpIt', 'FTK Imager', 'adb (for Android)']
        elif os_type == 'darwin':
            info['required_tools'] = ['dd', 'osxpmem', 'adb (for Android)', 'libimobiledevice (for iOS)']
        
        return info