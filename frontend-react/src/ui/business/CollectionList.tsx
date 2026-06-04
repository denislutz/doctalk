import { Badge } from '@/ui/base/badge';
import { Button } from '@/ui/base/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/ui/base/card';
import { Separator } from '@/ui/base/separator';
import UploadDropzone from '@/ui/business/UploadDropzone';
import type { CollectionInfo, IndexedDocument } from '@/types/api';
import I18nS from '@/services/tech/I18nS';

interface Props {
  collections: CollectionInfo[];
  onDelete: (topic: string) => void;
  onUpload: (collection: string, file: File) => Promise<void>;
  deleting: string | null;
}

const formatBadgeVariant = (format: string) => {
  if (format === 'pdf') return 'default' as const;
  if (format === 'epub') return 'secondary' as const;
  return 'outline' as const;
};

const DocumentRow = ({ doc }: { doc: IndexedDocument }) => (
  <div className="flex items-start justify-between gap-4 py-2.5">
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-sm font-medium leading-snug">{doc.source_name}</span>
      <span className="text-xs text-muted-foreground">{doc.filename}</span>
    </div>
    <div className="flex items-center gap-2 shrink-0">
      <Badge variant={formatBadgeVariant(doc.format)} className="text-xs uppercase tracking-wide">
        {doc.format}
      </Badge>
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {I18nS.t('chunks_count', { count: doc.chunk_count.toString() })}
      </span>
    </div>
  </div>
);

const CollectionList = ({ collections, onDelete, onUpload, deleting }: Props) => {
  if (collections.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">{I18nS.t('collections_empty')}</p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {collections.map(col => (
        <Card key={col.name} className="w-full">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-col gap-2 min-w-0">
                <CardTitle className="text-lg">{col.name}</CardTitle>
                <div className="flex gap-1.5 flex-wrap">
                  <Badge variant="secondary">
                    {I18nS.t('chunks_count', { count: col.size.toString() })}
                  </Badge>
                  <Badge variant="outline">
                    {I18nS.t('docs_count', { count: (col.doc_count ?? 0).toString() })}
                  </Badge>
                  {col.formats?.map(f => (
                    <Badge key={f} variant={formatBadgeVariant(f)} className="text-xs uppercase tracking-wide">
                      {f}
                    </Badge>
                  ))}
                </div>
              </div>
              <Button
                variant="destructive"
                size="sm"
                disabled={deleting === col.name}
                onClick={() => onDelete(col.name)}
              >
                {I18nS.t(deleting === col.name ? 'action_deleting' : 'action_delete')}
              </Button>
            </div>
          </CardHeader>

          <CardContent className="pt-0">
            <Separator className="mb-4" />
            <UploadDropzone onUpload={file => onUpload(col.name, file)} />

            {col.documents && col.documents.length > 0 && (
              <>
                <Separator className="mt-4 mb-3" />
                <div className="flex items-center justify-between mb-2 px-0.5">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Documents
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {col.documents.length} {col.documents.length === 1 ? 'file' : 'files'}
                  </span>
                </div>
                <div className="divide-y divide-border">
                  {col.documents.map(doc => (
                    <DocumentRow key={doc.doc_id} doc={doc} />
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export default CollectionList;
