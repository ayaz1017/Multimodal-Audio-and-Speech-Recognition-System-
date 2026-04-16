type WsMessageHandler = (data: any) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: WsMessageHandler[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimer: any = null;
  private heartbeatTimer: any = null;
  private currentPath: string = "";
  private currentToken: string = "";

  connect(path: string, token: string) {
    this.currentPath = path;
    this.currentToken = token;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname === "localhost" ? "localhost:8000" : window.location.host;
    
    // Ensure the path is correct. The backend logic expects /ws/session/{id}
    const wsUrl = `${protocol}//${host}/ws/session/${path}?token=${token}`;
    
    console.log(`Connecting to WebSocket: ${wsUrl}`);
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log(`WebSocket Connected: ${path}`);
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.broadcast({ type: "connection_status", status: "connected" });
    };
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handlers.forEach(h => h(data));
      } catch (err) {
        // Handle binary data or malformed JSON
        if (!(event.data instanceof Blob || event.data instanceof ArrayBuffer)) {
             console.error("Ws Parse error", err);
        }
      }
    };
    
    this.ws.onclose = (event) => {
      console.log(`WebSocket Disconnected: ${event.code} ${event.reason}`);
      this.stopHeartbeat();
      this.broadcast({ type: "connection_status", status: "disconnected" });
      
      if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnect();
      }
    };

    this.ws.onerror = (err) => {
      console.error("WebSocket Error", err);
      this.broadcast({ type: "connection_status", status: "error" });
    };
  }

  private reconnect() {
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
    console.log(`Attempting reconnect ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms...`);
    
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.connect(this.currentPath, this.currentToken);
    }, delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: "ping" }));
      }
    }, 30000);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
  }

  private broadcast(data: any) {
    this.handlers.forEach(h => h(data));
  }

  send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      if (typeof data === 'object' && !(data instanceof Blob || data instanceof ArrayBuffer || ArrayBuffer.isView(data))) {
        this.ws.send(JSON.stringify(data));
      } else {
        this.ws.send(data);
      }
    }
  }

  onMessage(handler: WsMessageHandler) {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter(h => h !== handler);
    };
  }

  disconnect() {
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close(1000, "Normal closure");
      this.ws = null;
    }
    this.handlers = [];
  }
}

export const wsService = new WebSocketService();
