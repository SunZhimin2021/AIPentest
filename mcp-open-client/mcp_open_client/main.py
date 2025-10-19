from nicegui import ui, app
import asyncio
import json
import os

# Import UI components
from mcp_open_client.ui.home import show_content as show_home_content
from mcp_open_client.ui.mcp_servers import show_content as show_mcp_servers_content
# Import show_content function at runtime to avoid circular import
def get_show_configure_content():
    from mcp_open_client.ui.configure import show_content
    return show_content

# Use get_show_configure_content() when you need to call show_content
from mcp_open_client.ui.chat_window import show_content as show_chat_content
from mcp_open_client.ui.history_settings import create_history_settings_ui

# Import MCP client manager
from mcp_open_client.mcp_client import mcp_client_manager

# Import conversation manager
from mcp_open_client.ui.conversation_manager import conversation_manager
from mcp_open_client.ui.chat_handlers import (
    get_all_conversations, create_new_conversation, load_conversation,
    delete_conversation, get_current_conversation_id
)

# Import config utilities
from mcp_open_client.config_utils import load_initial_config_from_files

# Import conversation context
from mcp_open_client.meta_tools.conversation_context import register_conversation_hook


def init_storage():
    """Initialize storage - load from files only on first run"""
    # Initialize theme from browser storage or default to dark
    if 'dark_mode' not in app.storage.browser:
        app.storage.browser['dark_mode'] = True
    ui.dark_mode().bind_value(app.storage.browser, 'dark_mode')
    
    # Check if this is the first run (no user config exists)
    has_existing_config = 'user-settings' in app.storage.user and app.storage.user['user-settings']
    
    if not has_existing_config:
        print("First run detected - Loading initial configuration from files")
        initial_configs = load_initial_config_from_files()

        # Copy all configurations to user storage (only on first run)
        for key, config in initial_configs.items():
            app.storage.user[key] = config
            print(f"Initialized {key} in user storage with: {config}")
        
        print("Configuration migration complete - future changes will be stored in user storage only")
    else:
        print("Existing user configuration found - preserving user settings")
        print(f"Current user-settings: {app.storage.user.get('user-settings', {})}")
    
    # Always load initial configs for fallback purposes
    if 'initial_configs' not in locals():
        initial_configs = load_initial_config_from_files()
    
    # Ensure required keys exist with defaults if somehow missing
    if 'user-settings' not in app.storage.user:
        app.storage.user['user-settings'] = initial_configs.get("user-settings", {
            'api_key': '',
            'base_url': 'http://192.168.58.101:8123',
            'model': 'claude-3-5-sonnet',
            'system_prompt': 'You are a helpful assistant.'
        })
        print("Created default user-settings")

    if 'mcp-config' not in app.storage.user:
        app.storage.user['mcp-config'] = initial_configs.get("mcp-config", {"mcpServers": {}})
        print("Created default mcp-config")
    
   
        

async def init_mcp_client():
    """Initialize MCP client manager with the configuration"""
    # Add a flag to prevent multiple initializations
    if not hasattr(app.storage.user, 'mcp_initializing') or not app.storage.user.mcp_initializing:
        app.storage.user.mcp_initializing = True
        try:
            config = app.storage.user.get('mcp-config', {})
            
            if not config or 'mcpServers' not in config:
                raise ValueError("Invalid MCP configuration - missing mcpServers section")
            
            # Allow empty mcpServers configuration (no servers configured)
            if not config.get('mcpServers'):
                print("No MCP servers configured - this is valid, skipping MCP client initialization")
                app.storage.user['mcp_status'] = "No MCP servers configured"
                app.storage.user['mcp_status_color'] = 'info'
                return
            
            success = await mcp_client_manager.initialize(config)
            
            # We need to use a safe way to notify from background tasks
            if success:
                active_servers = mcp_client_manager.get_active_servers()
                server_count = len(active_servers)
                # Use app.storage to communicate with the UI
                app.storage.user['mcp_status'] = f"Connected to {server_count} MCP servers"
                app.storage.user['mcp_status_color'] = 'positive'
                
                # Registrar el hook de contexto de conversación
                try:
                    register_conversation_hook()
                except Exception as e:
                    print(f"Error al registrar el hook de contexto: {str(e)}")
            else:
                print("Failed to connect to any MCP servers")
                print("MCP client status:", mcp_client_manager.get_server_status())
                app.storage.user['mcp_status'] = "No active MCP servers found"
                app.storage.user['mcp_status_color'] = 'warning'
        except ValueError as ve:
            print(f"Configuration error: {str(ve)}")
            app.storage.user['mcp_status'] = f"Configuration error: {str(ve)}"
            app.storage.user['mcp_status_color'] = 'negative'
        except Exception as e:
            print(f"Error initializing MCP client: {str(e)}")
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception details: {repr(e)}")
            app.storage.user['mcp_status'] = f"Error: {str(e)}"
            app.storage.user['mcp_status_color'] = 'negative'
        finally:
            app.storage.user.mcp_initializing = False



