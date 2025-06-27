import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GitCommitIcon, GitBranchIcon, AlertTriangleIcon } from 'lucide-react'; // Example icons

interface RepositoryStatusProps {
  repoName: string;
  currentBranch: string; // This would eventually come from API or Git state
  isDirty?: boolean; // Placeholder for local changes status
  // We might add last commit info here later
}

const RepositoryStatus: React.FC<RepositoryStatusProps> = ({
  repoName,
  currentBranch,
  isDirty = false, // Default to not dirty
}) => {
  return (
    <Card className="w-full mb-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{repoName} Status</CardTitle>
      </CardHeader>
      <CardContent className="text-sm">
        <div className="flex items-center space-x-2 mb-2">
          <GitBranchIcon className="h-5 w-5 text-gray-600" />
          <span>Current Branch: <strong>{currentBranch}</strong></span>
        </div>
        {/* Placeholder for commit info - could be an API call */}
        <div className="flex items-center space-x-2 mb-2">
          <GitCommitIcon className="h-5 w-5 text-gray-600" />
          <span>Last Commit: <span className="italic text-gray-500">(Placeholder)</span></span>
        </div>
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
