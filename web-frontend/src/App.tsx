import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { GlassNav } from "./components/GlassNav";
import { ChatPage } from "./pages/Chat";
import { LibraryPage } from "./pages/Library";
import { DebugPage } from "./pages/Debug";
import { SettingsPage } from "./pages/Settings";
import { useTheme } from "./hooks/useTheme";

export default function App() {
  // Initialize theme on mount (writes data-theme to <html>)
  useTheme();

  return (
    <BrowserRouter>
      <GlassNav />
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/debug" element={<DebugPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
