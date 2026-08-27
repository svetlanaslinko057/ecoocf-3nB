/**
 * useWebSocket Hook
 * 
 * Real-time WebSocket connection for notifications and updates
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { io } from 'socket.io-client';
import { toast } from 'sonner';

const WS_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export const useWebSocket = (namespace = '/notifications') => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const socketRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    const token = localStorage.getItem('token') || localStorage.getItem('customerToken');
    
    if (!token) {
      console.log('[WS] No token, skipping connection');
      return;
    }

    if (socketRef.current?.connected) {
      return;
    }

    console.log('[WS] Connecting to', WS_URL + namespace);
    
    socketRef.current = io(WS_URL + namespace, {
      query: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: maxReconnectAttempts,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    socketRef.current.on('connect', () => {
      console.log('[WS] Connected');
      setIsConnected(true);
      reconnectAttempts.current = 0;
    });

    socketRef.current.on('disconnect', (reason) => {
      console.log('[WS] Disconnected:', reason);
      setIsConnected(false);
    });

    socketRef.current.on('connect_error', (error) => {
      console.error('[WS] Connection error:', error.message);
      reconnectAttempts.current++;
      
      if (reconnectAttempts.current >= maxReconnectAttempts) {
        console.log('[WS] Max reconnection attempts reached');
      }
    });

    // Shipment events
    socketRef.current.on('shipment:status_changed', (data) => {
      console.log('[WS] Shipment status changed:', data);
      setLastMessage({ type: 'shipment_status', data, timestamp: new Date() });
      toast.success(`Статус доставки оновлено: ${data.statusLabel || data.newStatus}`);
    });

    socketRef.current.on('shipment:eta_changed', (data) => {
      console.log('[WS] ETA changed:', data);
      setLastMessage({ type: 'eta_changed', data, timestamp: new Date() });
      toast.info(`ETA оновлено: ${data.formattedEta}`);
    });

    socketRef.current.on('shipment:arrived', (data) => {
      console.log('[WS] Shipment arrived:', data);
      setLastMessage({ type: 'shipment_arrived', data, timestamp: new Date() });
      toast.success(`Ваше авто прибуло! ${data.vehicleTitle}`);
    });

    // Alert events
    socketRef.current.on('alert:critical', (data) => {
      console.log('[WS] Critical alert:', data);
      setLastMessage({ type: 'alert', data, timestamp: new Date() });
      toast.error(data.message || 'Критичний алерт');
    });

    // Invoice events
    socketRef.current.on('invoice:paid', (data) => {
      console.log('[WS] Invoice paid:', data);
      setLastMessage({ type: 'invoice_paid', data, timestamp: new Date() });
      toast.success(`Платіж отримано: $${data.amount}`);
    });

    // Contract events
    socketRef.current.on('contract:signed', (data) => {
      console.log('[WS] Contract signed:', data);
      setLastMessage({ type: 'contract_signed', data, timestamp: new Date() });
      toast.success('Контракт підписано!');
    });

  }, [namespace]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    }
  }, []);

  const emit = useCallback((event, data) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit(event, data);
    }
  }, []);

  const subscribe = useCallback((event, callback) => {
    if (socketRef.current) {
      socketRef.current.on(event, callback);
      return () => socketRef.current?.off(event, callback);
    }
    return () => {};
  }, []);

  const subscribeToShipment = useCallback((shipmentId) => {
    emit('subscribe:shipment', { shipmentId });
  }, [emit]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    emit,
    subscribe,
    subscribeToShipment,
    reconnect: connect,
    disconnect,
  };
};

export default useWebSocket;
