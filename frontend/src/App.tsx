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
import { SearchSettings } from './modules/settings/SearchSettings';
import { WebpageSettings } from './modules/settings/WebpageSettings';
import { TitleGenerationSettings } from './modules/settings/TitleGenerationSettings';
import { FollowupSettings } from './modules/settings/FollowupSettings';
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
          <Route path="settings" element={<SettingsModule />}>
            <Route index element={<Navigate to="assistants" replace />} />
            <Route path="assistants" element={<AssistantsPage />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="providers" element={<ProvidersPage />} />
            <Route path="search" element={<SearchSettings />} />
            <Route path="webpage" element={<WebpageSettings />} />
            <Route path="title-generation" element={<TitleGenerationSettings />} />
            <Route path="followup" element={<FollowupSettings />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
