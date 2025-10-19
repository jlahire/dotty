"""
progress_manager.py - Safe progress tracking and callback management

This module provides a robust progress tracking system that prevents crashes
from callback errors and provides helpful progress monitoring utilities.
"""

import time
import threading
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class ProgressState(Enum):
    """Progress tracking states"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressStep:
    """Represents a single progress step"""
    name: str
    value: int
    message: str
    timestamp: datetime
    duration: Optional[float] = None


class ProgressTracker:
    """
    Thread-safe progress tracker with safe callback handling
    
    Features:
    - Safe callback execution (errors don't crash the operation)
    - Progress history tracking
    - Time estimation
    - Multi-step progress support
    - Automatic rate limiting to prevent UI flooding
    """
    
    def __init__(
        self,
        callback: Optional[Callable] = None,
        total: int = 100,
        min_interval: float = 0.1,
        enable_history: bool = True
    ):
        """
        Initialize progress tracker
        
        Args:
            callback: Progress callback function(value, message)
            total: Total progress value (typically 100 for percentage)
            min_interval: Minimum seconds between callbacks (rate limiting)
            enable_history: Track progress history
        """
        self.callback = callback
        self.total = total
        self.min_interval = min_interval
        self.enable_history = enable_history
        
        # State
        self.state = ProgressState.IDLE
        self.current_value = 0
        self.current_message = ""
        self.start_time = None
        self.end_time = None
        self.last_callback_time = 0
        
        # History
        self.history: List[ProgressStep] = []
        self.steps: Dict[str, ProgressStep] = {}
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Statistics
        self.callback_count = 0
        self.callback_errors = 0
        self.skipped_callbacks = 0
    
    def start(self, message: str = "Starting..."):
        """Start progress tracking"""
        with self._lock:
            self.state = ProgressState.RUNNING
            self.start_time = datetime.now()
            self.current_value = 0
            self.current_message = message
            self.history.clear()
            self.steps.clear()
            
            self._safe_callback(0, message)
            
            if self.enable_history:
                self._add_to_history("start", 0, message)
    
    def update(self, value: int, message: str = "", force: bool = False):
        """
        Update progress value and message
        
        Args:
            value: Progress value (0 to total)
            message: Progress message
            force: Force callback even if rate limited
        """
        with self._lock:
            if self.state not in [ProgressState.RUNNING, ProgressState.PAUSED]:
                return
            
            # Clamp value
            value = max(0, min(value, self.total))
            
            # Update state
            self.current_value = value
            if message:
                self.current_message = message
            
            # Check rate limiting
            current_time = time.time()
            should_callback = (
                force or
                (current_time - self.last_callback_time) >= self.min_interval or
                value == 0 or
                value == self.total
            )
            
            if should_callback:
                self._safe_callback(value, self.current_message)
                self.last_callback_time = current_time
            else:
                self.skipped_callbacks += 1
            
            # Add to history
            if self.enable_history and should_callback:
                self._add_to_history("update", value, self.current_message)
    
    def increment(self, amount: int = 1, message: str = ""):
        """Increment progress by amount"""
        with self._lock:
            new_value = self.current_value + amount
            self.update(new_value, message)
    
    def add_step(self, step_name: str, message: str = ""):
        """
        Mark a named progress step
        
        Useful for tracking specific milestones in multi-step operations
        """
        with self._lock:
            step = ProgressStep(
                name=step_name,
                value=self.current_value,
                message=message or step_name,
                timestamp=datetime.now(),
                duration=None
            )
            self.steps[step_name] = step
            
            if self.enable_history:
                self._add_to_history(f"step:{step_name}", self.current_value, message)
    
    def complete(self, message: str = "Complete"):
        """Mark progress as completed"""
        with self._lock:
            self.state = ProgressState.COMPLETED
            self.end_time = datetime.now()
            self.current_value = self.total
            self.current_message = message
            
            self._safe_callback(self.total, message)
            
            if self.enable_history:
                self._add_to_history("complete", self.total, message)
    
    def fail(self, message: str = "Failed"):
        """Mark progress as failed"""
        with self._lock:
            self.state = ProgressState.FAILED
            self.end_time = datetime.now()
            self.current_message = message
            
            self._safe_callback(self.current_value, f"ERROR: {message}")
            
            if self.enable_history:
                self._add_to_history("fail", self.current_value, message)
    
    def cancel(self, message: str = "Cancelled"):
        """Cancel progress tracking"""
        with self._lock:
            self.state = ProgressState.CANCELLED
            self.end_time = datetime.now()
            self.current_message = message
            
            self._safe_callback(self.current_value, message)
            
            if self.enable_history:
                self._add_to_history("cancel", self.current_value, message)
    
    def pause(self):
        """Pause progress tracking"""
        with self._lock:
            if self.state == ProgressState.RUNNING:
                self.state = ProgressState.PAUSED
    
    def resume(self):
        """Resume progress tracking"""
        with self._lock:
            if self.state == ProgressState.PAUSED:
                self.state = ProgressState.RUNNING
    
    def _safe_callback(self, value: int, message: str):
        """Execute callback with error handling"""
        if not self.callback:
            return
        
        try:
            self.callback(value, message)
            self.callback_count += 1
        except Exception as e:
            self.callback_errors += 1
            # Log error but don't raise - prevents crashes
            print(f"Progress callback error: {e}")
            # Continue execution - this is the key safety feature
    
    def _add_to_history(self, name: str, value: int, message: str):
        """Add entry to progress history"""
        step = ProgressStep(
            name=name,
            value=value,
            message=message,
            timestamp=datetime.now()
        )
        self.history.append(step)
    
    def get_elapsed_time(self) -> Optional[timedelta]:
        """Get elapsed time since start"""
        if not self.start_time:
            return None
        
        end = self.end_time or datetime.now()
        return end - self.start_time
    
    def get_estimated_time_remaining(self) -> Optional[timedelta]:
        """Estimate time remaining based on current progress"""
        if not self.start_time or self.current_value == 0:
            return None
        
        elapsed = self.get_elapsed_time()
        if not elapsed:
            return None
        
        if self.current_value >= self.total:
            return timedelta(0)
        
        # Calculate rate and estimate remaining
        rate = self.current_value / elapsed.total_seconds()
        remaining_value = self.total - self.current_value
        
        if rate > 0:
            remaining_seconds = remaining_value / rate
            return timedelta(seconds=remaining_seconds)
        
        return None
    
    def get_progress_percentage(self) -> float:
        """Get current progress as percentage"""
        if self.total == 0:
            return 0.0
        return (self.current_value / self.total) * 100
    
    def get_statistics(self) -> Dict:
        """Get progress tracking statistics"""
        elapsed = self.get_elapsed_time()
        remaining = self.get_estimated_time_remaining()
        
        return {
            'state': self.state.value,
            'progress': self.current_value,
            'total': self.total,
            'percentage': self.get_progress_percentage(),
            'message': self.current_message,
            'elapsed_time': str(elapsed) if elapsed else None,
            'estimated_remaining': str(remaining) if remaining else None,
            'callback_count': self.callback_count,
            'callback_errors': self.callback_errors,
            'skipped_callbacks': self.skipped_callbacks,
            'history_entries': len(self.history),
            'named_steps': len(self.steps)
        }
    
    def get_report(self) -> str:
        """Generate a formatted progress report"""
        stats = self.get_statistics()
        
        lines = [
            "="*60,
            "PROGRESS REPORT",
            "="*60,
            f"State: {stats['state']}",
            f"Progress: {stats['progress']}/{stats['total']} ({stats['percentage']:.1f}%)",
            f"Message: {stats['message']}",
            f"Elapsed Time: {stats['elapsed_time']}",
            f"Estimated Remaining: {stats['estimated_remaining']}",
            "",
            "Callback Statistics:",
            f"  Total Callbacks: {stats['callback_count']}",
            f"  Callback Errors: {stats['callback_errors']}",
            f"  Skipped (Rate Limited): {stats['skipped_callbacks']}",
            "",
            "History:",
            f"  Total Entries: {stats['history_entries']}",
            f"  Named Steps: {stats['named_steps']}",
        ]
        
        # Add named steps
        if self.steps:
            lines.append("")
            lines.append("Progress Steps:")
            for name, step in self.steps.items():
                lines.append(f"  [{step.value:3d}%] {name}: {step.message}")
        
        lines.append("="*60)
        
        return "\n".join(lines)
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is not None:
            self.fail(f"Error: {exc_val}")
        else:
            self.complete()
        return False


class MultiStepProgressTracker:
    """
    Progress tracker for multi-step operations with automatic value mapping
    
    Example:
        tracker = MultiStepProgressTracker(callback, [
            ("Scanning", 30),
            ("Processing", 50),
            ("Saving", 20)
        ])
        
        tracker.start_step("Scanning")
        for i in range(100):
            tracker.update_substep(i, "Scanning file...")
        
        tracker.start_step("Processing")
        ...
    """
    
    def __init__(
        self,
        callback: Optional[Callable],
        steps: List[tuple],  # [(name, weight), ...]
        total: int = 100
    ):
        """
        Initialize multi-step tracker
        
        Args:
            callback: Progress callback
            steps: List of (step_name, weight) tuples
            total: Total progress value
        """
        self.callback = callback
        self.total = total
        
        # Calculate step ranges
        total_weight = sum(weight for _, weight in steps)
        self.steps = []
        current_start = 0
        
        for name, weight in steps:
            step_size = (weight / total_weight) * total
            step_end = current_start + step_size
            
            self.steps.append({
                'name': name,
                'weight': weight,
                'start': current_start,
                'end': step_end,
                'size': step_size
            })
            
            current_start = step_end
        
        self.current_step_index = 0
        self.tracker = ProgressTracker(callback, total)
    
    def start(self, message: str = "Starting..."):
        """Start the multi-step process"""
        self.tracker.start(message)
        self.current_step_index = 0
    
    def start_step(self, step_name: str):
        """Start a named step"""
        # Find step index
        for i, step in enumerate(self.steps):
            if step['name'] == step_name:
                self.current_step_index = i
                break
        
        step = self.steps[self.current_step_index]
        self.tracker.update(int(step['start']), f"Starting: {step_name}")
        self.tracker.add_step(step_name)
    
    def update_substep(self, substep_progress: int, message: str = "", substep_total: int = 100):
        """
        Update progress within current step
        
        Args:
            substep_progress: Progress within current substep (0 to substep_total)
            message: Progress message
            substep_total: Total value for substep
        """
        if self.current_step_index >= len(self.steps):
            return
        
        step = self.steps[self.current_step_index]
        
        # Map substep progress to overall progress
        substep_percentage = substep_progress / substep_total
        overall_value = step['start'] + (step['size'] * substep_percentage)
        
        self.tracker.update(int(overall_value), message)
    
    def complete_step(self):
        """Mark current step as complete and move to next"""
        if self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]
            self.tracker.update(int(step['end']), f"Completed: {step['name']}")
            self.current_step_index += 1
    
    def complete(self, message: str = "Complete"):
        """Complete all steps"""
        self.tracker.complete(message)
    
    def fail(self, message: str = "Failed"):
        """Mark as failed"""
        self.tracker.fail(message)


# Convenience functions for common use cases

def create_simple_tracker(callback: Optional[Callable]) -> ProgressTracker:
    """Create a simple 0-100 progress tracker"""
    return ProgressTracker(callback, total=100)


def create_file_scan_tracker(callback: Optional[Callable], total_files: int) -> ProgressTracker:
    """Create a tracker for file scanning operations"""
    return ProgressTracker(callback, total=total_files, min_interval=0.05)


def create_analysis_tracker(callback: Optional[Callable]) -> MultiStepProgressTracker:
    """Create a tracker for typical forensic analysis workflow"""
    steps = [
        ("Initialization", 5),
        ("Scanning", 30),
        ("Processing", 40),
        ("Building Graph", 15),
        ("Finalizing", 10)
    ]
    return MultiStepProgressTracker(callback, steps)


# Example usage and testing
def example_usage():
    """Example of how to use the progress tracking system"""
    
    print("Example 1: Simple Progress Tracker")
    print("-" * 60)
    
    def my_callback(value, message):
        print(f"[{value:3d}%] {message}")
    
    # Simple progress
    tracker = ProgressTracker(my_callback)
    tracker.start("Starting operation")
    
    for i in range(0, 101, 10):
        time.sleep(0.1)
        tracker.update(i, f"Processing step {i}...")
    
    tracker.complete("Operation complete")
    print(tracker.get_report())
    
    print("\n" + "="*60 + "\n")
    print("Example 2: Multi-Step Progress Tracker")
    print("-" * 60)
    
    # Multi-step progress
    multi_tracker = MultiStepProgressTracker(
        my_callback,
        [
            ("Scanning", 30),
            ("Processing", 50),
            ("Saving", 20)
        ]
    )
    
    multi_tracker.start()
    
    # Step 1: Scanning
    multi_tracker.start_step("Scanning")
    for i in range(0, 101, 20):
        time.sleep(0.1)
        multi_tracker.update_substep(i, f"Scanning file {i}...")
    multi_tracker.complete_step()
    
    # Step 2: Processing
    multi_tracker.start_step("Processing")
    for i in range(0, 101, 20):
        time.sleep(0.1)
        multi_tracker.update_substep(i, f"Processing item {i}...")
    multi_tracker.complete_step()
    
    # Step 3: Saving
    multi_tracker.start_step("Saving")
    for i in range(0, 101, 20):
        time.sleep(0.1)
        multi_tracker.update_substep(i, f"Saving {i}%...")
    multi_tracker.complete_step()
    
    multi_tracker.complete()
    
    print("\n" + "="*60 + "\n")
    print("Example 3: Error Handling")
    print("-" * 60)
    
    def broken_callback(value, message):
        if value == 50:
            raise Exception("Simulated callback error!")
        print(f"[{value:3d}%] {message}")
    
    tracker = ProgressTracker(broken_callback)
    tracker.start("Testing error handling")
    
    for i in range(0, 101, 10):
        tracker.update(i, f"Step {i}...")
    
    print(f"\nCallback Errors: {tracker.callback_errors}")
    print("Operation continued despite callback error!")


if __name__ == '__main__':
    example_usage()