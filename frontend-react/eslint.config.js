import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';
import { defineConfig, globalIgnores } from 'eslint/config';

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strict,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      'react-hooks/exhaustive-deps': 'error',
      // Standard "fetch on mount → setState" pattern is valid; v7 rule is over-strict here
      'react-hooks/set-state-in-effect': 'off',
      // shadcn/ui components export cva variants alongside components — expected pattern
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
]);
