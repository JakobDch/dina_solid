import { Modal, Input, Typography, Space, Button, Alert, Tag, message } from 'antd';
import { KeyOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../../api/apiClient';
import { useApiKeys, KEY_PROVIDERS, type KeyProvider } from '../../contexts/ApiKeyContext';

interface ApiKeySettingsModalProps {
  visible: boolean;
  onClose: () => void;
}

const PROVIDER_LABELS: Record<KeyProvider, { name: string; hint: string; url: string }> = {
  deepseek: { name: 'DeepSeek', hint: 'sk-...', url: 'https://platform.deepseek.com/api_keys' },
  openai: { name: 'OpenAI', hint: 'sk-proj-...', url: 'https://platform.openai.com/api-keys' },
  fireworks: { name: 'Fireworks', hint: 'fw_...', url: 'https://fireworks.ai/account/api-keys' },
};

export default function ApiKeySettingsModal({ visible, onClose }: ApiKeySettingsModalProps) {
  const { t } = useTranslation();
  const { keys, setKey, clearAll } = useApiKeys();
  const [drafts, setDrafts] = useState<Partial<Record<KeyProvider, string>>>({});
  const [serverConfigured, setServerConfigured] = useState<Partial<Record<string, boolean>>>({});

  // Start from what is stored so an existing key can be edited rather than
  // retyped, and find out which providers the server already covers.
  useEffect(() => {
    if (!visible) return;
    setDrafts({ ...keys });
    api
      .get<{ configured_on_server: Record<string, boolean> }>('/api/v1/agent/profiles')
      .then((response) => setServerConfigured(response.data.configured_on_server ?? {}))
      .catch(() => setServerConfigured({}));
  }, [visible, keys]);

  const handleSave = () => {
    KEY_PROVIDERS.forEach((provider) => setKey(provider, drafts[provider] ?? ''));
    message.success(t('apiKeys.saved'));
    onClose();
  };

  const handleClear = () => {
    clearAll();
    setDrafts({});
    message.success(t('apiKeys.cleared'));
  };

  return (
    <Modal
      title={
        <Space>
          <KeyOutlined />
          <span>{t('apiKeys.title')}</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={620}
      footer={[
        <Button key="clear" danger onClick={handleClear}>
          {t('apiKeys.clearAll')}
        </Button>,
        <Button key="cancel" onClick={onClose}>
          {t('common.cancel')}
        </Button>,
        <Button key="save" type="primary" onClick={handleSave} style={{ backgroundColor: '#164475' }}>
          {t('common.save')}
        </Button>,
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Typography.Paragraph style={{ marginBottom: 0 }}>
          {t('apiKeys.intro')}
        </Typography.Paragraph>

        <Alert type="info" showIcon message={t('apiKeys.privacyNote')} />

        {KEY_PROVIDERS.map((provider) => {
          const meta = PROVIDER_LABELS[provider];
          const onServer = serverConfigured[provider];

          return (
            <div key={provider}>
              <Space style={{ marginBottom: 6 }} align="center">
                <Typography.Text strong>{meta.name}</Typography.Text>
                {keys[provider] ? (
                  <Tag color="green">{t('apiKeys.stored')}</Tag>
                ) : onServer ? (
                  <Tag color="blue">{t('apiKeys.onServer')}</Tag>
                ) : (
                  <Tag>{t('apiKeys.notSet')}</Tag>
                )}
              </Space>
              <Input.Password
                placeholder={meta.hint}
                value={drafts[provider] ?? ''}
                onChange={(event) =>
                  setDrafts((previous) => ({ ...previous, [provider]: event.target.value }))
                }
                autoComplete="off"
              />
              <Typography.Link
                href={meta.url}
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: 12 }}
              >
                {t('apiKeys.getKey', { provider: meta.name })}
              </Typography.Link>
            </div>
          );
        })}

        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {t('apiKeys.ollamaNote')}
        </Typography.Text>
      </Space>
    </Modal>
  );
}
