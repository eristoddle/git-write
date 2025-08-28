import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { GitWriteClient, type RepositoryTreeResponse, type RepositoryTreeEntry, type RepositoryTreeBreadcrumbItem, type CommitDetail, type RepositoryBranchesResponse } from 'gitwrite-sdk'; // Added RepositoryBranchesResponse
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { FolderIcon, FileTextIcon, ArrowLeftIcon, HomeIcon, HistoryIcon } from 'lucide-react'; // Icons
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
  const [headCommitSha, setHeadCommitSha] = useState<string | null>(null);
  const [allBranches, setAllBranches] = useState<string[] | null>(null); // ADDED

  // The splatPath in this route `repository/:repoName/tree/*` is expected to contain the ref (branch name or commit SHA)
  // and then the path. e.g., "main/src/components", "main", or "<commit_sha>/src/components"
  const pathParts = splatPath?.split('/') || ['main']; // Default to 'main' if splat is empty
  const currentRef = pathParts[0] || 'main'; // This can be a branch name or a commit SHA
  const currentPath = pathParts.slice(1).join('/');

  // Determine if the currentRef is likely a commit SHA (e.g., 40 hex chars)
  // This is a heuristic. A more robust way might involve an API check or specific URL structure.
  const isViewingCommit = /^[0-9a-f]{40}$/i.test(currentRef);
  const currentBranchForDisplay = isViewingCommit ? `Commit: ${currentRef.substring(0,7)}...` : currentRef;
  const branchForHistoryAndStatus = isViewingCommit ? null : currentRef; // Use null if viewing a commit for status components

  const fetchLatestCommitSha = useCallback(async () => {
    if (!repoName || !branchForHistoryAndStatus || isViewingCommit) {
      // If viewing a commit, the headCommitSha is the commit SHA itself for file viewing purposes.
      // If no branch (e.g. viewing a specific commit directly), don't fetch latest commit of a branch.
      if(isViewingCommit) setHeadCommitSha(currentRef);
      return;
    }
    try {
      const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
      const token = localStorage.getItem('jwtToken');
      if (token) client.setToken(token);
      else { navigate('/login'); return; }

      const commitsResponse = await client.listCommits(repoName, { branchName: branchForHistoryAndStatus, maxCount: 1 });
      if (commitsResponse.status === 'success' && commitsResponse.commits.length > 0) {
        setHeadCommitSha(commitsResponse.commits[0].sha);
      } else if (commitsResponse.status !== 'no_commits') {
        console.warn(`Failed to fetch latest commit for ${branchForHistoryAndStatus}: ${commitsResponse.message}`);
        setHeadCommitSha(null); // Explicitly set to null on failure to fetch
      } else {
        setHeadCommitSha(null); // No commits on the branch
      }
    } catch (err) {
      console.warn(`Error fetching latest commit for ${branchForHistoryAndStatus}:`, err);
      setHeadCommitSha(null);
    }
  }, [repoName, branchForHistoryAndStatus, navigate, isViewingCommit, currentRef]);

  // ADDED fetchAllBranches definition
  const fetchAllBranches = useCallback(async () => {
    if (!repoName) return;
    try {
      const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
      const token = localStorage.getItem('jwtToken');
      if (token) client.setToken(token);
      else { navigate('/login'); return; }

      const response: RepositoryBranchesResponse = await client.listBranches(repoName);
      if (response.status === 'success') {
        setAllBranches(response.branches);
      } else {
        console.warn(`Failed to fetch all branches for ${repoName}: ${response.message}`);
        setAllBranches(null); // Explicitly set to null on failure
      }
    } catch (err) {
      console.warn(`Error fetching all branches for ${repoName}:`, err);
      setAllBranches(null); // Explicitly set to null on error
    }
  }, [repoName, navigate]);

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

      // Replace mock data with actual API call
      const response = await client.listRepositoryTree(repoName, currentRef, pathToList);
      setTreeData(response);

    } catch (err) {
      console.error(`Failed to fetch tree for ${repoName}/${currentRef}/${pathToList}:`, err);
      setError(`Failed to load directory contents for "${pathToList || '/'}".`);
    } finally {
      setIsLoading(false);
    }
  }, [repoName, currentRef, navigate]);

  useEffect(() => {
    fetchAllBranches();
  }, [fetchAllBranches]); // This useEffect IS ALREADY PRESENT and now fetchAllBranches will be defined

  useEffect(() => {
    fetchTree(currentPath);
    fetchLatestCommitSha();
  }, [currentPath, currentRef, fetchTree, fetchLatestCommitSha]);

  const handleEntryClick = (entry: RepositoryTreeEntry) => {
    // entry.path from API is relative to repo root. We need to build the URL with currentRef
    const targetTreePath = `${currentRef}/${entry.path}`;
    if (entry.type === 'tree') {
      navigate(`/repository/${repoName}/tree/${targetTreePath}`);
    } else {
      // If viewing a specific commit (isViewingCommit is true), currentRef is the commit SHA.
      // If viewing a branch, headCommitSha should be the latest commit of that branch.
      const commitShaToView = isViewingCommit ? currentRef : headCommitSha;
      if (commitShaToView) {
        navigate(`/repository/${repoName}/commit/${commitShaToView}/file/${entry.path}`);
      } else {
        setError("Could not determine the commit SHA to view the file. Please try again or check branch/commit status.");
      }
    }
  };

  const handleBreadcrumbClick = (path: string) => {
    const targetPath = path ? `${currentRef}/${path}` : currentRef;
    navigate(`/repository/${repoName}/tree/${targetPath}`);
  };

  const navigateToHistory = () => {
    if (branchForHistoryAndStatus) { // Only allow navigating to history if viewing a branch
        navigate(`/repository/${repoName}/history/${branchForHistoryAndStatus}`);
    }
  };

  const navigateUp = () => {
    if (!currentPath) return; // Already at root of the current branch view
    const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
    const targetPath = parentPath ? `${currentBranch}/${parentPath}` : currentBranch;
    navigate(`/repository/${repoName}/tree/${targetPath}`);
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
        {/* Pass branchForHistoryAndStatus which will be null if viewing a commit */}
        <RepositoryStatus
          repoName={repoName}
          currentBranch={branchForHistoryAndStatus}
          commitSha={isViewingCommit ? currentRef : undefined}
          allBranches={allBranches} // ADDED allBranches prop
        />

        <div className="mb-4 flex justify-between items-center">
          <div>
            {currentPath && (
              <Button variant="outline" size="sm" onClick={navigateUp} className="mr-2">
                  <ArrowLeftIcon className="mr-2 h-4 w-4" /> Up a level
              </Button>
            )}
            {/* TODO: Add branch/ref selector dropdown here */}
          </div>
          {!isViewingCommit && branchForHistoryAndStatus && ( // Only show history button if viewing a branch
            <Button variant="outline" size="sm" onClick={navigateToHistory}>
              <HistoryIcon className="mr-2 h-4 w-4" /> View Branch History
            </Button>
          )}
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
