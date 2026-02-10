/**
 * Chat Manager Module
 * Handles chat state, message history, and conversation flow.
 */

class ChatManager extends EventTarget {
    constructor() {
        super();

        this.conversations = new Map(); // chatId -> ConversationState
        this.activeConversationId = null;
    }

    /**
     * Create a new conversation
     */
    createConversation(chatId = null) {
        const id = chatId || this._generateChatId();

        const conversation = {
            id,
            status: 'idle', // idle, processing, awaiting_clarification, completed, error
            messages: [],
            streamingContent: '',
            pendingClarification: null,
            workflow: null,
            validationProgress: null,
            searchResults: {
                web: [],
                taskBlock: []
            },
            createdAt: new Date(),
            updatedAt: new Date()
        };

        this.conversations.set(id, conversation);
        this.activeConversationId = id;

        this.dispatchEvent(new CustomEvent('conversation_created', {
            detail: { conversationId: id }
        }));

        return id;
    }

    /**
     * Get conversation by ID
     */
    getConversation(chatId) {
        return this.conversations.get(chatId);
    }

    /**
     * Get active conversation
     */
    getActiveConversation() {
        if (!this.activeConversationId) return null;
        return this.conversations.get(this.activeConversationId);
    }

    /**
     * Set active conversation
     */
    setActiveConversation(chatId) {
        if (this.conversations.has(chatId)) {
            this.activeConversationId = chatId;
            this.dispatchEvent(new CustomEvent('active_conversation_changed', {
                detail: { conversationId: chatId }
            }));
        }
    }

    /**
     * Add user message
     */
    addUserMessage(chatId, content, attachments = []) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return null;

        const message = {
            id: this._generateMessageId(),
            role: 'user',
            content,
            attachments,
            timestamp: new Date()
        };

        conversation.messages.push(message);
        conversation.updatedAt = new Date();

        this.dispatchEvent(new CustomEvent('message_added', {
            detail: { conversationId: chatId, message }
        }));

