# Frontend Application (React/TypeScript)

The GitWrite frontend is a modern, responsive web application built with React 18 and TypeScript, providing an intuitive writing environment that makes version control accessible to writers of all technical levels. The application emphasizes user experience, performance, and accessibility.

## Architecture Overview

### Technology Stack

**Core Framework:**
- **React 18**: Component-based UI with concurrent features
- **TypeScript**: Type safety and enhanced developer experience
- **Vite**: Lightning-fast development and optimized builds

**Styling and UI:**
- **Tailwind CSS**: Utility-first CSS framework
- **Radix UI**: Accessible component primitives
- **Lucide React**: Consistent icon library
- **Framer Motion**: Smooth animations and transitions

**State Management:**
- **Zustand**: Lightweight state management
- **TanStack Query**: Server state management and caching
- **React Hook Form**: Form handling and validation

**Development Tools:**
- **ESLint + Prettier**: Code quality and formatting
- **Vitest**: Unit testing framework
- **Playwright**: End-to-end testing
- **Storybook**: Component development and documentation

### Application Structure

```
gitwrite-web/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── ui/             # Base UI components (buttons, inputs, etc.)
│   │   ├── editor/         # Writing and editing components
│   │   ├── repository/     # Repository management components
│   │   ├── collaboration/  # Team and feedback components
│   │   └── export/         # Document export components
│   ├── pages/              # Page-level components
│   │   ├── Dashboard.tsx   # Project dashboard
│   │   ├── Editor.tsx      # Writing interface
│   │   ├── History.tsx     # Version history
│   │   └── Settings.tsx    # User and project settings
│   ├── hooks/              # Custom React hooks
│   ├── lib/                # Utility functions and configurations
│   ├── stores/             # Zustand state stores
│   ├── types/              # TypeScript type definitions
│   └── assets/             # Static assets
├── public/                 # Public assets
└── docs/                   # Component documentation
```

## Design System

### Component Architecture

The frontend follows a hierarchical component structure with clear separation of concerns:

```typescript
// Base UI Components (ui/)
interface BaseComponentProps {
  className?: string;
  children?: React.ReactNode;
  variant?: 'default' | 'secondary' | 'outline';
  size?: 'sm' | 'md' | 'lg';
}

// Composite Components (editor/, repository/, etc.)
interface FeatureComponentProps extends BaseComponentProps {
  data?: any;
  onAction?: (action: string, payload: any) => void;
  loading?: boolean;
  error?: string;
}

// Page Components
interface PageComponentProps {
  params?: Record<string, string>;
  searchParams?: Record<string, string>;
}
```

### Button Component Example

```typescript
// components/ui/button.tsx
import { forwardRef } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";

export { Button, buttonVariants };
```

## Core Components

### Writing Editor

The central writing interface built with a rich text editor:

```typescript
// components/editor/WritingEditor.tsx
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Collaboration } from '@tiptap/extension-collaboration';
import { CollaborationCursor } from '@tiptap/extension-collaboration-cursor';

interface WritingEditorProps {
  content: string;
  onChange: (content: string) => void;
  collaboration?: boolean;
  readOnly?: boolean;
  className?: string;
}

export function WritingEditor({
  content,
  onChange,
  collaboration = false,
  readOnly = false,
  className
}: WritingEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      ...(collaboration ? [
        Collaboration.configure({
          document: ydoc,
        }),
        CollaborationCursor.configure({
          provider: websocketProvider,
        }),
      ] : []),
    ],
    content,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    },
    editable: !readOnly,
  });

  return (
    <div className={cn("prose prose-slate max-w-none", className)}>
      <EditorToolbar editor={editor} />
      <EditorContent
        editor={editor}
        className="min-h-[500px] p-4 border rounded-lg focus-within:border-primary"
      />
      <EditorFooter editor={editor} />
    </div>
  );
}
```

### Repository Dashboard

Project overview and management interface:

```typescript
// components/repository/RepositoryDashboard.tsx
import { useQuery } from '@tanstack/react-query';
import { gitwriteClient } from '@/lib/api-client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface RepositoryDashboardProps {
  repositoryName: string;
}

export function RepositoryDashboard({ repositoryName }: RepositoryDashboardProps) {
  const { data: repository, isLoading, error } = useQuery({
    queryKey: ['repository', repositoryName],
    queryFn: () => gitwriteClient.repositories.get(repositoryName),
  });

  const { data: status } = useQuery({
    queryKey: ['repository-status', repositoryName],
    queryFn: () => gitwriteClient.repositories.getStatus(repositoryName),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isLoading) return <RepositoryDashboardSkeleton />;
  if (error) return <ErrorDisplay error={error} />;

  return (
    <div className="space-y-6">
      {/* Repository Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{repository.name}</h1>
          <p className="text-muted-foreground">{repository.description}</p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge variant={status?.is_clean ? 'default' : 'secondary'}>
            {status?.is_clean ? 'Clean' : 'Changes Pending'}
          </Badge>
          <Button onClick={() => openSaveDialog()}>
            Save Changes
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Word Count</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{repository.word_count.toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Files</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{repository.file_count}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Saves Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{status?.saves_today || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Collaborators</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{repository.collaborator_count || 0}</div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <RecentActivity repositoryName={repositoryName} />

      {/* File Browser */}
      <FileBrowser repositoryName={repositoryName} />
    </div>
  );
}
```

