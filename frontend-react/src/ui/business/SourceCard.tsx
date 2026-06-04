import { Card, CardContent, CardHeader, CardTitle } from '@/ui/base/card';
import type { SourceChunk } from '@/types/api';

interface Props {
  source: SourceChunk;
}

const SourceCard = ({ source }: Props) => (
  <Card className="text-sm">
    <CardHeader className="pb-1 pt-3 px-3">
      <CardTitle className="text-xs font-medium truncate">
        {source.source_name}
        {source.page_number != null && (
          <span className="text-muted-foreground ml-1">· p.{source.page_number}</span>
        )}
        {source.section_header && (
          <span className="text-muted-foreground ml-1">· {source.section_header}</span>
        )}
      </CardTitle>
    </CardHeader>
    <CardContent className="px-3 pb-3">
      <p className="text-muted-foreground text-xs line-clamp-3">{source.content_snippet}</p>
    </CardContent>
  </Card>
);

export default SourceCard;
