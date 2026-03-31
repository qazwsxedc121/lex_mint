import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import CodeMirror from '@uiw/react-codemirror';
import type { EditorView } from '@codemirror/view';
import { ProjectNotice } from './ProjectNotice';
import { EditorToolbar } from './EditorToolbar';
import { InlineRewritePanel } from './InlineRewritePanel';
import { CodeBlock } from '../../../shared/chat/components/CodeBlock';
import { MermaidBlock } from '../../../shared/chat/components/MermaidBlock';
import { SvgBlock } from '../../../shared/chat/components/SvgBlock';
import type { FileContent } from '../../../types/project';
import type { LauncherRecentItem } from '../../../shared/workflow-launcher/types';
import type { LauncherRecommendationContext } from '../../../shared/workflow-launcher/types';
import type { Workflow, WorkflowInputDef } from '../../../types/workflow';

interface FileViewerEditorContentProps {
  notice: Parameters<typeof ProjectNotice>[0]['notice'];
  onDismissNotice: () => void;
  content: FileContent;
  hasUnsavedChanges: boolean;
  saving: boolean;
  saveSuccess: boolean;
  saveError: string | null;
  saveConflictState: 'none' | 'detected' | 'remoteLoaded';
  conflictBusy: boolean;
  onLoadLatestAfterConflict?: () => void;
  onRestoreConflictDraft?: () => void;
  onCopyConflictDraft?: () => void;
  onSave: () => void;
  onCancel: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onFind: () => void;
  canUndo: boolean;
  canRedo: boolean;
  lineWrapping: boolean;
  onToggleLineWrapping: (next: boolean) => void;
  lineNumbers: boolean;
  onToggleLineNumbers: (next: boolean) => void;
  fontSize: 'small' | 'medium' | 'large';
  onChangeFontSize: (next: 'small' | 'medium' | 'large') => void;
  isMarkdownFile: boolean;
  markdownViewMode: 'edit' | 'preview';
  onSetMarkdownViewMode: (mode: 'edit' | 'preview') => void;
  autoSaveBeforeAgentSend: boolean;
  onToggleAutoSaveBeforeAgentSend: (next: boolean) => void;
  cursorPosition: { line: number; col: number };
  fileInfo: { encoding: string; mimeType: string; size: string };
  chatSidebarOpen: boolean;
  onToggleChatSidebar: () => void;
  onInsertToChat: () => void;
  insertToChatDisabled: boolean;
  insertToChatTitle: string;
  onSendToAgent: () => void;
  sendToAgentDisabled: boolean;
  sendToAgentTitle: string;
  onInlineRewrite: () => void;
  inlineRewriteDisabled: boolean;
  inlineRewriteTitle: string;
  onProjectWorkflow: () => void;
  projectWorkflowDisabled: boolean;
  projectWorkflowTitle: string;
  projectId: string;
  inlineRewriteOpen: boolean;
  inlineRewriteStreaming: boolean;
  inlineRewriteSourceText: string;
  inlineRewritePreview: string;
  inlineRewriteError: string | null;
  rewriteWorkflowOptions: Workflow[];
  selectedWorkflowId: string;
  inlineRewriteWorkflowsLoading: boolean;
  inlineRewriteWorkflowInputs: WorkflowInputDef[];
  inlineRewriteWorkflowNodeIds: string[];
  inlineRewriteInputs: Record<string, unknown>;
  favorites: Set<string>;
  recents: LauncherRecentItem[];
  inlineRewriteRecommendationContext: LauncherRecommendationContext;
  onInlineRewriteWorkflowChange: (workflowId: string) => void;
  onToggleInlineRewriteFavorite: (workflowId: string) => void;
  onInlineRewriteInputChange: (key: string, value: unknown) => void;
  onStartInlineRewrite: () => void;
  onStopInlineRewrite: () => void;
  showInlineRewriteNoSelectionPrompt: boolean;
  onRunInlineRewriteEmpty: () => void;
  onRunInlineRewriteFullFile: () => void;
  onCancelInlineRewriteNoSelection: () => void;
  onAcceptInlineRewrite: () => void;
  onCloseInlineRewrite: () => void;
  onOpenWorkflowsPage: () => void;
  showMarkdownPreview: boolean;
  value: string;
  isDarkMode: boolean;
  extensions: NonNullable<Parameters<typeof CodeMirror>[0]['extensions']>;
  onEditorCreate: (view: EditorView) => void;
  onEditorChange: (value: string) => void;
  prepareMarkdownForPreview: (text: string) => string;
}

