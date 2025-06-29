import React from 'react';
import { Annotation, AnnotationStatus } from 'gitwrite-sdk';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area'; // For potentially long lists of annotations
import { ThumbsUp, ThumbsDown, MessageSquare } from 'lucide-react';

interface AnnotationSidebarProps {
  annotations: Annotation[];
  onUpdateStatus: (annotationId: string, newStatus: AnnotationStatus) => void;
  isLoadingStatusUpdate: { [annotationId: string]: boolean }; // To show loading on specific annotation
  currentFilePath: string; // To filter annotations for the current file
}

const AnnotationSidebar: React.FC<AnnotationSidebarProps> = ({
  annotations,
  onUpdateStatus,
  isLoadingStatusUpdate,
  currentFilePath,
}) => {
  const relevantAnnotations = annotations.filter(
    (ann) => ann.file_path === currentFilePath
  );

  if (relevantAnnotations.length === 0) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No annotations for this file.
      </div>
    );
  }

  const getStatusBadgeVariant = (status: AnnotationStatus) => {
    switch (status) {
      case AnnotationStatus.NEW:
        return 'secondary';
      case AnnotationStatus.ACCEPTED:
        return 'default'; // Typically green-ish or primary
      case AnnotationStatus.REJECTED:
        return 'destructive';
      default:
        return 'outline';
    }
  };

  return (
    <Card className="w-full h-full flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center">
          <MessageSquare className="mr-2 h-5 w-5" /> Annotations
        </CardTitle>
        <CardDescription>Review feedback for: {currentFilePath}</CardDescription>
      </CardHeader>
      <CardContent className="flex-grow overflow-hidden p-0">
        <ScrollArea className="h-full p-4">
          <div className="space-y-3">
            {relevantAnnotations.map((annotation) => (
              <Card key={annotation.id || annotation.commit_id} className="shadow-sm">
                <CardHeader className="p-3">
                  <div className="flex justify-between items-start">
                    <CardTitle className="text-sm font-semibold">
                      {annotation.author}
                    </CardTitle>
                    <Badge variant={getStatusBadgeVariant(annotation.status)} className="capitalize">
                      {annotation.status}
                    </Badge>
                  </div>
                  {annotation.highlighted_text && (
                    <p className="text-xs text-muted-foreground italic border-l-2 border-primary pl-2 my-1">
                      "{annotation.highlighted_text}"
                    </p>
                  )}
                </CardHeader>
                <CardContent className="p-3 text-sm">
                  <p>{annotation.comment}</p>
                  <div className="mt-2 pt-2 border-t flex justify-end space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        onUpdateStatus(annotation.id!, AnnotationStatus.ACCEPTED)
                      }
                      disabled={isLoadingStatusUpdate[annotation.id!] || annotation.status === AnnotationStatus.ACCEPTED}
                      className="text-green-600 hover:text-green-700 border-green-500 hover:border-green-600"
                    >
                      <ThumbsUp className="mr-1 h-4 w-4" /> Accept
                      {isLoadingStatusUpdate[annotation.id!] && annotation.status !== AnnotationStatus.ACCEPTED && "ing..."}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        onUpdateStatus(annotation.id!, AnnotationStatus.REJECTED)
                      }
                      disabled={isLoadingStatusUpdate[annotation.id!] || annotation.status === AnnotationStatus.REJECTED}
                      className="text-red-600 hover:text-red-700 border-red-500 hover:border-red-600"
                    >
                      <ThumbsDown className="mr-1 h-4 w-4" /> Reject
                       {isLoadingStatusUpdate[annotation.id!] && annotation.status !== AnnotationStatus.REJECTED && "ing..."}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default AnnotationSidebar;
