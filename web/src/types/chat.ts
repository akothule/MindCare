export type RiskLevel = 'low' | 'medium' | 'high'

export type PolicyAction =
  | 'normal'
  | 'medium_llm'
  | 'medium_template'
  | 'high_template'
  | 'high_policy_template'
  | 'fallback'
  | 'blocked'

export interface ResourceItem {
  label: string
  value: string
}

export interface ChatResponse {
  session_id: string
  request_id: string
  reply_text: string
  risk_level: RiskLevel
  policy_action: PolicyAction
  resources: ResourceItem[]
  fallback_reason: string | null
  latency_ms: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
}
