# State Management

GitWrite's frontend uses a combination of Zustand for global state management and TanStack Query for server state, providing a clean separation between client-side application state and server-synchronized data with excellent performance and developer experience.

## Overview

The state management architecture consists of:
- **Zustand Stores**: Global client state (auth, UI, editor)
- **TanStack Query**: Server state management and caching
- **React Context**: Component-level state when needed
- **Local Storage**: Persistent client preferences
- **Session Storage**: Temporary session data

```
State Architecture
    │
    ├─ Global State (Zustand)
    │   ├─ Auth Store
    │   ├─ UI Store
    │   ├─ Editor Store
    │   └─ Repository Store
    │
    ├─ Server State (TanStack Query)
    │   ├─ Query Cache
    │   ├─ Mutation Queue
    │   └─ Background Updates
    │
    └─ Persistent State
        ├─ Local Storage
        └─ Session Storage
```

## Zustand Stores

### 1. Authentication Store

```typescript
// src/stores/authStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: 'writer' | 'editor' | 'beta_reader' | 'admin';
  preferences: UserPreferences;
}

interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  language: string;
  editorFont: string;
  editorFontSize: number;
  autoSave: boolean;
  spellCheck: boolean;
}

interface AuthState {
  // State
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
  updatePreferences: (preferences: Partial<UserPreferences>) => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          const response = await authService.login(email, password);
          const { user, token } = response;

          // Store token in secure storage
          tokenStorage.setToken(token);

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({
            error: error.message,
            isLoading: false,
          });
        }
      },

      logout: () => {
        tokenStorage.clearToken();
        set({
          user: null,
          isAuthenticated: false,
          error: null,
        });
      },

      updateUser: (updates: Partial<User>) => {
        const currentUser = get().user;
        if (currentUser) {
          set({
            user: { ...currentUser, ...updates },
          });
        }
      },

      updatePreferences: (preferences: Partial<UserPreferences>) => {
        const currentUser = get().user;
        if (currentUser) {
          set({
            user: {
              ...currentUser,
              preferences: { ...currentUser.preferences, ...preferences },
            },
          });
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
```

### 2. UI Store

```typescript
// src/stores/uiStore.ts
interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  duration?: number;
  actions?: Array<{
    label: string;
    action: () => void;
  }>;
}

interface UIState {
  // Navigation
  sidebarOpen: boolean;
  sidebarWidth: number;

  // Notifications
  notifications: Notification[];

  // Modals and dialogs
  activeModal: string | null;
  modalData: any;

  // Loading states
  globalLoading: boolean;
  loadingMessage: string;

  // Theme and appearance
  theme: 'light' | 'dark' | 'system';
  reducedMotion: boolean;

  // Actions
  toggleSidebar: () => void;
  setSidebarWidth: (width: number) => void;
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  openModal: (modalType: string, data?: any) => void;
  closeModal: () => void;
  setGlobalLoading: (loading: boolean, message?: string) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      // Initial state
      sidebarOpen: true,
      sidebarWidth: 280,
      notifications: [],
      activeModal: null,
      modalData: null,
      globalLoading: false,
      loadingMessage: '',
      theme: 'system',
      reducedMotion: false,

      // Actions
      toggleSidebar: () => set(state => ({
        sidebarOpen: !state.sidebarOpen
      })),

      setSidebarWidth: (width: number) => set({ sidebarWidth: width }),

      addNotification: (notification) => {
        const id = crypto.randomUUID();
        const newNotification = { ...notification, id };

        set(state => ({
          notifications: [...state.notifications, newNotification],
        }));

        // Auto-remove after duration
        if (notification.duration !== 0) {
          const duration = notification.duration || 5000;
          setTimeout(() => {
            get().removeNotification(id);
          }, duration);
        }
      },

      removeNotification: (id: string) => set(state => ({
        notifications: state.notifications.filter(n => n.id !== id),
      })),

      clearNotifications: () => set({ notifications: [] }),

      openModal: (modalType: string, data?: any) => set({
        activeModal: modalType,
        modalData: data,
      }),

      closeModal: () => set({
        activeModal: null,
        modalData: null,
      }),

      setGlobalLoading: (loading: boolean, message = '') => set({
        globalLoading: loading,
        loadingMessage: message,
      }),

      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'ui-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        sidebarWidth: state.sidebarWidth,
        theme: state.theme,
        reducedMotion: state.reducedMotion,
      }),
    }
  )
);
```

