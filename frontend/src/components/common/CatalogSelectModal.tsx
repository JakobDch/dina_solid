import { Modal, Button, List, Typography, Space, Alert } from 'antd';
import { useState, useEffect } from 'react';
import { DatabaseOutlined } from '@ant-design/icons';
import { useSolidAuth } from '../../contexts/SolidAuthContext';
import { api } from '../../api/apiClient';
import type { ExternalCatalog } from '../../types';
import { useTranslation } from 'react-i18next';

interface CatalogSelectModalProps {
  visible: boolean;
  onClose: () => void;
}

export default function CatalogSelectModal({ visible, onClose }: CatalogSelectModalProps) {
  const { t } = useTranslation();
  const { selectCatalog } = useSolidAuth();
  const [catalogs, setCatalogs] = useState<ExternalCatalog[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Fetch catalogs when modal opens
  useEffect(() => {
    if (visible) {
      fetchCatalogs();
    }
  }, [visible]);

  const fetchCatalogs = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // The backend resolves the catalogs from the configured Solid dataspace
      // federation, so this list follows the deployment configuration.
      const response = await api.get<ExternalCatalog[]>('/api/v1/catalogs');
      setCatalogs(response.data);
    } catch (err) {
      console.error('Failed to fetch catalogs:', err);
      setError(t('catalog.loadFailed'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectCatalog = (catalog: ExternalCatalog) => {
    setSelectedId(catalog.id);
    selectCatalog(catalog.id, catalog.title, catalog.catalog_url);
    onClose();
  };

  return (
    <Modal
      title={
        <Space>
          <DatabaseOutlined />
          <span>{t('catalog.title')}</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={600}
      closable={true}
      maskClosable={false}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Typography.Paragraph>
          {t('catalog.intro')}
        </Typography.Paragraph>

        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{
              width: '80px',
              height: '80px',
              borderRadius: '50%',
              overflow: 'hidden',
              flexShrink: 0
            }}>
              <video
                autoPlay
                loop
                muted
                playsInline
                ref={(el) => { if (el) el.playbackRate = 2.0; }}
                style={{
                  width: '110%',
                  height: '110%',
                  marginLeft: '-5%',
                  marginTop: '-5%',
                  objectFit: 'cover'
                }}
              >
                <source src="/dina_loading.mp4" type="video/mp4" />
              </video>
            </div>
            <Typography.Text style={{ display: 'block', marginTop: 16 }}>
              {t('catalog.loading')}
            </Typography.Text>
          </div>
        ) : error ? (
          <Alert
            type="error"
            message={t('common.error')}
            description={error}
            action={
              <Button size="small" onClick={fetchCatalogs}>
                {t('common.retry')}
              </Button>
            }
          />
        ) : catalogs.length === 0 ? (
          <Alert
            type="info"
            message={t('catalog.emptyTitle')}
            description={t('catalog.empty')}
          />
        ) : (
          <List
            bordered
            dataSource={catalogs}
            renderItem={(catalog) => (
              <List.Item
                actions={[
                  <Button
                    type={selectedId === catalog.id ? 'primary' : 'default'}
                    onClick={() => handleSelectCatalog(catalog)}
                    style={selectedId === catalog.id ? { backgroundColor: '#164475' } : {}}
                  >
                    {selectedId === catalog.id ? t('catalog.selected') : t('catalog.select')}
                  </Button>
                ]}
              >
                <List.Item.Meta
                  avatar={<DatabaseOutlined style={{ fontSize: 24, color: '#164475' }} />}
                  title={catalog.title}
                  description={catalog.description || t('catalog.noDescription')}
                />
              </List.Item>
            )}
          />
        )}
      </Space>
    </Modal>
  );
}
