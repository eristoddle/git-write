import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import FileContentViewer from '@/components/FileContentViewer';
import { Button } from '@/components/ui/button';
import { ArrowLeft } from 'lucide-react';
import { Card } from '@/components/ui/card';

interface FileContentViewerPageParams extends Record<string, string | undefined> {
  repoName: string;
  commitSha: string;
  '*': string; // Splat for the file path
}

const FileContentViewerPage: React.FC = () => {
  const { repoName, commitSha, '*': filePath } = useParams<FileContentViewerPageParams>();
  const navigate = useNavigate();

  if (!repoName || !commitSha || !filePath) {
    return (
      <div className="p-4">
        <p className="text-red-500">Error: Repository name, commit SHA, or file path is missing.</p>
        <Button onClick={() => navigate(-1)} variant="outline" className="mt-4">
          <ArrowLeft className="mr-2 h-4 w-4" /> Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4">
        <div className="mb-4">
            <Button onClick={() => navigate(-1)} variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" /> Back
            </Button>
        </div>
        <FileContentViewer
            repoName={repoName}
            filePath={filePath}
            commitSha={commitSha}
            feedbackBranch="feedback/main" // Hardcoded for now
        />
    </div>
  );
};

export default FileContentViewerPage;
