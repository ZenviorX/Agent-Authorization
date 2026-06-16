export type Decision = 'allow' | 'deny' | 'confirm' | 'review';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type RequestStatus = 'pending' | 'approved' | 'rejected' | 'blocked';

export interface Overview {
  totalRequests: number;
  blockedRequests: number;
  confirmRequests: number;
  averageLatencyMs: number;
  policyHitRate: number;
  securityScore: number;
  activePolicies: number;
  agentsOnline: number;
}

export interface GatewayRequest {
  id: string;
  agent: string;
  user: string;
  tool: string;
  target: string;
  intent: string;
  risk: RiskLevel;
  decision: Decision;
  status: RequestStatus;
  createdAt: string;
  reason: string;
  policy: string;
}

export interface PolicyRule {
  id: string;
  name: string;
  description: string;
  scope: string;
  effect: Decision;
  priority: number;
  enabled: boolean;
  updatedAt: string;
  examples: string[];
}

export interface AuditLog {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  resource: string;
  result: Decision;
  detail: string;
}

export interface EvaluationMetric {
  name: string;
  value: number;
  unit: string;
  trend: 'up' | 'down' | 'flat';
  description: string;
}

export interface SystemSetting {
  key: string;
  name: string;
  value: string;
  description: string;
}

export type AgentRunMode =
  | 'fake_check'
  | 'fake_plan'
  | 'fake_run'
  | 'llm_plan'
  | 'llm_run'
  | 'stepwise_llm';

export interface AgentCommandInput {
  user: string;
  userInput: string;
  mode: AgentRunMode;
  maxSteps: number;
  riskBudget: number;
}

export interface AgentCommandResponse {
  ok: boolean;
  fromMock?: boolean;
  endpoint?: string;
  error?: string;
  data: Record<string, unknown>;
}
