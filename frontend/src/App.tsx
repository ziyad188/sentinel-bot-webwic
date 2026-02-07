import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AuthSession, clearStoredAuth, getStoredAuth, getStoredSession, logoutSession, persistSession } from "@/lib/auth";
import Dashboard from "./pages/Dashboard";
import Runs from "./pages/Runs";
import Issues from "./pages/Issues";
import Evidence from "./pages/Evidence";
import Users from "./pages/Users";
import NotFound from "./pages/NotFound";
import Login from "./pages/Login";
import Signup from "./pages/Signup";

const queryClient = new QueryClient();
const RequireAuth = ({ isAuthenticated }: { isAuthenticated: boolean }) => {
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
};

const AppShell = ({ onLogout }: { onLogout: () => void }) => (
  <AppLayout onLogout={onLogout}>
    <Outlet />
  </AppLayout>
);

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(getStoredAuth);

  const handleLogin = (session: AuthSession, remember: boolean) => {
    persistSession(session, remember);
    setIsAuthenticated(true);
  };

  const handleSignup = (session: AuthSession) => {
    persistSession(session, true);
    setIsAuthenticated(true);
  };

  const handleLogout = async () => {
    const session = getStoredSession();
    await logoutSession(session?.refreshToken);
    clearStoredAuth();
    setIsAuthenticated(false);
  };

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route
              path="/login"
              element={
                isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login onLogin={handleLogin} />
              }
            />
            <Route
              path="/signup"
              element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Signup onSignup={handleSignup} />}
            />
            <Route
              path="/"
              element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />}
            />
            <Route element={<RequireAuth isAuthenticated={isAuthenticated} />}>
              <Route element={<AppShell onLogout={handleLogout} />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/runs" element={<Runs />} />
                <Route path="/issues" element={<Issues />} />
                <Route path="/evidence" element={<Evidence />} />
                <Route path="/users" element={<Users />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
