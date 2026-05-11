importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey:            "AIzaSyClZbRCX0Uf6UFr_Nvv7p6GG0nFnm8ezdU",
  authDomain:        "gcsw-cca5d.firebaseapp.com",
  projectId:         "gcsw-cca5d",
  storageBucket:     "gcsw-cca5d.firebasestorage.app",
  messagingSenderId: "1092609196334",
  appId:             "1:1092609196334:web:d39548bb55410c8eee3abf"
});

const messaging = firebase.messaging();

// Handle background messages (when browser tab is not in focus)
messaging.onBackgroundMessage(function(payload) {
  const { title, body, icon } = payload.notification || {};
  self.registration.showNotification(title || 'GCSW', {
    body:  body  || 'You have a new notification.',
    icon:  icon  || '/static/icons/icon-192.png',
    badge: '/static/icons/badge-72.png',
    data:  payload.data || {},
  });
});

// Clicking the notification opens the dashboard
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = event.notification.data?.url || '/dashboard';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(list) {
      for (const client of list) {
        if (client.url.includes(url) && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
