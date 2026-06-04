import { Badge } from '@/ui/base/badge';
import HealthS from '@/services/business/HealthS';
import I18nS from '@/services/tech/I18nS';

const HealthBadge = () => {
  const health = HealthS.useHealth();

  if (!health) {
    return (
      <Badge variant="outline" className="text-xs">
        {I18nS.t('health_checking')}
      </Badge>
    );
  }

  const variants = {
    ok: 'default',
    degraded: 'secondary',
    error: 'destructive',
  } as const;

  return (
    <Badge variant={variants[health.status]} className="text-xs">
      {I18nS.t(`health_${health.status}`)}
    </Badge>
  );
};

export default HealthBadge;
