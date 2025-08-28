# Component Architecture

GitWrite's frontend is built with React 18 and TypeScript, following modern component architecture patterns. The application uses a hierarchical component structure with clear separation of concerns, reusable design systems, and efficient state management.

## Overview

The component architecture emphasizes:
- **Modularity**: Self-contained, reusable components
- **Type Safety**: Full TypeScript integration
- **Performance**: Optimized rendering and lazy loading
- **Accessibility**: WCAG compliant components
- **Maintainability**: Clear component organization and documentation
- **Writer Focus**: UI optimized for writing workflows

```
Component Hierarchy
    │
    ├─ App (Root)
    │   ├─ Router (Navigation)
    │   ├─ Layout (Structure)
    │   │   ├─ Header (Navigation)
    │   │   ├─ Sidebar (Quick Access)
    │   │   ├─ Main (Content Area)
    │   │   └─ Footer (Status)
    │   └─ Providers (Context)
    └─ Pages (Route Components)
        ├─ Dashboard
        ├─ Editor
        ├─ Repository
        └─ Settings
```

## Core Component Structure

### 1. Application Root

```typescript
// src/App.tsx
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'react-hot-toast';

import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { AppRouter } from './components/routing/AppRouter';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { LoadingProvider } from './contexts/LoadingContext';

import './styles/globals.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ThemeProvider>
            <AuthProvider>
              <LoadingProvider>
                <AppRouter />
                <Toaster
                  position="top-right"
                  toastOptions={{
                    duration: 4000,
                    style: {
                      background: 'var(--color-surface)',
                      color: 'var(--color-text)',
                      border: '1px solid var(--color-border)',
                    },
                  }}
                />
              </LoadingProvider>
            </AuthProvider>
          </ThemeProvider>
        </BrowserRouter>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
};
```

### 2. Layout Components

```typescript
// src/components/layout/AppLayout.tsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { StatusBar } from './StatusBar';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';

interface AppLayoutProps {
  children?: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const { user } = useAuthStore();
  const { sidebarOpen, sidebarWidth } = useUIStore();

  if (!user) {
    return <div>Loading...</div>;
  }

  return (
    <div className="app-layout">
      <Header />

      <div className="app-content">
        {sidebarOpen && (
          <Sidebar
            width={sidebarWidth}
            className="app-sidebar"
          />
        )}

        <main
          className="main-content"
          style={{
            marginLeft: sidebarOpen ? `${sidebarWidth}px` : 0,
            transition: 'margin-left 0.3s ease',
          }}
        >
          {children || <Outlet />}
        </main>
      </div>

      <StatusBar />
    </div>
  );
};

// src/components/layout/Header.tsx
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../ui/Button';
import { Avatar } from '../ui/Avatar';
import { Dropdown } from '../ui/Dropdown';
import { useAuthStore } from '../../stores/authStore';
import { useRepositoryStore } from '../../stores/repositoryStore';

export const Header: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { currentRepository } = useRepositoryStore();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="app-header">
      <div className="header-left">
        <Link to="/dashboard" className="logo">
          <img src="/logo.svg" alt="GitWrite" />
        </Link>

        {currentRepository && (
          <div className="current-repository">
            <span className="repo-name">{currentRepository.name}</span>
            <span className="repo-branch">{currentRepository.currentBranch}</span>
          </div>
        )}
      </div>

      <div className="header-center">
        <nav className="main-nav">
          <Link to="/dashboard" className="nav-link">Dashboard</Link>
          <Link to="/repositories" className="nav-link">Repositories</Link>
          <Link to="/collaborations" className="nav-link">Collaborations</Link>
        </nav>
      </div>

      <div className="header-right">
        <Button variant="ghost" size="sm">
          <span>⌘K</span>
          Search
        </Button>

        <Dropdown
          trigger={
            <Avatar
              src={user?.avatar}
              name={user?.name}
              size="sm"
            />
          }
        >
          <div className="user-menu">
            <div className="user-info">
              <span className="user-name">{user?.name}</span>
              <span className="user-email">{user?.email}</span>
            </div>
            <hr />
            <Link to="/settings">Settings</Link>
            <Link to="/help">Help</Link>
            <hr />
            <button onClick={handleLogout}>Sign Out</button>
          </div>
        </Dropdown>
      </div>
    </header>
  );
};
```

