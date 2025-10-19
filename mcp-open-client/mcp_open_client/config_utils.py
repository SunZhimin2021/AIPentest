import json
import os
from typing import Dict, Any, Optional
from nicegui import app

def load_initial_config_from_files():
    """Load initial configuration from files into user storage (one-time operation)"""
    configs_loaded = {}
    
    # Get the directory where this module is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    settings_dir = os.path.join(current_dir, 'settings')
    
    # Load MCP configuration (only MCP servers)
    mcp_config_path = os.path.join(settings_dir, 'mcp-config.json')
    try:
        with open(mcp_config_path, 'r', encoding='utf-8') as f:
            mcp_file_config = json.load(f)
            configs_loaded['mcp-config'] = mcp_file_config
            print("Loaded MCP servers configuration from mcp-config.json")
    except Exception as e:
        print(f"Warning: Could not load MCP config: {str(e)}")
        configs_loaded['mcp-config'] = {"mcpServers": {}}

    # Load user settings (API settings) from user-settings.json
    user_settings_path = os.path.join(settings_dir, 'user-settings.json')
    try:
        with open(user_settings_path, 'r', encoding='utf-8') as f:
            user_settings_file = json.load(f)
            configs_loaded['user-settings'] = user_settings_file
            print("Loaded user settings from user-settings.json")
            print(f"Base URL: {user_settings_file.get('base_url', 'Not found')}")
    except Exception as e:
        print(f"Warning: Could not load user settings: {str(e)}")
        # Provide default user settings if file doesn't exist
        configs_loaded['user-settings'] = {
            'api_key': '',
            'base_url': 'http://192.168.58.101:8123',
            'model': 'claude-3-5-sonnet'
        }
        print("Using default user settings")

    # Ensure both configs are always present
    if 'user-settings' not in configs_loaded:
        configs_loaded['user-settings'] = {
            'api_key': '',
            'base_url': 'http://192.168.58.101:8123',
            'model': 'claude-3-5-sonnet'
        }
    
    if 'mcp-config' not in configs_loaded:
        configs_loaded['mcp-config'] = {"mcpServers": {}}
    
    return configs_loaded


# === SISTEMA DE CONFIGURACIÓN DE TOOLS INDIVIDUALES ===

def get_tools_config() -> Dict[str, Any]:
    """Obtener la configuración de tools individuales."""
    return app.storage.user.get('tools_config', {
        'mcp_tools': {},
        'meta_tools': {}
    })

def set_tools_config(config: Dict[str, Any]) -> None:
    """Guardar la configuración de tools individuales."""
    app.storage.user['tools_config'] = config

def is_tool_enabled(tool_name: str, tool_type: str = 'auto') -> bool:
    """Verificar si una tool está habilitada.
    
    Args:
        tool_name: Nombre de la tool (ej: 'meta-ui_notify' o 'mcp-requests:http_get')
        tool_type: 'mcp', 'meta' o 'auto' (detecta automáticamente)
        
    Returns:
        True si está habilitada, False si está deshabilitada
        Por defecto, todas las tools están habilitadas si no hay configuración
    """
    config = get_tools_config()
    
    # Detectar tipo automáticamente si es 'auto'
    if tool_type == 'auto':
        if tool_name.startswith('meta-'):
            tool_type = 'meta'
        elif ':' in tool_name:
            tool_type = 'mcp'
        else:
            # Asumir meta tool si no tiene formato servidor:tool
            tool_type = 'meta'
            if not tool_name.startswith('meta-'):
                tool_name = f'meta-{tool_name}'
    
    # Buscar en la configuración correspondiente
    tools_section = config.get(f'{tool_type}_tools', {})
    tool_config = tools_section.get(tool_name)
    
    # Si no hay configuración específica, está habilitada por defecto
    if tool_config is None:
        return True
        
    return tool_config.get('enabled', True)

def set_tool_enabled(tool_name: str, enabled: bool, tool_type: str = 'auto') -> None:
    """Habilitar o deshabilitar una tool específica.
    
    Args:
        tool_name: Nombre de la tool
        enabled: True para habilitar, False para deshabilitar
        tool_type: 'mcp', 'meta' o 'auto'
    """
    config = get_tools_config()
    
    # Detectar tipo automáticamente si es 'auto'
    if tool_type == 'auto':
        if tool_name.startswith('meta-'):
            tool_type = 'meta'
        elif ':' in tool_name:
            tool_type = 'mcp'
        else:
            tool_type = 'meta'
            if not tool_name.startswith('meta-'):
                tool_name = f'meta-{tool_name}'
    
    # Asegurar que existe la sección
    tools_section_key = f'{tool_type}_tools'
    if tools_section_key not in config:
        config[tools_section_key] = {}
    
    # Configurar la tool
    config[tools_section_key][tool_name] = {'enabled': enabled}
    
    # Guardar configuración
    set_tools_config(config)

def get_enabled_tools_by_type(tool_type: str) -> Dict[str, bool]:
    """Obtener todas las tools de un tipo y su estado.
    
    Args:
        tool_type: 'mcp' o 'meta'
        
    Returns:
        Diccionario con tool_name: enabled_status
    """
    config = get_tools_config()
    tools_section = config.get(f'{tool_type}_tools', {})
    
    result = {}
    for tool_name, tool_config in tools_section.items():
        result[tool_name] = tool_config.get('enabled', True)
    
    return result

def reset_tools_config() -> None:
    """Resetear la configuración de tools a valores por defecto (todas habilitadas)."""
    set_tools_config({
        'mcp_tools': {},
        'meta_tools': {}
    })