export const FileViewerEditorContent = ({
  notice,
  onDismissNotice,
  content,
  hasUnsavedChanges,
  saving,
  saveSuccess,
  saveError,
  saveConflictState,
  conflictBusy,
  onLoadLatestAfterConflict,
  onRestoreConflictDraft,
  onCopyConflictDraft,
  onSave,
  onCancel,
  onUndo,
  onRedo,
  onFind,
  canUndo,
  canRedo,
  lineWrapping,
  onToggleLineWrapping,
  lineNumbers,
  onToggleLineNumbers,
  fontSize,
  onChangeFontSize,
  isMarkdownFile,
  markdownViewMode,
  onSetMarkdownViewMode,
  autoSaveBeforeAgentSend,
  onToggleAutoSaveBeforeAgentSend,
  cursorPosition,
  fileInfo,
  chatSidebarOpen,
  onToggleChatSidebar,
  onInsertToChat,
  insertToChatDisabled,
  insertToChatTitle,
  onSendToAgent,
  sendToAgentDisabled,
  sendToAgentTitle,
  onInlineRewrite,
  inlineRewriteDisabled,
  inlineRewriteTitle,
  onProjectWorkflow,
  projectWorkflowDisabled,
  projectWorkflowTitle,
  projectId,
  inlineRewriteOpen,
  inlineRewriteStreaming,
  inlineRewriteSourceText,
  inlineRewritePreview,
  inlineRewriteError,
  rewriteWorkflowOptions,
  selectedWorkflowId,
  inlineRewriteWorkflowsLoading,
  inlineRewriteWorkflowInputs,
  inlineRewriteWorkflowNodeIds,
  inlineRewriteInputs,
  favorites,
  recents,
  inlineRewriteRecommendationContext,
  onInlineRewriteWorkflowChange,
  onToggleInlineRewriteFavorite,
  onInlineRewriteInputChange,
  onStartInlineRewrite,
  onStopInlineRewrite,
  showInlineRewriteNoSelectionPrompt,
  onRunInlineRewriteEmpty,
  onRunInlineRewriteFullFile,
  onCancelInlineRewriteNoSelection,
  onAcceptInlineRewrite,
  onCloseInlineRewrite,
  onOpenWorkflowsPage,
  showMarkdownPreview,
  value,
  isDarkMode,
  extensions,
  onEditorCreate,
  onEditorChange,
  prepareMarkdownForPreview,
}: FileViewerEditorContentProps) => {
  const markdownPreviewComponents = useMemo(
    () => ({
      code({ inline, className, children, ...props }: any) {
        const match = /language-([a-zA-Z0-9_-]+)/.exec(className || '');
        const languageName = match ? match[1].toLowerCase() : '';
        const valueText = String(children).replace(/\n$/, '');
        const isInline = typeof inline === 'boolean' ? inline : !className;

        if (!isInline) {
          if (languageName === 'mermaid') {
            return <MermaidBlock value={valueText} />;
          }
          if (languageName === 'svg') {
            return <SvgBlock value={valueText} />;
          }
          return <CodeBlock language={languageName || 'text'} value={valueText} />;
        }

        return (
          <code
            className="rounded bg-gray-100 px-1 py-0.5 text-[13px] text-gray-900 dark:bg-gray-800 dark:text-gray-100"
            {...props}
          >
            {children}
          </code>
        );
      },
      table({ children }: any) {
        return (
          <div className="my-4 overflow-x-auto rounded-lg border border-gray-300 dark:border-gray-600">
            <table className="w-full min-w-[960px] border-collapse text-sm leading-6">{children}</table>
          </div>
        );
      },
      a({ href, children, ...props }: any) {
        const isExternal = typeof href === 'string' && /^https?:\/\//i.test(href);
        const externalProps = isExternal ? { target: '_blank', rel: 'noreferrer noopener' } : {};

        return (
          <a href={href} {...externalProps} {...props}>
            {children}
          </a>
        );
      },
    }),
    []
  );

  return (
    <>
      <ProjectNotice notice={notice} onDismiss={onDismissNotice} />
      <EditorToolbar
        onSave={onSave}
        onCancel={onCancel}
        hasUnsavedChanges={hasUnsavedChanges}
        saving={saving}
        saveSuccess={saveSuccess}
        saveError={saveError}
        saveConflictState={saveConflictState}
        conflictBusy={conflictBusy}
        onLoadLatestAfterConflict={onLoadLatestAfterConflict}
        onRestoreConflictDraft={onRestoreConflictDraft}
        onCopyConflictDraft={onCopyConflictDraft}
        onUndo={onUndo}
        onRedo={onRedo}
        onFind={onFind}
        canUndo={canUndo}
        canRedo={canRedo}
        lineWrapping={lineWrapping}
        onToggleLineWrapping={onToggleLineWrapping}
        lineNumbers={lineNumbers}
        onToggleLineNumbers={onToggleLineNumbers}
        fontSize={fontSize}
        onChangeFontSize={onChangeFontSize}
        isMarkdownFile={isMarkdownFile}
        markdownViewMode={markdownViewMode}
        onSetMarkdownViewMode={onSetMarkdownViewMode}
        autoSaveBeforeAgentSend={autoSaveBeforeAgentSend}
        onToggleAutoSaveBeforeAgentSend={onToggleAutoSaveBeforeAgentSend}
        cursorPosition={cursorPosition}
        fileInfo={fileInfo}
        chatSidebarOpen={chatSidebarOpen}
        onToggleChatSidebar={onToggleChatSidebar}
        onInsertToChat={onInsertToChat}
        insertToChatDisabled={insertToChatDisabled}
        insertToChatTitle={insertToChatTitle}
        onSendToAgent={onSendToAgent}
        sendToAgentDisabled={sendToAgentDisabled}
        sendToAgentTitle={sendToAgentTitle}
        onInlineRewrite={onInlineRewrite}
        inlineRewriteDisabled={inlineRewriteDisabled}
        inlineRewriteTitle={inlineRewriteTitle}
        onProjectWorkflow={onProjectWorkflow}
        projectWorkflowDisabled={projectWorkflowDisabled}
        projectWorkflowTitle={projectWorkflowTitle}
      />
      <InlineRewritePanel
        projectId={projectId}
        currentFilePath={content.path}
        isOpen={inlineRewriteOpen}
        isStreaming={inlineRewriteStreaming}
        sourceText={inlineRewriteSourceText}
        rewrittenText={inlineRewritePreview}
        error={inlineRewriteError}
        workflows={rewriteWorkflowOptions}
        selectedWorkflowId={selectedWorkflowId}
        workflowLoading={inlineRewriteWorkflowsLoading}
        workflowInputs={inlineRewriteWorkflowInputs}
        workflowNodeIds={inlineRewriteWorkflowNodeIds}
        inputValues={inlineRewriteInputs}
        favorites={favorites}
        recents={recents}
        recommendationContext={inlineRewriteRecommendationContext}
        onWorkflowChange={onInlineRewriteWorkflowChange}
        onToggleFavorite={onToggleInlineRewriteFavorite}
        onInputChange={onInlineRewriteInputChange}
        onGenerate={onStartInlineRewrite}
        onStop={onStopInlineRewrite}
        showNoSelectionPrompt={showInlineRewriteNoSelectionPrompt}
        onNoSelectionRunEmpty={onRunInlineRewriteEmpty}
        onNoSelectionRunFullFile={onRunInlineRewriteFullFile}
        onNoSelectionRunCancel={onCancelInlineRewriteNoSelection}
        onAccept={onAcceptInlineRewrite}
        onReject={onCloseInlineRewrite}
        onClose={onCloseInlineRewrite}
        onOpenWorkflows={onOpenWorkflowsPage}
      />
      <div className="flex-1 min-h-0 w-full min-w-0 overflow-hidden">
        <div className={showMarkdownPreview ? 'hidden h-full' : 'h-full'}>
          <CodeMirror
            className="h-full"
            value={value}
            height="100%"
            theme={isDarkMode ? 'dark' : 'light'}
            extensions={extensions}
            onChange={onEditorChange}
            onCreateEditor={onEditorCreate}
            basicSetup={{
              lineNumbers,
              highlightActiveLineGutter: true,
              highlightSpecialChars: true,
              foldGutter: true,
              drawSelection: true,
              dropCursor: true,
              allowMultipleSelections: true,
              indentOnInput: true,
              syntaxHighlighting: true,
              bracketMatching: true,
              closeBrackets: true,
              autocompletion: true,
              rectangularSelection: true,
              crosshairCursor: true,
              highlightActiveLine: true,
              highlightSelectionMatches: true,
              closeBracketsKeymap: true,
              searchKeymap: true,
              foldKeymap: true,
              completionKeymap: true,
              lintKeymap: true,
            }}
          />
        </div>
        {showMarkdownPreview && (
          <div data-name="markdown-preview-pane" className="h-full overflow-auto bg-gray-50 dark:bg-gray-950 px-5 py-4">
            <div
              className={`
                mx-auto w-full max-w-5xl rounded-xl border border-gray-200 bg-white px-6 py-5 shadow-sm
                dark:border-gray-700 dark:bg-gray-900
                text-[15px] leading-8 text-gray-800 dark:text-gray-100 break-words
                [&_h1:first-child]:mt-0 [&_h2:first-child]:mt-0 [&_h3:first-child]:mt-0
                [&_h1]:mt-8 [&_h1]:mb-3 [&_h1]:text-3xl [&_h1]:font-semibold [&_h1]:tracking-tight [&_h1]:border-b [&_h1]:border-gray-200 [&_h1]:pb-2 [&_h1]:dark:border-gray-700
                [&_h2]:mt-7 [&_h2]:mb-3 [&_h2]:text-2xl [&_h2]:font-semibold
                [&_h3]:mt-6 [&_h3]:mb-2 [&_h3]:text-xl [&_h3]:font-semibold
                [&_p]:my-4 [&_p]:leading-8
                [&_strong]:font-semibold
                [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6
                [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6
                [&_li]:my-1.5
                [&_blockquote]:my-4 [&_blockquote]:border-l-4 [&_blockquote]:border-gray-300 [&_blockquote]:bg-gray-50 [&_blockquote]:px-3 [&_blockquote]:py-2 [&_blockquote]:text-gray-700 [&_blockquote]:dark:border-gray-600 [&_blockquote]:dark:bg-gray-800 [&_blockquote]:dark:text-gray-200
                [&_hr]:my-6 [&_hr]:border-gray-200 [&_hr]:dark:border-gray-700
                [&_a]:text-blue-600 [&_a]:underline [&_a]:underline-offset-2 [&_a]:dark:text-blue-400
                [&_table]:w-full [&_table]:border-collapse [&_table]:text-sm
                [&_thead]:bg-gray-100 [&_thead]:dark:bg-gray-800
                [&_tbody_tr:nth-child(even)]:bg-gray-50 [&_tbody_tr:nth-child(even)]:dark:bg-gray-800/50
                [&_th]:border [&_th]:border-gray-300 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold [&_th]:dark:border-gray-600
                [&_td]:border [&_td]:border-gray-300 [&_td]:px-3 [&_td]:py-2 [&_td]:align-top [&_td]:dark:border-gray-600
                [&_pre]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-lg
                [&_img]:my-4 [&_img]:max-w-full [&_img]:rounded-lg
              `}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={markdownPreviewComponents}
              >
                {prepareMarkdownForPreview(value)}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </>
  );
};
