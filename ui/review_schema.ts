// Approval request UI model -- mirrors the database schema

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired';
export type AgentRunType = 'platform' | 'builder';
export type AgentRunStatus = 'queued' | 'running' | 'awaiting_approval' | 'completed' | 'failed' | 'cancelled';

export interface ApprovalRequestViewModel {
  id: string;
  agentRunId: string;
  requestedAction: string;
  requestedByAgent: string;
  riskLevel: RiskLevel;
  approvalStatus: ApprovalStatus;
  requestedAt: string;  // ISO 8601
  decidedAt?: string;
  decidedBy?: string;
  decisionNotes?: string;
}

export interface AgentRunViewModel {
  id: string;
  agentName: string;
  runType: AgentRunType;
  status: AgentRunStatus;
  userPrompt: string;
  summarizedPlan?: string;
  approvalRequired: boolean;
  startedAt: string;
  completedAt?: string;
  errorMessage?: string;
}

export interface CreateApprovalRequest {
  agentRunId: string;
  requestedAction: string;
  riskLevel: RiskLevel;
}

export interface ApprovalDecisionRequest {
  decision: 'approved' | 'rejected';
  decidedBy: string;
  decisionNotes?: string;
}

export interface ReindexRequest {
  basePath: string;
  recreate: boolean;
}

export interface ReindexResponse {
  indexedDocumentCount: number;
  status: string;
}

export interface HealthResponse {
  status: string;
  agentsReady: boolean;
  dbConnected: boolean;
}

// Safe filename regex
export const SAFE_FILENAME_REGEX = /^[a-z0-9][a-z0-9\-_.]{0,127}$/;

// UUID validation regex
export const UUID_REGEX = /^[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[1-5][0-9a-fA-F]{3}\-[89abAB][0-9a-fA-F]{3}\-[0-9a-fA-F]{12}$/;

// Risk level colors for UI
export const RISK_LEVEL_COLORS: Record<RiskLevel, string> = {
  low: '#22c55e',      // green
  medium: '#eab308',   // yellow
  high: '#f97316',     // orange
  critical: '#ef4444', // red
};

// Agent display names
export const AGENT_DISPLAY_NAMES: Record<string, string> = {
  ingestion_orchestrator: 'Ingestion Orchestrator',
  analysis_orchestrator: 'Analysis Orchestrator',
  review_gatekeeper: 'Review Gatekeeper',
  dev_copilot: 'Dev Copilot',
  project_pal: 'Project PAL',
  forensic_data_agent: 'Forensic Data Agent',
};
