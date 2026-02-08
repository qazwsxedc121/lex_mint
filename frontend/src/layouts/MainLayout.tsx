/**
 * MainLayout - Main application layout with global sidebar
 *
 * Contains the global sidebar and outlet for nested routes
 */

import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { GlobalSidebar } from './GlobalSidebar';
import { useCommandPalette } from '../hooks/useCommandPalette';
import { CommandPalette } from '../components/CommandPalette';

export const MainLayout: React.FC = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { isOpen, close } = useCommandPalette();

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

      {/* Command Palette (Global Overlay) */}
      <CommandPalette isOpen={isOpen} onClose={close} />
    </div>
  );
};
