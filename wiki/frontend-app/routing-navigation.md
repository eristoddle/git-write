# Routing & Navigation

GitWrite's frontend uses React Router v6 for client-side routing, providing a seamless single-page application experience with deep linking, route protection, and intuitive navigation patterns optimized for writing workflows.

## Overview

The routing system provides:
- **Declarative Routing**: Clear route definitions with TypeScript support
- **Nested Routes**: Hierarchical page structure matching user workflows
- **Route Protection**: Authentication and permission-based access control
- **Lazy Loading**: Code splitting for optimal performance
- **Deep Linking**: Direct access to specific writing contexts
- **Browser Integration**: Full history and bookmark support

```
Route Hierarchy
    │
    ├─ / (Public Routes)
    │   ├─ /login
    │   ├─ /register
    │   └─ /reset-password
    │
    ├─ /app (Protected Routes)
    │   ├─ /dashboard
    │   ├─ /repositories
    │   │   ├─ /:name
    │   │   ├─ /:name/edit/:file?
    │   │   ├─ /:name/history
    │   │   └─ /:name/settings
    │   ├─ /collaborations
    │   └─ /settings
    └─ /public (Repository Access)
        └─ /:username/:repository
```

## Core Routing Setup

### 1. Router Configuration

```typescript
// src/components/routing/AppRouter.tsx
import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary } from '../common/ErrorBoundary';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ProtectedRoute } from './ProtectedRoute';
import { PublicRoute } from './PublicRoute';
import { AppLayout } from '../layout/AppLayout';
import { AuthLayout } from '../layout/AuthLayout';

// Lazy load page components for code splitting
const Dashboard = React.lazy(() => import('../pages/Dashboard'));
const Editor = React.lazy(() => import('../pages/Editor'));
const RepositoryList = React.lazy(() => import('../pages/RepositoryList'));
const RepositoryDetail = React.lazy(() => import('../pages/RepositoryDetail'));
const RepositoryHistory = React.lazy(() => import('../pages/RepositoryHistory'));
const RepositorySettings = React.lazy(() => import('../pages/RepositorySettings'));
const Collaborations = React.lazy(() => import('../pages/Collaborations'));
const Settings = React.lazy(() => import('../pages/Settings'));
const Login = React.lazy(() => import('../pages/Login'));
const Register = React.lazy(() => import('../pages/Register'));
const ResetPassword = React.lazy(() => import('../pages/ResetPassword'));
const PublicRepository = React.lazy(() => import('../pages/PublicRepository'));
const NotFound = React.lazy(() => import('../pages/NotFound'));

export const AppRouter: React.FC = () => {
  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          {/* Authentication Routes */}
          <Route element={<PublicRoute />}>
            <Route element={<AuthLayout />}>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/reset-password" element={<ResetPassword />} />
            </Route>
          </Route>

          {/* Protected Application Routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />

              {/* Repository Routes */}
              <Route path="/repositories">
                <Route index element={<RepositoryList />} />
                <Route path=":repositoryName">
                  <Route index element={<RepositoryDetail />} />
                  <Route path="edit/:filePath?" element={<Editor />} />
                  <Route path="history" element={<RepositoryHistory />} />
                  <Route path="settings" element={<RepositorySettings />} />
                </Route>
              </Route>

              <Route path="/collaborations" element={<Collaborations />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
          </Route>

          {/* Public Repository Access */}
          <Route
            path="/public/:username/:repository"
            element={<PublicRepository />}
          />

          {/* Fallback Routes */}
          <Route path="/404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
};
```

### 2. Route Protection

