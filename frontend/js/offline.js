/* Register the service worker and surface connection state.
 *
 * Registration is deliberately late (after load) so it never competes with the
 * first render for bandwidth.
 */

import { toast } from '/js/toast.js';
import { t } from '/js/i18n.js';

export function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  // A worker cannot be registered from a file:// page, and there is no point
  // on an insecure origin other than localhost.
  if (location.protocol !== 'https:' && location.hostname !== 'localhost'
      && location.hostname !== '127.0.0.1') return;

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
      // Offline support is a bonus; failing to register is not worth a message.
    });
  });
}

let offlineToast = null;

export function watchConnection() {
  const online = () => {
    if (offlineToast) { offlineToast(); offlineToast = null; }
  };
  const offline = () => {
    if (!offlineToast) {
      offlineToast = toast(t('errors.offlineMode'), { tone: 'info', duration: 600000 });
    }
  };
  window.addEventListener('online', online);
  window.addEventListener('offline', offline);
  if (!navigator.onLine) offline();
}
