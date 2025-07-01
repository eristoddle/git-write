import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { GitWriteClient } from 'gitwrite-sdk';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner'; // Corrected import for sonner
import { LucideGitBranch, LucideGitMerge, LucideGitFork, LucideAlertCircle } from 'lucide-react';

const BranchManagementPage: React.FC = () => {
  const { repoName } = useParams<{ repoName: string }>();
  const navigate = useNavigate();
  const [client] = useState(() => new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'));

  const [branches, setBranches] = useState<string[]>([]);
  const [currentBranch, setCurrentBranch] = useState<string | null>(null); // Placeholder
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newBranchName, setNewBranchName] = useState('');
  const [selectedBranchToSwitch, setSelectedBranchToSwitch] = useState<string>('');
  const [selectedBranchToMerge, setSelectedBranchToMerge] = useState<string>('');

  const [isCreating, setIsCreating] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const [isMerging, setIsMerging] = useState(false);

  const fetchBranches = useCallback(async () => {
    if (!repoName) return;
    setIsLoading(true);
    setError(null);
    try {
      // TODO: Determine current branch. API's listBranches doesn't explicitly state it.
      // For now, we'll assume the first branch or a known default like 'main' is current,
      // or leave it as a UI challenge. A dedicated API endpoint /repository/branch (GET) would be ideal.
      // Alternatively, the `RepositoryStatus.tsx` component might have logic to derive this.
      // For this initial setup, currentBranch will remain a concept.
      const response = await client.listBranches(); // This client method might need repoName if API changes
      if (response.status === 'success' || response.status === 'empty_repo') { // empty_repo can have branches if initialized then all deleted
        setBranches(response.branches || []);
        // Heuristic: try to find main or master, or first branch as current if list is not empty
        if (response.branches && response.branches.length > 0) {
            if (response.branches.includes('main')) setCurrentBranch('main');
            else if (response.branches.includes('master')) setCurrentBranch('master');
            else setCurrentBranch(response.branches[0]);

            // Set default selections for dropdowns
            if (response.branches.length > 1) {
                const defaultSwitchTarget = response.branches.find(b => b !== currentBranch) || response.branches[0];
                setSelectedBranchToSwitch(defaultSwitchTarget);
                setSelectedBranchToMerge(defaultSwitchTarget);
            } else if (response.branches.length === 1) {
                setSelectedBranchToSwitch(response.branches[0]);
                setSelectedBranchToMerge(response.branches[0]);
            }

        } else {
            setCurrentBranch(null);
        }

      } else {
        setError(response.message || 'Failed to fetch branches.');
        setBranches([]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'An unknown error occurred.');
      setBranches([]);
    } finally {
      setIsLoading(false);
    }
  }, [repoName, client]);

  useEffect(() => {
    const token = localStorage.getItem('jwtToken');
    if (token) {
      client.setToken(token);
    } else {
      navigate('/login');
    }
    fetchBranches();
  }, [client, fetchBranches, navigate]);

  const handleCreateBranch = async () => {
    if (!newBranchName.trim() || !repoName) return;
    setIsCreating(true);
    setError(null);
    try {
      const response = await client.createBranch({ branch_name: newBranchName.trim() });
      toast.success("Branch Created", {
        description: `Branch '${response.branch_name}' created successfully. Head: ${response.head_commit_oid?.substring(0,7)}`,
      });
      setNewBranchName('');
      await fetchBranches(); // Refresh branch list
      setCurrentBranch(response.branch_name); // Switch current branch context
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to create branch.';
      setError(errorMessage);
      toast.error("Error Creating Branch", {
        description: errorMessage,
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleSwitchBranch = async (targetBranch?: string) => {
    const branchToSwitch = targetBranch || selectedBranchToSwitch;
    if (!branchToSwitch || !repoName) return;

    setIsSwitching(true);
    setError(null);
    try {
      const response = await client.switchBranch({ branch_name: branchToSwitch });
      toast.success("Branch Switched", {
        description: `Switched to branch '${response.branch_name}'. ${response.message}`,
      });
      setCurrentBranch(response.branch_name); // Update current branch context
      await fetchBranches(); // Refresh list and potentially other state
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to switch branch.';
      setError(errorMessage);
      toast.error("Error Switching Branch", {
        description: errorMessage,
      });
    } finally {
      setIsSwitching(false);
    }
  };

  const handleMergeBranch = async () => {
    if (!selectedBranchToMerge || !repoName) return;
    setIsMerging(true);
    setError(null);
    try {
      const response = await client.mergeBranch({ source_branch: selectedBranchToMerge });
      const toastDescription = response.message;

      if (response.status === 'conflict') {
        toast.error("Merge Conflict", {
          description: `${toastDescription} Conflicting files: ${response.conflicting_files?.join(', ')}`,
        });
      } else if (response.status.includes('error')) {
        toast.error("Merge Error", { description: toastDescription });
      } else if (response.status === 'merged_ok' || response.status === 'fast_forwarded') {
        toast.success("Merge Successful", { description: toastDescription });
      } else if (response.status === 'up_to_date') {
        toast.info("Already Up-to-date", { description: toastDescription });
      } else { // Should not happen ideally
        toast.info("Merge Operation", { description: toastDescription });
      }

      // Potentially refresh other data if merge affects current view, e.g., commit list
      await fetchBranches(); // Refresh branch list, current branch might have new commits
    } catch (err: any) {
      const errorMessageContent = err.response?.data?.detail || err.message || 'Failed to merge branch.';
      let descriptionForToast = '';
      if (typeof errorMessageContent === 'string') {
          descriptionForToast = errorMessageContent;
      } else if (typeof errorMessageContent === 'object' && errorMessageContent !== null && 'message' in errorMessageContent) {
          descriptionForToast = (errorMessageContent as any).message;
          if ((errorMessageContent as any).conflicting_files) {
              descriptionForToast += ` Conflicting files: ${((errorMessageContent as any).conflicting_files as string[]).join(', ')}`;
          }
      } else {
          descriptionForToast = JSON.stringify(errorMessageContent);
      }
      setError(descriptionForToast); // Keep page level error state if needed
      toast.error("Error Merging Branch", {
        description: descriptionForToast,
      });
    } finally {
      setIsMerging(false);
    }
  };


  if (!repoName) {
    return <Alert variant="destructive"><AlertTitle>Error</AlertTitle><AlertDescription>Repository name is missing.</AlertDescription></Alert>;
  }

  if (isLoading && branches.length === 0) {
    return (
      <div className="container mx-auto p-4">
        <CardHeader>
          <CardTitle>Branch Management for {repoName}</CardTitle>
          <CardDescription>Loading branch information...</CardDescription>
        </CardHeader>
        <Skeleton className="h-8 w-1/4 my-4" />
        <Skeleton className="h-32 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 space-y-6">
      <header className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Branch Management: {repoName}</h1>
        <Button onClick={() => navigate(`/repository/${repoName}/tree/${currentBranch || 'main'}`)}>Back to Browser</Button>
      </header>

      {currentBranch && <p className="text-lg">Current branch: <span className="font-semibold text-primary">{currentBranch}</span></p>}

      {error && (
        <Alert variant="destructive">
          <LucideAlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><LucideGitBranch className="mr-2" /> Branches</CardTitle>
          <CardDescription>View and manage branches in this repository.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && branches.length > 0 && <p>Refreshing branch list...</p>}
          {branches.length === 0 && !isLoading ? (
            <p>No branches found. Create one below.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Branch Name</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {branches.map((branch) => (
                  <TableRow key={branch} className={branch === currentBranch ? 'bg-muted/50' : ''}>
                    <TableCell className="font-medium">{branch}{branch === currentBranch && " (current)"}</TableCell>
                    <TableCell>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleSwitchBranch(branch)} // Pass branch directly
                        disabled={isSwitching || branch === currentBranch}
                        className="mr-2"
                      >
                        Switch To
                      </Button>
                      {/* Add delete button later if needed */}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center"><LucideGitFork className="mr-2" /> Create New Branch</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              type="text"
              placeholder="New branch name"
              value={newBranchName}
              onChange={(e) => setNewBranchName(e.target.value)}
              disabled={isCreating}
            />
            <Button onClick={handleCreateBranch} disabled={isCreating || !newBranchName.trim()}>
              {isCreating ? 'Creating...' : 'Create Branch'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center"><LucideGitBranch className="mr-2" /> Switch Branch</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select
              value={selectedBranchToSwitch}
              onValueChange={setSelectedBranchToSwitch}
              disabled={isSwitching || branches.length <= 1}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select branch to switch to" />
              </SelectTrigger>
              <SelectContent>
                {branches.filter(b => b !== currentBranch).map((branch) => (
                  <SelectItem key={branch} value={branch}>
                    {branch}
                  </SelectItem>
                ))}
                 {branches.filter(b => b !== currentBranch).length === 0 && branches.length > 0 &&
                    <SelectItem value={currentBranch!} disabled>{currentBranch} (current)</SelectItem>
                 }
              </SelectContent>
            </Select>
            <Button onClick={handleSwitchBranch} disabled={isSwitching || !selectedBranchToSwitch || selectedBranchToSwitch === currentBranch || branches.length === 0}>
              {isSwitching ? 'Switching...' : 'Switch to Selected'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center"><LucideGitMerge className="mr-2" /> Merge Branch</CardTitle>
            <CardDescription>Merge a branch into the current branch ({currentBranch || 'N/A'}).</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select
              value={selectedBranchToMerge}
              onValueChange={setSelectedBranchToMerge}
              disabled={isMerging || branches.length <=1}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select branch to merge" />
              </SelectTrigger>
              <SelectContent>
                {branches.filter(b => b !== currentBranch).map((branch) => (
                  <SelectItem key={branch} value={branch}>
                    {branch}
                  </SelectItem>
                ))}
                {branches.filter(b => b !== currentBranch).length === 0 && branches.length > 0 &&
                    <SelectItem value={currentBranch!} disabled>{currentBranch} (current, cannot merge into self)</SelectItem>
                 }
              </SelectContent>
            </Select>
            <Button onClick={handleMergeBranch} disabled={isMerging || !selectedBranchToMerge || selectedBranchToMerge === currentBranch || !currentBranch || branches.length === 0}>
              {isMerging ? 'Merging...' : `Merge into ${currentBranch || 'Current'}`}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default BranchManagementPage;
