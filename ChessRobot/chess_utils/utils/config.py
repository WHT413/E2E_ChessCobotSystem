"""
Configuration management utilities for the chess detection project.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """Load configuration from config.yaml in project root."""
        # Get project root (parent of chess package)
        current_dir = Path(__file__).parent  # chess/utils/
        project_root = current_dir.parent.parent  # d:\Workspaces\chess\
        config_path = project_root / "config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as file:
            self._config = yaml.safe_load(file)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_model_path(self, model_type: str) -> str:
        """Get absolute path for model."""
        relative_path = self.get(f'models.{model_type}.path')
        if not relative_path:
            raise ValueError(f"Model path not found for {model_type}")
        
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / relative_path)
    
    def get_resource_path(self, resource_type: str) -> str:
        """Get absolute path for resource."""
        relative_path = self.get(f'resources.{resource_type}')
        if not relative_path:
            raise ValueError(f"Resource path not found for {resource_type}")
        
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / relative_path)
    
    def get_fen_mapping(self) -> Dict[str, str]:
        """Get FEN mapping dictionary."""
        fen_mapping = self.get('fen_mapping')
        if not fen_mapping:
            raise ValueError("FEN mapping not found in config")
        return fen_mapping

def get_config() -> ConfigManager:
    """Get singleton instance of ConfigManager."""
    return ConfigManager()
