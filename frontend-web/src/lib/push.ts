import { getJson, postJson, putJson, deleteJson } from './api';

export type PushSubscriptionRow = {
  id: number;
  endpoint: string;
  device_label: string | null;
  created_at: string;
  last_seen_at: string;
};

export type ReminderSchedule = {
  id: number;
  time_of_day: string;
  message: string | null;
  enabled: boolean;
};

// Converts the VAPID public key (URL-safe base64) into the Uint8Array the Push API expects.
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return null;
  return navigator.serviceWorker.register('/sw.js');
}

export function pushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    typeof Notification !== 'undefined'
  );
}

function detectDeviceLabel(): string {
  const ua = navigator.userAgent;
  const platform = /Android/i.test(ua) ? 'Android' : /iPhone|iPad/i.test(ua) ? 'iOS' : /Mac/i.test(ua) ? 'Mac' : /Win/i.test(ua) ? 'Windows' : 'Device';
  const browser = /Chrome/i.test(ua) ? 'Chrome' : /Firefox/i.test(ua) ? 'Firefox' : /Safari/i.test(ua) ? 'Safari' : 'Browser';
  return `${platform} · ${browser}`;
}

export async function subscribeThisDevice(): Promise<void> {
  if (!pushSupported()) throw new Error('Push notifications are not supported on this browser.');

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Notification permission was not granted.');

  const registration = (await registerServiceWorker()) || (await navigator.serviceWorker.ready);
  const { public_key } = await getJson<{ public_key: string }>('/push/public-key');

  const existing = await registration.pushManager.getSubscription();
  const subscription =
    existing ||
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key) as unknown as BufferSource
    }));

  const json = subscription.toJSON();
  await postJson('/push/subscribe', {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys?.p256dh, auth: json.keys?.auth },
    device_label: detectDeviceLabel()
  });
}

export const listSubscriptions = () => getJson<PushSubscriptionRow[]>('/push/subscriptions');
export const removeSubscription = (id: number) => deleteJson(`/push/subscriptions/${id}`);

export const listReminders = () => getJson<ReminderSchedule[]>('/push/reminders');
export const createReminder = (payload: { time_of_day: string; message: string | null; enabled: boolean }) =>
  postJson<ReminderSchedule>('/push/reminders', payload);
export const updateReminder = (id: number, payload: Partial<{ time_of_day: string; message: string | null; enabled: boolean }>) =>
  putJson<ReminderSchedule>(`/push/reminders/${id}`, payload);
export const deleteReminder = (id: number) => deleteJson(`/push/reminders/${id}`);
