import { useState } from 'react';
import { Button, Card, Checkbox, Select, Space, Typography, Divider, Alert } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

const { Title, Text } = Typography;

interface ModelSelectorProps {
  selectedModels: string[];
  availableModels: string[];
  onSelectionChange: (selectedModels: string[]) => void;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export default function ModelSelector({
  selectedModels,
  availableModels,
  onSelectionChange,
  onConfirm,
  onCancel,
  isLoading = false
}: ModelSelectorProps) {
  const { t } = useTranslation();
  const [showAddModels, setShowAddModels] = useState(false);

  // Models that are not currently selected
  const unselectedModels = availableModels.filter(model => !selectedModels.includes(model));

  const handleToggleModel = (modelName: string) => {
    if (selectedModels.includes(modelName)) {
      // Remove model
      onSelectionChange(selectedModels.filter(m => m !== modelName));
    } else {
      // Add model
      onSelectionChange([...selectedModels, modelName]);
    }
  };

  const handleAddModel = (modelName: string) => {
    if (!selectedModels.includes(modelName)) {
      onSelectionChange([...selectedModels, modelName]);
    }
    setShowAddModels(false);
  };

  return (
    <Card 
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Title level={4} style={{ margin: 0, color: '#1890ff' }}>
            {t('models.title')}
          </Title>
          <Text type="secondary">
            {t('models.counter', { selected: selectedModels.length, total: availableModels.length })}
          </Text>
        </div>
      }
      style={{ 
        maxWidth: '800px', 
        margin: '20px auto',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.1)' 
      }}
    >
      <Alert
        message="Modellauswahl erforderlich"
        description={t('models.hint')}
        type="info"
        showIcon
        style={{ marginBottom: '20px' }}
      />

      <div style={{ marginBottom: '20px' }}>
        <Title level={5}>Vorgeschlagene Modelle:</Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          {selectedModels.length === 0 ? (
            <Text type="secondary" style={{ fontStyle: 'italic' }}>
              {t('models.noneSelected')}
            </Text>
          ) : (
            selectedModels.map(modelName => (
              <Card
                key={modelName}
                size="small"
                style={{ 
                  background: '#f6ffed',
                  border: '1px solid #b7eb8f',
                  borderRadius: '6px'
                }}
                bodyStyle={{ padding: '12px 16px' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Checkbox
                      checked={true}
                      onChange={() => handleToggleModel(modelName)}
                      disabled={isLoading}
                    />
                    <Text strong style={{ color: '#389e0d' }}>
                      {modelName}
                    </Text>
                  </div>
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => handleToggleModel(modelName)}
                    disabled={isLoading}
                    danger
                    style={{ color: '#cf1322' }}
                  />
                </div>
              </Card>
            ))
          )}
        </Space>
      </div>

      <Divider />

      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <Title level={5} style={{ margin: 0 }}>
            {t('models.addMore')}
          </Title>
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={() => setShowAddModels(!showAddModels)}
            disabled={isLoading || unselectedModels.length === 0}
            style={{ 
              background: showAddModels ? '#e6f7ff' : undefined,
              borderColor: showAddModels ? '#1890ff' : undefined
            }}
          >
            {showAddModels ? t('models.close') : t('models.addModels')}
          </Button>
        </div>
        
        {unselectedModels.length === 0 && (
          <Text type="secondary" style={{ fontStyle: 'italic' }}>
            {t('models.allSelected')}
          </Text>
        )}

        {showAddModels && unselectedModels.length > 0 && (
          <Card 
            size="small" 
            style={{ background: '#fafafa', border: '1px dashed #d9d9d9' }}
          >
            <Select
              placeholder={t('models.pickModel')}
              style={{ width: '100%' }}
              onSelect={(value) => { if (value) handleAddModel(value); }}
              disabled={isLoading}
              value={undefined}
              options={unselectedModels.map(modelName => ({
                label: modelName,
                value: modelName
              }))}
            />
          </Card>
        )}
      </div>

      <Divider />

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
        <Button
          onClick={onCancel}
          disabled={isLoading}
          size="large"
          style={{ minWidth: '120px' }}
        >
          {t('common.cancel')}
        </Button>
        <Button
          type="primary"
          onClick={onConfirm}
          disabled={selectedModels.length === 0 || isLoading}
          loading={isLoading}
          size="large"
          style={{ 
            minWidth: '160px',
            background: selectedModels.length > 0 ? 'linear-gradient(135deg, #1890ff 0%, #096dd9 100%)' : undefined
          }}
        >
          {t('models.continue')}
        </Button>
      </div>
    </Card>
  );
}