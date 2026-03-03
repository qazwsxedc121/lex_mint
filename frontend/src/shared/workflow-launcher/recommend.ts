import type { Workflow } from '../../types/workflow';
import type { LauncherRecentItem, LauncherRecommendationContext } from './types';

const PRIMARY_SELECTION_INPUT_KEYS = new Set(['input', 'text', 'selected_text']);
const KEYWORDS_BY_EXTENSION: Record<string, string[]> = {
  md: ['rewrite', 'polish', 'summary', 'summarize', 'translate', '润色', '总结', '改写'],
  txt: ['rewrite', 'polish', 'summary', 'summarize', '润色', '总结', '改写'],
  py: ['python', 'code', 'refactor', 'clarity'],
  ts: ['typescript', 'code', 'refactor', 'clarity'],
  tsx: ['react', 'tsx', 'component', 'code', 'refactor'],
  js: ['javascript', 'code', 'refactor', 'clarity'],
  jsx: ['react', 'jsx', 'component', 'code', 'refactor'],
  json: ['json', 'format', 'schema'],
  yaml: ['yaml', 'config', 'settings'],
  yml: ['yaml', 'config', 'settings'],
  css: ['css', 'style', 'ui'],
  html: ['html', 'markup', 'ui'],
};

const normalizeSelectionKey = (key: string): string => key.replace(/^_+/, '').toLowerCase();

const workflowRequiresSelection = (workflow: Workflow): boolean =>
  workflow.input_schema.some(
    (inputDef) => inputDef.required && PRIMARY_SELECTION_INPUT_KEYS.has(normalizeSelectionKey(inputDef.key))
  );

const fileExtension = (filePath: string | undefined): string => {
  if (!filePath) {
    return '';
  }
  const lastDot = filePath.lastIndexOf('.');
  if (lastDot < 0 || lastDot === filePath.length - 1) {
    return '';
  }
  return filePath.slice(lastDot + 1).toLowerCase();
};

const keywordScore = (workflow: Workflow, ext: string): number => {
  const keywords = KEYWORDS_BY_EXTENSION[ext];
  if (!keywords || keywords.length === 0) {
    return 0;
  }
  const haystack = `${workflow.name} ${workflow.description || ''}`.toLowerCase();
  return keywords.some((keyword) => haystack.includes(keyword)) ? 20 : 0;
};

const recentScore = (workflowId: string, recents: LauncherRecentItem[], now: number): number => {
  const entry = recents.find((item) => item.id === workflowId);
  if (!entry) {
    return 0;
  }
  const ageHours = Math.max(0, (now - entry.ts) / 3_600_000);
  return Math.max(0, 80 - ageHours);
};

interface RecommendOptions {
  workflows: Workflow[];
  favorites: Set<string>;
  recents: LauncherRecentItem[];
  context: LauncherRecommendationContext;
  now?: number;
}

export const recommendWorkflows = ({
  workflows,
  favorites,
  recents,
  context,
  now = Date.now(),
}: RecommendOptions): { recommended: Workflow[]; others: Workflow[] } => {
  const ext = fileExtension(context.filePath);
  const ranked = workflows
    .map((workflow) => {
      let score = workflow.enabled ? 10 : -20;
      if (favorites.has(workflow.id)) {
        score += 100;
      }
      score += recentScore(workflow.id, recents, now);

      if (context.requiredScenario && workflow.scenario !== context.requiredScenario) {
        score -= 200;
      } else if (context.module === 'projects' && workflow.scenario === 'editor_rewrite') {
        score += 40;
      }

      score += keywordScore(workflow, ext);

      if (context.module === 'projects' && context.hasSelection === false && workflowRequiresSelection(workflow)) {
        score -= 30;
      }

      return { workflow, score };
    })
    .sort((a, b) => {
      if (b.score !== a.score) {
        return b.score - a.score;
      }
      if (b.workflow.updated_at !== a.workflow.updated_at) {
        return b.workflow.updated_at.localeCompare(a.workflow.updated_at);
      }
      return a.workflow.name.localeCompare(b.workflow.name);
    });

  const recommended = ranked
    .filter((item) => item.score > 15)
    .slice(0, 5)
    .map((item) => item.workflow);
  const recommendedIds = new Set(recommended.map((item) => item.id));
  const others = ranked
    .map((item) => item.workflow)
    .filter((workflow) => !recommendedIds.has(workflow.id));

  return { recommended, others };
};
