import type { ChatMessage } from '../types/chat'

interface Props {
  messages: ChatMessage[]
  disabled: boolean
  error: string | null
  onSend: (text: string) => void
}

export function ChatPanel({ messages, disabled, error, onSend }: Props) {
  return (
    <div className="chat-panel">
      <div className="chat-panel__header">
        <span className="chat-panel__title">MindCare chat</span>
      </div>

      <div className="chat-panel__messages" role="log" aria-live="polite" aria-relevant="additions">
        {messages.map((m, i) => (
          <div
            key={`${m.role}-${i}-${m.text.slice(0, 24)}`}
            className={`chat-bubble chat-bubble--${m.role}`}
          >
            <span className="chat-bubble__role">{m.role === 'user' ? 'You' : 'MindCare'}</span>
            <div className="chat-bubble__text">{m.text}</div>
          </div>
        ))}
      </div>

      {error ? (
        <p className="chat-panel__error" role="alert">
          {error}
        </p>
      ) : null}

      <form
        className="chat-panel__form"
        onSubmit={(e) => {
          e.preventDefault()
          const form = e.currentTarget
          const input = form.elements.namedItem('message') as HTMLInputElement
          const text = input.value.trim()
          if (!text || disabled) return
          input.value = ''
          onSend(text)
        }}
      >
        <input
          id="chat-message"
          name="message"
          type="text"
          className="chat-panel__input"
          placeholder="Type something…"
          autoComplete="off"
          disabled={disabled}
          aria-label="Message"
        />
        <button type="submit" className="chat-panel__send" disabled={disabled}>
          Send
        </button>
      </form>
    </div>
  )
}
