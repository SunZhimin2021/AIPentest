"""
Sistema de Meta Tools para MCP Open Client.

Este módulo proporciona un sistema para crear y registrar herramientas personalizadas
que pueden ser utilizadas por el LLM para interactuar con la interfaz de usuario
o realizar otras tareas que no son parte de las herramientas MCP estándar.
"""

from mcp_open_client.meta_tools.meta_tool import meta_tool_registry, meta_tool

# Importar las meta tools para registrarlas automáticamente
import mcp_open_client.meta_tools.server_control
import mcp_open_client.meta_tools.conversation_context
import mcp_open_client.meta_tools.ui_colors
import mcp_open_client.meta_tools.respond_to_user
import mcp_open_client.meta_tools.notify_user

__all__ = ['meta_tool_registry', 'meta_tool']
