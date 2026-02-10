/**
 * Main Application Module
 * Ties together WebSocket client, chat manager, and UI controller.
 */

class ReasoningEngineApp {
    constructor(options = {}) {
        this.wsUrl = options.wsUrl || `ws://${window.location.hostname}:8765/ws`;

        // Initialize modules
        this.wsClient = new WebSocketClient({ url: this.wsUrl });
        this.chatManager = new ChatManager();
        this.ui = new UIController();

        // Bind methods
        this._handleSendMessage = this._handleSendMessage.bind(this);
        this._handleClarificationSubmit = this._handleClarificationSubmit.bind(this);
        this._handleNewChat = this._handleNewChat.bind(this);
    }

    /**
     * Initialize the application
     */
    async init() {
        console.log('[App] Initializing...');

        // Initialize UI
        this.ui.init();

        // Setup event listeners
        this._setupWebSocketListeners();
        this._setupChatManagerListeners();
        this._setupUIListeners();

        // Connect to WebSocket
        this.ui.updateConnectionStatus('connecting');

        try {
            await this.wsClient.connect();
        } catch (error) {
            console.error('[App] Failed to connect:', error);
            this.ui.showToast('Failed to connect to server', 'error');
        }

        // Create initial conversation
        this._handleNewChat();

        console.log('[App] Initialized');
    }

    /**
     * Setup WebSocket event listeners
     */
    _setupWebSocketListeners() {
        // Connection events
        this.wsClient.addEventListener('connected', () => {
            this.ui.updateConnectionStatus('connected');
            this.ui.showToast('Connected to server', 'success');
        });

        this.wsClient.addEventListener('disconnected', (event) => {
            this.ui.updateConnectionStatus('disconnected');
        });

        this.wsClient.addEventListener('reconnecting', (event) => {
            this.ui.updateConnectionStatus('reconnecting', event.detail);
        });

        this.wsClient.addEventListener('reconnect_failed', () => {
            this.ui.updateConnectionStatus('error');
            this.ui.showToast('Failed to reconnect. Please refresh the page.', 'error');
        });

        this.wsClient.addEventListener('max_connections_exceeded', () => {
            this.ui.showToast('Server at maximum capacity. Please try again later.', 'error');
        });

        this.wsClient.addEventListener('error', (event) => {
            console.error('[App] WebSocket error:', event.detail);
        });

        // Server events
        this.wsClient.addEventListener('processing_started', (event) => {
            const { chat_id } = event.detail;
            this.chatManager.setStatus(chat_id, 'processing');
            this.ui.showProcessing(true);
        });

        this.wsClient.addEventListener('stream_response', (event) => {
            const { chat_id, chunk, is_complete } = event.detail;
            this.chatManager.appendStreamContent(chat_id, chunk);

            if (is_complete) {
                this.chatManager.finalizeStreamContent(chat_id);
                this.ui.finalizeStreaming();
            }
        });

        this.wsClient.addEventListener('clarification_requested', (event) => {
            const { chat_id, clarification_id, questions } = event.detail;
            this.chatManager.setPendingClarification(chat_id, clarification_id, questions);
            this.ui.showClarificationModal(clarification_id, questions);
            this.ui.showProcessing(false);
        });

        this.wsClient.addEventListener('clarification_received', (event) => {
            const { chat_id, clarification_id } = event.detail;
            this.chatManager.clearPendingClarification(chat_id);
            this.ui.hideClarificationModal();
            this.ui.showProcessing(true);
        });

        this.wsClient.addEventListener('web_search_started', (event) => {
            const { chat_id, tool_name } = event.detail;
            this.ui.showToast('Searching the web...', 'info');
        });

        this.wsClient.addEventListener('web_search_results', (event) => {
            const { chat_id, results, query_count, total_results } = event.detail;
            this.chatManager.addSearchResults(chat_id, 'web', results);
            this.ui.showSearchResults('web', results);
        });

        this.wsClient.addEventListener('task_block_search_started', (event) => {
            const { chat_id } = event.detail;
            this.ui.showToast('Searching task blocks...', 'info');
        });

        this.wsClient.addEventListener('task_block_search_results', (event) => {
            const { chat_id, results, query_count, total_results } = event.detail;
            this.chatManager.addSearchResults(chat_id, 'task_block', results);
            this.ui.showSearchResults('task_block', results);
        });

        this.wsClient.addEventListener('validator_progress_update', (event) => {
            const { chat_id, stage, progress, message, errors } = event.detail;
            this.chatManager.updateValidationProgress(chat_id, stage, progress, message, errors);
            this.ui.updateValidationProgress(stage, progress, message, errors);
        });

        this.wsClient.addEventListener('opkey_workflow_json', (event) => {
            const { chat_id, workflow, job_name } = event.detail;
            this.chatManager.setWorkflow(chat_id, workflow, job_name);
            this.ui.showWorkflowModal(workflow, job_name);
            this.ui.showProcessing(false);
        });

        this.wsClient.addEventListener('error', (event) => {
            const { chat_id, error_code, message } = event.detail;

            if (chat_id) {
                this.chatManager.setError(chat_id, error_code, message);
            }

            this.ui.showToast(`Error: ${message}`, 'error');
            this.ui.showProcessing(false);
        });
    }

