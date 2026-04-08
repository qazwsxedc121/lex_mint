import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { ChatModule } from './modules/chat';
import { ChatWelcome, ChatView } from './shared/chat';
import { ProjectsModule } from './modules/projects';
import { ProjectsWelcome } from './modules/projects/ProjectsWelcome';
import { ProjectExplorer } from './modules/projects/ProjectExplorer';
import { ProjectHomeView } from './modules/projects/ProjectHomeView';
import { ProjectWorkspaceLayout } from './modules/projects/ProjectWorkspaceLayout';
import { ProjectTabRedirect } from './modules/projects/ProjectTabRedirect';
import { ProjectSearchView } from './modules/projects/ProjectSearchView';
import { ProjectWorkflowsView } from './modules/projects/ProjectWorkflowsView';
import { ProjectAgentView } from './modules/projects/ProjectAgentView';
import { ProjectSettingsView } from './modules/projects/ProjectSettingsView';
import { SettingsModule } from './modules/settings';
import { AssistantsPage } from './modules/settings/AssistantsPage';
import { GetStartedPage } from './modules/settings/GetStartedPage';
import { ModelsPage } from './modules/settings/ModelsPage';
import { ProvidersPage } from './modules/settings/ProvidersPage';
import {
  AssistantsCreatePage,
  AssistantsEditPage,
  ModelsCreatePage,
  ModelsEditPage,
  ProvidersCreatePage,
  ProvidersEditPage,
} from './modules/settings/CrudPages';
import { KnowledgeBaseCreatePage } from './modules/settings/KnowledgeBaseCreatePage';
import { KnowledgeBaseEditPage } from './modules/settings/KnowledgeBaseEditPage';
import { TitleGenerationSettings } from './modules/settings/TitleGenerationSettings';
import { FollowupSettings } from './modules/settings/FollowupSettings';
import { CompressionSettings } from './modules/settings/CompressionSettings';
import { FileReferenceSettings } from './modules/settings/FileReferenceSettings';
import { TranslationSettings } from './modules/settings/TranslationSettings';
import { TTSSettings } from './modules/settings/TTSSettings';
import { KnowledgeBasesPage } from './modules/settings/KnowledgeBasesPage';
import { RagSettings } from './modules/settings/RagSettings';
import { DeveloperSettings } from './modules/settings/DeveloperSettings';
import { PromptTemplatesPage } from './modules/settings/PromptTemplatesPage';
import { MemorySettings } from './modules/settings/MemorySettings';
import { CodeExecutionSettingsPage } from './modules/settings/CodeExecutionSettings';
import { ToolGateSettings } from './modules/settings/ToolGateSettings';
import { ToolDescriptionsSettings } from './modules/settings/ToolDescriptionsSettings';
import { ToolDescriptionDetailPage } from './modules/settings/ToolDescriptionDetailPage';
import { ToolPluginSettingsPage } from './modules/settings/ToolPluginSettingsPage';
import { DeveloperModule } from './modules/developer';
import { WorkflowsModule } from './modules/workflows';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ChatModule />}>
            <Route index element={<ChatWelcome />} />
            <Route path=":sessionId" element={<ChatView />} />
          </Route>
          <Route path="projects" element={<ProjectsModule />}>
            <Route index element={<ProjectsWelcome />} />
            <Route path=":projectId" element={<ProjectWorkspaceLayout />}>
              <Route index element={<ProjectTabRedirect />} />
              <Route path="project" element={<ProjectHomeView />} />
              <Route path="files" element={<ProjectExplorer />} />
              <Route path="search" element={<ProjectSearchView />} />
              <Route path="workflows" element={<ProjectWorkflowsView />} />
              <Route path="agent" element={<ProjectAgentView />} />
              <Route path="settings" element={<ProjectSettingsView />} />
            </Route>
          </Route>
          <Route path="workflows" element={<WorkflowsModule />} />
          <Route path="developer" element={<DeveloperModule />} />
          <Route path="settings" element={<SettingsModule />}>
            <Route index element={<Navigate to="get-started" replace />} />
            <Route path="get-started" element={<GetStartedPage />} />
            <Route path="assistants" element={<AssistantsPage />} />
            <Route path="assistants/new" element={<AssistantsCreatePage />} />
            <Route path="assistants/:assistantId" element={<AssistantsEditPage />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="models/new" element={<ModelsCreatePage />} />
            <Route path="models/:modelId" element={<ModelsEditPage />} />
            <Route path="providers" element={<ProvidersPage />} />
            <Route path="providers/new" element={<ProvidersCreatePage />} />
            <Route path="providers/:providerId" element={<ProvidersEditPage />} />
            <Route path="knowledge-bases" element={<KnowledgeBasesPage />} />
            <Route path="knowledge-bases/new" element={<KnowledgeBaseCreatePage />} />
            <Route path="knowledge-bases/:kbId" element={<KnowledgeBaseEditPage />} />
            <Route path="prompt-templates" element={<PromptTemplatesPage />} />
            <Route path="memory" element={<MemorySettings />} />
            <Route path="rag" element={<RagSettings />} />
            <Route path="title-generation" element={<TitleGenerationSettings />} />
            <Route path="followup" element={<FollowupSettings />} />
            <Route path="compression" element={<CompressionSettings />} />
            <Route path="file-reference" element={<FileReferenceSettings />} />
            <Route path="code-execution" element={<CodeExecutionSettingsPage />} />
            <Route path="tools" element={<ToolDescriptionsSettings />} />
            <Route path="tools/plugins/:pluginId" element={<ToolPluginSettingsPage />} />
            <Route path="tools/:toolName" element={<ToolDescriptionDetailPage />} />
            <Route path="tool-gate" element={<ToolGateSettings />} />
            <Route path="translation" element={<TranslationSettings />} />
            <Route path="tts" element={<TTSSettings />} />
            <Route path="developer" element={<DeveloperSettings />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
