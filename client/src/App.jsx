import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import TopNav from "./components/TopNav";
import ConsolePage from "./pages/ConsolePage";
import LabPage from "./pages/LabPage";
import { useAppContext } from "./context/AppContext";

function AppShell() {
  const { bootstrap } = useAppContext();

  return (
    <div className="scan-grid min-h-screen">
      <TopNav categories={bootstrap?.categories ?? []} />
      <main className="sql-main">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<ConsolePage />} />
        <Route path="lab/:categorySlug/:level" element={<LabPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
