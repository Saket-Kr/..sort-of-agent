/**
 * UI Controller Module
 * Handles DOM manipulation and rendering for the chat interface.
 */

class UIController {
    constructor() {
        // DOM element references
        this.elements = {
            connectionStatus: null,
            messagesContainer: null,
            inputForm: null,
            messageInput: null,
            sendButton: null,
            newChatButton: null,
            conversationsList: null,
            streamingIndicator: null,
            clarificationModal: null,
            workflowModal: null,
            searchResultsPanel: null,
            validationProgress: null,
            // Workflow panel elements
            workflowResultsPanel: null,
            panelJobInfo: null,
            panelGraphView: null,
            panelJsonView: null,
            panelJsonContent: null
        };

        this.templates = {};
        this.currentWorkflow = null;
        this.currentJobName = null;
    }

    /**
     * Initialize UI controller with DOM elements
     */
    init() {
        // Get DOM elements
        this.elements.connectionStatus = document.getElementById('connection-status');
        this.elements.messagesContainer = document.getElementById('messages-container');
        this.elements.inputForm = document.getElementById('input-form');
        this.elements.messageInput = document.getElementById('message-input');
        this.elements.sendButton = document.getElementById('send-button');
        this.elements.newChatButton = document.getElementById('new-chat-button');
        this.elements.conversationsList = document.getElementById('conversations-list');
        this.elements.streamingIndicator = document.getElementById('streaming-indicator');
        this.elements.clarificationModal = document.getElementById('clarification-modal');
        this.elements.workflowModal = document.getElementById('workflow-modal');
        this.elements.searchResultsPanel = document.getElementById('search-results-panel');
        this.elements.validationProgress = document.getElementById('validation-progress');

        // Workflow panel elements
        this.elements.workflowResultsPanel = document.getElementById('workflow-results-panel');
        this.elements.panelJobInfo = document.getElementById('panel-job-info');
        this.elements.panelGraphView = document.getElementById('panel-graph-view');
        this.elements.panelJsonView = document.getElementById('panel-json-view');
        this.elements.panelJsonContent = document.getElementById('panel-json-content');

        // Load templates
        this._loadTemplates();

        // Initialize workflow panel
        this._initWorkflowPanel();
    }

    /**
     * Update connection status display
     */
    updateConnectionStatus(state, details = {}) {
        const el = this.elements.connectionStatus;
        if (!el) return;

        el.className = `connection-status connection-${state}`;

        const statusTexts = {
            'connecting': 'Connecting...',
            'connected': 'Connected',
            'disconnected': 'Disconnected',
            'reconnecting': `Reconnecting (${details.attempt || 1}/${details.maxAttempts || 10})...`,
            'error': 'Connection Error'
        };

        el.textContent = statusTexts[state] || state;
    }

    /**
     * Render a message
     */
    renderMessage(message) {
        const container = this.elements.messagesContainer;
        if (!container) return;

        const messageEl = document.createElement('div');
        messageEl.className = `message message-${message.role}`;
        messageEl.dataset.messageId = message.id;

        switch (message.role) {
            case 'user':
                messageEl.innerHTML = this._renderUserMessage(message);
                break;
            case 'assistant':
                messageEl.innerHTML = this._renderAssistantMessage(message);
                break;
            case 'clarification':
                messageEl.innerHTML = this._renderClarificationMessage(message);
                break;
            case 'clarification_response':
                messageEl.innerHTML = this._renderClarificationResponseMessage(message);
                break;
            case 'workflow':
                messageEl.innerHTML = this._renderWorkflowMessage(message);
                break;
            case 'error':
                messageEl.innerHTML = this._renderErrorMessage(message);
                break;
            default:
                messageEl.innerHTML = this._renderGenericMessage(message);
        }

        container.appendChild(messageEl);
        this._scrollToBottom();
    }