        return message;
    }

    /**
     * Add assistant message
     */
    addAssistantMessage(chatId, content) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return null;

        const message = {
            id: this._generateMessageId(),
            role: 'assistant',
            content,
            timestamp: new Date()
        };

        conversation.messages.push(message);
        conversation.streamingContent = '';
        conversation.updatedAt = new Date();

        this.dispatchEvent(new CustomEvent('message_added', {
            detail: { conversationId: chatId, message }
        }));

        return message;
    }

    /**
     * Append to streaming content
     */
    appendStreamContent(chatId, chunk) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        conversation.streamingContent += chunk;
        conversation.updatedAt = new Date();

        this.dispatchEvent(new CustomEvent('stream_chunk', {
            detail: {
                conversationId: chatId,
                chunk,
                fullContent: conversation.streamingContent
            }
        }));
    }

    /**
     * Finalize streaming content as assistant message
     */
    finalizeStreamContent(chatId) {
        const conversation = this.conversations.get(chatId);
        if (!conversation || !conversation.streamingContent) return;

        this.addAssistantMessage(chatId, conversation.streamingContent);
    }

    /**
     * Set conversation status
     */
    setStatus(chatId, status) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        const previousStatus = conversation.status;
        conversation.status = status;
        conversation.updatedAt = new Date();

        this.dispatchEvent(new CustomEvent('status_changed', {
            detail: { conversationId: chatId, status, previousStatus }
        }));
    }

    /**
     * Set pending clarification
     */
    setPendingClarification(chatId, clarificationId, questions) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        conversation.pendingClarification = {
            id: clarificationId,
            questions,
            createdAt: new Date()
        };
        conversation.status = 'awaiting_clarification';
        conversation.updatedAt = new Date();

        // Add clarification as a system message
        const message = {
            id: this._generateMessageId(),
            role: 'clarification',
            clarificationId,
            questions,
            timestamp: new Date()
        };
        conversation.messages.push(message);

        this.dispatchEvent(new CustomEvent('clarification_requested', {
            detail: {
                conversationId: chatId,
                clarificationId,
                questions
            }
        }));
    }

    /**
     * Clear pending clarification
     */
    clearPendingClarification(chatId) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        conversation.pendingClarification = null;
        conversation.updatedAt = new Date();
    }

    /**
     * Add clarification response
     */
    addClarificationResponse(chatId, clarificationId, response) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        const message = {
            id: this._generateMessageId(),
            role: 'clarification_response',
            clarificationId,
            content: response,
            timestamp: new Date()
        };
        conversation.messages.push(message);
        conversation.updatedAt = new Date();

        this.dispatchEvent(new CustomEvent('clarification_response_added', {
            detail: { conversationId: chatId, message }
        }));
    }

    /**
     * Add search results
     */
    addSearchResults(chatId, type, results) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        if (type === 'web') {
            conversation.searchResults.web = results;
        } else if (type === 'task_block') {
            conversation.searchResults.taskBlock = results;
        }
        conversation.updatedAt = new Date();

        this.dispatchEvent(new CustomEvent('search_results_added', {
            detail: { conversationId: chatId, type, results }
        }));
    }

    /**
     * Set workflow output
     */
    setWorkflow(chatId, workflow, jobName) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        conversation.workflow = { ...workflow, jobName };
        conversation.status = 'completed';
        conversation.updatedAt = new Date();

        // Add workflow as system message
        const message = {
            id: this._generateMessageId(),
            role: 'workflow',
            workflow,
            jobName,
            timestamp: new Date()
        };
        conversation.messages.push(message);

        this.dispatchEvent(new CustomEvent('workflow_received', {
            detail: { conversationId: chatId, workflow, jobName }
        }));
    }

    /**
     * Update validation progress
     */
    updateValidationProgress(chatId, stage, progress, message, errors = []) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        conversation.validationProgress = { stage, progress, message, errors };
        conversation.updatedAt = new Date();

        this.dispatchEvent(new CustomEvent('validation_progress', {
            detail: { conversationId: chatId, stage, progress, message, errors }
        }));
    }

    /**
     * Set error state
     */
    setError(chatId, errorCode, errorMessage) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        conversation.status = 'error';
        conversation.error = { code: errorCode, message: errorMessage };
        conversation.updatedAt = new Date();

        // Add error as system message
        const message = {
            id: this._generateMessageId(),
            role: 'error',
            errorCode,
            content: errorMessage,
            timestamp: new Date()
        };
        conversation.messages.push(message);

        this.dispatchEvent(new CustomEvent('error', {
            detail: { conversationId: chatId, errorCode, errorMessage }
        }));
    }

    /**
     * Clear conversation
     */
    clearConversation(chatId) {
        const conversation = this.conversations.get(chatId);
        if (!conversation) return;

        conversation.messages = [];
        conversation.streamingContent = '';
        conversation.pendingClarification = null;
        conversation.workflow = null;
        conversation.validationProgress = null;
        conversation.searchResults = { web: [], taskBlock: [] };
        conversation.status = 'idle';
        conversation.error = null;
        conversation.updatedAt = new Date();

        this.dispatchEvent(new CustomEvent('conversation_cleared', {
            detail: { conversationId: chatId }
        }));
    }

    /**
     * Delete conversation
     */
    deleteConversation(chatId) {
        this.conversations.delete(chatId);

        if (this.activeConversationId === chatId) {
            this.activeConversationId = this.conversations.keys().next().value || null;
        }

        this.dispatchEvent(new CustomEvent('conversation_deleted', {
            detail: { conversationId: chatId }
        }));
    }

    /**
     * Get all conversations
     */
    getAllConversations() {
        return Array.from(this.conversations.values());
    }

    // Private methods

    _generateChatId() {
        // Generate UUID v4 format
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    _generateMessageId() {
        return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
}

// Export for use in other modules
window.ChatManager = ChatManager;
