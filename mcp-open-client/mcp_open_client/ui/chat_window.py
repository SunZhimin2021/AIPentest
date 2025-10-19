from nicegui import ui
from .chat_interface import create_chat_interface


def show_content(container):
    """
    Creates a GPT-style chat interface in the provided container.
    
    This is the main entry point for the chat window functionality.
    The implementation has been refactored into smaller, more manageable modules:
    
    - message_parser.py: Handles parsing and rendering of messages with code blocks
    - chat_handlers.py: Contains event handlers for chat interactions
    - chat_interface.py: Creates the main UI layout and components
    
    Args:
        container: The container to render the chat interface in
    """
    # Clear and setup the container
    container.clear()
    container.classes('h-full w-full flex flex-col')
    
    with container:
        # Note: Pyodide is now loaded only by the Python Console tab
        # to avoid conflicts with multiple instances
        
        # Create the main chat interface
        create_chat_interface(container)