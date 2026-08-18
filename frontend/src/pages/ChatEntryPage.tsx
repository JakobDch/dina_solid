import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Typography, Button, Space } from 'antd';
import { useTranslation } from 'react-i18next';
import { api } from '../api/apiClient';
import MinimalSpinner from '../components/common/MinimalSpinner';

/**
 * Sends the user straight into a chat.
 *
 * Conversations are filed under a workspace, but that is bookkeeping rather
 * than something worth asking about: the data comes from the dataspace, so
 * there is nothing to set up per workspace. This resolves the default one and
 * redirects, keeping the concept out of the interface entirely.
 */
export default function ChatEntryPage() {
  const { t } = useTranslation();
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    api
      .get<{ id: string }>('/api/v1/workspaces/default')
      .then((response) => {
        if (!cancelled) setWorkspaceId(response.data.id);
      })
      .catch((error) => {
        console.error('Could not resolve the default workspace:', error);
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (workspaceId) {
    return <Navigate to={`/workspace/${workspaceId}`} replace />;
  }

  if (failed) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 24px' }}>
        <Space direction="vertical" align="center">
          <Typography.Title level={4}>{t('errors.backendUnavailable')}</Typography.Title>
          <Button type="primary" onClick={() => window.location.reload()}>
            {t('common.retry')}
          </Button>
        </Space>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 24px' }}>
      <MinimalSpinner size="large" text={t('common.loading')} />
    </div>
  );
}