### File Browser

Navigate and manage project files:

```typescript
// components/repository/FileBrowser.tsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { File, Folder, MoreHorizontal } from 'lucide-react';
import { gitwriteClient } from '@/lib/api-client';

interface FileBrowserProps {
  repositoryName: string;
  currentPath?: string;
}

export function FileBrowser({ repositoryName, currentPath = '' }: FileBrowserProps) {
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);

  const { data: files, isLoading } = useQuery({
    queryKey: ['repository-files', repositoryName, currentPath],
    queryFn: () => gitwriteClient.repositories.getFiles(repositoryName, currentPath),
  });

  const handleFileSelect = (filePath: string) => {
    setSelectedFiles(prev =>
      prev.includes(filePath)
        ? prev.filter(f => f !== filePath)
        : [...prev, filePath]
    );
  };

  const handleFileOpen = (filePath: string) => {
    // Navigate to editor with file
    navigate(`/repositories/${repositoryName}/edit/${encodeURIComponent(filePath)}`);
  };

  if (isLoading) return <FileBrowserSkeleton />;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          Files
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm">
              <File className="h-4 w-4 mr-2" />
              New File
            </Button>
            <Button variant="outline" size="sm">
              <Folder className="h-4 w-4 mr-2" />
              New Folder
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {files?.map((file) => (
            <div
              key={file.path}
              className={cn(
                "flex items-center justify-between p-2 rounded-md hover:bg-accent cursor-pointer",
                selectedFiles.includes(file.path) && "bg-accent"
              )}
              onClick={() => handleFileSelect(file.path)}
              onDoubleClick={() => handleFileOpen(file.path)}
            >
              <div className="flex items-center space-x-3">
                {file.type === 'directory' ? (
                  <Folder className="h-4 w-4 text-blue-500" />
                ) : (
                  <File className="h-4 w-4 text-gray-500" />
                )}
                <span className="font-medium">{file.name}</span>
                {file.status && (
                  <Badge variant="secondary" className="text-xs">
                    {file.status}
                  </Badge>
                )}
              </div>

              <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                <span>{file.size}</span>
                <span>{file.modified}</span>
                <Button variant="ghost" size="sm">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

## State Management

### Zustand Stores

```typescript
// stores/repository-store.ts
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

interface RepositoryState {
  currentRepository: string | null;
  currentExploration: string;
  unsavedChanges: boolean;
  lastSaveTime: Date | null;

  // Actions
  setCurrentRepository: (name: string) => void;
  setCurrentExploration: (exploration: string) => void;
  markUnsavedChanges: () => void;
  markSaved: () => void;
}

export const useRepositoryStore = create<RepositoryState>()(
  devtools(
    (set, get) => ({
      currentRepository: null,
      currentExploration: 'main',
      unsavedChanges: false,
      lastSaveTime: null,

      setCurrentRepository: (name) => {
        set({ currentRepository: name });
      },

      setCurrentExploration: (exploration) => {
        set({ currentExploration: exploration });
      },

      markUnsavedChanges: () => {
        set({ unsavedChanges: true });
      },

      markSaved: () => {
        set({
          unsavedChanges: false,
          lastSaveTime: new Date()
        });
      },
    }),
    {
      name: 'repository-store',
    }
  )
);

// stores/user-store.ts
interface UserState {
  user: User | null;
  isAuthenticated: boolean;
  preferences: UserPreferences;

  // Actions
  setUser: (user: User | null) => void;
  updatePreferences: (preferences: Partial<UserPreferences>) => void;
  logout: () => void;
}

