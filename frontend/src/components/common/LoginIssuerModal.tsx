import { Modal, Button, Input, List, Typography, Space, message } from 'antd';
import { useState } from 'react';
import { LoginOutlined } from '@ant-design/icons';
import { useSolidAuth } from '../../contexts/SolidAuthContext';
import { config, type SolidProvider } from '../../config';
import { useTranslation } from 'react-i18next';

interface LoginIssuerModalProps {
  visible: boolean;
  onClose: () => void;
}

// The issuer configured for this deployment is offered first, followed by any
// additional providers. Both come from the application configuration so a
// different dataspace can be used without touching this component.
const KNOWN_PROVIDERS: SolidProvider[] = (() => {
  const normalise = (url: string) => url.replace(/\/$/, '');

  let primary: SolidProvider;
  try {
    primary = { name: new URL(config.solidOidcIssuer).hostname, url: config.solidOidcIssuer };
  } catch {
    primary = { name: config.solidOidcIssuer, url: config.solidOidcIssuer };
  }

  const seen = new Set([normalise(primary.url)]);
  const additional = config.solidProviders.filter((provider) => {
    const key = normalise(provider.url);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return [primary, ...additional];
})();

export default function LoginIssuerModal({ visible, onClose }: LoginIssuerModalProps) {
  const { t } = useTranslation();
  const { login } = useSolidAuth();
  const [customIssuer, setCustomIssuer] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleProviderLogin = async (issuerUrl: string) => {
    setIsLoggingIn(true);
    try {
      await login(issuerUrl);
      // Note: The page will redirect to the IDP, so this code may not execute
    } catch (error) {
      console.error('Login failed:', error);
      message.error(t('login.failed'));
      setIsLoggingIn(false);
    }
  };

  const handleCustomLogin = async () => {
    if (!customIssuer.trim()) {
      message.warning(t('login.missingUrl'));
      return;
    }

    // Validate URL format
    try {
      new URL(customIssuer.trim());
    } catch {
      message.error(t('login.invalidUrl'));
      return;
    }

    await handleProviderLogin(customIssuer.trim());
  };

  return (
    <Modal
      title={
        <Space>
          <LoginOutlined />
          <span>{t('login.title')}</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={500}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Typography.Paragraph>
          {t('login.intro')}
        </Typography.Paragraph>

        <div>
          <Typography.Text strong>{t('login.knownProviders')}</Typography.Text>
          <List
            style={{ marginTop: 8 }}
            bordered
            dataSource={KNOWN_PROVIDERS}
            renderItem={(provider) => (
              <List.Item
                actions={[
                  <Button
                    type="primary"
                    size="small"
                    loading={isLoggingIn}
                    onClick={() => handleProviderLogin(provider.url)}
                    style={{ backgroundColor: '#164475' }}
                  >
                    {t('login.signIn')}
                  </Button>
                ]}
              >
                <Typography.Text>{provider.name}</Typography.Text>
              </List.Item>
            )}
          />
        </div>

        <div>
          <Typography.Text strong>{t('login.customProvider')}</Typography.Text>
          <Space.Compact style={{ width: '100%', marginTop: 8 }}>
            <Input
              placeholder={t('login.customPlaceholder')}
              value={customIssuer}
              onChange={(e) => setCustomIssuer(e.target.value)}
              onPressEnter={handleCustomLogin}
              disabled={isLoggingIn}
            />
            <Button
              type="primary"
              onClick={handleCustomLogin}
              loading={isLoggingIn}
              disabled={!customIssuer.trim()}
              style={{ backgroundColor: '#164475' }}
            >
              {t('login.signIn')}
            </Button>
          </Space.Compact>
        </div>
      </Space>
    </Modal>
  );
}
