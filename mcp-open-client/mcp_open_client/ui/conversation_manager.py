from typing import Optional, Callable
import asyncio
from nicegui import ui, app
from .chat_handlers import (
    get_all_conversations, create_new_conversation, load_conversation,
    delete_conversation, get_current_conversation_id
)

class ConversationManager:
    def __init__(self):
        self._refresh_chat_callback: Optional[Callable] = None
        self._conversations_container: Optional[ui.column] = None
        self._update_content_callback: Optional[Callable] = None
    
    def set_refresh_callback(self, callback: Callable):
        """Set the callback function to refresh chat UI"""
        self._refresh_chat_callback = callback
    
    def set_update_content_callback(self, callback: Callable):
        """Set the callback function to update content view"""
        self._update_content_callback = callback
    
    def refresh_chat_ui(self):
        """Refresh the chat UI - SYNC ONLY to preserve UI context"""
        if self._refresh_chat_callback:
            # Always call as sync function to preserve UI context (NO asyncio.create_task)
            self._refresh_chat_callback()
    
    def refresh_conversations_list(self):
        """Refresh the conversations list in the sidebar"""
        print(f"Debug: refresh_conversations_list called, container exists: {self._conversations_container is not None}")
        if self._conversations_container:
            print("Debug: Clearing and repopulating conversations list")
            try:
                self._conversations_container.clear()
                self._populate_conversations_list()
                # Force UI update
                ui.update()
            except Exception as e:
                print(f"Error refreshing conversations container: {e}")
                raise
        else:
            print("Debug: No conversations container found, skipping refresh")
            # Don't force reload when showing dialogs - just skip the refresh
            # The container will be available once the dialog closes
    
    def _safe_refresh_after_delete(self):
        """Safely refresh UI after deleting a conversation"""
        try:
            self.refresh_conversations_list()
            self.refresh_chat_ui()
        except Exception as e:
            print(f"Error during post-delete refresh: {e}")
    
    def _populate_conversations_list(self):
        """Populate the conversations list"""
        if not self._conversations_container:
            return
            
        conversations = get_all_conversations()
        current_id = get_current_conversation_id()
        
        with self._conversations_container:
            if not conversations:
                ui.label('No conversations yet').classes('text-gray-500 text-sm p-2')
                return
            
            # Sort conversations by updated_at (most recent first)
            sorted_conversations = sorted(
                conversations.items(),
                key=lambda x: x[1].get('updated_at', '0'),
                reverse=True
            )
            
            for conv_id, conv_data in sorted_conversations:
                title = conv_data.get('title', f'Conversation {conv_id[:8]}')
                message_count = len(conv_data.get('messages', []))
                
                # Highlight current conversation
                card_classes = 'w-full p-2 mb-1 cursor-pointer hover:bg-gray-100'
                if conv_id == current_id:
                    card_classes += ' bg-blue-100 border-l-4 border-blue-500'
                
                with ui.card().classes(card_classes) as conv_card:
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.column().classes('flex-1'):
                            ui.markdown(title).classes('font-medium text-sm')
                            ui.label(f'{message_count} messages').classes('text-xs text-gray-500')
                        
                        # Delete button
                        delete_btn = ui.button(
                            icon='delete'
                        ).props('flat round size=sm color=red').classes('ml-2')
                        delete_btn.on('click.stop', lambda conv_id=conv_id: self._delete_conversation(conv_id))
                    
                    # Click to load conversation
                    conv_card.on('click', lambda conv_id=conv_id: self._load_conversation(conv_id))
    
    def _load_conversation(self, conversation_id: str):
        """Load a specific conversation"""
        load_conversation(conversation_id)
        self.refresh_conversations_list()
        self.refresh_chat_ui()
        # Switch to chat view automatically
        if self._update_content_callback:
            self._update_content_callback('chat')
    
    def _delete_conversation(self, conversation_id: str):
        """Delete a conversation with confirmation"""
        def confirm_delete():
            try:
                delete_conversation(conversation_id)
                dialog.close()
                
                # Defer the UI refresh to avoid conflicts with dialog closing
                ui.timer(0.1, lambda: self._safe_refresh_after_delete(), once=True)
                
                ui.notify('Conversation deleted', color='positive', position='top')
            except Exception as e:
                print(f"Error deleting conversation: {e}")
                ui.notify('Error deleting conversation', color='negative', position='top')
        
        def cancel_delete():
            dialog.close()
        
        with ui.dialog() as dialog:
            with ui.card():
                ui.label('Delete Conversation?').classes('text-h6 mb-4')
                ui.label('This action cannot be undone.').classes('mb-4')
                
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('Cancel', on_click=cancel_delete).props('flat')
                    ui.button('Delete', on_click=confirm_delete).props('color=red')
        
        dialog.open()
    
    def _create_new_conversation(self):
        """Create a new conversation"""
        create_new_conversation()
        self.refresh_conversations_list()
        self.refresh_chat_ui()
    
    def create_conversation_sidebar(self):
        """Create the conversation management sidebar"""
        with ui.column().classes('w-full h-full p-4 bg-gray-50'):
            # Header
            ui.label('Conversations').classes('text-lg font-bold mb-4')
            
            # New conversation button
            ui.button(
                'New Conversation',
                icon='add',
                on_click=self._create_new_conversation
            ).classes('w-full mb-4').props('color=primary')
            
            # Conversations list
            ui.separator().classes('mb-4')
            
            # Scroll area with fixed height - following NiceGUI best practices
            with ui.scroll_area().classes('w-full').style('height: 400px; max-height: calc(100vh - 250px);') as scroll_area:
                self._conversations_container = ui.column().classes('w-full')
                self._populate_conversations_list()

# Global instance
conversation_manager = ConversationManager()