export const useUserStore = create<UserState>()(
  devtools((set) => ({
    user: null,
    isAuthenticated: false,
    preferences: {
      theme: 'system',
      editorFont: 'inter',
      autoSave: true,
      showWordCount: true,
    },

    setUser: (user) => {
      set({
        user,
        isAuthenticated: !!user
      });
    },

    updatePreferences: (newPreferences) => {
      set((state) => ({
        preferences: {
          ...state.preferences,
          ...newPreferences,
        },
      }));
    },

    logout: () => {
      set({
        user: null,
        isAuthenticated: false
      });
      // Clear local storage
      localStorage.removeItem('gitwrite-token');
    },
  }))
);
```

### API Client Integration

```typescript
// lib/api-client.ts
import { GitWriteClient } from '@gitwrite/sdk';
import { useUserStore } from '@/stores/user-store';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create authenticated client
export const createApiClient = () => {
  const token = localStorage.getItem('gitwrite-token');
  return new GitWriteClient(API_BASE_URL, token || undefined);
};

// Global client instance
export const gitwriteClient = createApiClient();

// Hook for reactive API client
export function useApiClient() {
  const { user } = useUserStore();

  return useMemo(() => {
    const token = localStorage.getItem('gitwrite-token');
    return new GitWriteClient(API_BASE_URL, token || undefined);
  }, [user]);
}
```

## Routing and Navigation

### React Router Setup

```typescript
// App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-background text-foreground">
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected routes */}
            <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/repositories/:name" element={<ProtectedRoute><RepositoryView /></ProtectedRoute>} />
            <Route path="/repositories/:name/edit/*" element={<ProtectedRoute><EditorPage /></ProtectedRoute>} />
            <Route path="/repositories/:name/history" element={<ProtectedRoute><HistoryPage /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

### Protected Routes

```typescript
// components/ProtectedRoute.tsx
import { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useUserStore } from '@/stores/user-store';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: UserRole;
}

export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { user, isAuthenticated } = useUserStore();
  const location = useLocation();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if user is authenticated on mount
    const token = localStorage.getItem('gitwrite-token');
    if (token && !user) {
      // Validate token and fetch user info
      validateTokenAndFetchUser(token).finally(() => {
        setIsLoading(false);
      });
    } else {
      setIsLoading(false);
    }
  }, [user]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRole && user && !hasRequiredRole(user.role, requiredRole)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}

async function validateTokenAndFetchUser(token: string) {
  try {
    const client = new GitWriteClient(API_BASE_URL, token);
    const user = await client.auth.getCurrentUser();
    useUserStore.getState().setUser(user);
  } catch (error) {
    // Token is invalid, clear it
    localStorage.removeItem('gitwrite-token');
    useUserStore.getState().logout();
  }
}
```

## Performance Optimizations

### Code Splitting

```typescript
// Lazy load pages for better performance
import { lazy, Suspense } from 'react';

const Dashboard = lazy(() => import('@/pages/Dashboard'));
const EditorPage = lazy(() => import('@/pages/EditorPage'));
const HistoryPage = lazy(() => import('@/pages/HistoryPage'));

// Wrap in Suspense
<Suspense fallback={<PageLoadingSkeleton />}>
  <Routes>
    <Route path="/" element={<Dashboard />} />
    <Route path="/editor/*" element={<EditorPage />} />
    <Route path="/history" element={<HistoryPage />} />
  </Routes>
</Suspense>
```

### Virtual Scrolling

```typescript
// components/VirtualList.tsx
import { FixedSizeList as List } from 'react-window';

interface VirtualCommitListProps {
  commits: CommitInfo[];
  onCommitSelect: (commit: CommitInfo) => void;
}

export function VirtualCommitList({ commits, onCommitSelect }: VirtualCommitListProps) {
  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => {
    const commit = commits[index];

    return (
      <div style={style} className="px-4 py-2 border-b hover:bg-accent cursor-pointer">
        <CommitListItem
          commit={commit}
          onClick={() => onCommitSelect(commit)}
        />
      </div>
    );
  };

  return (
    <List
      height={600}
      itemCount={commits.length}
      itemSize={80}
      className="border rounded-md"
    >
      {Row}
    </List>
  );
}
```

### Memoization

```typescript
// Optimize expensive components
const MemoizedEditor = memo(WritingEditor, (prevProps, nextProps) => {
  return (
    prevProps.content === nextProps.content &&
    prevProps.readOnly === nextProps.readOnly &&
    prevProps.collaboration === nextProps.collaboration
  );
});

// Optimize context values
const EditorContext = createContext<EditorContextValue | null>(null);

export function EditorProvider({ children }: { children: React.ReactNode }) {
  const [content, setContent] = useState('');
  const [selection, setSelection] = useState<Selection | null>(null);

  const contextValue = useMemo(() => ({
    content,
    setContent,
    selection,
    setSelection,
  }), [content, selection]);

  return (
    <EditorContext.Provider value={contextValue}>
      {children}
    </EditorContext.Provider>
  );
}
```

---

*The GitWrite frontend provides a modern, accessible, and performant writing environment that abstracts Git complexity while maintaining professional-grade version control capabilities.*