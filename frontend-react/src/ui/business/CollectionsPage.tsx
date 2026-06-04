import { useCallback, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/ui/base/button';
import { Input } from '@/ui/base/input';
import { ScrollArea } from '@/ui/base/scroll-area';
import { Separator } from '@/ui/base/separator';
import CollectionList from '@/ui/business/CollectionList';
import CollectionS from '@/services/business/CollectionS';
import I18nS from '@/services/tech/I18nS';
import { useCollectionsState } from './CollectionsProvider';

const CollectionsPage = () => {
  const { collections, loading, refresh } = useCollectionsState();
  const [newTopic, setNewTopic] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const onCreate = useCallback(async () => {
    const topic = newTopic.trim();
    if (!topic) return;
    setCreating(true);
    try {
      await CollectionS.create(topic);
      setNewTopic('');
      await refresh();
      toast.success(I18nS.t('collection_created', { name: topic }));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : I18nS.t('collection_create_failed'));
    } finally {
      setCreating(false);
    }
  }, [newTopic, refresh]);

  const onDelete = useCallback(
    async (topic: string) => {
      setDeleting(topic);
      try {
        await CollectionS.remove(topic);
        await refresh();
        toast.success(I18nS.t('collection_deleted', { name: topic }));
      } catch (e) {
        toast.error(e instanceof Error ? e.message : I18nS.t('collection_delete_failed'));
      } finally {
        setDeleting(null);
      }
    },
    [refresh],
  );

  const onUpload = useCallback(
    async (collection: string, file: File) => {
      try {
        await CollectionS.upload(collection, file);
        await refresh();
        toast.success(I18nS.t('upload_success', { name: file.name, topic: collection }));
      } catch (e) {
        toast.error(e instanceof Error ? e.message : I18nS.t('upload_failed'));
      }
    },
    [refresh],
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') void onCreate();
    },
    [onCreate],
  );

  return (
    <div className="h-full flex flex-col">
      <header className="px-4 py-[11px] shrink-0">
        <p className="text-sm font-semibold">{I18nS.t('collections_title')}</p>
        <p className="text-xs text-muted-foreground">{I18nS.t('collections_subtitle')}</p>
      </header>
      <Separator />
      <div className="px-6 py-4 shrink-0 flex gap-2">
        <Input
          value={newTopic}
          onChange={e => setNewTopic(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={I18nS.t('collections_new_placeholder')}
          className="flex-1"
        />
        <Button onClick={() => void onCreate()} disabled={!newTopic.trim() || creating}>
          {I18nS.t(creating ? 'action_creating' : 'action_create')}
        </Button>
      </div>
      <Separator />
      <ScrollArea className="flex-1">
        <div className="p-6">
          {loading ? (
            <p className="text-sm text-muted-foreground">{I18nS.t('loading')}</p>
          ) : (
            <CollectionList
              collections={collections}
              onDelete={topic => void onDelete(topic)}
              onUpload={onUpload}
              deleting={deleting}
            />
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

export default CollectionsPage;
