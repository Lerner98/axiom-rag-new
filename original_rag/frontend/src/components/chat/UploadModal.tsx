import { useState, useCallback, useEffect, useRef } from 'react';
import { Upload, X, FileText, File, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { useChatStore } from '@/stores/chatStore';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface UploadFile {
  file: File;
  id: string;
}

type UploadState = 'idle' | 'uploading' | 'processing' | 'indexing' | 'success' | 'error';

export function UploadModal() {
  const { uploadModalOpen, setUploadModalOpen, collections, addCollection, addDocuments } = useChatStore();
  
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [newCollectionName, setNewCollectionName] = useState('');
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const acceptedTypes = ['.pdf', '.txt', '.md', '.docx'];

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files).filter((file) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      return acceptedTypes.includes(ext);
    });

    const newFiles = droppedFiles.map((file) => ({
      file,
      id: Math.random().toString(36).substring(2, 15),
    }));

    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files).map((file) => ({
        file,
        id: Math.random().toString(36).substring(2, 15),
      }));
      setFiles((prev) => [...prev, ...selectedFiles]);
    }
  };

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return <FileText className="h-5 w-5 text-red-500" />;
    if (ext === 'md') return <FileText className="h-5 w-5 text-blue-500" />;
    return <File className="h-5 w-5 text-muted-foreground" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    let collectionName = '';

    // Determine collection name
    if (selectedCollection === 'new' && newCollectionName.trim()) {
      collectionName = newCollectionName.trim();
      addCollection(collectionName);
    } else if (selectedCollection) {
      collectionName = collections.find((c) => c.id === selectedCollection)?.name || '';
    }

    setUploadState('uploading');
    setProgress(0);
    setError(null);

    try {
      const uploadPromises = files.map(async (f, index) => {
        const response = await api.ingestFile(f.file, collectionName || undefined);
        // Update progress based on files completed
        setProgress(Math.round(((index + 1) / files.length) * 60));
        return response;
      });

      const results = await Promise.all(uploadPromises);
      setUploadState('processing');
      setProgress(70);

      // Poll for completion of ingestion jobs
      const jobIds = results.map((r) => r.job_id);
      let allCompleted = false;
      let attempts = 0;
      const maxAttempts = 30;

      while (!allCompleted && attempts < maxAttempts) {
        await new Promise((r) => setTimeout(r, 1000));
        attempts++;

        const statuses = await Promise.all(jobIds.map((id) => api.getIngestStatus(id)));
        const completed = statuses.filter((s) => s.status === 'completed').length;
        const failed = statuses.filter((s) => s.status === 'failed');

        setProgress(70 + Math.round((completed / jobIds.length) * 30));

        if (failed.length > 0) {
          throw new Error(`Failed to process ${failed.length} file(s): ${failed.map((f) => f.errors.join(', ')).join('; ')}`);
        }

        allCompleted = statuses.every((s) => s.status === 'completed');
        if (statuses.some((s) => s.status === 'processing')) {
          setUploadState('indexing');
        }
      }

      if (!allCompleted) {
        throw new Error('Upload timed out. Files may still be processing.');
      }

      // Update local store with uploaded documents
      const collectionId = selectedCollection === 'new'
        ? useChatStore.getState().collections.find((c) => c.name === collectionName)?.id || ''
        : selectedCollection;

      addDocuments(
        files.map((f) => ({
          name: f.file.name,
          type: f.file.type,
          size: f.file.size,
          chunkCount: Math.ceil(f.file.size / 1000),
          collectionId,
        }))
      );

      setUploadState('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploadState('error');
    }
  };

  const handleClose = () => {
    setUploadModalOpen(false);
    // Reset state after animation
    setTimeout(() => {
      setFiles([]);
      setSelectedCollection('');
      setNewCollectionName('');
      setUploadState('idle');
      setProgress(0);
      setError(null);
    }, 200);
  };

  const getStatusText = (): string => {
    if (uploadState === 'uploading') return 'Uploading...';
    if (uploadState === 'processing') return 'Processing...';
    if (uploadState === 'indexing') return 'Indexing...';
    return '';
  };

  const isUploading = uploadState === 'uploading' || uploadState === 'processing' || uploadState === 'indexing';

  return (
    <Dialog open={uploadModalOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Upload Documents</DialogTitle>
        </DialogHeader>

        {uploadState === 'success' ? (
          <div className="py-8 text-center animate-scale-in">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-100 flex items-center justify-center">
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
            <h3 className="text-lg font-medium mb-2">
              {files.length} document{files.length > 1 ? 's' : ''} uploaded successfully
            </h3>
            <p className="text-sm text-muted-foreground mb-6">
              Added to {selectedCollection === 'new' ? newCollectionName : collections.find(c => c.id === selectedCollection)?.name || 'All Documents'}
            </p>
            <Button onClick={handleClose}>Done</Button>
          </div>
        ) : uploadState === 'error' ? (
          <div className="py-8 text-center animate-scale-in">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-destructive/10 flex items-center justify-center">
              <AlertCircle className="w-8 h-8 text-destructive" />
            </div>
            <h3 className="text-lg font-medium mb-2">Upload failed</h3>
            <p className="text-sm text-muted-foreground mb-6">{error || 'An error occurred'}</p>
            <div className="flex gap-3 justify-center">
              <Button variant="outline" onClick={() => setUploadState('idle')}>
                Try Again
              </Button>
              <Button onClick={handleClose}>Close</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Drop zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={cn(
                'relative border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer',
                isDragging
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-primary/50 hover:bg-muted/50'
              )}
            >
              <input
                type="file"
                accept={acceptedTypes.join(',')}
                multiple
                onChange={handleFileSelect}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                disabled={uploadState !== 'idle'}
              />
              <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
              <p className="text-sm font-medium mb-1">Drag and drop files here</p>
              <p className="text-xs text-muted-foreground">or click to browse</p>
            </div>

            {/* File type info */}
            <div className="text-xs text-muted-foreground text-center">
              <p>Supported: PDF, TXT, Markdown, DOCX</p>
              <p>Max size: 50MB per file</p>
            </div>

            {/* Selected files */}
            {files.length > 0 && (
              <div className="space-y-2 max-h-40 overflow-y-auto scrollbar-thin">
                {files.map((f) => (
                  <div
                    key={f.id}
                    className="flex items-center gap-3 p-2 rounded-lg bg-muted"
                  >
                    {getFileIcon(f.file.name)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{f.file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(f.file.size)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                      onClick={() => removeFile(f.id)}
                      disabled={uploadState !== 'idle'}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            {/* Collection selector */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Add to collection</label>
              <Select
                value={selectedCollection}
                onValueChange={setSelectedCollection}
                disabled={uploadState !== 'idle'}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a collection" />
                </SelectTrigger>
                <SelectContent>
                  {collections.map((collection) => (
                    <SelectItem key={collection.id} value={collection.id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                  <SelectItem value="new">+ Create new collection</SelectItem>
                </SelectContent>
              </Select>

              {selectedCollection === 'new' && (
                <Input
                  placeholder="Collection name"
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                  disabled={uploadState !== 'idle'}
                />
              )}
            </div>

            {/* Upload progress */}
            {isUploading && (
              <div className="space-y-2">
                <Progress value={progress} className="h-2" />
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {getStatusText()}
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-3 pt-2">
              <Button
                variant="outline"
                onClick={handleClose}
                className="flex-1"
                disabled={uploadState !== 'idle'}
              >
                Cancel
              </Button>
              <Button
                onClick={handleUpload}
                className="flex-1"
                disabled={
                  files.length === 0 ||
                  uploadState !== 'idle' ||
                  (selectedCollection === 'new' && !newCollectionName.trim())
                }
              >
                Upload
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
