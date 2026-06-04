import { MessageSquare, BookOpen } from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/base/select';
import { Separator } from '@/ui/base/separator';
import RoutingS from '@/services/tech/RoutingS';
import I18nS from '@/services/tech/I18nS';
import { useCollectionsState } from './CollectionsProvider';
import HealthBadge from './HealthBadge';

const navClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2.5 text-sm px-3 py-2 rounded-lg transition-colors ${
    isActive
      ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
      : 'text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/60'
  }`;

const Sidebar = () => {
  const { collections, selected, setSelected } = useCollectionsState();

  return (
    <aside className="w-56 shrink-0 flex flex-col border-r bg-sidebar h-full">
      <div className="px-4 py-4">
        <p className="font-semibold text-sm tracking-tight">{I18nS.t('appName')}</p>
      </div>
      <Separator />
      <nav className="flex flex-col gap-0.5 px-2 py-3">
        <NavLink to={RoutingS.paths.chat} end className={navClass}>
          <MessageSquare className="h-4 w-4 shrink-0" />
          {I18nS.t('nav_chat')}
        </NavLink>
        <NavLink to={RoutingS.paths.collections} className={navClass}>
          <BookOpen className="h-4 w-4 shrink-0" />
          {I18nS.t('nav_collections')}
        </NavLink>
      </nav>
      <Separator />
      <div className="px-3 py-3 flex flex-col gap-2">
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide px-0.5">
          {I18nS.t('sidebar_collection_label')}
        </p>
        <Select
          value={selected}
          onValueChange={v => v !== null && setSelected(v)}
          disabled={collections.length === 0}
        >
          <SelectTrigger className="w-full text-sm">
            <SelectValue
              placeholder={I18nS.t(collections.length === 0 ? 'collection_none' : 'select_placeholder')}
            />
          </SelectTrigger>
          <SelectContent>
            {collections.map(c => (
              <SelectItem key={c.name} value={c.name}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="mt-auto px-3 py-3 flex items-center gap-2">
        <span className="text-xs text-muted-foreground">{I18nS.t('api_label')}</span>
        <HealthBadge />
      </div>
    </aside>
  );
};

export default Sidebar;
