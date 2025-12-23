import { useState } from 'react';
import { FileText, Trash2, Calendar, Layers, FolderOpen, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
import { ScrollArea } from '@/components/ui/scroll-area';
import { useChatStore } from '@/stores/chatStore';
import { cn } from '@/lib/utils';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

function getFileIcon(type: string) {
  return FileText;
}

export function ViewDocumentsModal() {
  const {
    viewDocumentsModalOpen,
    setViewDocumentsModalOpen,
    viewingCollectionId,
    setViewingCollectionId,
    collections,
    getDocumentsByCollection,
    deleteDocument,
  } = useChatStore();

  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deletingDoc, setDeletingDoc] = useState<{ id: string; name: string } | null>(null);

  const collection = collections.find((c) => c.id === viewingCollectionId);
  const documents = getDocumentsByCollection(viewingCollectionId);
  const collectionName = collection?.name || 'All Documents';

  const handleClose = () => {
    setViewDocumentsModalOpen(false);
    setViewingCollectionId(null);
  };

  const handleDeleteClick = (doc: { id: string; name: string }) => {
    setDeletingDoc(doc);
    setDeleteConfirmId(doc.id);
  };

  const handleConfirmDelete = () => {
    if (deletingDoc) {
      deleteDocument(deletingDoc.id);
    }
    setDeleteConfirmId(null);
    setDeletingDoc(null);
  };

  return (
    <>
      <Dialog open={viewDocumentsModalOpen} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-[550px] max-h-[80vh] flex flex-col">
          <DialogHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <FolderOpen className="h-5 w-5 text-primary" />
              </div>
              <div>
                <DialogTitle>{collectionName}</DialogTitle>
                <DialogDescription>
                  {documents.length} document{documents.length !== 1 ? 's' : ''} in this collection
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <ScrollArea className="flex-1 -mx-6 px-6">
            {documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-4">
                  <FileText className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="text-sm font-medium text-foreground mb-1">No documents yet</p>
                <p className="text-sm text-muted-foreground">
                  Upload documents to this collection to get started
                </p>
              </div>
            ) : (
              <div className="space-y-2 py-2">
                {documents.map((doc) => {
                  const FileIcon = getFileIcon(doc.type);
                  return (
                    <div
                      key={doc.id}
                      className="group flex items-center gap-3 p-3 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors"
                    >
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                        <FileIcon className="h-5 w-5 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">
                          {doc.name}
                        </p>
                        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {formatDate(doc.uploadedAt)}
                          </span>
                          <span className="flex items-center gap-1">
                            <Layers className="h-3 w-3" />
                            {doc.chunkCount} chunks
                          </span>
                          <span>{formatFileSize(doc.size)}</span>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                        onClick={() => handleDeleteClick({ id: doc.id, name: doc.name })}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation dialog */}
      <AlertDialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              Delete Document
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deletingDoc?.name}"? This will remove all indexed chunks for this document. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete Document
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
