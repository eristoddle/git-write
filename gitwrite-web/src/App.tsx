import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import RepositoryBrowser from './components/RepositoryBrowser';
import CommitHistoryView from './components/CommitHistoryView';
import FileContentViewerPage from './pages/FileContentViewerPage';
import WordDiffViewerPage from './pages/WordDiffViewerPage';
import BranchReviewPage from './pages/BranchReviewPage'; // Added for Task 11.7
import ThemeToggle from './components/ThemeToggle';
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
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            {/* Route for general repository browsing (files at current branch HEAD) */}
            <Route path="/repository/:repoName/tree/*" element={<RepositoryBrowser />} />
            {/* Route for commit history of a branch */}
            <Route path="/repository/:repoName/history/*" element={<CommitHistoryView />} />
            {/* Route for viewing a specific file at a specific commit */}
            {/* The '*' (splat) in filePath will capture the full file path including slashes */}
            <Route path="/repository/:repoName/commit/:commitSha/file/*" element={<FileContentViewerPage />} />
            {/* Route for comparing two refs (commits, branches, etc.) */}
            <Route path="/repository/:repoName/compare/:ref1/:ref2" element={<WordDiffViewerPage />} />
            {/* Redirect base /repository/:repoName to its tree view of the default branch (e.g., main) */}
            <Route path="/repository/:repoName" element={<Navigate to="tree/main" replace />} />
          </Route>
        </Route>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Router>
  );
};

export default App;
