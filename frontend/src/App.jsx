import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import Dashboard from './pages/Dashboard';
import NewScan from './pages/NewScan';
import Inventory from './pages/Inventory';
import EvidenceGaps from './pages/EvidenceGaps';
import DetectionRules from './pages/DetectionRules';
import Evaluation from './pages/Evaluation';
import Reports from './pages/Reports';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans text-slate-800 antialiased">
        {/* Left Navigation Sidebar */}
        <Sidebar />

        {/* Right Content Area */}
        <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
          {/* Topbar */}
          <Topbar />

          {/* Main Content View with custom scroll */}
          <main className="flex-1 overflow-y-auto px-6 py-6 bg-slate-50/80">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/scan" element={<NewScan />} />
              <Route path="/inventory" element={<Inventory />} />
              <Route path="/gaps" element={<EvidenceGaps />} />
              <Route path="/rules" element={<DetectionRules />} />
              <Route path="/evaluation" element={<Evaluation />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