    /**
     * Setup chat manager event listeners
     */
    _setupChatManagerListeners() {
        this.chatManager.addEventListener('message_added', (event) => {
            const { conversationId, message } = event.detail;

            // Only render for active conversation
            if (conversationId === this.chatManager.activeConversationId) {
                this.ui.renderMessage(message);
            }
        });

        this.chatManager.addEventListener('stream_chunk', (event) => {
            const { conversationId, fullContent } = event.detail;

            if (conversationId === this.chatManager.activeConversationId) {
                this.ui.updateStreamingContent(fullContent);
            }
        });

        this.chatManager.addEventListener('status_changed', (event) => {
            const { conversationId, status } = event.detail;

            if (status === 'completed' || status === 'error') {
                this.ui.showProcessing(false);
            }

            this._updateConversationsList();
        });

        this.chatManager.addEventListener('conversation_created', () => {
            this._updateConversationsList();
        });

        this.chatManager.addEventListener('conversation_cleared', () => {
            this.ui.clearMessages();
        });

        this.chatManager.addEventListener('active_conversation_changed', (event) => {
            const { conversationId } = event.detail;
            this._loadConversation(conversationId);
            this._updateConversationsList();
        });
    }

    /**
     * Setup UI event listeners
     */
    _setupUIListeners() {
        // Send message form
        this.ui.elements.inputForm?.addEventListener('submit', this._handleSendMessage);

        // New chat button
        this.ui.elements.newChatButton?.addEventListener('click', this._handleNewChat);

        // Conversation list clicks
        this.ui.elements.conversationsList?.addEventListener('click', (e) => {
            const item = e.target.closest('.conversation-item');
            if (item) {
                const convId = item.dataset.conversationId;
                this.chatManager.setActiveConversation(convId);
            }
        });

        // Clarification form submission (delegated)
        document.addEventListener('submit', (e) => {
            if (e.target.id === 'clarification-form') {
                e.preventDefault();
                this._handleClarificationSubmit(e.target);
            }
        });

        // View workflow button (delegated) - opens modal
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-workflow-btn')) {
                const workflow = JSON.parse(e.target.dataset.workflow);
                const jobName = e.target.dataset.jobName;
                this.ui.showWorkflowModal(workflow, jobName);
            }
        });

        // Show panel button (delegated) - opens side panel only
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('show-panel-btn')) {
                const workflow = JSON.parse(e.target.dataset.workflow);
                const jobName = e.target.dataset.jobName;
                this.ui.showWorkflowInPanel(workflow, jobName);
            }
        });

        // Modal close on overlay click
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                this.ui.hideClarificationModal();
                this.ui.hideWorkflowModal();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Escape to close modals
            if (e.key === 'Escape') {
                this.ui.hideClarificationModal();
                this.ui.hideWorkflowModal();
                this.ui.hideSearchResults();
            }

            // Ctrl+Enter to send message
            if (e.ctrlKey && e.key === 'Enter') {
                const form = this.ui.elements.inputForm;
                if (form && document.activeElement === this.ui.elements.messageInput) {
                    form.dispatchEvent(new Event('submit'));
                }
            }
        });
    }

    /**
     * Handle send message
     */
    _handleSendMessage(event) {
        event.preventDefault();

        const message = this.ui.getInputValue();
        if (!message) {
            console.log('[App] Empty message, ignoring');
            return;
        }

        const conv = this.chatManager.getActiveConversation();
        if (!conv) {
            this.ui.showToast('No active conversation', 'error');
            return;
        }

        if (!this.wsClient.isConnected) {
            this.ui.showToast('Not connected to server', 'error');
            return;
        }

        // Check if awaiting clarification
        if (conv.status === 'awaiting_clarification') {
            this.ui.showToast('Please answer the clarification questions first', 'warning');
            return;
        }

        // Add user message to chat
        this.chatManager.addUserMessage(conv.id, message);

        // Build payload matching the expected schema
        const payload = {
            chat_id: conv.id,
            message: message,
            user_id: this._generateUUID(),
            service_type: 'planner',
            attachment: [],
            userDTO: {
                U_ID: this._generateUUID(),
                Name: 'Web Client User',
                UserName: 'webclient@example.com',
                email_ID: 'webclient@example.com',
                Is_Enabled: true
            },
            domain: window.location.origin,
            history: '',
            clarification_id: null,
            keycloak_token: null,
            project_key: null
        };

        console.log('[App] Sending start_chat', payload);

        // Send to server
        this.wsClient.send('start_chat', payload);

        // Clear input
        this.ui.clearInput();

        // Show processing
        this.ui.showProcessing(true);
    }

    /**
     * Generate a UUID v4
     */
    _generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    /**
     * Handle clarification form submission
     */
    _handleClarificationSubmit(form) {
        const clarificationId = form.dataset.clarificationId;
        const answers = [];

        form.querySelectorAll('.clarification-answer').forEach((textarea) => {
            answers.push(textarea.value.trim());
        });

        // Check if all answers are provided
        if (answers.some(a => !a)) {
            this.ui.showToast('Please answer all questions', 'warning');
            return;
        }

        const conv = this.chatManager.getActiveConversation();
        if (!conv) return;

        // Combine answers into response
        const response = answers.join('\n\n');

        // Add response to chat
        this.chatManager.addClarificationResponse(conv.id, clarificationId, response);

        // Send to server
        this.wsClient.send('provide_clarification', {
            chat_id: conv.id,
            clarification_id: clarificationId,
            response: response
        });

        // Hide modal
        this.ui.hideClarificationModal();
    }

    /**
     * Handle new chat button
     */
    _handleNewChat() {
        const chatId = this.chatManager.createConversation();
        this.ui.clearMessages();
        this.ui.focusInput();
        this._updateConversationsList();
    }

    /**
     * Load conversation into UI
     */
    _loadConversation(conversationId) {
        const conv = this.chatManager.getConversation(conversationId);
        if (!conv) return;

        // Clear and re-render messages
        this.ui.clearMessages();

        for (const message of conv.messages) {
            this.ui.renderMessage(message);
        }

        // Show streaming content if any
        if (conv.streamingContent) {
            this.ui.updateStreamingContent(conv.streamingContent);
        }

        // Show clarification modal if pending
        if (conv.pendingClarification) {
            this.ui.showClarificationModal(
                conv.pendingClarification.id,
                conv.pendingClarification.questions
            );
        }

        // Update processing state
        this.ui.showProcessing(conv.status === 'processing');
    }

    /**
     * Update conversations list in UI
     */
    _updateConversationsList() {
        const conversations = this.chatManager.getAllConversations();
        const activeId = this.chatManager.activeConversationId;
        this.ui.updateConversationsList(conversations, activeId);
    }

    /**
     * End current conversation
     */
    endCurrentConversation() {
        const conv = this.chatManager.getActiveConversation();
        if (conv) {
            this.wsClient.send('end_chat', { chat_id: conv.id });
            this.chatManager.setStatus(conv.id, 'completed');
        }
    }

    /**
     * Disconnect and cleanup
     */
    destroy() {
        this.wsClient.disconnect();
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('[App] DOM loaded, initializing application...');

    // Get WebSocket URL from config or use default
    const wsUrl = window.REASONING_ENGINE_CONFIG?.wsUrl ||
                  `ws://${window.location.hostname}:8765/ws`;

    console.log('[App] WebSocket URL:', wsUrl);

    window.app = new ReasoningEngineApp({ wsUrl });
    window.app.init().catch((error) => {
        console.error('[App] Initialization failed:', error);
    });
});

// Export for use
window.ReasoningEngineApp = ReasoningEngineApp;
