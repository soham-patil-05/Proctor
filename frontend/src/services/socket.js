const WS_BASE = import.meta.env.VITE_WS_BASE;

class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000;
    this.listeners = {};
    this.heartbeatInterval = null;
    this.lastHeartbeat = null;
    this.isManualClose = false;
  }

  connect(sessionId, rollNo, token) {
    return new Promise((resolve, reject) => {
      try {
        const url = `${WS_BASE}/ws/teachers/sessions/${sessionId}/students/${rollNo}/processes?token=${token}`;
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          this.reconnectAttempts = 0;
          this.reconnectDelay = 1000;
          this.isManualClose = false;
          this.startHeartbeat();
          this.emit('connected');
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.lastHeartbeat = Date.now();

            if (message.type === 'heartbeat') {
              return;
            }

            this.emit(message.type, message.data);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          this.emit('error', error);
          reject(error);
        };

        this.ws.onclose = (event) => {
          this.stopHeartbeat();
          
          // Don't emit 'disconnected' if it was a manual close
          if (!this.isManualClose) {
            console.log('WebSocket closed unexpectedly, code:', event.code);
            this.emit('disconnected');

            if (this.reconnectAttempts < this.maxReconnectAttempts) {
              this.reconnect(sessionId, rollNo, token);
            }
          } else {
            console.log('WebSocket closed manually');
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  reconnect(sessionId, rollNo, token) {
    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      60000
    );

    this.emit('reconnecting', { attempt: this.reconnectAttempts, delay });

    setTimeout(() => {
      this.connect(sessionId, rollNo, token).catch(() => {});
    }, delay);
  }

  startHeartbeat() {
    this.lastHeartbeat = Date.now();

    this.heartbeatInterval = setInterval(() => {
      const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeat;

      // Only mark as lost if no heartbeat for 30 seconds (more lenient)
      if (timeSinceLastHeartbeat > 30000 && this.ws.readyState === WebSocket.OPEN) {
        console.warn('Connection lost - no heartbeat for 30s');
        this.emit('connectionLost');
        this.stopHeartbeat();
      }
    }, 10000); // Check every 10 seconds instead of 5
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  off(event, callback) {
    if (!this.listeners[event]) return;

    if (callback) {
      this.listeners[event] = this.listeners[event].filter((cb) => cb !== callback);
    } else {
      this.listeners[event] = [];
    }
  }

  emit(event, data) {
    if (!this.listeners[event]) return;

    this.listeners[event].forEach((callback) => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in ${event} listener:`, error);
      }
    });
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  close() {
    this.isManualClose = true;
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.listeners = {};
  }
}

export default WebSocketService;
