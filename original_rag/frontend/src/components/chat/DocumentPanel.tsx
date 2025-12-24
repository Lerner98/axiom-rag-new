import { useState, useCallback } from 'react';
import { X, Upload, FileText, File, Trash2, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useChatStore, Document } from '@/stores/chatStore';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface DocumentPanelProps {
  chatId: string;
  chatTitle: string;
}

export function DocumentPanel({ chatId, chatTitle }: DocumentPanelProps) {
  const {
    documentPanelOpen,
    setDocumentPanelOpen,
    getCurrentChatDocuments,
    addDocumentToChat,
    removeDocumentFromChat,
  } = useChatStore();

  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deleteConfirmDoc, setDeleteConfirmDoc] = useState<Document | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const documents = getCurrentChatDocuments();
  const acceptedTypes = ['.pdf', '.txt', '.md', '.docx'];

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files).filter((file) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      return acceptedTypes.includes(ext);
    });

    if (droppedFiles.length > 0) {
      await uploadFiles(droppedFiles);
    }
  }, [chatId]);

  const uploadFiles = async (files: File[]) => {
    setIsUploading(true);
    setUploadError(null);

    try {
      const result = await api.uploadChatDocuments(chatId, files);

      // Add successfully uploaded documents to store
      for (const uploaded of result.uploaded) {
        const file = files.find((f) => f.name === uploaded.name);
        addDocumentToChat(chatId, {
          id: uploaded.id,
          name: uploaded.name,
          type: file?.type || 'application/octet-stream',
          size: file?.size || 0,
          chunkCount: uploaded.chunk_count,
        });
      }

      // Show error if any files failed
      if (result.failed.length > 0) {
        setUploadError(
          `Failed to upload: ${result.failed.map((f) => `${f.name} (${f.error})`).join(', ')}`
        );
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteDocument = async () => {
    if (!deleteConfirmDoc) return;

    setIsDeleting(true);
    try {
      await api.deleteChatDocument(chatId, deleteConfirmDoc.id);
      removeDocumentFromChat(chatId, deleteConfirmDoc.id);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setIsDeleting(false);
      setDeleteConfirmDoc(null);
    }
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return <FileText className="h-5 w-5 text-red-500" />;
    if (ext === 'md') return <FileText className="h-5 w-5 text-blue-500" />;
    if (ext === 'txt') return <FileText className="h-5 w-5 text-gray-500" />;
    return <File className="h-5 w-5 text-muted-foreground" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  if (!documentPanelOpen) return null;

  return (
    <>
      <aside className="w-80 h-full bg-card border-l border-border flex flex-col shrink-0">
        {/* Header */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-border">
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-foreground truncate">{chatTitle}</h2>
            <p className="text-xs text-muted-foreground">
              {documents.length} document{documents.length !== 1 ? 's' : ''}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setDocumentPanelOpen(false)}
            className="h-8 w-8 shrink-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Upload zone - drag and drop only */}
        <div className="p-4">
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={cn(
              'border-2 border-dashed rounded-lg p-4 text-center transition-colors',
              isDragging
                ? 'border-primary bg-primary/5'
                : 'border-border',
              isUploading && 'opacity-50 pointer-events-none'
            )}
          >
            {isUploading ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">Uploading...</span>
              </div>
            ) : (
              <>
                <Upload className="h-6 w-6 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm font-medium">Drop files here</p>
                <p className="text-xs text-muted-foreground mt-1">PDF, TXT, MD, DOCX</p>
              </>
            )}
          </div>
        </div>

        {/* Error message */}
        {uploadError && (
          <div className="mx-4 mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{uploadError}</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5 shrink-0 ml-auto -mr-1 -mt-1"
              onClick={() => setUploadError(null)}
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        )}

        {/* Document list */}
        <div className="flex-1 overflow-y-auto px-2 pb-4">
          {documents.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <FileText className="h-10 w-10 mx-auto mb-3 opacity-50" />
              <p className="text-sm font-medium">No documents yet</p>
              <p className="text-xs mt-1">Upload documents to this chat to get started</p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-2 p-2 pr-1 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                >
                  {getFileIcon(doc.name)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{doc.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(doc.size)} · {doc.chunkCount} chunks
                    </p>
                  </div>
                  <button
                    type="button"
                    className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors flex-shrink-0"
                    onClick={() => setDeleteConfirmDoc(doc)}
                    title="Delete document"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Delete confirmation dialog */}
      <AlertDialog open={!!deleteConfirmDoc} onOpenChange={() => setDeleteConfirmDoc(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Document</AlertDialogTitle>
            <AlertDialogDescription>
              Delete "{deleteConfirmDoc?.name}"? This will remove the document and all its indexed
              content from this chat. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteDocument}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete Document'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
