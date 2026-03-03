import type { Workflow, WorkflowScenario } from '../../types/workflow';

export interface LauncherRecentItem {
  id: string;
  ts: number;
}

export interface LauncherRecommendationContext {
  module: 'projects' | 'workflows';
  requiredScenario?: WorkflowScenario;
  filePath?: string;
  hasSelection?: boolean;
}

export interface WorkflowLauncherSection {
  key: 'recommended' | 'recent' | 'favorites' | 'all';
  items: Workflow[];
}