### 3. Page Components

```typescript
// src/components/pages/Dashboard.tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Grid } from '../ui/Grid';
import { Card } from '../ui/Card';
import { RepositoryCard } from '../repository/RepositoryCard';
import { ActivityFeed } from '../activity/ActivityFeed';
import { WritingStats } from '../writing/WritingStats';
import { QuickActions } from '../common/QuickActions';
import { useRepositoriesQuery } from '../../hooks/useRepositories';

export const Dashboard: React.FC = () => {
  const { data: repositories, isLoading } = useRepositoriesQuery();

  if (isLoading) {
    return <div>Loading dashboard...</div>;
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Welcome back!</h1>
        <QuickActions />
      </div>

      <Grid className="dashboard-grid">
        <div className="dashboard-main">
          <section className="recent-repositories">
            <h2>Recent Repositories</h2>
            <div className="repository-grid">
              {repositories?.slice(0, 6).map((repo) => (
                <RepositoryCard key={repo.id} repository={repo} />
              ))}
            </div>
          </section>

          <section className="writing-progress">
            <h2>Writing Progress</h2>
            <WritingStats repositories={repositories} />
          </section>
        </div>

        <aside className="dashboard-sidebar">
          <Card>
            <h3>Recent Activity</h3>
            <ActivityFeed limit={10} />
          </Card>
        </aside>
      </Grid>
    </div>
  );
};

// src/components/pages/Editor.tsx
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { MarkdownEditor } from '../editor/MarkdownEditor';
import { FileExplorer } from '../editor/FileExplorer';
import { PreviewPanel } from '../editor/PreviewPanel';
import { AnnotationPanel } from '../editor/AnnotationPanel';
import { EditorToolbar } from '../editor/EditorToolbar';
import { useRepositoryStore } from '../../stores/repositoryStore';
import { useEditorStore } from '../../stores/editorStore';

export const Editor: React.FC = () => {
  const { repositoryName, filePath } = useParams<{
    repositoryName: string;
    filePath?: string;
  }>();

  const { currentRepository, setCurrentRepository } = useRepositoryStore();
  const {
    currentFile,
    content,
    previewMode,
    showAnnotations,
    setCurrentFile,
    updateContent
  } = useEditorStore();

  useEffect(() => {
    if (repositoryName && (!currentRepository || currentRepository.name !== repositoryName)) {
      // Load repository if not current
      setCurrentRepository(repositoryName);
    }
  }, [repositoryName, currentRepository, setCurrentRepository]);

  useEffect(() => {
    if (filePath && filePath !== currentFile?.path) {
      setCurrentFile(filePath);
    }
  }, [filePath, currentFile, setCurrentFile]);

  return (
    <div className="editor-layout">
      <EditorToolbar />

      <div className="editor-content">
        <div className="editor-left">
          <FileExplorer repository={currentRepository} />
        </div>

        <div className="editor-main">
          {currentFile ? (
            <MarkdownEditor
              file={currentFile}
              content={content}
              onChange={updateContent}
              className="main-editor"
            />
          ) : (
            <div className="no-file-selected">
              <h3>No file selected</h3>
              <p>Choose a file from the explorer to start editing</p>
            </div>
          )}
        </div>

        {previewMode && (
          <div className="editor-preview">
            <PreviewPanel content={content} />
          </div>
        )}

        {showAnnotations && (
          <div className="editor-annotations">
            <AnnotationPanel file={currentFile} />
          </div>
        )}
      </div>
    </div>
  );
};
```

### 4. UI Component Library

