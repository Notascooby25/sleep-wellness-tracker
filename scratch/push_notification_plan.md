# Plan: Improve Push Notification Reliability on Android/PWA

## 1. Context
Push notifications on Android Progressive Web Apps (PWAs) often fail silently due to environmental constraints rather than code bugs. The primary culprits are usually:
1. **Insecure Contexts:** Android Chrome/Brave strictly requires HTTPS for Service Workers and the Push API. Local IPs (e.g., `http://192.168.x.x`) fail silently.
2. **Browser Blocking (Brave):** Brave Shields aggressively blocks notification requests and payloads by default.
3. **OS Battery Optimization:** Android often kills background browser processes unless they are given unrestricted battery usage.
4. **Lack of Priority Headers:** Android's FCM (Firebase Cloud Messaging) handles push wakeups better if the push payload explicitly defines a high urgency and a time-to-live (TTL).
5. **No Immediate Feedback:** Currently, the app only sends pushes at scheduled times, making it very difficult to know if the subscription actually succeeded or if the OS/browser is blocking the delivery.

We will add a "Test Push" feature for immediate feedback, add priority headers to the backend push requests, and add explicit UI diagnostics so you know exactly what is blocking the notifications.

## 2. Steps
1. **Backend - Add Priority Headers & Test Endpoint**:
   - Update `backend/app/services/push_sender.py` to add `ttl=43200` (12 hours) and `headers={"Urgency": "high"}` to the `pywebpush` call. This tells Google Play Services to wake up the Android device promptly.
   - In `backend/app/routes/push.py`, add a new `POST /subscriptions/{subscription_id}/test` endpoint that triggers an immediate test push to a specific device.
2. **Frontend - Add "Test Push" Button**:
   - In `frontend-web/src/lib/push.ts`, add a `testSubscription(id)` function.
   - In `frontend-web/src/routes/settings/+page.svelte`, add a "Test" button next to the "Remove" button in the device list. This allows you to verify that notifications work immediately after subscribing.
3. **Frontend - UI Diagnostics & Warnings**:
   - Enhance the settings page to show explicit instructions for Android users:
     - Warn that **HTTPS is required** if push is marked as unsupported.
     - Add a note to **disable Brave Shields** for the app.
     - Add a note to set **Battery Optimization to "Unrestricted"** for Chrome/Brave.
4. **Frontend - Service Worker Updates**:
   - Update `subscribeThisDevice` to call `await registration.update()` to ensure the browser fetches the latest `sw.js` before requesting the subscription.

## 3. Rollout
- No database schema changes are required.
- The standard `docker compose build && docker compose up -d` will deploy the changes.
- Ensure your `.env` has valid VAPID keys generated (the UI already catches the 503 error if they are missing).
- **Crucial:** You must be accessing the app via a secure context (like Tailscale with HTTPS enabled, or a reverse proxy with SSL). If you access it via `http://192.168.68.126`, Android will not allow notifications.
