import type { ChatResponse } from '../types/chat'

function apiBase(): string {
  const base = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, '')
  if (!base) {
    throw new Error(
      'VITE_API_BASE_URL is not set. Copy web/.env.example to web/.env and set it (e.g. http://127.0.0.1:8000).',
    )
  }
  return base
}

export class ChatApiError extends Error {
  readonly status: number
  readonly detail?: string

  constructor(message: string, status: number, detail?: string) {
    super(message)
    this.name = 'ChatApiError'
    this.status = status
    this.detail = detail
  }
}

export async function postChat(
  message: string,
  sessionId: string | null,
): Promise<ChatResponse> {
  const res = await fetch(`${apiBase()}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...(sessionId ? { session_id: sessionId } : {}),
      message,
      metadata: { locale: 'en-US' },
    }),
  })

  if (!res.ok) {
    let detail: string | undefined
    try {
      const body = (await res.json()) as { detail?: string | unknown }
      if (typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      /* ignore */
    }
    throw new ChatApiError(
      detail ?? `Request failed (${res.status})`,
      res.status,
      detail,
    )
  }

  return (await res.json()) as ChatResponse
}
