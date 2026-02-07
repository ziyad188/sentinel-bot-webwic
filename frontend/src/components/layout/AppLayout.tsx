import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { ProjectProvider } from '@/lib/project';
import { RunConfigProvider } from '@/lib/run-config';

export function AppLayout({ children, onLogout }: { children: ReactNode; onLogout: () => void }) {
  return (
    <ProjectProvider>
      <RunConfigProvider>
        <div className="flex h-screen w-full overflow-hidden">
          <Sidebar onLogout={onLogout} />
          <div className="flex flex-1 flex-col min-w-0">
            <TopBar />
            <main className="flex-1 overflow-auto p-6 scrollbar-thin">
              <div className="animate-fade-in">
                {children}
              </div>
            </main>
          </div>
        </div>
      </RunConfigProvider>
    </ProjectProvider>
  );
}
