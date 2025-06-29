import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GitCommitIcon, GitBranchIcon, AlertTriangleIcon, EyeIcon } from 'lucide-react'; // Added EyeIcon

interface RepositoryStatusProps {
  repoName: string;
  currentBranch?: string | null; // Can be null if viewing a specific commit
  commitSha?: string; // Displayed if viewing a specific commit's tree
  isDirty?: boolean; // Placeholder for local changes status
}

const RepositoryStatus: React.FC<RepositoryStatusProps> = ({
  repoName,
  currentBranch,
  commitSha,
  isDirty = false,
}) => {
  return (
    <Card className="w-full mb-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{repoName} Status</CardTitle>
      </CardHeader>
      <CardContent className="text-sm space-y-2">
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

        {!commitSha && ( // Only show last commit if not viewing a specific commit's tree
            <div className="flex items-center space-x-2">
            <GitCommitIcon className="h-5 w-5 text-gray-600" />
            {/* TODO: Fetch and display actual last commit for the branch */}
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
