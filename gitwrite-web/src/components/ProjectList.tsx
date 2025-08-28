import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GitWriteClient, type RepositoryListItem, type RepositoriesListResponse } from 'gitwrite-sdk';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton'; // For loading state
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'; // For error state
import { ExternalLink } from 'lucide-react'; // Example icon

const ProjectList: React.FC = () => {
  const [projects, setProjects] = useState<RepositoryListItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProjects = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // Assuming the API client is instantiated correctly, possibly from a context or global instance
        // For now, direct instantiation for simplicity. Ensure API is running at this address.
        const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
        const token = localStorage.getItem('jwtToken');
        if (token) {
          client.setToken(token);
        } else {
          // Handle case where token is not available, e.g., redirect to login
          setError("Authentication token not found. Please log in.");
          setIsLoading(false);
          return;
        }

        // Replace mock data with actual API call
        const response: RepositoriesListResponse = await client.listRepositories();
        setProjects(response.repositories);

      } catch (err) {
        console.error("Failed to fetch projects:", err);
        setError("Failed to load projects. Please try again later.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const handleProjectClick = (repoName: string) => {
    navigate(`/repository/${repoName}`);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Your Projects</CardTitle>
          <CardDescription>Loading your GitWrite projects...</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (projects.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Your Projects</CardTitle>
        </CardHeader>
        <CardContent>
          <p>No projects found. You can create a new project using the GitWrite CLI or API.</p>
          {/* TODO: Link to a "Create Project" UI if/when that's built */}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-4xl mx-auto">
      <CardHeader>
        <CardTitle>Your Projects</CardTitle>
        <CardDescription>Select a project to view its details and browse files.</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Last Modified</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {projects.map((project) => (
              <TableRow key={project.name} className="hover:bg-muted/50 cursor-pointer" onClick={() => handleProjectClick(project.name)}>
                <TableCell className="font-medium">{project.name}</TableCell>
                <TableCell>{project.description || 'N/A'}</TableCell>
                <TableCell>{new Date(project.last_modified).toLocaleDateString()}</TableCell>
                <TableCell className="text-right">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleProjectClick(project.name);}}
                    className="text-sm text-blue-600 hover:underline inline-flex items-center"
                  >
                    Open <ExternalLink className="ml-1 h-4 w-4" />
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};

export default ProjectList;
