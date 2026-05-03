import type { ChatMessage } from '../types/chat'

/** Shown as the first assistant bubble when the chat opens or after “Start a new conversation”. */
const INTRO_ASSISTANT_TEXT =
  "Hello, I'm MindCare. I'm glad you're here.\n\n" +
  "This is a space to share what you're going through at your own pace. " +
  "What's on your mind today?"

export function introMessages(): ChatMessage[] {
  return [{ role: 'assistant', text: INTRO_ASSISTANT_TEXT }]
}
