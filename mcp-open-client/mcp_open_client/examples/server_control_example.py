"""
Ejemplo de uso de las meta tools de control de servidores MCP.

Este script muestra cómo se pueden utilizar las meta tools para controlar
servidores MCP desde el LLM, sin necesidad de navegar a la interfaz de usuario.
"""

from nicegui import ui, app
from mcp_open_client.meta_tools import meta_tool_registry

async def main():
    """Función principal del ejemplo."""
    ui.label("Ejemplo de control de servidores MCP con meta tools").classes("text-h4 mb-4")
    
    with ui.card().classes("w-full mb-4"):
        ui.label("Listar servidores MCP").classes("text-h6")
        ui.button("Listar servidores", on_click=list_servers).props("color=primary")
    
    with ui.card().classes("w-full mb-4"):
        ui.label("Activar/Desactivar servidor MCP").classes("text-h6")
        
        server_name = ui.input("Nombre del servidor").classes("w-full mb-2")
        
        with ui.row():
            ui.button("Activar", on_click=lambda: toggle_server(server_name.value, True)).props("color=positive")
            ui.button("Desactivar", on_click=lambda: toggle_server(server_name.value, False)).props("color=negative")
    
    with ui.card().classes("w-full mb-4"):
        ui.label("Reiniciar todos los servidores MCP").classes("text-h6")
        ui.button("Reiniciar servidores", on_click=restart_servers).props("color=warning")
    
    # Área para mostrar resultados
    global result_area
    result_area = ui.textarea("Resultados").classes("w-full h-40").props("readonly")

async def list_servers():
    """Lista todos los servidores MCP."""
    result = await meta_tool_registry.execute_tool("meta-mcp_list_servers", {})
    result_area.value = f"Resultado de listar servidores:\n{result}"

async def toggle_server(server_name, enable):
    """Activa o desactiva un servidor MCP."""
    if not server_name:
        ui.notify("Debe especificar un nombre de servidor", color="negative")
        return
    
    action = "activar" if enable else "desactivar"
    result = await meta_tool_registry.execute_tool("meta-mcp_toggle_server", {
        "server_name": server_name,
        "enable": enable
    })
    result_area.value = f"Resultado de {action} servidor '{server_name}':\n{result}"

async def restart_servers():
    """Reinicia todos los servidores MCP."""
    result = await meta_tool_registry.execute_tool("meta-mcp_restart_all_servers", {})
    result_area.value = f"Resultado de reiniciar servidores:\n{result}"

# Variable global para el área de resultados
result_area = None

# Este script puede ejecutarse directamente para probar las meta tools
if __name__ == "__main__":
    ui.run(on_startup=main)