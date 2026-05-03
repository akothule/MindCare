const STORAGE_KEY = 'mindcare_session_id'

export function getSessionId(): string | null {
  const v = localStorage.getItem(STORAGE_KEY)
  return v && v.trim() ? v.trim() : null
}

export function setSessionId(id: string): void {
  localStorage.setItem(STORAGE_KEY, id)
}

export function clearSessionId(): void {
  localStorage.removeItem(STORAGE_KEY)
}
