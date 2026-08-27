import { useState, useEffect, useCallback, useRef } from 'react';
import { io } from 'socket.io-client';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Sound files mapping
const SOUNDS = {
  lead: '/sounds/lead.mp3',
  shipment: '/sounds/shipment.mp3',
  alert: '/sounds/alert.mp3',
  payment: '/sounds/payment.mp3',
  success: '/sounds/success.mp3',
};

/**
 * useNotifications hook
 * 
 * @param {Object} options
 * @param {string} options.userId - User ID for socket connection
 * @param {string} options.role - User role for socket connection
 * @param {boolean} options.soundEnabled - Whether to play sounds
 * @param {Function} options.onNotification - Callback when notification received
 */
export function useNotifications(options = {}) {
  const { userId, role, soundEnabled = true, onNotification } = options;
  
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);
  const audioRef = useRef(null);

  // Play notification sound
  const playSound = useCallback((soundKey) => {
    const soundUrl = SOUNDS[soundKey] || SOUNDS.alert;
    
    try {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      
      const audio = new Audio(soundUrl);
      audioRef.current = audio;
      
      audio.volume = 0.5;
      audio.play().catch((err) => {
        console.warn('Could not play notification sound:', err);
      });
    } catch (err) {
      console.warn('Error playing sound:', err);
    }
  }, []);

  // Initialize socket connection
  useEffect(() => {
    if (!userId) return;

    const socket = io(`${API_URL}/notifications`, {
      auth: { userId, role },
      query: { userId, role },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('Notification socket connected');
      setConnected(true);
    });

    socket.on('disconnect', () => {
      console.log('Notification socket disconnected');
      setConnected(false);
    });

    socket.on('notification', (payload) => {
      console.log('Received notification:', payload);
      
      setNotifications((prev) => [payload, ...prev]);
      setUnreadCount((prev) => prev + 1);

      // Play sound if enabled
      if (soundEnabled && payload.soundKey) {
        playSound(payload.soundKey);
      }

      // Call custom handler
      if (onNotification) {
        onNotification(payload);
      }
    });

    socket.on('play-sound', (payload) => {
      if (soundEnabled) {
        playSound(payload.soundKey);
      }
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [userId, role, soundEnabled, onNotification, playSound]);

  // Mark notification as read
  const markAsRead = useCallback(async (notificationId) => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/notifications/${notificationId}/read`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notificationId ? { ...n, isRead: true } : n
        )
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Failed to mark notification as read:', err);
    }
  }, []);

  // Mark all as read
  const markAllAsRead = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/notifications/read-all`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      setNotifications((prev) =>
        prev.map((n) => ({ ...n, isRead: true }))
      );
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all as read:', err);
    }
  }, []);

  // Fetch initial notifications
  const fetchNotifications = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/notifications/me`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        setNotifications(data.notifications || []);
        setUnreadCount(data.unreadCount || 0);
      }
    } catch (err) {
      console.error('Failed to fetch notifications:', err);
    }
  }, []);

  // Clear notifications
  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  // Test notification (for development)
  const sendTestNotification = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/notifications/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type: 'test.notification',
          title: '🧪 Тестове сповіщення',
          message: 'Це тестове сповіщення для перевірки системи',
          soundKey: 'alert',
        }),
      });
    } catch (err) {
      console.error('Failed to send test notification:', err);
    }
  }, []);

  return {
    notifications,
    unreadCount,
    connected,
    markAsRead,
    markAllAsRead,
    fetchNotifications,
    clearNotifications,
    sendTestNotification,
    playSound,
  };
}

export default useNotifications;
