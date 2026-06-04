import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

const paths = {
  chat: '/',
  collections: '/collections',
} as const;

export type RoutePath = (typeof paths)[keyof typeof paths];

const useNavTo = (): ((path: RoutePath) => void) => {
  const navigate = useNavigate();
  return useCallback((path: RoutePath) => navigate(path), [navigate]);
};

const RoutingS = { paths, useNavTo };
export default RoutingS;