### 3. Editor Store

```typescript
// src/stores/editorStore.ts
interface EditorFile {
  path: string;
  name: string;
  content: string;
  modified: boolean;
  lastSaved: Date;
  cursorPosition: number;
  scrollPosition: number;
}

interface EditorState {
  // Current editing context
  currentRepository: string | null;
  openFiles: EditorFile[];
  activeFile: string | null;

  // Editor configuration
  wordWrap: boolean;
  showLineNumbers: boolean;
  fontSize: number;
  tabSize: number;
  autoSave: boolean;
  autoSaveInterval: number;

  // Writing statistics
  dailyWordCount: number;
  sessionWordCount: number;
  totalWordCount: number;
  writingGoal: number;

  // Actions
  openFile: (file: EditorFile) => void;
  closeFile: (path: string) => void;
  setActiveFile: (path: string) => void;
  updateFileContent: (path: string, content: string) => void;
  saveFile: (path: string) => Promise<void>;
  saveAllFiles: () => Promise<void>;
  updateEditorConfig: (config: Partial<EditorState>) => void;
  updateWritingStats: (wordCount: number) => void;
}

export const useEditorStore = create<EditorState>()(
  persist(
    (set, get) => ({
      // Initial state
      currentRepository: null,
      openFiles: [],
      activeFile: null,
      wordWrap: true,
      showLineNumbers: true,
      fontSize: 16,
      tabSize: 2,
      autoSave: true,
      autoSaveInterval: 30000,
      dailyWordCount: 0,
      sessionWordCount: 0,
      totalWordCount: 0,
      writingGoal: 500,

      // Actions
      openFile: (file: EditorFile) => {
        set(state => {
          const existingIndex = state.openFiles.findIndex(f => f.path === file.path);

          if (existingIndex >= 0) {
            // File already open, just activate it
            return { activeFile: file.path };
          } else {
            // Add new file
            return {
              openFiles: [...state.openFiles, file],
              activeFile: file.path,
            };
          }
        });
      },

      closeFile: (path: string) => {
        set(state => {
          const newOpenFiles = state.openFiles.filter(f => f.path !== path);
          let newActiveFile = state.activeFile;

          // If closing active file, switch to another
          if (state.activeFile === path) {
            if (newOpenFiles.length > 0) {
              const closedIndex = state.openFiles.findIndex(f => f.path === path);
              const nextIndex = Math.min(closedIndex, newOpenFiles.length - 1);
              newActiveFile = newOpenFiles[nextIndex]?.path || null;
            } else {
              newActiveFile = null;
            }
          }

          return {
            openFiles: newOpenFiles,
            activeFile: newActiveFile,
          };
        });
      },

      setActiveFile: (path: string) => set({ activeFile: path }),

      updateFileContent: (path: string, content: string) => {
        set(state => ({
          openFiles: state.openFiles.map(file =>
            file.path === path
              ? { ...file, content, modified: true }
              : file
          ),
        }));
      },

      saveFile: async (path: string) => {
        const state = get();
        const file = state.openFiles.find(f => f.path === path);

        if (!file || !file.modified) return;

        try {
          await fileService.saveFile(state.currentRepository!, path, file.content);

          set(state => ({
            openFiles: state.openFiles.map(f =>
              f.path === path
                ? { ...f, modified: false, lastSaved: new Date() }
                : f
            ),
          }));
        } catch (error) {
          console.error('Failed to save file:', error);
          throw error;
        }
      },

      saveAllFiles: async () => {
        const state = get();
        const modifiedFiles = state.openFiles.filter(f => f.modified);

        await Promise.all(
          modifiedFiles.map(file => get().saveFile(file.path))
        );
      },

      updateEditorConfig: (config) => set(config),

      updateWritingStats: (wordCount: number) => {
        set(state => {
          const wordDiff = wordCount - state.totalWordCount;
          return {
            totalWordCount: wordCount,
            sessionWordCount: state.sessionWordCount + Math.max(0, wordDiff),
            dailyWordCount: state.dailyWordCount + Math.max(0, wordDiff),
          };
        });
      },
    }),
    {
      name: 'editor-storage',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        wordWrap: state.wordWrap,
        showLineNumbers: state.showLineNumbers,
        fontSize: state.fontSize,
        tabSize: state.tabSize,
        autoSave: state.autoSave,
        autoSaveInterval: state.autoSaveInterval,
        writingGoal: state.writingGoal,
      }),
    }
  )
);
```

