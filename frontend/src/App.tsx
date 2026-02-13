import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { ChatModule } from './modules/chat';
import { ChatWelcome, ChatView } from './shared/chat';
import { ProjectsModule } from './modules/projects';
import { ProjectsWelcome } from './modules/projects/ProjectsWelcome';
import { ProjectExplorer } from './modules/projects/ProjectExplorer';
import { SettingsModule } from './modules/settings';
import { AssistantsPage } from './modules/settings/AssistantsPage';
import { ModelsPage } from './modules/settings/ModelsPage';
import { ProvidersPage } from './modules/settings/ProvidersPage';
import {
  AssistantsCreatePage,
  AssistantsEditPage,
  ModelsCreatePage,
  ModelsEditPage,
  ProvidersCreatePage,
  ProvidersEditPage,
  KnowledgeBasesCreatePage,
} from './modules/settings/CrudPages';
import { KnowledgeBaseEditPage } from './modules/settings/KnowledgeBaseEditPage';
import { SearchSettings } from './modules/settings/SearchSettings';
import { WebpageSettings } from './modules/settings/WebpageSettings';
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
import { DeveloperModule } from './modules/developer';
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
            <Route path=":projectId" element={<ProjectExplorer />} />
          </Route>
          <Route path="developer" element={<DeveloperModule />} />
          <Route path="settings" element={<SettingsModule />}>
            <Route index element={<Navigate to="assistants" replace />} />
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
            <Route path="knowledge-bases/new" element={<KnowledgeBasesCreatePage />} />
            <Route path="knowledge-bases/:kbId" element={<KnowledgeBaseEditPage />} />
            <Route path="prompt-templates" element={<PromptTemplatesPage />} />
            <Route path="memory" element={<MemorySettings />} />
            <Route path="rag" element={<RagSettings />} />
            <Route path="search" element={<SearchSettings />} />
            <Route path="webpage" element={<WebpageSettings />} />
            <Route path="title-generation" element={<TitleGenerationSettings />} />
            <Route path="followup" element={<FollowupSettings />} />
            <Route path="compression" element={<CompressionSettings />} />
            <Route path="file-reference" element={<FileReferenceSettings />} />
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