```typescript
// src/components/ui/Button.tsx
import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../utils/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input hover:bg-accent hover:text-accent-foreground',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'underline-offset-4 hover:underline text-primary',
      },
      size: {
        default: 'h-10 py-2 px-4',
        sm: 'h-9 px-3 rounded-md',
        lg: 'h-11 px-8 rounded-md',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };

// src/components/ui/Card.tsx
import React from 'react';
import { cn } from '../../utils/cn';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({ children, className, ...props }) => {
  return (
    <div
      className={cn(
        'rounded-lg border bg-card text-card-foreground shadow-sm',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  ...props
}) => (
  <div className={cn('flex flex-col space-y-1.5 p-6', className)} {...props} />
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className,
  ...props
}) => (
  <h3
    className={cn('text-lg font-semibold leading-none tracking-tight', className)}
    {...props}
  />
);

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  ...props
}) => <div className={cn('p-6 pt-0', className)} {...props} />;
```

### 5. Feature-Specific Components

```typescript
// src/components/repository/RepositoryCard.tsx
import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { formatDistanceToNow } from 'date-fns';
import type { Repository } from '../../types/repository';

interface RepositoryCardProps {
  repository: Repository;
}

export const RepositoryCard: React.FC<RepositoryCardProps> = ({ repository }) => {
  return (
    <Card className="repository-card hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <CardTitle>
            <Link
              to={`/repositories/${repository.name}`}
              className="text-lg font-semibold hover:text-primary"
            >
              {repository.name}
            </Link>
          </CardTitle>
          <Badge variant={repository.status === 'active' ? 'default' : 'secondary'}>
            {repository.status}
          </Badge>
        </div>
        {repository.description && (
          <p className="text-sm text-muted-foreground mt-2">
            {repository.description}
          </p>
        )}
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Word Count:</span>
            <span className="ml-2 font-medium">
              {repository.wordCount.toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Files:</span>
            <span className="ml-2 font-medium">{repository.fileCount}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Last Save:</span>
            <span className="ml-2">
              {formatDistanceToNow(new Date(repository.updatedAt), { addSuffix: true })}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Type:</span>
            <span className="ml-2 capitalize">{repository.type}</span>
          </div>
        </div>

        {repository.collaboratorCount > 0 && (
          <div className="mt-4 pt-4 border-t">
            <span className="text-sm text-muted-foreground">
              {repository.collaboratorCount} collaborator(s)
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// src/components/editor/MarkdownEditor.tsx
import React, { useCallback, useRef, useEffect } from 'react';
import { EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
import { markdown } from '@codemirror/lang-markdown';
import { oneDark } from '@codemirror/theme-one-dark';
import { useTheme } from '../../contexts/ThemeContext';
import type { EditorFile } from '../../types/editor';

interface MarkdownEditorProps {
  file: EditorFile;
  content: string;
  onChange: (content: string) => void;
  className?: string;
}

export const MarkdownEditor: React.FC<MarkdownEditorProps> = ({
  file,
  content,
  onChange,
  className,
}) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView>();
  const { theme } = useTheme();

  const handleChange = useCallback((value: string) => {
    onChange(value);
  }, [onChange]);

  useEffect(() => {
    if (!editorRef.current) return;

    const extensions = [
      markdown(),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          handleChange(update.state.doc.toString());
        }
      }),
      EditorView.theme({
        '&': {
          height: '100%',
        },
        '.cm-content': {
          padding: '1rem',
          minHeight: '100%',
          fontFamily: '"Fira Code", "Monaco", monospace',
          fontSize: '14px',
          lineHeight: '1.6',
        },
        '.cm-focused': {
          outline: 'none',
        },
      }),
    ];

    if (theme === 'dark') {
      extensions.push(oneDark);
    }

    const state = EditorState.create({
      doc: content,
      extensions,
    });

    const view = new EditorView({
      state,
      parent: editorRef.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
    };
  }, [theme, handleChange]);

  useEffect(() => {
    if (viewRef.current && content !== viewRef.current.state.doc.toString()) {
      viewRef.current.dispatch({
        changes: {
          from: 0,
          to: viewRef.current.state.doc.length,
          insert: content,
        },
      });
    }
  }, [content]);

  return (
    <div className={`markdown-editor ${className}`}>
      <div className="editor-header">
        <span className="file-path">{file.path}</span>
        <div className="editor-actions">
          {/* Save indicator, word count, etc. */}
        </div>
      </div>
      <div ref={editorRef} className="editor-content" />
    </div>
  );
};
```