```typescript
// src/components/routing/ProtectedRoute.tsx
import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { LoadingSpinner } from '../common/LoadingSpinner';

export const ProtectedRoute: React.FC = () => {
  const { user, isLoading, isAuthenticated } = useAuthStore();
  const location = useLocation();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    // Redirect to login with return URL
    return (
      <Navigate
        to="/login"
        state={{ from: location.pathname + location.search }}
        replace
      />
    );
  }

  return <Outlet />;
};

// src/components/routing/PublicRoute.tsx
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

export const PublicRoute: React.FC = () => {
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
};

// src/components/routing/RepositoryRoute.tsx
import React, { useEffect } from 'react';
import { useParams, Navigate, Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useRepositoryStore } from '../../stores/repositoryStore';
import { repositoryService } from '../../services/repositoryService';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorMessage } from '../common/ErrorMessage';

export const RepositoryRoute: React.FC = () => {
  const { repositoryName } = useParams<{ repositoryName: string }>();
  const { setCurrentRepository } = useRepositoryStore();

  const {
    data: repository,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['repository', repositoryName],
    queryFn: () => repositoryService.getRepository(repositoryName!),
    enabled: !!repositoryName,
  });

  useEffect(() => {
    if (repository) {
      setCurrentRepository(repository);
    }
  }, [repository, setCurrentRepository]);

  if (isLoading) {
    return <LoadingSpinner message={`Loading ${repositoryName}...`} />;
  }

  if (error) {
    return (
      <ErrorMessage
        title="Repository Not Found"
        message={`The repository "${repositoryName}" could not be found or you don't have access to it.`}
        actionLabel="Go to Repositories"
        actionTo="/repositories"
      />
    );
  }

  if (!repository) {
    return <Navigate to="/repositories" replace />;
  }

  return <Outlet />;
};
```

### 3. Navigation Components

```typescript
// src/components/navigation/MainNavigation.tsx
import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { cn } from '../../utils/cn';
import {
  HomeIcon,
  FolderIcon,
  UsersIcon,
  SettingsIcon,
  PenToolIcon
} from 'lucide-react';

interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  badge?: string | number;
}

const navItems: NavItem[] = [
  { to: '/dashboard', icon: HomeIcon, label: 'Dashboard' },
  { to: '/repositories', icon: FolderIcon, label: 'Repositories' },
  { to: '/collaborations', icon: UsersIcon, label: 'Collaborations' },
  { to: '/settings', icon: SettingsIcon, label: 'Settings' },
];

