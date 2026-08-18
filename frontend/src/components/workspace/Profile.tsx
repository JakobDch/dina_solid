import React, { useState } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Upload,
  Avatar,
  Space,
  Typography,
  message,
  Divider,
  Row,
  Col,
  Switch
} from 'antd';
import {
  UserOutlined,
  UploadOutlined,
  SaveOutlined,
  ClearOutlined,
  MailOutlined,
  BankOutlined,
  FileTextOutlined,
  MoonOutlined,
  SunOutlined
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useProfile } from '../../contexts/ProfileContext';
import { useTheme } from '../../contexts/ThemeContext';
import type { UploadProps } from 'antd';

const { Title, Text } = Typography;
const { TextArea } = Input;

export default function Profile() {
  const { t } = useTranslation();
  const { profile, updateProfile, clearProfile } = useProfile();
  const { theme, toggleTheme } = useTheme();
  const [form] = Form.useForm();
  const [avatarPreview, setAvatarPreview] = useState<string | undefined>(profile?.avatarUrl);

  // Initialize form with current profile data
  React.useEffect(() => {
    if (profile) {
      form.setFieldsValue({
        name: profile.name,
        email: profile.email || '',
        institution: profile.institution || '',
        bio: profile.bio || ''
      });
      setAvatarPreview(profile.avatarUrl);
    }
  }, [profile, form]);

  const handleAvatarChange = (file: File) => {
    if (file.size > 5 * 1024 * 1024) { // 5MB limit
      message.error(t('profilePage.fileTooLarge'));
      return;
    }

    if (!file.type.startsWith('image/')) {
      message.error(t('profilePage.imagesOnly'));
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const result = e.target?.result as string;
      setAvatarPreview(result);
    };
    reader.readAsDataURL(file);
  };

  const uploadProps: UploadProps = {
    beforeUpload: (file) => {
      handleAvatarChange(file);
      return false; // Prevent auto upload
    },
    showUploadList: false,
    accept: 'image/*'
  };

  const onFinish = (values: any) => {
    updateProfile({
      name: values.name,
      email: values.email,
      institution: values.institution,
      bio: values.bio,
      avatarUrl: avatarPreview
    });
    message.success(t('profilePage.savedSuccess'));
  };

  const handleClearProfile = () => {
    clearProfile();
    form.resetFields();
    setAvatarPreview(undefined);
    message.success(t('profilePage.deletedSuccess'));
  };

  return (
    <div style={{
      padding: 'var(--space-8)',
      maxWidth: '800px',
      margin: '0 auto',
      background: theme === 'dark' ? '#0f172a' : '#f8fafc',
      minHeight: 'calc(100vh - 140px)'
    }}>
      <Card
        style={{
          borderRadius: 'var(--radius-2xl)',
          boxShadow: 'var(--shadow-xl)',
          border: theme === 'dark' ? '1px solid #475569' : '1px solid rgba(255, 255, 255, 0.2)',
          background: theme === 'dark' ? '#1e293b' : '#ffffff'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-8)' }}>
          <Title level={2} style={{
            color: theme === 'dark' ? '#60a5fa' : 'var(--color-primary-700)',
            marginBottom: 'var(--space-2)',
            fontWeight: 'var(--font-weight-extrabold)'
          }}>
            👤 {t('profilePage.heading')}
          </Title>
          <Text type="secondary" style={{ fontSize: 'var(--font-size-lg)' }}>
            {t('profilePage.subtitle')}
          </Text>
        </div>

        <Row gutter={[32, 32]}>
          <Col xs={24} md={8}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ marginBottom: 'var(--space-6)' }}>
                <Avatar
                  size={120}
                  src={avatarPreview}
                  icon={<UserOutlined />}
                  style={{
                    backgroundColor: 'var(--color-primary-500)',
                    border: '4px solid white',
                    boxShadow: 'var(--shadow-primary-lg)'
                  }}
                />
              </div>

              <Upload {...uploadProps}>
                <Button
                  icon={<UploadOutlined />}
                  style={{
                    borderRadius: 'var(--radius-lg)',
                    height: '44px',
                    fontWeight: 'var(--font-weight-semibold)'
                  }}
                >
                  {t('profilePage.uploadAvatar')}
                </Button>
              </Upload>

              <div style={{ marginTop: 'var(--space-4)' }}>
                <Text type="secondary" style={{ fontSize: '13px' }}>
                  {t('profilePage.maxSize')}<br />
                  {t('profilePage.supportedFormats')}
                </Text>
              </div>
            </div>
          </Col>

          <Col xs={24} md={16}>
            <Form
              form={form}
              layout="vertical"
              onFinish={onFinish}
              autoComplete="off"
            >
              <Form.Item
                label={
                  <span style={{ fontWeight: 'var(--font-weight-semibold)', fontSize: '15px' }}>
                    <UserOutlined style={{ marginRight: '8px' }} />
                    {t('profilePage.fullName')}
                  </span>
                }
                name="name"
                rules={[{ required: true, message: t('profilePage.nameRequired') }]}
              >
                <Input
                  placeholder={t('profilePage.namePlaceholder')}
                  style={{
                    borderRadius: 'var(--radius-lg)',
                    height: '44px'
                  }}
                />
              </Form.Item>

              <Form.Item
                label={
                  <span style={{ fontWeight: 'var(--font-weight-semibold)', fontSize: '15px' }}>
                    <MailOutlined style={{ marginRight: '8px' }} />
                    {t('profilePage.emailLabel')}
                  </span>
                }
                name="email"
                rules={[
                  { type: 'email', message: t('profilePage.emailInvalid') }
                ]}
              >
                <Input
                  placeholder={t('profilePage.emailPlaceholder')}
                  style={{
                    borderRadius: 'var(--radius-lg)',
                    height: '44px'
                  }}
                />
              </Form.Item>

              <Form.Item
                label={
                  <span style={{ fontWeight: 'var(--font-weight-semibold)', fontSize: '15px' }}>
                    <BankOutlined style={{ marginRight: '8px' }} />
                    {t('profilePage.institution')}
                  </span>
                }
                name="institution"
              >
                <Input
                  placeholder={t('profilePage.institutionPlaceholder')}
                  style={{
                    borderRadius: 'var(--radius-lg)',
                    height: '44px'
                  }}
                />
              </Form.Item>

              <Form.Item
                label={
                  <span style={{ fontWeight: 'var(--font-weight-semibold)', fontSize: '15px' }}>
                    <FileTextOutlined style={{ marginRight: '8px' }} />
                    {t('profilePage.bio')}
                  </span>
                }
                name="bio"
              >
                <TextArea
                  placeholder={t('profilePage.bioPlaceholder')}
                  rows={4}
                  style={{
                    borderRadius: 'var(--radius-lg)'
                  }}
                />
              </Form.Item>

              <Divider />

              {/* Theme Settings */}
              <div style={{
                background: theme === 'dark' ? 'rgba(51, 65, 85, 0.3)' : 'rgba(9, 153, 241, 0.05)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-4)',
                marginBottom: 'var(--space-6)',
                border: theme === 'dark' ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid rgba(9, 153, 241, 0.1)'
              }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <Text strong style={{
                      fontSize: '15px',
                      color: theme === 'dark' ? '#60a5fa' : 'var(--color-primary-700)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}>
                      {theme === 'dark' ? <MoonOutlined /> : <SunOutlined />}
                      {t('profilePage.designTheme')}
                    </Text>
                    <div style={{ marginTop: '4px' }}>
                      <Text type="secondary" style={{ fontSize: '13px' }}>
                        {theme === 'dark' ? t('profilePage.darkHint') : t('profilePage.lightHint')}
                      </Text>
                    </div>
                  </div>
                  <Switch
                    checked={theme === 'dark'}
                    onChange={toggleTheme}
                    checkedChildren={<MoonOutlined />}
                    unCheckedChildren={<SunOutlined />}
                    style={{
                      backgroundColor: theme === 'dark' ? '#1890ff' : '#f0f0f0'
                    }}
                  />
                </div>
              </div>

              <Form.Item style={{ marginBottom: 0 }}>
                <Space size="middle" style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<SaveOutlined />}
                    size="large"
                    style={{
                      borderRadius: 'var(--radius-lg)',
                      height: '48px',
                      fontWeight: 'var(--font-weight-semibold)',
                      paddingInline: '32px'
                    }}
                  >
                    {t('profilePage.saveProfile')}
                  </Button>

                  <Button
                    danger
                    icon={<ClearOutlined />}
                    onClick={handleClearProfile}
                    size="large"
                    style={{
                      borderRadius: 'var(--radius-lg)',
                      height: '48px'
                    }}
                  >
                    {t('profilePage.deleteProfile')}
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Col>
        </Row>

        {profile && (
          <div style={{
            marginTop: 'var(--space-8)',
            padding: 'var(--space-4)',
            background: theme === 'dark' ? 'rgba(51, 65, 85, 0.3)' : 'rgba(9, 153, 241, 0.05)',
            borderRadius: 'var(--radius-lg)',
            border: theme === 'dark' ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid rgba(9, 153, 241, 0.1)'
          }}>
            <Text type="secondary" style={{ fontSize: '13px' }}>
              Profil erstellt am: {new Date(profile.createdAt).toLocaleString('de-DE')}<br />
              Zuletzt aktualisiert: {new Date(profile.updatedAt).toLocaleString('de-DE')}
            </Text>
          </div>
        )}
      </Card>
    </div>
  );
}