### 6. Component Testing

```typescript
// src/components/__tests__/Button.test.tsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '../ui/Button';

describe('Button', () => {
  it('renders correctly', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button')).toHaveTextContent('Click me');
  });

  it('handles click events', () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click me</Button>);

    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('applies variant styles correctly', () => {
    render(<Button variant="destructive">Delete</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-destructive');
  });

  it('can be disabled', () => {
    render(<Button disabled>Disabled</Button>);
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(button).toHaveClass('disabled:opacity-50');
  });
});

// src/components/__tests__/RepositoryCard.test.tsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { RepositoryCard } from '../repository/RepositoryCard';
import type { Repository } from '../../types/repository';

const mockRepository: Repository = {
  id: '1',
  name: 'test-repo',
  description: 'A test repository',
  type: 'novel',
  status: 'active',
  wordCount: 15000,
  fileCount: 12,
  collaboratorCount: 2,
  updatedAt: '2023-11-20T10:00:00Z',
  createdAt: '2023-11-01T10:00:00Z',
  owner: 'test@example.com',
};

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('RepositoryCard', () => {
  it('displays repository information correctly', () => {
    renderWithRouter(<RepositoryCard repository={mockRepository} />);

    expect(screen.getByText('test-repo')).toBeInTheDocument();
    expect(screen.getByText('A test repository')).toBeInTheDocument();
    expect(screen.getByText('15,000')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('2 collaborator(s)')).toBeInTheDocument();
  });

  it('creates correct link to repository', () => {
    renderWithRouter(<RepositoryCard repository={mockRepository} />);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/repositories/test-repo');
  });
});
```

## Component Organization

### Directory Structure

```
src/components/
├── common/          # Shared components
│   ├── ErrorBoundary.tsx
│   ├── LoadingSpinner.tsx
│   └── QuickActions.tsx
├── layout/          # Layout components
│   ├── AppLayout.tsx
│   ├── Header.tsx
│   ├── Sidebar.tsx
│   └── StatusBar.tsx
├── pages/           # Page components
│   ├── Dashboard.tsx
│   ├── Editor.tsx
│   ├── Repository.tsx
│   └── Settings.tsx
├── ui/              # Basic UI components
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── Input.tsx
│   └── Modal.tsx
├── editor/          # Editor-specific components
│   ├── MarkdownEditor.tsx
│   ├── FileExplorer.tsx
│   ├── PreviewPanel.tsx
│   └── AnnotationPanel.tsx
├── repository/      # Repository components
│   ├── RepositoryCard.tsx
│   ├── RepositoryList.tsx
│   └── RepositorySettings.tsx
└── __tests__/       # Component tests
    ├── Button.test.tsx
    └── RepositoryCard.test.tsx
```

### Naming Conventions

- **PascalCase** for component names
- **camelCase** for props and functions
- **kebab-case** for CSS classes
- **SCREAMING_SNAKE_CASE** for constants

### Component Guidelines

1. **Single Responsibility**: Each component has one clear purpose
2. **Props Interface**: Always define TypeScript interfaces for props
3. **Error Handling**: Include error boundaries and fallbacks
4. **Accessibility**: Use semantic HTML and ARIA attributes
5. **Performance**: Implement React.memo and useMemo where appropriate
6. **Testing**: Write tests for all components with significant logic

---

*GitWrite's component architecture provides a solid foundation for building a scalable, maintainable, and user-friendly writing platform. The modular design enables rapid development while maintaining code quality and consistency.*