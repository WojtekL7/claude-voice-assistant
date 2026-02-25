"""
Claude Voice Assistant - Claude Code Bridge
Handles communication with Claude Code CLI using --print mode.
"""
import os
import re
import subprocess
import threading
import time
from typing import Callable, Optional
from queue import Queue
from pathlib import Path

# Debug log file
DEBUG_LOG = Path.home() / ".claude-voice-assistant" / "debug.log"

def debug_log(msg: str):
    """Write debug message to log file."""
    try:
        with open(DEBUG_LOG, 'a') as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except:
        pass


class ClaudeBridge:
    """
    Bridge for communicating with Claude Code CLI.
    Uses --print mode for simple request/response communication.
    """

    def __init__(self, command: str = "claude"):
        self.command = command
        self.running = False
        self.current_process: Optional[subprocess.Popen] = None

        # Callbacks
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_response_complete: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    def start(self) -> bool:
        """Initialize the bridge (check if claude command exists)."""
        try:
            # Check if command exists
            result = subprocess.run(
                [self.command, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            debug_log(f"Claude version: {result.stdout.strip()}")
            self.running = True
            return True

        except FileNotFoundError:
            if self.on_error:
                self.on_error(f"Command '{self.command}' not found. Is Claude Code installed?")
            return False
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to start Claude Code: {str(e)}")
            return False

    def stop(self):
        """Stop any running process."""
        self.running = False
        if self.current_process:
            try:
                self.current_process.terminate()
            except:
                pass
            self.current_process = None

    def send(self, text: str):
        """Send text to Claude Code and get response."""
        debug_log(f"send() called with: {text[:100]}")

        if not self.running:
            debug_log("Not running, cannot send")
            return

        # Run in background thread to not block GUI
        thread = threading.Thread(target=self._execute_query, args=(text,), daemon=True)
        thread.start()

    def _execute_query(self, text: str):
        """Execute query in background thread."""
        try:
            debug_log(f"Executing query: {text[:50]}...")

            # Notify that we're processing
            if self.on_output:
                self.on_output("⏳ Processing...\n")

            # Run claude with --print flag
            self.current_process = subprocess.Popen(
                [self.command, '--print', text],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Read output in real-time
            response_text = ""
            for line in self.current_process.stdout:
                debug_log(f"Output line: {line[:100] if line else '(empty)'}")
                response_text += line
                if self.on_output:
                    self.on_output(line)

            # Wait for completion
            self.current_process.wait()

            # Check for errors
            stderr = self.current_process.stderr.read()
            if stderr:
                debug_log(f"Stderr: {stderr}")

            # Notify completion
            if self.on_response_complete and response_text.strip():
                self.on_response_complete(response_text)

            debug_log(f"Query completed, response length: {len(response_text)}")

        except Exception as e:
            debug_log(f"Error executing query: {e}")
            if self.on_error:
                self.on_error(f"Error: {str(e)}")
        finally:
            self.current_process = None

    def send_interrupt(self):
        """Interrupt current operation."""
        if self.current_process:
            try:
                self.current_process.terminate()
                debug_log("Process terminated")
            except:
                pass

    def is_running(self) -> bool:
        """Check if bridge is active."""
        return self.running


class ClaudeBridgeAsync:
    """
    Async wrapper for ClaudeBridge with callback-based communication.
    Useful for Qt/PyQt integration.
    """

    def __init__(self, command: str = "claude"):
        self.bridge = ClaudeBridge(command)
        self._output_callbacks = []
        self._response_callbacks = []
        self._error_callbacks = []

        # Set up internal callbacks
        self.bridge.on_output = self._handle_output
        self.bridge.on_response_complete = self._handle_response
        self.bridge.on_error = self._handle_error

    def connect_output(self, callback: Callable[[str], None]):
        """Connect callback for real-time output."""
        self._output_callbacks.append(callback)

    def connect_response(self, callback: Callable[[str], None]):
        """Connect callback for complete responses."""
        self._response_callbacks.append(callback)

    def connect_error(self, callback: Callable[[str], None]):
        """Connect callback for errors."""
        self._error_callbacks.append(callback)

    def _handle_output(self, text: str):
        for cb in self._output_callbacks:
            try:
                cb(text)
            except Exception as e:
                debug_log(f"Error in output callback: {e}")

    def _handle_response(self, text: str):
        for cb in self._response_callbacks:
            try:
                cb(text)
            except Exception as e:
                debug_log(f"Error in response callback: {e}")

    def _handle_error(self, text: str):
        for cb in self._error_callbacks:
            try:
                cb(text)
            except Exception as e:
                debug_log(f"Error in error callback: {e}")

    def start(self) -> bool:
        return self.bridge.start()

    def stop(self):
        self.bridge.stop()

    def send(self, text: str):
        self.bridge.send(text)

    def send_interrupt(self):
        self.bridge.send_interrupt()

    def is_running(self) -> bool:
        return self.bridge.is_running()
