import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Toaster } from '@/ui/base/sonner';
import { TooltipProvider } from '@/ui/base/tooltip';
import Sidebar from '@/ui/business/Sidebar';
import ChatPage from '@/ui/business/ChatPage';
import CollectionsPage from '@/ui/business/CollectionsPage';
import { CollectionsProvider } from '@/ui/business/CollectionsProvider';
import RoutingS from '@/services/tech/RoutingS';

const App = () => (
  <BrowserRouter>
    <TooltipProvider>
      <CollectionsProvider>
        <div className="flex h-screen overflow-hidden bg-background">
          <Sidebar />
          <main className="flex-1 min-w-0 overflow-hidden">
            <Routes>
              <Route path={RoutingS.paths.chat} element={<ChatPage />} />
              <Route path={RoutingS.paths.collections} element={<CollectionsPage />} />
            </Routes>
          </main>
        </div>
        <Toaster />
      </CollectionsProvider>
    </TooltipProvider>
  </BrowserRouter>
);

export default App;
