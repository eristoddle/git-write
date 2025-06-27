import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import RepositoryBrowser from './components/RepositoryBrowser'; // Import RepositoryBrowser
import ThemeToggle from './components/ThemeToggle'; // For a consistent layout perhaps
import './App.css';

const ProtectedRoute: React.FC = () => {
  const isAuthenticated = !!localStorage.getItem('jwtToken');
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

// Optional: Create a simple layout component for authenticated views
const AppLayout: React.FC = () => (
  <div className="min-h-screen bg-background text-foreground">
    {/* Consider adding a persistent navbar or header here if needed later */}
    {/* <header className="p-4 border-b">
      <div className="container mx-auto flex justify-between items-center">
        <span className="font-bold text-xl">GitWrite</span>
        <ThemeToggle />
      </div>
    </header> */}
    <main>
      <Outlet /> {/* Nested routes will render here */}
    </main>
  </div>
);

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}> {/* Wrap protected routes with AppLayout */}
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/repository/:repoName/*" element={<RepositoryBrowser />} />
             {/* The '*' in the path for repoName allows for deep linking into file paths */}
          </Route>
        </Route>
        <Route path="/" element={<Navigate to="/dashboard" replace />} /> {/* Default to dashboard if logged in */}
        {/* Fallback for non-authenticated users if they try to go to '/' directly could be /login */}
        {/* This is slightly changed: if not authenticated, ProtectedRoute handles redirect to /login */}
      </Routes>
    </Router>
  );
};

export default App;
