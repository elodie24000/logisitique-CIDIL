const CACHE = 'cidil-v56';
const ASSETS = [
  '/logisitique-CIDIL/',
  '/logisitique-CIDIL/index.html',
  '/logisitique-CIDIL/logo.jpg',
  'https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&family=DM+Mono:wght@400;500&display=swap'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});

// Réception d'une notification push
self.addEventListener('push', e => {
  let data = { title: 'CIDIL Maraîchage', body: 'Les commandes de la semaine sont ouvertes 🥕' };
  try { if (e.data) data = Object.assign(data, e.data.json()); } catch(_) {}
  e.waitUntil(self.registration.showNotification(data.title, {
    body: data.body,
    icon: '/logisitique-CIDIL/logo.jpg',
    badge: '/logisitique-CIDIL/logo.jpg',
    vibrate: [200, 100, 200, 100, 200],
    requireInteraction: true,
    silent: false,
    tag: data.tag || 'cidil-rappel',
    renotify: true,
    data: { url: data.url || '/logisitique-CIDIL/?commande' }
  }));
});

// Clic sur la notification → ouvre l'appli (page commande)
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/logisitique-CIDIL/?commande';
  e.waitUntil(clients.matchAll({type:'window', includeUncontrolled:true}).then(list => {
    for (const c of list) { if ('focus' in c) return c.focus(); }
    if (clients.openWindow) return clients.openWindow(url);
  }));
});
