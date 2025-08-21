"""
LiteLLM integration manager for Luthien Control Framework.
"""
import asyncio
import subprocess
import os
import time
from typing import Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class LiteLLMManager:
    """Manages LiteLLM proxy server lifecycle."""
    
    def __init__(self, config_path: str, port: int = 4000):
        """
        Initialize LiteLLM manager.
        
        Args:
            config_path: Path to LiteLLM configuration YAML file
            port: Port for LiteLLM proxy server
        """
        self.config_path = Path(config_path)
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.base_url = f"http://localhost:{port}"
        
    async def start(self) -> bool:
        """
        Start LiteLLM proxy server.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.process and self.process.poll() is None:
            logger.info("LiteLLM proxy server already running")
            return True
            
        try:
            # Start LiteLLM proxy server
            cmd = [
                "litellm", 
                "--config", str(self.config_path),
                "--port", str(self.port),
                "--detailed_debug"
            ]
            
            logger.info(f"Starting LiteLLM proxy server with command: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )
            
            # Wait for server to start up
            await self._wait_for_startup()
            
            logger.info(f"LiteLLM proxy server started on port {self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start LiteLLM proxy server: {str(e)}")
            return False
    
    async def _wait_for_startup(self, timeout: int = 30):
        """Wait for LiteLLM server to be ready."""
        import httpx
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.base_url}/health")
                    if response.status_code == 200:
                        return
            except:
                pass
            await asyncio.sleep(1)
        
        raise TimeoutError(f"LiteLLM server failed to start within {timeout} seconds")
    
    async def stop(self):
        """Stop LiteLLM proxy server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
            logger.info("LiteLLM proxy server stopped")
    
    def is_running(self) -> bool:
        """Check if LiteLLM proxy server is running."""
        return self.process is not None and self.process.poll() is None
    
    def get_endpoint_url(self, path: str = "") -> str:
        """Get the full endpoint URL for a given path."""
        return f"{self.base_url}/{path.lstrip('/')}"


# Global instance
_litellm_manager: Optional[LiteLLMManager] = None


def get_litellm_manager() -> LiteLLMManager:
    """Get the global LiteLLM manager instance."""
    global _litellm_manager
    if _litellm_manager is None:
        config_path = Path(__file__).parent.parent.parent / "litellm_config.yaml"
        _litellm_manager = LiteLLMManager(str(config_path))
    return _litellm_manager