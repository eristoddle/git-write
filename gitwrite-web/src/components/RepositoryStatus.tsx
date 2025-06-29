import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { GitCommitIcon, GitBranchIcon, AlertTriangleIcon, EyeIcon, GitMergeIcon, ChevronsUpDownIcon } from 'lucide-react';

interface RepositoryStatusProps {
  repoName: string; // Changed from currentRepoName to repoName for consistency
  currentBranch?: string | null;
  commitSha?: string;
  isDirty?: boolean;
  allBranches?: string[] | null; // List of all branches for the dropdown
}

const RepositoryStatus: React.FC<RepositoryStatusProps> = ({
  repoName,
  currentBranch,
  commitSha,
  isDirty = false,
  allBranches,
}) => {
  const navigate = useNavigate();

  const handleReviewBranchSelect = (selectedBranchName: string) => {
    if (repoName && selectedBranchName) {
      navigate(`/repository/${repoName}/review-branch/${selectedBranchName}`);
    }
  };

  const otherBranches = allBranches?.filter(b => b !== currentBranch) || [];

  return (
    <Card className="w-full mb-4">
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <CardTitle className="text-lg">{repoName} Status</CardTitle>
        {/* Cherry Pick Dropdown - only if not viewing a specific commit and other branches exist */}
        {!commitSha && currentBranch && otherBranches.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <GitMergeIcon className="mr-2 h-4 w-4" /> Review for Cherry-Pick <ChevronsUpDownIcon className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Review Commits From Branch</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {otherBranches.map((branch) => (
                <DropdownMenuItem key={branch} onClick={() => handleReviewBranchSelect(branch)}>
                  {branch}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </CardHeader>
      <CardContent className="text-sm space-y-2 pt-2">
        {commitSha ? (
          <div className="flex items-center space-x-2">
            <EyeIcon className="h-5 w-5 text-blue-600" />
            <span>Viewing Commit: <strong className="font-mono">{commitSha.substring(0, 12)}...</strong></span>
          </div>
        ) : currentBranch ? (
          <div className="flex items-center space-x-2">
            <GitBranchIcon className="h-5 w-5 text-gray-600" />
            <span>Current Branch: <strong>{currentBranch}</strong></span>
          </div>
        ) : (
          <div className="flex items-center space-x-2">
            <GitBranchIcon className="h-5 w-5 text-gray-400" />
            <span>Branch: <span className="italic text-gray-500">(Unknown/Not Applicable)</span></span>
          </div>
        )}

        {!commitSha && (
            <div className="flex items-center space-x-2">
            <GitCommitIcon className="h-5 w-5 text-gray-600" />
            <span>Last Commit on {currentBranch || 'current view'}: <span className="italic text-gray-500">(Placeholder SHA)</span></span>
            </div>
        )}

        {isDirty && (
          <div className="flex items-center space-x-2 text-yellow-600">
            <AlertTriangleIcon className="h-5 w-5" />
            <span>Uncommitted changes present (Placeholder)</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default RepositoryStatus;
