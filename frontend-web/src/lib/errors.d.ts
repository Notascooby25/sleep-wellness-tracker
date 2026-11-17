export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, raw?: string);
}
export function describeError(error: unknown): string;
export function isSignedOutRedirect(response: { redirected?: boolean; url?: string }): boolean;
export function safeRedirectPath(target: string | null | undefined): string;
