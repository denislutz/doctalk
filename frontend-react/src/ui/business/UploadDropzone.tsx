import { useCallback, useRef, useState } from 'react';

import { Button } from '@/ui/base/button';
import { Progress } from '@/ui/base/progress';
import I18nS from '@/services/tech/I18nS';

interface Props {
  onUpload: (file: File) => Promise<void>;
  uploading?: boolean;
}

const UploadDropzone = ({ onUpload, uploading: uploadingProp }: Props) => {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const isUploading = uploading || uploadingProp;

  const handleFile = useCallback(
    async (file: File) => {
      setFileName(file.name);
      setUploading(true);
      try {
        await onUpload(file);
      } finally {
        setUploading(false);
      }
    },
    [onUpload],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      if (isUploading) return;
      const file = e.dataTransfer.files[0];
      if (file) void handleFile(file);
    },
    [handleFile, isUploading],
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) void handleFile(file);
      e.target.value = '';
    },
    [handleFile],
  );

  const openPicker = useCallback(() => {
    if (!isUploading) inputRef.current?.click();
  }, [isUploading]);

  return (
    <div
      onDragOver={e => { e.preventDefault(); if (!isUploading) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={openPicker}
      className={`cursor-pointer border-2 border-dashed rounded-lg p-8 flex flex-col items-center gap-3 transition-colors ${
        dragging ? 'border-primary bg-primary/5' : 'border-border hover:border-muted-foreground/50'
      } ${isUploading ? 'opacity-60 cursor-not-allowed' : ''}`}
    >
      <p className="text-sm text-muted-foreground text-center select-none">
        {isUploading
          ? I18nS.t('dropzone_uploading', { name: fileName ?? 'file' })
          : I18nS.t('dropzone_prompt')}
      </p>
      {isUploading ? (
        <Progress value={null} className="w-40" />
      ) : (
        <Button
          variant="outline"
          size="sm"
          disabled={isUploading}
          onClick={e => { e.stopPropagation(); openPicker(); }}
        >
          {I18nS.t('dropzone_choose')}
        </Button>
      )}
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        onChange={onInputChange}
        accept=".pdf,.txt,.md,.csv,.docx"
        tabIndex={-1}
      />
    </div>
  );
};

export default UploadDropzone;
