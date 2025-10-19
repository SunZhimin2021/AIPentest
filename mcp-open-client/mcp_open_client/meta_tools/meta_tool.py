"""
Implementación del sistema de meta tools para MCP Open Client.
"""

import inspect
from typing import Dict, Any, List, Callable, Optional
from nicegui import ui

class MetaToolRegistry:
    """Registro y gestor de meta tools para MCP Open Client."""
    
    def __init__(self):
        self.tools = {}
        self.tool_schemas = {}
        self._register_default_tools()
    
    def register_tool(self, name: str, func: Callable, description: str, parameters_schema: Dict[str, Any]):
        """Registrar una nueva meta tool."""
        # Prefijamos el nombre para distinguirlo de herramientas MCP
        tool_name = f"meta-{name}" if not name.startswith("meta-") else name
        self.tools[tool_name] = func
        self.tool_schemas[tool_name] = {
            "name": tool_name,
            "description": description,
            "parameters": parameters_schema
        }
    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar una meta tool registrada si está habilitada."""
        from mcp_open_client.config_utils import is_tool_enabled
        
        if not tool_name.startswith("meta-"):
            tool_name = f"meta-{tool_name}"
            
        if tool_name not in self.tools:
            return {"error": f"Meta tool '{tool_name}' not found"}
        
        # Verificar si la tool está habilitada
        if not is_tool_enabled(tool_name, 'meta'):
            return {"error": f"Meta tool '{tool_name}' is disabled"}
        
        # Extraer metadata obligatoria
        intention = params.pop("intention", "No especificado")
        success_criteria = params.pop("success_criteria", "No especificado")
        
        try:
            func = self.tools[tool_name]
            # Verificar si la función es asíncrona
            if inspect.iscoroutinefunction(func):
                result = await func(**params)
            else:
                result = func(**params)
            
            # Formatear el resultado para que sea compatible con el formato de tool call
            # Incluir metadata en el resultado
            return {
                "result": result,
                "_tool_metadata": {
                    "intention": intention,
                    "success_criteria": success_criteria,
                    "tool_name": tool_name
                }
            }
        except Exception as e:
            return {"error": f"Error executing meta tool '{tool_name}': {str(e)}"}
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Obtener el esquema de todas las meta tools habilitadas en formato compatible con OpenAI."""
        from mcp_open_client.config_utils import is_tool_enabled
        
        tools = []
        for name, schema in self.tool_schemas.items():
            # Solo incluir la tool si está habilitada
            if is_tool_enabled(name, 'meta'):
                # Agregar campos obligatorios de metadata
                enhanced_params = schema["parameters"].copy()
                if "properties" not in enhanced_params:
                    enhanced_params["properties"] = {}
                if "required" not in enhanced_params:
                    enhanced_params["required"] = []
                
                # Agregar intention y success_criteria como campos obligatorios
                enhanced_params["properties"].update({
                    "intention": {
                        "type": "string",
                        "description": "Describe qué quieres lograr con este meta tool y por qué es necesario"
                    },
                    "success_criteria": {
                        "type": "string", 
                        "description": "Define cómo sabrás si el meta tool cumplió exitosamente su propósito"
                    }
                })
                
                # Asegurar que intention y success_criteria sean obligatorios
                if "intention" not in enhanced_params["required"]:
                    enhanced_params["required"].append("intention")
                if "success_criteria" not in enhanced_params["required"]:
                    enhanced_params["required"].append("success_criteria")
                
                tools.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": schema["description"],
                        "parameters": enhanced_params
                    }
                })
        return tools
    
    def _register_default_tools(self):
        """Registrar las meta tools predeterminadas."""
        # No hay meta tools por defecto

# Decorador para facilitar el registro de meta tools
def meta_tool(name: str, description: str, parameters_schema: Dict[str, Any]):
    """Decorador para registrar una función como meta tool."""
    def decorator(func):
        meta_tool_registry.register_tool(name, func, description, parameters_schema)
        return func
    return decorator

def get_registered_meta_tools() -> Dict[str, Dict[str, Any]]:
    """Obtener todas las meta tools registradas (incluyendo las desactivadas)."""
    return meta_tool_registry.tool_schemas

# Instancia global del registro de meta tools
meta_tool_registry = MetaToolRegistry()
