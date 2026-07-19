// Bridges axios interceptors (plain JS, outside React) to the ToastContext
// (React state) — the interceptor calls notifyToast(), and ToastProvider
// registers itself as the handler on mount.
let handler = null

export function registerToastHandler(fn) {
  handler = fn
}

export function notifyToast(message, type = 'error') {
  handler?.(message, type)
}
