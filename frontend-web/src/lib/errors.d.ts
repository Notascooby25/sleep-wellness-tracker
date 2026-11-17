export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown);
}
export function describeError(error: unknown): string;
export function safeRedirectPath(target: string | null | undefined): string;
