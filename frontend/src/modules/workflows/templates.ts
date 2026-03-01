import type { WorkflowCreate } from '../../types/workflow';

export interface WorkflowTemplatePreset {
  id: string;
  nameKey: string;
  descriptionKey: string;
  workflowNameKey: string;
  workflowDescriptionKey: string;
  name: string;
  description: string;
  workflow: WorkflowCreate;
}

export const WORKFLOW_TEMPLATE_PRESETS: WorkflowTemplatePreset[] = [
  {
    id: 'summarize_then_translate',
    nameKey: 'templates.summarizeTranslate.name',
    descriptionKey: 'templates.summarizeTranslate.description',
    workflowNameKey: 'templates.summarizeTranslate.workflowName',
    workflowDescriptionKey: 'templates.summarizeTranslate.workflowDescription',
    name: 'Summarize + Translate',
    description: 'Summarize input first, then translate to target language if needed.',
    workflow: {
      name: 'Summarize + Translate',
      description: 'Summarize long text and optionally translate',
      enabled: true,
      input_schema: [
        { key: 'text', type: 'string', required: true, description: 'Raw text to process' },
        { key: 'target_language', type: 'string', required: false, default: 'English' },
        { key: 'need_translation', type: 'boolean', required: false, default: true },
      ],
      entry_node_id: 'start_1',
      nodes: [
        { id: 'start_1', type: 'start', next_id: 'llm_summary' },
        {
          id: 'llm_summary',
          type: 'llm',
          prompt_template: 'Please summarize the following text in bullet points:\n\n{{inputs.text}}',
          output_key: 'summary',
          next_id: 'cond_translate',
        },
        {
          id: 'cond_translate',
          type: 'condition',
          expression: 'inputs.need_translation == true',
          true_next_id: 'llm_translate',
          false_next_id: 'end_summary',
        },
        {
          id: 'llm_translate',
          type: 'llm',
          prompt_template: 'Translate the following summary to {{inputs.target_language}}:\n\n{{ctx.summary}}',
          output_key: 'translated_summary',
          next_id: 'end_translated',
        },
        {
          id: 'end_summary',
          type: 'end',
          result_template: '{{ctx.summary}}',
        },
        {
          id: 'end_translated',
          type: 'end',
          result_template: '{{ctx.translated_summary}}',
        },
      ],
    },
  },
  {
    id: 'meeting_minutes',
    nameKey: 'templates.meetingMinutes.name',
    descriptionKey: 'templates.meetingMinutes.description',
    workflowNameKey: 'templates.meetingMinutes.workflowName',
    workflowDescriptionKey: 'templates.meetingMinutes.workflowDescription',
    name: 'Meeting Minutes',
    description: 'Extract action items, risks and owners from meeting notes.',
    workflow: {
      name: 'Meeting Minutes',
      description: 'Generate structured meeting minutes',
      enabled: true,
      input_schema: [
        { key: 'notes', type: 'string', required: true, description: 'Meeting notes' },
      ],
      entry_node_id: 'start_1',
      nodes: [
        { id: 'start_1', type: 'start', next_id: 'llm_extract' },
        {
          id: 'llm_extract',
          type: 'llm',
          prompt_template: [
            'Convert the meeting notes into markdown with sections:',
            '1) Summary',
            '2) Decisions',
            '3) Action Items (owner + due date if available)',
            '4) Risks',
            '',
            '{{inputs.notes}}',
          ].join('\n'),
          output_key: 'minutes',
          next_id: 'end_1',
        },
        { id: 'end_1', type: 'end', result_template: '{{ctx.minutes}}' },
      ],
    },
  },
  {
    id: 'draft_review',
    nameKey: 'templates.draftReview.name',
    descriptionKey: 'templates.draftReview.description',
    workflowNameKey: 'templates.draftReview.workflowName',
    workflowDescriptionKey: 'templates.draftReview.workflowDescription',
    name: 'Draft Reviewer',
    description: 'Review text and route to strict or light feedback.',
    workflow: {
      name: 'Draft Reviewer',
      description: 'Quality review with branch by strictness',
      enabled: true,
      input_schema: [
        { key: 'draft', type: 'string', required: true, description: 'Draft content' },
        { key: 'strict_mode', type: 'boolean', required: false, default: false },
      ],
      entry_node_id: 'start_1',
      nodes: [
        { id: 'start_1', type: 'start', next_id: 'cond_1' },
        {
          id: 'cond_1',
          type: 'condition',
          expression: 'inputs.strict_mode == true',
          true_next_id: 'llm_strict',
          false_next_id: 'llm_light',
        },
        {
          id: 'llm_strict',
          type: 'llm',
          prompt_template: [
            'Review the draft with strict standards.',
            'Return: major issues, minor issues, and rewrite suggestions.',
            '',
            '{{inputs.draft}}',
          ].join('\n'),
          output_key: 'review',
          next_id: 'end_1',
        },
        {
          id: 'llm_light',
          type: 'llm',
          prompt_template: [
            'Review the draft briefly.',
            'Return top 3 improvements and one polished paragraph.',
            '',
            '{{inputs.draft}}',
          ].join('\n'),
          output_key: 'review',
          next_id: 'end_1',
        },
        { id: 'end_1', type: 'end', result_template: '{{ctx.review}}' },
      ],
    },
  },
];
