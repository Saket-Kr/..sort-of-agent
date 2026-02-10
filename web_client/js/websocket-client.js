/**
 * WebSocket Client Module
 * Handles connection management, reconnection, message queuing, and event dispatching.
 */

class WebSocketClient extends EventTarget {
    constructor(options = {}) {
        super();

        this.url = options.url || `ws://${window.location.hostname}:8765/ws`;
        this.reconnectInterval = options.reconnectInterval || 3000;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.pingInterval = options.pingInterval || 30000;

        this.socket = null;
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        this.isManualClose = false;
        this.messageQueue = [];
        this.pingTimer = null;
        this.connectionId = this._generateConnectionId();

        // Bind methods
        this._onOpen = this._onOpen.bind(this);
        this._onClose = this._onClose.bind(this);
        this._onError = this._onError.bind(this);
        this._onMessage = this._onMessage.bind(this);
    }

    /**
     * Generate unique connection ID for this client instance
     */
    _generateConnectionId() {
        return `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.socket?.readyState === WebSocket.OPEN) {
            console.log('[WS] Already connected');
            return Promise.resolve();
        }

        if (this.isConnecting) {
            console.log('[WS] Connection already in progress');
            return Promise.resolve();
        }

        this.isConnecting = true;
        this.isManualClose = false;

        return new Promise((resolve, reject) => {
            try {
                console.log(`[WS] Connecting to ${this.url}...`);
                this.socket = new WebSocket(this.url);

                const onOpenOnce = () => {
                    this.socket.removeEventListener('open', onOpenOnce);
                    this.socket.removeEventListener('error', onErrorOnce);
                    resolve();
                };

                const onErrorOnce = (error) => {
                    this.socket.removeEventListener('open', onOpenOnce);
                    this.socket.removeEventListener('error', onErrorOnce);
                    reject(error);
                };

                this.socket.addEventListener('open', onOpenOnce);
                this.socket.addEventListener('error', onErrorOnce);

                this.socket.addEventListener('open', this._onOpen);
                this.socket.addEventListener('close', this._onClose);
                this.socket.addEventListener('error', this._onError);
                this.socket.addEventListener('message', this._onMessage);

            } catch (error) {
                this.isConnecting = false;
                reject(error);
            }
        });
    }

    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        this.isManualClose = true;
        this._stopPing();

        if (this.socket) {
            this.socket.close(1000, 'Client disconnect');
            this.socket = null;
        }
    }

    /**
     * Send message to server
     */
    send(event, payload = {}) {
        const message = JSON.stringify({ event, payload });

        if (this.socket?.readyState === WebSocket.OPEN) {
            this.socket.send(message);
            console.log(`[WS] Sent: ${event}`, payload);
        } else {
            // Queue message for when connection is restored
            console.log(`[WS] Queuing message: ${event}`);
            this.messageQueue.push(message);
        }
    }

    /**
     * Check if connected
     */
    get isConnected() {
        return this.socket?.readyState === WebSocket.OPEN;
    }

    /**
     * Get connection state
     */
    get state() {
        if (!this.socket) return 'disconnected';
        switch (this.socket.readyState) {
            case WebSocket.CONNECTING: return 'connecting';
            case WebSocket.OPEN: return 'connected';
            case WebSocket.CLOSING: return 'closing';
            case WebSocket.CLOSED: return 'disconnected';
            default: return 'unknown';
        }
    }

    // Private methods

    _onOpen() {
        console.log('[WS] Connected');
        this.isConnecting = false;
        this.reconnectAttempts = 0;

        // Start ping interval
        this._startPing();

        // Flush queued messages
        this._flushMessageQueue();

        // Dispatch connected event
        this.dispatchEvent(new CustomEvent('connected', {
            detail: { connectionId: this.connectionId }
        }));
    }

    _onClose(event) {
        console.log(`[WS] Disconnected: code=${event.code}, reason=${event.reason}`);
        this.isConnecting = false;
        this._stopPing();

        // Dispatch disconnected event
        this.dispatchEvent(new CustomEvent('disconnected', {
            detail: { code: event.code, reason: event.reason }
        }));

        // Handle specific close codes
        if (event.code === 4000) {
            // Max connections exceeded - don't reconnect
            this.dispatchEvent(new CustomEvent('max_connections_exceeded'));
            return;
        }

        // Attempt reconnection if not manual close
        if (!this.isManualClose) {
            this._scheduleReconnect();
        }
    }

    _onError(error) {
        console.error('[WS] Error:', error);
        this.dispatchEvent(new CustomEvent('error', {
            detail: { error }
        }));
    }

    _onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log(`[WS] Received: ${data.event}`, data.payload);

            // Handle pong internally
            if (data.event === 'pong') {
                return;
            }

            // Dispatch typed event
            this.dispatchEvent(new CustomEvent('message', {
                detail: data
            }));

            // Also dispatch event-specific custom event
            this.dispatchEvent(new CustomEvent(data.event, {
                detail: data.payload
            }));

        } catch (error) {
            console.error('[WS] Failed to parse message:', error);
        }
    }

    _startPing() {
        this._stopPing();
        this.pingTimer = setInterval(() => {
            if (this.isConnected) {
                this.send('ping');
            }
        }, this.pingInterval);
    }

    _stopPing() {
        if (this.pingTimer) {
            clearInterval(this.pingTimer);
            this.pingTimer = null;
        }
    }

    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('[WS] Max reconnect attempts reached');
            this.dispatchEvent(new CustomEvent('reconnect_failed'));
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectInterval * Math.min(this.reconnectAttempts, 5);

        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        this.dispatchEvent(new CustomEvent('reconnecting', {
            detail: { attempt: this.reconnectAttempts, maxAttempts: this.maxReconnectAttempts }
        }));

        setTimeout(() => {
            if (!this.isManualClose) {
                this.connect().catch(() => {});
            }
        }, delay);
    }

    _flushMessageQueue() {
        while (this.messageQueue.length > 0 && this.isConnected) {
            const message = this.messageQueue.shift();
            this.socket.send(message);
            console.log('[WS] Sent queued message');
        }
    }
}

// Export for use in other modules
window.WebSocketClient = WebSocketClient;
