import { useState } from 'react';
import { FolderPlus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useChatStore } from '@/stores/chatStore';

export function CreateCollectionModal() {
  const { createCollectionModalOpen, setCreateCollectionModalOpen, addCollection } = useChatStore();
  const [name, setName] = useState('');
  const [error, setError] = useState('');

  const handleCreate = () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Collection name is required');
      return;
    }
    if (trimmedName.length > 50) {
      setError('Name must be less than 50 characters');
      return;
    }
    
    addCollection(trimmedName);
    setName('');
    setError('');
    setCreateCollectionModalOpen(false);
  };

  const handleClose = () => {
    setName('');
    setError('');
    setCreateCollectionModalOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleCreate();
    }
  };

  return (
    <Dialog open={createCollectionModalOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <FolderPlus className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle>New Collection</DialogTitle>
              <DialogDescription>
                Create a collection to organize your documents
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="py-4">
          <Label htmlFor="collection-name" className="text-sm font-medium">
            Collection name
          </Label>
          <Input
            id="collection-name"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setError('');
            }}
            onKeyDown={handleKeyDown}
            placeholder="e.g., Research Papers, Meeting Notes"
            className="mt-2"
            autoFocus
          />
          {error && (
            <p className="text-sm text-destructive mt-2">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={!name.trim()}>
            Create Collection
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
