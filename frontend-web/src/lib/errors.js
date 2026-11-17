// Turns failures into short plain-English sentences. Never returns server text that isn't
// clearly a validation message, so people never see raw technical output.

export class ApiError extends Error {
  /**
   * @param {number} status HTTP status code
   * @param {unknown} detail parsed `detail` from the server response, or its text
   * @param {string} [raw] the full response text. Kept in `message` for code that matches on it
   *   (never shown to people; use describeError for that).
   */
  constructor(status, detail, raw = '') {
    super(`${status} ${raw}`.trim());
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

const OFFLINE =
  "You appear to be offline or the server can't be reached. Check your connection and try again.";
const GENERIC = 'Something went wrong. Please try again.';

/** @param {unknown} detail */
function readableDetail(detail) {
  if (typeof detail === 'string') {
    const text = detail.trim();
    // Reject anything that looks like raw JSON, HTML or a stack trace.
    if (text && text.length <= 200 && !/^[\[{<]/.test(text) && !/Traceback|\n\s+at /.test(text)) return text;
    return null;
  }
  if (Array.isArray(detail) && detail.length && typeof detail[0]?.msg === 'string') {
    return detail[0].msg;
  }
  return null;
}

/**
 * @param {unknown} error
 * @returns {string}
 */
export function describeError(error) {
  if (error instanceof ApiError) {
    const { status, detail } = error;
    if (status === 401) return "You've been signed out. Please sign in again.";
    if (status === 403) return "You don't have permission to do that.";
    if (status === 404) return "That couldn't be found. It may have been removed.";
    if (status === 408 || status === 429) return 'Too many requests. Wait a moment and try again.';
    if (status === 400 || status === 422) {
      return readableDetail(detail) || "Some of that wasn't accepted. Check what you entered and try again.";
    }
    if (status >= 500) return 'Something went wrong on the server. Please try again in a moment.';
    return GENERIC;
  }
  if (error && typeof error === 'object' && 'name' in error && error.name === 'AbortError') {
    return 'That took too long. Please try again.';
  }
  if (error instanceof TypeError) return OFFLINE; // what fetch throws when nothing answers
  return GENERIC;
}

/**
 * When the session has ended, the server answers API calls with a redirect to the login page, and the
 * browser follows it and hands back the login page's HTML with a 200 status. That is "signed out".
 * @param {{ redirected?: boolean, url?: string }} response
 * @returns {boolean}
 */
export function isSignedOutRedirect(response) {
  if (!response || !response.redirected || typeof response.url !== 'string') return false;
  try {
    return new URL(response.url, 'http://localhost').pathname.startsWith('/login');
  } catch {
    return false;
  }
}

/**
 * Only ever lets a person be sent to a path inside this app.
 * @param {string | null | undefined} target
 * @returns {string}
 */
export function safeRedirectPath(target) {
  const fallback = '/mood-entry';
  if (typeof target !== 'string' || !target.startsWith('/') || target.startsWith('//') || target.includes('\\')) {
    return fallback;
  }
  if (target === '/login' || target.startsWith('/login?') || target.startsWith('/login/')) return fallback;
  return target;
}
