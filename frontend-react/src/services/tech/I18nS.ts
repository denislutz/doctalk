import React from 'react';

// ============================================================================
// Private — translation builder (one-file variant: EN is the default language)
// ============================================================================

type Translation = Record<string, string>;
type Translations<T> = Record<keyof T, Translation>;
type TranslationKey<T> = keyof T[keyof T] & string;
type LanguageKey<T> = keyof T;

const buildService = <T extends Translations<T>>(translations: T) => {
  let currentLanguage: LanguageKey<T> = Object.keys(translations)[0] as LanguageKey<T>;

  const setLanguage = (language: LanguageKey<T>): void => {
    if (translations[language]) currentLanguage = language;
  };

  const translateKey = (key: TranslationKey<T>): string | undefined =>
    translations[currentLanguage][key];

  function t(key: TranslationKey<T>, params?: Record<string, string>): string;
  function t(
    key: TranslationKey<T>,
    params?: Record<string, string | React.ReactNode>,
  ): React.ReactNode;
  function t(
    key: TranslationKey<T>,
    params?: Record<string, string | React.ReactNode>,
  ): string | React.ReactNode {
    const template = translateKey(key);
    if (!template) return '';
    if (!params) return template;

    const anyReactComponent = Object.values(params).some(param => typeof param !== 'string');

    if (!anyReactComponent) {
      return Object.keys(params).reduce(
        (result, attr) => result.replace(`{${attr}}`, params[attr] as string),
        template,
      );
    }

    const elements = template.split(/(\{[^}]+\})/g).map((part, index) => {
      const placeholder = /\{([^}]+)\}/.exec(part);
      if (placeholder) {
        const value = params[placeholder[1]];
        return value !== undefined
          ? React.createElement(React.Fragment, { key: index }, value)
          : part;
      }
      return part;
    });

    return React.createElement(React.Fragment, {}, ...elements);
  }

  return { setLanguage, t };
};

// ============================================================================
// Translations
// ============================================================================

const EN = {
  appName: 'DocTalk',

  nav_chat: 'Chat',
  nav_collections: 'Collections',
  nav_upload: 'Upload',

  sidebar_collection_label: 'Collection',
  api_label: 'API',
  select_placeholder: 'Select…',
  collection_none: 'No collections',
  collection_none_available: 'No collections available',

  health_checking: 'checking…',
  health_ok: 'ok',
  health_degraded: 'degraded',
  health_error: 'error',

  chat_empty_ready: 'Ask a question about your documents.',
  chat_empty_no_collection: 'Select a collection to start.',
  chat_input_placeholder: 'Ask a question…',
  chat_input_disabled: 'Select a collection first',

  collections_title: 'Collections',
  collections_subtitle: 'Manage your document collections.',
  collections_new_placeholder: 'New collection name…',
  collections_empty: 'No collections yet. Create one to get started.',

  upload_title: 'Upload',
  upload_subtitle: 'Add documents to a collection.',
  upload_target: 'Target collection',
  upload_file: 'File',
  upload_select_collection: 'Select a collection first',

  dropzone_uploading: 'Uploading {name}…',
  dropzone_prompt: 'Drag & drop a file here, or click anywhere to select',
  dropzone_choose: 'Choose file',

  loading: 'Loading…',
  action_create: 'Create',
  action_creating: 'Creating…',
  action_delete: 'Delete',
  action_deleting: 'Deleting…',

  chunks_count: '{count} chunks',
  docs_count: '{count} docs',
  doc_line: '{name} ({count} chunks)',

  collection_created: 'Collection "{name}" created',
  collection_deleted: 'Collection "{name}" deleted',
  collection_create_failed: 'Failed to create collection',
  collection_delete_failed: 'Failed to delete collection',
  upload_success: '"{name}" uploaded to {topic}',
  upload_failed: 'Upload failed',
  error_prefix: 'Error: {message}',
};

const DE: Record<keyof typeof EN, string> = {
  appName: 'DocTalk',

  nav_chat: 'Chat',
  nav_collections: 'Sammlungen',
  nav_upload: 'Hochladen',

  sidebar_collection_label: 'Sammlung',
  api_label: 'API',
  select_placeholder: 'Auswählen…',
  collection_none: 'Keine Sammlungen',
  collection_none_available: 'Keine Sammlungen verfügbar',

  health_checking: 'prüfe…',
  health_ok: 'ok',
  health_degraded: 'eingeschränkt',
  health_error: 'Fehler',

  chat_empty_ready: 'Stellen Sie eine Frage zu Ihren Dokumenten.',
  chat_empty_no_collection: 'Wählen Sie eine Sammlung, um zu beginnen.',
  chat_input_placeholder: 'Frage stellen…',
  chat_input_disabled: 'Wählen Sie zuerst eine Sammlung',

  collections_title: 'Sammlungen',
  collections_subtitle: 'Verwalten Sie Ihre Dokumentsammlungen.',
  collections_new_placeholder: 'Name der neuen Sammlung…',
  collections_empty: 'Noch keine Sammlungen. Erstellen Sie eine, um zu beginnen.',

  upload_title: 'Hochladen',
  upload_subtitle: 'Fügen Sie Dokumente zu einer Sammlung hinzu.',
  upload_target: 'Zielsammlung',
  upload_file: 'Datei',
  upload_select_collection: 'Wählen Sie zuerst eine Sammlung',

  dropzone_uploading: 'Lade {name} hoch…',
  dropzone_prompt: 'Datei hierher ziehen oder klicken, um auszuwählen',
  dropzone_choose: 'Datei wählen',

  loading: 'Wird geladen…',
  action_create: 'Erstellen',
  action_creating: 'Erstelle…',
  action_delete: 'Löschen',
  action_deleting: 'Lösche…',

  chunks_count: '{count} Abschnitte',
  docs_count: '{count} Dokumente',
  doc_line: '{name} ({count} Abschnitte)',

  collection_created: 'Sammlung „{name}“ erstellt',
  collection_deleted: 'Sammlung „{name}“ gelöscht',
  collection_create_failed: 'Sammlung konnte nicht erstellt werden',
  collection_delete_failed: 'Sammlung konnte nicht gelöscht werden',
  upload_success: '„{name}“ in {topic} hochgeladen',
  upload_failed: 'Hochladen fehlgeschlagen',
  error_prefix: 'Fehler: {message}',
};

const I18nS = buildService({ EN, DE });
export default I18nS;