# Global variables
current_update_content_function = None

def create_conversations_section():
    """Create the conversations section in the sidebar using ConversationManager"""
    from .ui.conversation_manager import conversation_manager
    return conversation_manager.create_conversation_sidebar()

def create_new_conversation_and_refresh():
    """Create a new conversation and refresh the UI"""
    from .ui.conversation_manager import conversation_manager
    conversation_manager._create_new_conversation()

def refresh_conversations_list():
    """Refresh the conversations list using ConversationManager"""
    from .ui.conversation_manager import conversation_manager
    conversation_manager.refresh_conversations_list()

def populate_conversations_list(container):
    """Legacy function - delegates to ConversationManager"""
    # This function is kept for backward compatibility but delegates to ConversationManager
    pass

def load_conversation_and_refresh(conversation_id: str):
    """Load a conversation and refresh the UI"""
    load_conversation(conversation_id)
    refresh_conversations_list()
    # Also refresh chat UI if callback is set
    conversation_manager.refresh_chat_ui()
    # Switch to chat view automatically
    global current_update_content_function
    if current_update_content_function:
        current_update_content_function('chat')
    ui.notify(f'Loaded conversation', color='info', position='top')

def delete_conversation_with_confirm(conversation_id: str):
    """Delete a conversation with confirmation"""
    def confirm_delete():
        delete_conversation(conversation_id)
        refresh_conversations_list()
        # Also refresh chat UI if callback is set
        conversation_manager.refresh_chat_ui()
        ui.notify('Conversation deleted', color='warning', position='top')
        dialog.close()
    
    def cancel_delete():
        dialog.close()
    
    with ui.dialog() as dialog:
        with ui.card().classes('q-pa-md'):
            ui.label('Delete Conversation?').classes('text-h6 q-mb-md')
            ui.label('This action cannot be undone.').classes('q-mb-md')
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=cancel_delete).props('flat')
                ui.button('Delete', on_click=confirm_delete).props('color=red')
    
    dialog.open()

