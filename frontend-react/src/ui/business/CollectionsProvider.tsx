import { createContext, useContext, type ReactNode } from 'react';

import CollectionS, { type CollectionsState } from '@/services/business/CollectionS';

const CollectionsContext = createContext<CollectionsState | null>(null);

export const CollectionsProvider = ({ children }: { children: ReactNode }) => {
  const state = CollectionS.useCollections();
  return <CollectionsContext value={state}>{children}</CollectionsContext>;
};

export const useCollectionsState = (): CollectionsState => {
  const ctx = useContext(CollectionsContext);
  if (!ctx) throw new Error('useCollectionsState must be used within CollectionsProvider');
  return ctx;
};
