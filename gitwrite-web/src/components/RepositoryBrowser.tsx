import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { GitWriteClient, type RepositoryTreeResponse, type RepositoryTreeEntry, type RepositoryTreeBreadcrumbItem } from 'gitwrite-sdk';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { FolderIcon, FileTextIcon, ArrowLeftIcon, HomeIcon } from 'lucide-react'; // Icons
import { Button } from '@/components/ui/button';
import RepositoryStatus from './RepositoryStatus'; // Import the status component

// Helper to parse path from URL splat
const getPathFromSplat = (splat: string | undefined): string => {
  return splat ? splat.replace(/^\//, '') : '';
};

const RepositoryBrowser: React.FC = () => {
  const { repoName, '*': splatPath } = useParams<{ repoName: string; '*': string }>();
  const navigate = useNavigate();
  const location = useLocation(); // To get query params like branch

  const [treeData, setTreeData] = useState<RepositoryTreeResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // TODO: Branch selection logic. For now, hardcode or get from a non-existent query param for structure.
  const queryParams = new URLSearchParams(location.search);
  const currentBranch = queryParams.get('branch') || treeData?.ref || 'main'; // Fallback to main
  const currentPath = getPathFromSplat(splatPath);

  const fetchTree = useCallback(async (pathToList: string) => {
    if (!repoName) return;
    setIsLoading(true);
    setError(null);
    try {
      const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
      const token = localStorage.getItem('jwtToken');
      if (token) client.setToken(token);
      else {
        setError("Authentication token not found.");
        setIsLoading(false);
        return;
      }

      // MOCK DATA - Replace with actual API call
      // const response = await client.listRepositoryTree(repoName, currentBranch, pathToList);
      // setTreeData(response);

      // Simulating API call
      await new Promise(resolve => setTimeout(resolve, 700));
      const mockEntries: RepositoryTreeEntry[] = (pathToList === '' || pathToList === '/')
        ? [
            { name: 'README.md', path: 'README.md', type: 'blob', size: 1024, mode: '100644', oid: 'abc1' },
            { name: 'src', path: 'src', type: 'tree', mode: '040000', oid: 'def2' },
            { name: 'docs', path: 'docs', type: 'tree', mode: '040000', oid: 'ghi3' },
          ]
        : pathToList === 'src'
        ? [
            { name: 'index.js', path: 'src/index.js', type: 'blob', size: 2048, mode: '100644', oid: 'jkl4' },
            { name: 'components', path: 'src/components', type: 'tree', mode: '040000', oid: 'mno5' },
          ]
        : pathToList === 'src/components'
        ? [
            { name: 'Button.tsx', path: 'src/components/Button.tsx', type: 'blob', size: 1500, mode: '100644', oid: 'pqr6' },
          ]
        : pathToList === 'docs'
        ? [
            { name: 'getting-started.md', path: 'docs/getting-started.md', type: 'blob', size: 3000, mode: '100644', oid: 'stu7' },
          ]
        : [];

      const mockBreadcrumb: RepositoryTreeBreadcrumbItem[] = [{ name: repoName, path: '' }];
      if (pathToList) {
        pathToList.split('/').forEach((part, index, arr) => {
            mockBreadcrumb.push({ name: part, path: arr.slice(0, index + 1).join('/') });
        });
      }

      const mockResponse: RepositoryTreeResponse = {
        repo_name: repoName,
        ref: currentBranch,
        request_path: pathToList,
        entries: mockEntries,
        breadcrumb: mockBreadcrumb,
      };
      setTreeData(mockResponse);

    } catch (err) {
      console.error(`Failed to fetch tree for ${repoName}/${pathToList}:`, err);
      setError(`Failed to load directory contents for "${pathToList || '/'}".`);
    } finally {
      setIsLoading(false);
    }
  }, [repoName, currentBranch]); // Removed currentPath from deps as it's derived and causes re-fetch loops if not careful

  useEffect(() => {
    fetchTree(currentPath);
  }, [currentPath, fetchTree]); // fetchTree is memoized with useCallback

  const handleEntryClick = (entry: RepositoryTreeEntry) => {
    if (entry.type === 'tree') {
      navigate(`/repository/${repoName}/${entry.path}${location.search}`); // Preserve query params like branch
    } else {
      // TODO: Navigate to file viewer (Task 11.4)
      alert(`File clicked: ${entry.path}. File viewing not yet implemented.`);
    }
  };

  const handleBreadcrumbClick = (path: string) => {
    navigate(`/repository/${repoName}/${path}${location.search}`);
  };

  const navigateUp = () => {
    if (!currentPath) return; // Already at root
    const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
    navigate(`/repository/${repoName}/${parentPath}${location.search}`);
  };

  if (!repoName) {
    return <Alert variant="destructive"><AlertTitle>Error</AlertTitle><AlertDescription>Repository name not provided.</AlertDescription></Alert>;
  }

  return (
    <Card className="w-full max-w-5xl mx-auto">
      <CardHeader>
        <CardTitle className="text-2xl">Browse: {repoName}</CardTitle>
        {/* Breadcrumbs */}
        <div className="text-sm text-muted-foreground flex items-center space-x-1 mt-1">
          <HomeIcon className="h-4 w-4 cursor-pointer hover:text-primary" onClick={() => handleBreadcrumbClick('')} />
          <span>/</span>
          {treeData?.breadcrumb?.slice(1).map((item, index, arr) => (
            <React.Fragment key={item.path}>
              <span
                className={`hover:text-primary ${index === arr.length - 1 ? 'font-semibold text-primary' : 'cursor-pointer'}`}
                onClick={() => index !== arr.length - 1 && handleBreadcrumbClick(item.path)}
              >
                {item.name}
              </span>
              {index < arr.length - 1 && <span>/</span>}
            </React.Fragment>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <RepositoryStatus repoName={repoName} currentBranch={currentBranch} />

        <div className="mb-4">
          {currentPath && (
             <Button variant="outline" size="sm" onClick={navigateUp} className="mr-2">
                <ArrowLeftIcon className="mr-2 h-4 w-4" /> Up a level
            </Button>
          )}
          {/* TODO: Add branch selector dropdown here */}
        </div>

        {isLoading && (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        )}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {!isLoading && !error && treeData && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[50px]"></TableHead> {/* Icon column */}
                <TableHead>Name</TableHead>
                <TableHead>Last Commit (Placeholder)</TableHead>
                <TableHead className="text-right">Size</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {treeData.entries.length === 0 && !isLoading && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    This directory is empty.
                  </TableCell>
                </TableRow>
              )}
              {treeData.entries.map((entry) => (
                <TableRow key={entry.name} className="hover:bg-muted/50 cursor-pointer" onClick={() => handleEntryClick(entry)}>
                  <TableCell>
                    {entry.type === 'tree' ? <FolderIcon className="h-5 w-5 text-blue-500" /> : <FileTextIcon className="h-5 w-5 text-gray-500" />}
                  </TableCell>
                  <TableCell className="font-medium">{entry.name}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">Placeholder commit message...</TableCell>
                  <TableCell className="text-right text-sm text-muted-foreground">
                    {entry.type === 'blob' ? (entry.size !== null && entry.size !== undefined ? `${(entry.size / 1024).toFixed(1)} KB` : 'N/A') : ''}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
};

export default RepositoryBrowser;
