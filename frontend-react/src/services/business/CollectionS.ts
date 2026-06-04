import { useCallback, useEffect, useRef, useState } from 'react';

import type { CollectionInfo } from '@/types/api';
import HttpS from '@/services/tech/HttpS';

// ============================================================================
// Public service API
// ============================================================================

const list = (): Promise<CollectionInfo[]> => HttpS.get<CollectionInfo[]>('/collections');

const get = (topic: string): Promise<CollectionInfo> =>
  HttpS.get<CollectionInfo>(`/collections/${topic}`);

const create = (topic: string): Promise<void> =>
  HttpS.post('/collections', null, { topic }).then(() => undefined);

const remove = (topic: string): Promise<void> => HttpS.del(`/collections/${topic}`);

const upload = (topic: string, file: File, sourceName?: string): Promise<void> => {
  const formData = new FormData();
  formData.append('file', file);
  if (sourceName) formData.append('source_name', sourceName);
  return HttpS.postForm(`/upload/${topic}`, formData).then(() => undefined);
};

export interface CollectionsState {
  collections: CollectionInfo[];
  selected: string;
  setSelected: (topic: string) => void;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const useCollections = (): CollectionsState => {
  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await list();
      if (!mounted.current) return;
      setCollections(data);
      setSelected(prev => (prev === '' && data.length > 0 ? data[0].name : prev));
      setError(null);
    } catch (e) {
      if (!mounted.current) return;
      setError(e instanceof Error ? e.message : 'Failed to load collections');
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);

  return { collections, selected, setSelected, loading, error, refresh };
};

const CollectionS = { list, get, create, remove, upload, useCollections };
export default CollectionS;
