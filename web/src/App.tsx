import { useCallback, useState } from 'react'
import { postChat, ChatApiError } from './api/chat'
import { CrisisBanner } from './components/CrisisBanner'
import { ChatPanel } from './components/ChatPanel'
import { introMessages } from './content/intro'
import { clearSessionId, getSessionId, setSessionId } from './session'
import type { ChatMessage, ResourceItem } from './types/chat'
import './App.css'

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => introMessages())
  const [stickyCrisis, setStickyCrisis] = useState(false)
  const [crisisResources, setCrisisResources] = useState<ResourceItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const sendMessage = useCallback(async (text: string) => {
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', text }])
    setLoading(true)

    const sid = getSessionId()
    try {
      const res = await postChat(text, sid)
      setSessionId(res.session_id)
      if (res.risk_level === 'medium' || res.risk_level === 'high') {
        setStickyCrisis(true)
        if (res.resources.length > 0) {
          setCrisisResources(res.resources)
        }
      }
      setMessages((prev) => [...prev, { role: 'assistant', text: res.reply_text }])
    } catch (e) {
      if (e instanceof ChatApiError) {
        setError(e.detail ?? e.message)
      } else {
        setError(e instanceof Error ? e.message : 'Something went wrong.')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  const resetSession = useCallback(() => {
    clearSessionId()
    setMessages(introMessages())
    setStickyCrisis(false)
    setCrisisResources([])
    setError(null)
  }, [])

  return (
    <div className="app">
      <header className="hero">
        <div className="hero__brand">
          <div className="hero__logo" aria-hidden />
          <h1 className="hero__title">MindCare</h1>
        </div>
        <p className="hero__tagline">Your compassionate guide to emotional wellness</p>
        <p className="hero__hint">Share what’s on your mind below. I’m here to listen and offer supportive guidance.</p>
      </header>

      <main className="main">
        {stickyCrisis ? <CrisisBanner resources={crisisResources} /> : null}

        <ChatPanel messages={messages} disabled={loading} error={error} onSend={sendMessage} />

        <p className="footnote">
          MindCare is not therapy or emergency care. If you may be in danger, use the resources above or contact local
          emergency services.
        </p>
        <button type="button" className="link-button" onClick={resetSession}>
          Start a new conversation
        </button>
      </main>
    </div>
  )
}
