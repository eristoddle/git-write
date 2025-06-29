import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { GitWriteClient, type StructuredDiffFile, type CompareRefsResponse } from 'gitwrite-sdk';
import WordDiffDisplay from '@/components/WordDiffDisplay';
import { Button } from '@/components/ui/button';
import { ArrowLeft } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface WordDiffViewerPageParams extends Record<string, string | undefined> {
  repoName: string;
  ref1: string;
  ref2: string;
}

const WordDiffViewerPage: React.FC = () => {
  const { repoName, ref1, ref2 } = useParams<WordDiffViewerPageParams>();
  const navigate = useNavigate();
  const [diffData, setDiffData] = useState<StructuredDiffFile[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!repoName || !ref1 || !ref2) {
      setError("Repository name or commit references are missing.");
      setIsLoading(false);
      return;
    }

    const fetchDiff = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const token = localStorage.getItem('jwtToken');
        if (!token) {
          navigate('/login');
          return;
        }
        const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
        client.setToken(token);

        // Assuming the API and SDK handle repoName contextually or it's part of baseURL setup
        const response = await client.compareRefs({ ref1, ref2, diff_mode: 'word' });

        // The CompareRefsResponse.patch_data can be string | StructuredDiffFile[]
        // We need to assert or check the type when diff_mode is 'word'
        if (typeof response.patch_data === 'string') {
          setError("Received plain text diff instead of structured word diff. Check API call.");
          setDiffData(null);
        } else {
          setDiffData(response.patch_data);
        }

      } catch (err: any) {
        console.error("Error fetching diff:", err);
        setError(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || err.message || 'An unexpected error occurred while fetching the diff.');
        if (err.response?.status === 401) {
          navigate('/login');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchDiff();
  }, [repoName, ref1, ref2, navigate]);

  return (
    <div className="container mx-auto p-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center">
                <Button variant="outline" size="icon" onClick={() => navigate(-1)} className="mr-4">
                    <ArrowLeft className="h-4 w-4" />
                </Button>
                <CardTitle>
                    Viewing Diff for {repoName}
                </CardTitle>
            </div>
        </CardHeader>
        <CardContent>
            <div className="mb-4 p-2 border rounded-md bg-muted">
                <p className="text-sm text-muted-foreground">Comparing:</p>
                <p className="font-mono text-xs">Base (Old): {ref1}</p>
                <p className="font-mono text-xs">Changed (New): {ref2}</p>
            </div>
            <WordDiffDisplay
            diffData={diffData}
            isLoading={isLoading}
            error={error}
            repoName={repoName}
            ref1={ref1}
            ref2={ref2}
            />
        </CardContent>
      </Card>
    </div>
  );
};

export default WordDiffViewerPage;