export const MainNavigation: React.FC = () => {
  const location = useLocation();

  return (
    <nav className="main-navigation">
      <ul className="nav-list">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname.startsWith(item.to);

          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'nav-link flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                  )
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
                {item.badge && (
                  <span className="ml-auto bg-primary text-primary-foreground text-xs px-2 py-1 rounded-full">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
};

// src/components/navigation/Breadcrumbs.tsx
import React from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ChevronRightIcon } from 'lucide-react';
import { useRepositoryStore } from '../../stores/repositoryStore';
import { useEditorStore } from '../../stores/editorStore';

interface BreadcrumbItem {
  label: string;
  href?: string;
  current?: boolean;
}

export const Breadcrumbs: React.FC = () => {
  const location = useLocation();
  const params = useParams();
  const { currentRepository } = useRepositoryStore();
  const { currentFile } = useEditorStore();

  const getBreadcrumbs = (): BreadcrumbItem[] => {
    const items: BreadcrumbItem[] = [];
    const pathSegments = location.pathname.split('/').filter(Boolean);

    if (pathSegments[0] === 'dashboard') {
      items.push({ label: 'Dashboard', current: true });
    } else if (pathSegments[0] === 'repositories') {
      items.push({ label: 'Repositories', href: '/repositories' });

      if (params.repositoryName) {
        items.push({
          label: currentRepository?.name || params.repositoryName,
          href: `/repositories/${params.repositoryName}`,
        });

        if (pathSegments[2] === 'edit') {
          items.push({ label: 'Editor', href: `/repositories/${params.repositoryName}/edit` });

          if (currentFile) {
            items.push({ label: currentFile.name, current: true });
          }
        } else if (pathSegments[2] === 'history') {
          items.push({ label: 'History', current: true });
        } else if (pathSegments[2] === 'settings') {
          items.push({ label: 'Settings', current: true });
        } else {
          items[items.length - 1].current = true;
        }
      } else {
        items[items.length - 1].current = true;
      }
    } else if (pathSegments[0] === 'collaborations') {
      items.push({ label: 'Collaborations', current: true });
    } else if (pathSegments[0] === 'settings') {
      items.push({ label: 'Settings', current: true });
    }

    return items;
  };

  const breadcrumbs = getBreadcrumbs();

  if (breadcrumbs.length <= 1) {
    return null;
  }

  return (
    <nav className="breadcrumbs flex items-center space-x-1 text-sm text-muted-foreground">
      {breadcrumbs.map((item, index) => (
        <React.Fragment key={index}>
          {index > 0 && <ChevronRightIcon className="w-4 h-4" />}
          {item.current ? (
            <span className="font-medium text-foreground">{item.label}</span>
          ) : (
            <Link
              to={item.href!}
              className="hover:text-foreground transition-colors"
            >
              {item.label}
            </Link>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
};
```

### 4. Route Hooks

```typescript
// src/hooks/useNavigation.ts
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { useCallback } from 'react';

export const useNavigation = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams();

  const goToRepository = useCallback((repositoryName: string) => {
    navigate(`/repositories/${repositoryName}`);
  }, [navigate]);

  const goToEditor = useCallback((repositoryName: string, filePath?: string) => {
    const path = `/repositories/${repositoryName}/edit`;
    if (filePath) {
      navigate(`${path}/${encodeURIComponent(filePath)}`);
    } else {
      navigate(path);
    }
  }, [navigate]);

  const goToHistory = useCallback((repositoryName: string) => {
    navigate(`/repositories/${repositoryName}/history`);
  }, [navigate]);

  const goBack = useCallback(() => {
    navigate(-1);
  }, [navigate]);

  const isCurrentRoute = useCallback((path: string) => {
    return location.pathname === path;
  }, [location.pathname]);

  const isRouteActive = useCallback((path: string) => {
    return location.pathname.startsWith(path);
  }, [location.pathname]);

  return {
    navigate,
    location,
    params,
    goToRepository,
    goToEditor,
    goToHistory,
    goBack,
    isCurrentRoute,
    isRouteActive,
  };
};

// src/hooks/useRouteParams.ts
import { useParams } from 'react-router-dom';

export const useRepositoryParams = () => {
  const { repositoryName, filePath } = useParams<{
    repositoryName: string;
    filePath?: string;
  }>();

  return {
    repositoryName: repositoryName!,
    filePath: filePath ? decodeURIComponent(filePath) : undefined,
  };
};

// src/hooks/useQueryParams.ts
import { useSearchParams } from 'react-router-dom';
import { useCallback } from 'react';

export const useQueryParams = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const getParam = useCallback((key: string) => {
    return searchParams.get(key);
  }, [searchParams]);

  const setParam = useCallback((key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set(key, value);
    setSearchParams(newParams);
  }, [searchParams, setSearchParams]);

  const removeParam = useCallback((key: string) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.delete(key);
    setSearchParams(newParams);
  }, [searchParams, setSearchParams]);

  const clearParams = useCallback(() => {
    setSearchParams({});
  }, [setSearchParams]);

  return {
    searchParams,
    getParam,
    setParam,
    removeParam,
    clearParams,
  };
};
```

### 5. Route Data Loading

```typescript
// src/components/routing/RouteLoader.tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorMessage } from '../common/ErrorMessage';

interface RouteLoaderProps<T> {
  queryKey: string[];
  queryFn: () => Promise<T>;
  children: (data: T) => React.ReactNode;
  loadingMessage?: string;
  errorTitle?: string;
  errorMessage?: string;
}

export function RouteLoader<T>({
  queryKey,
  queryFn,
  children,
  loadingMessage = 'Loading...',
  errorTitle = 'Error',
  errorMessage = 'Failed to load data',
}: RouteLoaderProps<T>) {
  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn,
  });

  if (isLoading) {
    return <LoadingSpinner message={loadingMessage} />;
  }

  if (error) {
    return (
      <ErrorMessage
        title={errorTitle}
        message={errorMessage}
        error={error}
      />
    );
  }

  if (!data) {
    return (
      <ErrorMessage
        title="No Data"
        message="No data available"
      />
    );
  }

  return <>{children(data)}</>;
}

// Usage example
export const RepositoryDetailPage: React.FC = () => {
  const { repositoryName } = useRepositoryParams();

  return (
    <RouteLoader
      queryKey={['repository', repositoryName]}
      queryFn={() => repositoryService.getRepository(repositoryName)}
      loadingMessage={`Loading ${repositoryName}...`}
      errorTitle="Repository Not Found"
      errorMessage={`Could not load repository "${repositoryName}"`}
    >
      {(repository) => <RepositoryDetail repository={repository} />}
    </RouteLoader>
  );
};
```

### 6. Navigation Analytics

```typescript
// src/hooks/useNavigationTracking.ts
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { analytics } from '../services/analytics';

export const useNavigationTracking = () => {
  const location = useLocation();

  useEffect(() => {
    // Track page views
    analytics.track('page_view', {
      path: location.pathname,
      search: location.search,
      timestamp: new Date().toISOString(),
    });
  }, [location]);

  useEffect(() => {
    // Track time spent on page
    const startTime = Date.now();

    return () => {
      const timeSpent = Date.now() - startTime;
      analytics.track('page_time', {
        path: location.pathname,
        timeSpent,
      });
    };
  }, [location]);
};

// src/components/routing/AnalyticsRouter.tsx
import React from 'react';
import { AppRouter } from './AppRouter';
import { useNavigationTracking } from '../../hooks/useNavigationTracking';

export const AnalyticsRouter: React.FC = () => {
  useNavigationTracking();
  return <AppRouter />;
};
```

## Route Configuration

### Route Patterns

```typescript
// Route patterns used in GitWrite
export const ROUTES = {
  // Public routes
  LOGIN: '/login',
  REGISTER: '/register',
  RESET_PASSWORD: '/reset-password',

  // App routes
  DASHBOARD: '/dashboard',
  REPOSITORIES: '/repositories',
  REPOSITORY_DETAIL: '/repositories/:repositoryName',
  EDITOR: '/repositories/:repositoryName/edit/:filePath?',
  REPOSITORY_HISTORY: '/repositories/:repositoryName/history',
  REPOSITORY_SETTINGS: '/repositories/:repositoryName/settings',
  COLLABORATIONS: '/collaborations',
  SETTINGS: '/settings',

  // Public repository access
  PUBLIC_REPOSITORY: '/public/:username/:repository',

  // Error pages
  NOT_FOUND: '/404',
} as const;

// Route builders for type safety
export const buildRoute = {
  repositoryDetail: (name: string) => `/repositories/${name}`,
  editor: (name: string, filePath?: string) =>
    `/repositories/${name}/edit${filePath ? `/${encodeURIComponent(filePath)}` : ''}`,
  repositoryHistory: (name: string) => `/repositories/${name}/history`,
  repositorySettings: (name: string) => `/repositories/${name}/settings`,
  publicRepository: (username: string, repository: string) =>
    `/public/${username}/${repository}`,
};
```

### Route Guards

```typescript
// src/components/routing/RouteGuard.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { usePermissions } from '../../hooks/usePermissions';

interface RouteGuardProps {
  children: React.ReactNode;
  requireAuth?: boolean;
  requirePermissions?: string[];
  redirectTo?: string;
}

export const RouteGuard: React.FC<RouteGuardProps> = ({
  children,
  requireAuth = true,
  requirePermissions = [],
  redirectTo = '/login',
}) => {
  const { isAuthenticated } = useAuthStore();
  const { hasPermissions } = usePermissions();
  const location = useLocation();

  if (requireAuth && !isAuthenticated) {
    return (
      <Navigate
        to={redirectTo}
        state={{ from: location }}
        replace
      />
    );
  }

  if (requirePermissions.length > 0 && !hasPermissions(requirePermissions)) {
    return (
      <Navigate
        to="/403"
        state={{ from: location }}
        replace
      />
    );
  }

  return <>{children}</>;
};
```

---

*GitWrite's routing and navigation system provides intuitive navigation patterns that match writing workflows while maintaining the technical robustness needed for a modern web application. The system balances user experience with developer productivity through clear abstractions and type safety.*