def setup_ui():
    """Setup the UI components"""
    
    @ui.page('/')
    def index():
        """Main application page"""
        # Add mobile viewport meta tag
        ui.add_head_html('<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">')
        ui.add_head_html('<meta name="mobile-web-app-capable" content="yes">')
        ui.add_head_html('<meta name="apple-mobile-web-app-capable" content="yes">')
        ui.add_head_html('<meta name="apple-mobile-web-app-status-bar-style" content="default">')
        ui.add_css(os.path.join(os.path.dirname(__file__), 'settings', 'app-styles.css'))
        
        # Initialize storage first
        init_storage()
        
        # Configure NiceGUI color theme - load from storage or use defaults
        default_colors = {
            'primary': '#dc2626',      # Red to match favicon
            'secondary': '#1f2937',    # Dark gray
            'accent': '#3b82f6',       # Blue accent
            'positive': '#10b981',     # Green for success
            'negative': '#ef4444',     # Red for errors
            'info': '#3b82f6',         # Blue for info
            'warning': '#f59e0b'       # Orange for warnings
        }
        
        # Load saved colors or use defaults
        saved_colors = app.storage.user.get('ui_colors', default_colors)
        ui.colors(**saved_colors)
        # Run the MCP initialization asynchronously
        asyncio.create_task(init_mcp_client())
        
        # Create a status indicator that updates from storage
        last_status = {'message': None, 'color': None}
        
        def update_status():
            nonlocal last_status
            if 'mcp_status' in app.storage.user:
                status = app.storage.user['mcp_status']
                color = app.storage.user.get('mcp_status_color', 'info')
                
                # Only show notification if status has changed
                if status != last_status['message'] or color != last_status['color']:
                    ui.notify(status, color=color, position='top')
                    last_status['message'] = status
                    last_status['color'] = color
        
        # Check for status updates periodically
        ui.timer(1.0, update_status)
        
        # Variable local para sección activa (NO usar storage para esto)
        active_section = 'home'
        
        # Función para verificar si una sección está activa
        def is_active(section):
            return 'active' if section == active_section else ''
        
        content_container = ui.row().classes('main-content w-full').style('padding: 0; margin: 0;')
        
        def update_content(section):
            nonlocal active_section
            active_section = section  # ✅ Variable local, NO storage
            
            # Clear content first
            content_container.clear()
            
            # Show content based on section
            if section == 'home':
                show_home_content(content_container)
            elif section == 'mcp_servers':
                show_mcp_servers_content(content_container)
            elif section == 'configure':
                get_show_configure_content()(content_container)
            elif section == 'chat':
                show_chat_content(content_container)
            elif section == 'history_settings':
                create_history_settings_ui(content_container)
        
        # Make update_content available globally
        global current_update_content_function
        current_update_content_function = update_content
        
        # Configure ConversationManager callback to avoid middleware issues
        from .ui.conversation_manager import conversation_manager
        conversation_manager.set_update_content_callback(update_content)

        
        with ui.header(elevated=False).classes('app-header'):
            with ui.row().classes('items-center full-width no-wrap header-row'):
                with ui.row().classes('items-center no-wrap header-left'):
                    ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').classes('header-btn text-white').props('flat dense')
                    ui.label('MCP-Open-Client').classes('app-title text-subtitle1')
                
                ui.space()
                
                with ui.row().classes('header-actions items-center no-wrap'):
                    ui.button(icon='account_circle', on_click=lambda: ui.notify('User settings coming soon!', position='top')).classes('header-btn text-white').props('flat dense').tooltip('User Account')
        
        with ui.left_drawer(top_corner=True, bottom_corner=True).classes('nav-drawer') as left_drawer:
            ui.label('Navigation Menu').classes('text-h6 nav-title q-mb-lg')
            
            def handle_navigation(section):
                """Handle navigation and close drawer on mobile"""
                update_content(section)
                # Auto-close drawer on mobile after selection
                left_drawer.set_value(False)  # Close drawer
            
            with ui.column().classes('w-full'):
                # Home button
                ui.button(
                    'Home',
                    icon='home',
                    on_click=lambda: handle_navigation('home')
                ).props(
                    'flat no-caps align-left full-width'
                ).classes(
                    f'drawer-btn text-weight-medium text-subtitle1 {is_active("home")}'
                )
                # MCP Servers button
                ui.button(
                    'MCP Servers',
                    icon='dns',
                    on_click=lambda: handle_navigation('mcp_servers')
                ).props(
                    'flat no-caps align-left full-width'
                ).classes(
                    f'drawer-btn text-weight-medium text-subtitle1 {is_active("mcp_servers")}'
                )
                
                # Configure button
                ui.button(
                    'Configure',
                    icon='settings',
                    on_click=lambda: handle_navigation('configure')
                ).props(
                    'flat no-caps align-left full-width'
                ).classes(
                    f'drawer-btn text-weight-medium text-subtitle1 {is_active("configure")}'
                )
                

                # History Settings button
                ui.button(
                    'History Settings',
                    icon='history',
                    on_click=lambda: handle_navigation('history_settings')
                ).props(
                    'flat no-caps align-left full-width'
                ).classes(
                    f'drawer-btn text-weight-medium text-subtitle1 {is_active("history_settings")}'
                )
                
                # Chat button
                ui.button(
                    'Chat',
                    icon='chat',
                    on_click=lambda: handle_navigation('chat')
                ).props(
                    'flat no-caps align-left full-width'
                ).classes(
                    f'drawer-btn text-weight-medium text-subtitle1 {is_active("chat")}'
                )
            
            # Conversations section
            ui.separator().classes('q-my-md')
            create_conversations_section()
            
            ui.separator().classes('q-my-md')
            with ui.column().classes('w-full'):
                ui.label('© 2025 MCP Open Client').classes('text-caption text-center q-mb-sm')
                ui.button('Documentation', icon='help_outline', on_click=lambda: ui.open('https://docs.mcp-open-client.com')).props('flat no-caps full-width size=sm').classes('drawer-btn')
        
        # Set home as the default content
        update_content('chat')

def main():
    """Main entry point"""
    setup_ui()

def cli_entry():
    """Entry point for console script"""
    setup_ui()

# Setup UI when module is imported
setup_ui()

# Custom favicon - M letter in red with white background
favicon_svg = '''
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <rect width="200" height="200" fill="white" stroke="#cccccc" stroke-width="2"/>
        <text x="100" y="140" font-family="Arial, sans-serif" font-size="120" font-weight="bold"
              text-anchor="middle" fill="#dc2626">M</text>
    </svg>
'''

# Run the server - this needs to be at module level for entry points
ui.run(
    title="MCP Open Client",
    storage_secret="ultrasecretkeyboard",
    port=8091,
    reload=False,
    dark=True,
    show_welcome_message=True,
    show=False,
    favicon=favicon_svg
)
