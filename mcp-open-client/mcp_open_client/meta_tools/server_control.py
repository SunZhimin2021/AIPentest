"""
Meta tools para gestionar tools MCP y Meta.

Este módulo proporciona meta tools para listar y controlar el estado
de activación de tools MCP y Meta Tools individuales.
"""

from nicegui import ui, app
from mcp_open_client.meta_tools.meta_tool import meta_tool
from mcp_open_client.mcp_client import mcp_client_manager



@meta_tool(
    name="list_all_tools",
    description="Lista TODAS las tools disponibles (MCP y Meta Tools), incluyendo las desactivadas",
    parameters_schema={
        "type": "object",
        "properties": {
            "show_only_enabled": {
                "type": "boolean",
                "description": "Si es true, solo muestra tools habilitadas",
                "default": False
            },
            "filter_type": {
                "type": "string",
                "enum": ["all", "mcp", "meta"],
                "description": "Filtrar por tipo de tool: 'all' (todas), 'mcp' (solo MCP), 'meta' (solo Meta)",
                "default": "all"
            }
        },
        "required": []
    }
)
async def list_all_tools(show_only_enabled: bool = False, filter_type: str = "all"):
    """
    Lista TODAS las tools disponibles (MCP y Meta Tools), incluyendo las desactivadas.
    
    Args:
        show_only_enabled: Si es true, solo muestra tools habilitadas
        filter_type: Filtrar por tipo ('all', 'mcp', 'meta')
    
    Returns:
        Lista completa de todas las tools con su estado
    """
    from mcp_open_client.config_utils import is_tool_enabled
    from mcp_open_client.meta_tools.meta_tool import get_registered_meta_tools
    
    all_tools = []
    
    # 1. Obtener Meta Tools (incluyendo las desactivadas)
    if filter_type in ["all", "meta"]:
        try:
            meta_tools = get_registered_meta_tools()
            for tool_name, tool_info in meta_tools.items():
                is_enabled = is_tool_enabled(tool_name, 'meta')
                
                if show_only_enabled and not is_enabled:
                    continue
                
                all_tools.append({
                    "tool_id": tool_name,
                    "tipo": "meta",
                    "nombre": tool_name,
                    "descripcion": tool_info.get('description', 'Meta tool'),
                    "habilitada": is_enabled
                })
        except Exception as e:
            print(f"Error obteniendo meta tools: {e}")
    
    # 2. Obtener Tools MCP (solo si hay conexion)
    if filter_type in ["all", "mcp"] and mcp_client_manager.is_connected():
        try:
            mcp_tools = await mcp_client_manager.list_tools()
            
            for tool in mcp_tools:
                # Handle both dict and object formats
                if hasattr(tool, 'name'):
                    full_tool_name = tool.name
                    tool_desc = tool.description
                else:
                    full_tool_name = tool.get('name', '')
                    tool_desc = tool.get('description', '')
                
                # Extraer servidor y nombre real de la tool
                if '_' in full_tool_name:
                    parts = full_tool_name.split('_', 1)
                    server_name = parts[0]
                    actual_tool_name = parts[1]
                else:
                    server_name = 'unknown'
                    actual_tool_name = full_tool_name
                
                tool_id = f"{server_name}:{actual_tool_name}"
                is_enabled = is_tool_enabled(tool_id, 'mcp')
                
                if show_only_enabled and not is_enabled:
                    continue
                
                all_tools.append({
                    "tool_id": tool_id,
                    "tipo": "mcp",
                    "servidor": server_name,
                    "nombre": actual_tool_name,
                    "nombre_completo": full_tool_name,
                    "descripcion": tool_desc[:100] + "..." if len(tool_desc) > 100 else tool_desc,
                    "habilitada": is_enabled
                })
        except Exception as e:
            print(f"Error obteniendo MCP tools: {e}")
    
    # Estadisticas
    enabled_count = sum(1 for tool in all_tools if tool["habilitada"])
    meta_count = sum(1 for tool in all_tools if tool["tipo"] == "meta")
    mcp_count = sum(1 for tool in all_tools if tool["tipo"] == "mcp")
    
    # Incluir resumen en el resultado en lugar de usar ui.notify()
    summary = f"Total: {len(all_tools)} tools ({meta_count} meta, {mcp_count} mcp), {enabled_count} habilitadas"
    
    return {
        "total_tools": len(all_tools),
        "meta_tools_count": meta_count,
        "mcp_tools_count": mcp_count,
        "tools_habilitadas": enabled_count,
        "resumen": summary,
        "tools": all_tools
    }

@meta_tool(
    name="mcp_toggle_tool",
    description="Activa o desactiva una tool específica (MCP o Meta) por su ID",
    parameters_schema={
        "type": "object",
        "properties": {
            "tool_id": {
                "type": "string",
                "description": "ID de la tool a activar/desactivar. Para MCP tools usa formato 'servidor:nombre', para Meta tools solo el nombre"
            },
            "enabled": {
                "type": "boolean",
                "description": "True para activar la tool, False para desactivarla"
            },
            "tool_type": {
                "type": "string",
                "enum": ["mcp", "meta"],
                "description": "Tipo de tool: 'mcp' para tools MCP, 'meta' para Meta Tools"
            }
        },
        "required": ["tool_id", "enabled", "tool_type"]
    }
)
def toggle_tool(tool_id: str, enabled: bool, tool_type: str):
    """
    Activa o desactiva una tool específica por su ID.
    
    Args:
        tool_id: ID de la tool (formato 'servidor:nombre' para MCP, nombre para Meta)
        enabled: True para activar, False para desactivar
        tool_type: Tipo de tool ('mcp' o 'meta')
    
    Returns:
        Mensaje con el resultado de la operación
    """
    from mcp_open_client.config_utils import set_tool_enabled
    
    # Validar tipo de tool
    if tool_type not in ['mcp', 'meta']:
        return {"error": f"Tipo de tool inválido: {tool_type}. Debe ser 'mcp' o 'meta'"}
    
    try:
        # Realizar el toggle
        set_tool_enabled(tool_id, enabled, tool_type)
        
        # Incluir resultado en la respuesta
        action = "habilitada" if enabled else "deshabilitada"
        
        return {
            "result": f"{tool_type.upper()} tool '{tool_id}' {action} correctamente",
            "tool_id": tool_id,
            "enabled": enabled,
            "tool_type": tool_type,
            "message": f"{tool_type.upper()} tool '{tool_id}' {action}"
        }
    except Exception as e:
        error_msg = f"Error al cambiar estado de la tool '{tool_id}': {str(e)}"
        return {"error": error_msg}