    /**
     * Update streaming content
     */
    updateStreamingContent(content) {
        let streamingEl = document.getElementById('streaming-message');

        if (!streamingEl) {
            streamingEl = document.createElement('div');
            streamingEl.id = 'streaming-message';
            streamingEl.className = 'message message-assistant streaming';
            this.elements.messagesContainer.appendChild(streamingEl);
        }

        streamingEl.innerHTML = `
            <div class="message-header">
                <span class="message-role">Assistant</span>
                <span class="streaming-indicator">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </span>
            </div>
            <div class="message-content">${this._formatMarkdown(content)}</div>
        `;

        this._scrollToBottom();
    }

    /**
     * Finalize streaming (remove streaming indicator)
     */
    finalizeStreaming() {
        const streamingEl = document.getElementById('streaming-message');
        if (streamingEl) {
            streamingEl.remove();
        }
    }

    /**
     * Show clarification modal
     */
    showClarificationModal(clarificationId, questions) {
        const modal = this.elements.clarificationModal;
        if (!modal) return;

        const questionsHtml = questions.map((q, i) => `
            <div class="clarification-question">
                <label for="clarification-answer-${i}">${q}</label>
                <textarea
                    id="clarification-answer-${i}"
                    class="clarification-answer"
                    data-question-index="${i}"
                    placeholder="Your answer..."
                    rows="2"
                ></textarea>
            </div>
        `).join('');

        modal.innerHTML = `
            <div class="modal-overlay">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Clarification Needed</h3>
                    </div>
                    <div class="modal-body">
                        <p>Please answer the following questions to help create your workflow:</p>
                        <form id="clarification-form" data-clarification-id="${clarificationId}">
                            ${questionsHtml}
                            <div class="modal-actions">
                                <button type="submit" class="btn btn-primary">Submit Answers</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        modal.classList.add('visible');
    }

    /**
     * Hide clarification modal
     */
    hideClarificationModal() {
        const modal = this.elements.clarificationModal;
        if (modal) {
            modal.classList.remove('visible');
            modal.innerHTML = '';
        }
    }

    /**
     * Show workflow modal
     */
    showWorkflowModal(workflow, jobName) {
        // Also populate the persistent panel
        this.showWorkflowInPanel(workflow, jobName);

        const modal = this.elements.workflowModal;
        if (!modal) return;

        const workflowJson = JSON.stringify(workflow, null, 2);

        modal.innerHTML = `
            <div class="modal-overlay">
                <div class="modal-content modal-large">
                    <div class="modal-header">
                        <h3>Workflow Generated</h3>
                        <button class="modal-close" id="workflow-modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        ${jobName ? `<p class="job-name"><strong>Job Name:</strong> ${jobName}</p>` : ''}
                        <p class="modal-note">You can review this workflow anytime in the panel on the right.</p>
                        <div class="workflow-visualization">
                            ${this._renderWorkflowVisualization(workflow)}
                        </div>
                        <div class="workflow-json">
                            <h4>JSON Output</h4>
                            <pre><code>${this._escapeHtml(workflowJson)}</code></pre>
                        </div>
                        <div class="modal-actions">
                            <button class="btn btn-secondary" id="copy-workflow-btn">Copy JSON</button>
                            <button class="btn btn-primary" id="download-workflow-btn">Download</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        modal.classList.add('visible');

        // Add event listeners
        document.getElementById('workflow-modal-close')?.addEventListener('click', () => {
            this.hideWorkflowModal();
        });

        document.getElementById('copy-workflow-btn')?.addEventListener('click', () => {
            navigator.clipboard.writeText(workflowJson);
            this.showToast('Workflow JSON copied to clipboard');
        });

        document.getElementById('download-workflow-btn')?.addEventListener('click', () => {
            this._downloadJson(workflow, `workflow_${jobName || 'output'}.json`);
        });
    }

