/**
 * MainLayout - Main application layout with global sidebar
 *
 * Contains the global sidebar and outlet for nested routes
 */

import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { GlobalSidebar } from './GlobalSidebar';

export const MainLayout: React.FC = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-white dark:bg-gray-900">
      {/* Global Sidebar (Level 1) */}
      <GlobalSidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Area */}
      <main className="flex-1 flex overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
};
