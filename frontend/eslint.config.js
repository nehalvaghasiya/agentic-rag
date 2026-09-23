import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import { reactRefresh } from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import tseslint from 'typescript-eslint'

const languageOptions = {
  ecmaVersion: 'latest',
  sourceType: 'module',
  globals: globals.browser,
  parserOptions: {
    ecmaFeatures: { jsx: true },
  },
}

const reactPlugins = {
  'react-hooks': reactHooks,
  'react-refresh': reactRefresh.plugin,
}

const reactRules = {
  'react-hooks/rules-of-hooks': 'error',
  'react-hooks/exhaustive-deps': 'error',
  'react-refresh/only-export-components': [
    'error',
    {
      allowConstantExport: true,
      allowExportNames: ['useAppState'],
    },
  ],
}

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [js.configs.recommended],
    languageOptions,
    plugins: reactPlugins,
    rules: {
      ...reactRules,
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    languageOptions,
    plugins: reactPlugins,
    rules: reactRules,
  },
  {
    files: ['src/test/**/*.{js,jsx,ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