    /**
     * Hide workflow modal
     */
    hideWorkflowModal() {
        const modal = this.elements.workflowModal;
        if (modal) {
            modal.classList.remove('visible');
            modal.innerHTML = '';
        }
    }

    /**
     * Update validation progress
     */
    updateValidationProgress(stage, progress, message, errors = []) {
        const el = this.elements.validationProgress;
        if (!el) return;

        el.innerHTML = `
            <div class="validation-progress-container ${errors.length ? 'has-errors' : ''}">
                <div class="validation-header">
                    <span class="validation-stage">${stage}</span>
                    <span class="validation-percent">${Math.round(progress)}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progress}%"></div>
                </div>
                <p class="validation-message">${message}</p>
                ${errors.length ? `
                    <div class="validation-errors">
                        ${errors.map(e => `<div class="error-item">${this._escapeHtml(e)}</div>`).join('')}
                    </div>
                ` : ''}
            </div>
        `;

        el.classList.add('visible');

        if (progress >= 100) {
            setTimeout(() => el.classList.remove('visible'), 3000);
        }
    }

    /**
     * Show search results
     */
    showSearchResults(type, results) {
        const panel = this.elements.searchResultsPanel;
        if (!panel) return;

        const title = type === 'web' ? 'Web Search Results' : 'Task Block Results';

        const resultsHtml = results.map(r => {
            if (type === 'web') {
                return `
                    <div class="search-result">
                        <a href="${r.url}" target="_blank" class="result-title">${this._escapeHtml(r.title)}</a>
                        <p class="result-snippet">${this._escapeHtml(r.snippet || '')}</p>
                    </div>
                `;
            } else {
                return `
                    <div class="search-result task-block">
                        <div class="result-title">${this._escapeHtml(r.name)}</div>
                        <div class="result-meta">
                            <span class="action-code">${r.action_code}</span>
                            <span class="relevance">Score: ${(r.relevance_score * 100).toFixed(0)}%</span>
                        </div>
                        ${r.description ? `<p class="result-description">${this._escapeHtml(r.description)}</p>` : ''}
                    </div>
                `;
            }
        }).join('');

        panel.innerHTML = `
            <div class="search-results-header">
                <h4>${title}</h4>
                <button class="close-panel" id="close-search-results">&times;</button>
            </div>
            <div class="search-results-body">
                ${resultsHtml || '<p class="no-results">No results found</p>'}
            </div>
        `;

        panel.classList.add('visible');

        document.getElementById('close-search-results')?.addEventListener('click', () => {
            this.hideSearchResults();
        });
    }

    /**
     * Hide search results panel
     */
    hideSearchResults() {
        const panel = this.elements.searchResultsPanel;
        if (panel) {
            panel.classList.remove('visible');
        }
    }

    /**
     * Show processing indicator
     */
    showProcessing(show = true) {
        const indicator = this.elements.streamingIndicator;
        if (indicator) {
            indicator.classList.toggle('visible', show);
        }

        // Disable input while processing
        if (this.elements.messageInput) {
            this.elements.messageInput.disabled = show;
        }
        if (this.elements.sendButton) {
            this.elements.sendButton.disabled = show;
        }
    }

    /**
     * Clear messages
     */
    clearMessages() {
        if (this.elements.messagesContainer) {
            this.elements.messagesContainer.innerHTML = '';
        }
    }

    /**
     * Get input value
     */
    getInputValue() {
        return this.elements.messageInput?.value.trim() || '';
    }

    /**
     * Clear input
     */
    clearInput() {
        if (this.elements.messageInput) {
            this.elements.messageInput.value = '';
            this.elements.messageInput.focus();
        }
    }