## TanStack Query Integration

### 1. Query Client Setup

```typescript
// src/lib/queryClient.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      retry: (failureCount, error) => {
        // Don't retry on 401/403 errors
        if (error.status === 401 || error.status === 403) {
          return false;
        }
        return failureCount < 3;
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 1,
    },
  },
});

// Query invalidation patterns
export const queryKeys = {
  repositories: ['repositories'] as const,
  repository: (id: string) => ['repositories', id] as const,
  files: (repositoryId: string) => ['repositories', repositoryId, 'files'] as const,
  file: (repositoryId: string, path: string) => ['repositories', repositoryId, 'files', path] as const,
  collaborations: ['collaborations'] as const,
  annotations: (repositoryId: string) => ['repositories', repositoryId, 'annotations'] as const,
};
```

### 2. Repository Queries

```typescript
// src/hooks/useRepositories.ts
export const useRepositories = () => {
  return useQuery({
    queryKey: queryKeys.repositories,
    queryFn: repositoryService.getRepositories,
  });
};

export const useRepository = (name: string) => {
  return useQuery({
    queryKey: queryKeys.repository(name),
    queryFn: () => repositoryService.getRepository(name),
    enabled: !!name,
  });
};

export const useRepositoryFiles = (repositoryId: string) => {
  return useQuery({
    queryKey: queryKeys.files(repositoryId),
    queryFn: () => fileService.getFiles(repositoryId),
    enabled: !!repositoryId,
  });
};

// Mutations
export const useCreateRepository = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: repositoryService.createRepository,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.repositories });
    },
  });
};

export const useSaveFile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ repositoryId, path, content }: SaveFileParams) =>
      fileService.saveFile(repositoryId, path, content),
    onSuccess: (data, variables) => {
      // Update file cache
      queryClient.setQueryData(
        queryKeys.file(variables.repositoryId, variables.path),
        data
      );

      // Invalidate files list
      queryClient.invalidateQueries({
        queryKey: queryKeys.files(variables.repositoryId),
      });
    },
  });
};
```

### 3. Real-time Updates

```typescript
// src/hooks/useRealtimeUpdates.ts
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../stores/authStore';
import { useUIStore } from '../stores/uiStore';

export const useRealtimeUpdates = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const { addNotification } = useUIStore();

  useEffect(() => {
    if (!user) return;

    const ws = new WebSocket(`${config.wsUrl}?token=${user.token}`);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'repository_updated':
          queryClient.invalidateQueries({
            queryKey: queryKeys.repository(message.repositoryId),
          });
          break;
        case 'file_changed':
          queryClient.invalidateQueries({
            queryKey: queryKeys.file(message.repositoryId, message.filePath),
          });
          break;
        case 'collaboration_invite':
          addNotification({
            type: 'info',
            title: 'Collaboration Invite',
            message: `Invited to collaborate on ${message.repositoryName}`,
          });
          queryClient.invalidateQueries({
            queryKey: queryKeys.collaborations,
          });
          break;
      }
    };

    return () => ws.close();
  }, [user, queryClient, addNotification]);
};
```

## Performance Optimization

### State Selectors

```typescript
// Optimized selectors to prevent unnecessary re-renders
const useRepositorySelector = <T>(selector: (state: RepositoryState) => T) => {
  return useRepositoryStore(useCallback(selector, []));
};

const useCurrentRepository = () => {
  return useRepositorySelector(state => state.currentRepository);
};

const useRepositoryFiles = () => {
  return useRepositorySelector(state =>
    state.currentRepository?.files || []
  );
};
```

### State Persistence

```typescript
// Persist important state to localStorage
const createPersistentStore = <T>(name: string, initialState: T) => {
  return create<T>()(persist(
    (set, get) => ({
      ...initialState,
      // Store methods here
    }),
    {
      name: `gitwrite-${name}`,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // Only persist specific fields
        theme: state.theme,
        preferences: state.preferences,
      }),
    }
  ));
};
```

---

*GitWrite's state management system provides a robust, scalable foundation for handling complex writing workflows while maintaining excellent performance and developer experience through careful separation of concerns and optimized data flow patterns.*