    /**
     * Focus input
     */
    focusInput() {
        this.elements.messageInput?.focus();
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;

        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            document.body.appendChild(toastContainer);
        }

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    /**
     * Update conversation list
     */
    updateConversationsList(conversations, activeId) {
        const list = this.elements.conversationsList;
        if (!list) return;

        list.innerHTML = conversations.map(conv => `
            <div class="conversation-item ${conv.id === activeId ? 'active' : ''}"
                 data-conversation-id="${conv.id}">
                <div class="conversation-title">
                    ${conv.messages[0]?.content?.substring(0, 30) || 'New Conversation'}...
                </div>
                <div class="conversation-meta">
                    <span class="conversation-status status-${conv.status}">${conv.status}</span>
                    <span class="conversation-time">${this._formatTime(conv.updatedAt)}</span>
                </div>
            </div>
        `).join('');
    }

    // Private rendering methods

    _renderUserMessage(message) {
        return `
            <div class="message-header">
                <span class="message-role">You</span>
                <span class="message-time">${this._formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content">${this._escapeHtml(message.content)}</div>
        `;
    }

    _renderAssistantMessage(message) {
        return `
            <div class="message-header">
                <span class="message-role">Assistant</span>
                <span class="message-time">${this._formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content">${this._formatMarkdown(message.content)}</div>
        `;
    }

    _renderClarificationMessage(message) {
        const questionsHtml = message.questions.map((q, i) =>
            `<li>${this._escapeHtml(q)}</li>`
        ).join('');

        return `
            <div class="message-header">
                <span class="message-role">Clarification Request</span>
                <span class="message-time">${this._formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content clarification-content">
                <p>I need some clarification to proceed:</p>
                <ol class="clarification-questions">${questionsHtml}</ol>
            </div>
        `;
    }

    _renderClarificationResponseMessage(message) {
        return `
            <div class="message-header">
                <span class="message-role">Your Clarification</span>
                <span class="message-time">${this._formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content">${this._escapeHtml(message.content)}</div>
        `;
    }

    _renderWorkflowMessage(message) {
        const blockCount = message.workflow?.workflow_json?.length || 0;
        const edgeCount = message.workflow?.edges?.length || 0;

        return `
            <div class="message-header">
                <span class="message-role">Workflow Generated</span>
                <span class="message-time">${this._formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content workflow-summary">
                ${message.jobName ? `<p><strong>Job:</strong> ${this._escapeHtml(message.jobName)}</p>` : ''}
                <p><strong>Blocks:</strong> ${blockCount} | <strong>Edges:</strong> ${edgeCount}</p>
                <div class="workflow-actions">
                    <button class="btn btn-secondary view-workflow-btn" data-workflow='${JSON.stringify(message.workflow)}' data-job-name="${message.jobName || ''}">
                        View Details
                    </button>
                    <button class="btn btn-primary show-panel-btn" data-workflow='${JSON.stringify(message.workflow)}' data-job-name="${message.jobName || ''}">
                        Open Panel
                    </button>
                </div>
            </div>
        `;
    }

    _renderErrorMessage(message) {
        return `
            <div class="message-header">
                <span class="message-role error">Error</span>
                <span class="message-time">${this._formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content error-content">
                <p><strong>${message.errorCode}:</strong> ${this._escapeHtml(message.content)}</p>
            </div>
        `;
    }

    _renderGenericMessage(message) {
        return `
            <div class="message-header">
                <span class="message-role">${message.role}</span>
                <span class="message-time">${this._formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content">${this._escapeHtml(message.content || '')}</div>
        `;
    }

    _renderWorkflowVisualization(workflow) {
        if (!workflow?.workflow_json) return '<p>No workflow data</p>';

        const blocks = workflow.workflow_json.map(block => `
            <div class="workflow-block">
                <div class="block-id">${block.BlockId}</div>
                <div class="block-name">${this._escapeHtml(block.Name)}</div>
                <div class="block-action">${block.ActionCode}</div>
            </div>
        `).join('<div class="workflow-arrow">→</div>');

        return `<div class="workflow-blocks">${blocks}</div>`;
    }

    // Utility methods

    _escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    _formatMarkdown(text) {
        if (!text) return '';
        // Simple markdown formatting
        return text
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }

    _formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    _scrollToBottom() {
        const container = this.elements.messagesContainer;
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    _downloadJson(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    _loadTemplates() {
        // Templates can be loaded from DOM or defined here
    }

    /**
     * Initialize workflow panel event listeners
     */
    _initWorkflowPanel() {
        const panel = this.elements.workflowResultsPanel;
        if (!panel) return;

        // Tab switching
        panel.querySelectorAll('.panel-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                this._switchPanelTab(tabName);
            });
        });

        // Collapse/expand button
        document.getElementById('panel-collapse-btn')?.addEventListener('click', () => {
            this._togglePanelCollapse();
        });

        // Copy button
        document.getElementById('panel-copy-btn')?.addEventListener('click', () => {
            this._copyWorkflowJson();
        });

        // Download button
        document.getElementById('panel-download-btn')?.addEventListener('click', () => {
            this._downloadWorkflowJson();
        });
    }

    /**
     * Show workflow in the results panel
     */
    showWorkflowInPanel(workflow, jobName) {
        const panel = this.elements.workflowResultsPanel;
        if (!panel) return;

        this.currentWorkflow = workflow;
        this.currentJobName = jobName;

        // Show panel
        panel.classList.add('visible');
        panel.classList.remove('collapsed');

        // Update job info
        this._updatePanelJobInfo(jobName);

        // Update graph view
        this._updatePanelGraphView(workflow);

        // Update JSON view
        this._updatePanelJsonView(workflow);

        // Switch to graph tab by default
        this._switchPanelTab('graph');
    }

    /**
     * Hide workflow results panel
     */
    hideWorkflowPanel() {
        const panel = this.elements.workflowResultsPanel;
        if (panel) {
            panel.classList.remove('visible');
        }
    }

    /**
     * Update panel job info
     */
    _updatePanelJobInfo(jobName) {
        const jobInfo = this.elements.panelJobInfo;
        if (!jobInfo) return;

        if (jobName) {
            jobInfo.innerHTML = `
                <div class="job-label">Job Name</div>
                <div class="job-name">${this._escapeHtml(jobName)}</div>
            `;
        } else {
            jobInfo.innerHTML = '';
        }
    }

    /**
     * Update panel graph view with workflow visualization
     */
    _updatePanelGraphView(workflow) {
        const graphView = this.elements.panelGraphView;
        if (!graphView) return;

        if (!workflow?.workflow_json || workflow.workflow_json.length === 0) {
            graphView.innerHTML = `
                <div class="workflow-graph-container">
                    <div class="empty-state">
                        <p>No workflow data available</p>
                    </div>
                </div>
            `;
            return;
        }

        const blocks = workflow.workflow_json;
        const edges = workflow.edges || [];

        // Build graph HTML
        let graphHtml = '<div class="workflow-graph">';

        blocks.forEach((block, index) => {
            const isStart = block.ActionCode === 'Start' || index === 0;
            const isEnd = block.ActionCode === 'End' || index === blocks.length - 1;

            let nodeClass = 'graph-node';
            if (isStart) nodeClass += ' start-node';
            if (isEnd) nodeClass += ' end-node';

            graphHtml += `
                <div class="${nodeClass}" data-block-id="${block.BlockId}">
                    <div class="node-header">
                        <span class="node-id">${block.BlockId}</span>
                        <span class="node-name">${this._escapeHtml(block.Name)}</span>
                    </div>
                    <div class="node-action">${this._escapeHtml(block.ActionCode)}</div>
                    ${this._renderNodeIO(block)}
                </div>
            `;

            // Add connector between nodes (except after last node)
            if (index < blocks.length - 1) {
                const edge = edges.find(e => e.From === block.BlockId);
                const edgeLabel = edge?.EdgeCondition || '';

                graphHtml += `
                    <div class="graph-connector">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="12" y1="5" x2="12" y2="19"></line>
                            <polyline points="19 12 12 19 5 12"></polyline>
                        </svg>
                        ${edgeLabel ? `<span class="connector-label">${edgeLabel}</span>` : ''}
                    </div>
                `;
            }
        });

        graphHtml += '</div>';

        graphView.innerHTML = `
            <div class="workflow-graph-container">
                ${graphHtml}
            </div>
        `;
    }

    /**
     * Render node inputs/outputs
     */
    _renderNodeIO(block) {
        const inputs = block.Inputs || [];
        const outputs = block.Outputs || [];

        if (inputs.length === 0 && outputs.length === 0) {
            return '';
        }

        let html = '<div class="node-io">';

        if (inputs.length > 0) {
            html += `
                <div class="node-io-section">
                    <div class="node-io-label">Inputs</div>
                    ${inputs.map(inp => `
                        <div class="node-io-item">
                            ${this._escapeHtml(inp.Name)}${inp.ReferencedOutputVariableName ? ` ← ${inp.ReferencedOutputVariableName}` : ''}
                        </div>
                    `).join('')}
                </div>
            `;
        }

        if (outputs.length > 0) {
            html += `
                <div class="node-io-section">
                    <div class="node-io-label">Outputs</div>
                    ${outputs.map(out => `
                        <div class="node-io-item">${this._escapeHtml(out.OutputVariableName || out.Name)}</div>
                    `).join('')}
                </div>
            `;
        }

        html += '</div>';
        return html;
    }

    /**
     * Update panel JSON view
     */
    _updatePanelJsonView(workflow) {
        const jsonContent = this.elements.panelJsonContent;
        if (!jsonContent) return;

        const jsonStr = JSON.stringify(workflow, null, 2);
        jsonContent.innerHTML = `<code>${this._syntaxHighlightJson(jsonStr)}</code>`;
    }

    /**
     * Syntax highlight JSON
     */
    _syntaxHighlightJson(json) {
        // Escape HTML first
        json = this._escapeHtml(json);

        // Apply syntax highlighting
        return json.replace(
            /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
            (match) => {
                let cls = 'json-number';
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'json-key';
                        match = match.replace(/:$/, '') + ':';
                    } else {
                        cls = 'json-string';
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'json-boolean';
                } else if (/null/.test(match)) {
                    cls = 'json-null';
                }
                return `<span class="${cls}">${match}</span>`;
            }
        );
    }

    /**
     * Switch panel tab
     */
    _switchPanelTab(tabName) {
        const panel = this.elements.workflowResultsPanel;
        if (!panel) return;

        // Update tab buttons
        panel.querySelectorAll('.panel-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab content
        panel.querySelectorAll('.panel-tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `panel-${tabName}-view`);
        });
    }

    /**
     * Toggle panel collapse state
     */
    _togglePanelCollapse() {
        const panel = this.elements.workflowResultsPanel;
        if (panel) {
            panel.classList.toggle('collapsed');
        }
    }

    /**
     * Copy workflow JSON to clipboard
     */
    _copyWorkflowJson() {
        if (!this.currentWorkflow) {
            this.showToast('No workflow to copy', 'warning');
            return;
        }

        const jsonStr = JSON.stringify(this.currentWorkflow, null, 2);
        navigator.clipboard.writeText(jsonStr).then(() => {
            this.showToast('Workflow JSON copied to clipboard', 'success');
        }).catch(() => {
            this.showToast('Failed to copy to clipboard', 'error');
        });
    }

    /**
     * Download workflow JSON
     */
    _downloadWorkflowJson() {
        if (!this.currentWorkflow) {
            this.showToast('No workflow to download', 'warning');
            return;
        }

        this._downloadJson(this.currentWorkflow, `workflow_${this.currentJobName || 'output'}.json`);
        this.showToast('Workflow downloaded', 'success');
    }
}

// Export for use in other modules
window.UIController = UIController;
