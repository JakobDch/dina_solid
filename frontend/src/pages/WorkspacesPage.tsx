import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table, Button, message, Space, Modal, Form, Popconfirm, Input
} from 'antd';
import {
  RocketOutlined,
  CopyOutlined,
  DeleteOutlined,
  PlusOutlined,
  EnvironmentOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { Link } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { api } from '../api/apiClient';
import { formatDateTime } from '../utils/formatters';
import type { WorkspaceRow } from '../types';
import { useTranslation } from 'react-i18next';

export default function WorkspacesPage() {
  const [data, setData] = useState<WorkspaceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { theme } = useTheme();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.get<WorkspaceRow[]>("/api/v1/workspaces");
      setData(res.data);
    } catch (err) {
      message.error(t('workspaces.loadFailed'));
      console.error("Error fetching workspaces:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleClone = async (record: WorkspaceRow) => {
    try {
      await api.post("/api/v1/workspaces", {
        title: `${record.title} ${t('workspaces.copySuffix')}`,
        description: record.description,
        clone_from_id: record.id
      });
      message.success(t('workspaces.cloned'));
      fetchData();
    } catch (err) {
      message.error(t('workspaces.cloneFailed'));
      console.error("Error cloning workspace:", err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/v1/workspaces/${id}`);
      message.success(t('workspaces.deleted'));
      fetchData();
    } catch (err) {
      message.error(t('workspaces.deleteFailed'));
      console.error("Error deleting workspace:", err);
    }
  };

  const columns: ColumnsType<WorkspaceRow> = [
    {
      title: "Titel",
      dataIndex: "title",
      key: "title",
      width: '25%',
      render: (text, record) => (
        <Link 
          to={`/workspace/${record.id}`}
          style={{
            fontWeight: 700,
            fontSize: '16px',
            color: theme === 'dark' ? '#60a5fa' : '#1f4788',
            textDecoration: 'none',
            background: theme === 'dark' ? 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)' : 'linear-gradient(135deg, #1f4788 0%, #0999F1 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            transition: 'all 0.3s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateX(4px)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateX(0)';
          }}
        >
          {text}
        </Link>
      ),
    },
    { title: "Beschreibung", dataIndex: "description", key: "description", width: '40%' },
    {
      title: "Erstellt am",
      dataIndex: "created",
      key: "created",
      width: '20%',
      render: (t: string) => formatDateTime(t),
    },
    {
      title: "Aktionen",
      key: "actions",
      width: '15%',
      render: (_: unknown, record: WorkspaceRow) => (
        <Space size="small">
          <Button
            type="primary"
            size="small"
            onClick={() => navigate(`/workspace/${record.id}`)}
            style={{
              background: 'linear-gradient(135deg, var(--color-primary-500) 0%, var(--color-primary-600) 100%)',
              border: 'none',
              borderRadius: 'var(--radius-lg)',
              fontWeight: 'var(--font-weight-semibold)',
              fontSize: 'var(--font-size-sm)',
              height: '36px',
              padding: '0 var(--space-4)',
              boxShadow: 'var(--shadow-primary)',
              transition: 'all var(--transition-normal)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-1px)';
              e.currentTarget.style.boxShadow = 'var(--shadow-primary-lg)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = 'var(--shadow-primary)';
            }}
          >
            <RocketOutlined /> {t('workspaces.open')}
          </Button>
          <Button
            type="default"
            size="small"
            onClick={() => handleClone(record)}
            style={{
              borderRadius: 'var(--radius-lg)',
              fontWeight: 'var(--font-weight-semibold)',
              fontSize: 'var(--font-size-sm)',
              height: '36px',
              padding: '0 var(--space-4)',
              background: 'var(--color-primary-50)',
              borderColor: 'var(--color-primary-200)',
              color: 'var(--color-primary-700)',
              transition: 'all var(--transition-normal)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--color-primary-100)';
              e.currentTarget.style.borderColor = 'var(--color-primary-300)';
              e.currentTarget.style.transform = 'translateY(-1px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'var(--color-primary-50)';
              e.currentTarget.style.borderColor = 'var(--color-primary-200)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <CopyOutlined /> Klonen
          </Button>
          <Popconfirm
            title={
              <div style={{ maxWidth: '200px' }}>
                <strong>{t('workspaces.deleteConfirm')}</strong>
                <br />
                <span style={{ fontSize: '13px', color: theme === 'dark' ? '#cbd5e1' : '#64748b' }}>
                  {t('workspaces.deleteHint')}
                </span>
              </div>
            }
            onConfirm={() => handleDelete(record.id)}
            okText={t('common.delete')}
            cancelText="Abbrechen"
            okButtonProps={{
              style: {
                background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                border: 'none',
                fontWeight: 600
              }
            }}
          >
            <Button
              type="text"
              size="small"
              danger
              style={{
                borderRadius: 'var(--radius-lg)',
                fontWeight: 'var(--font-weight-semibold)',
                fontSize: 'var(--font-size-sm)',
                height: '36px',
                padding: '0 var(--space-4)',
                color: 'var(--color-error-500)',
                background: 'transparent',
                border: '1px solid transparent',
                transition: 'all var(--transition-normal)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--color-error-50)';
                e.currentTarget.style.borderColor = 'var(--color-error-200)';
                e.currentTarget.style.color = 'var(--color-error-600)';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.borderColor = 'transparent';
                e.currentTarget.style.color = 'var(--color-error-500)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <DeleteOutlined /> {t('common.delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await api.post("/api/v1/workspaces", values);
      message.success("Umgebung erfolgreich angelegt.");
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch (err) {
      message.error("Anlage der Umgebung fehlgeschlagen.");
      console.error("Error creating workspace:", err);
    }
  };

  return (
    <>
      {/* Floating Action Button */}
      <div
        className="floating-element modern-fab"
        style={{
          bottom: 'var(--space-10)',
          right: 'var(--space-10)',
          padding: 'var(--space-4)',
          borderRadius: 'var(--radius-full)',
          width: '72px',
          height: '72px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          background: 'linear-gradient(135deg, var(--color-primary-500) 0%, var(--color-primary-600) 100%)',
          color: 'white',
          fontSize: 'var(--font-size-2xl)',
          boxShadow: 'var(--shadow-primary-lg)',
          transition: 'all var(--transition-bounce)',
          border: '3px solid white',
          backdropFilter: 'blur(10px)'
        }}
        onClick={() => setModalOpen(true)}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'scale(1.1) rotate(90deg)';
          e.currentTarget.style.boxShadow = 'var(--shadow-2xl)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'scale(1) rotate(0deg)';
          e.currentTarget.style.boxShadow = 'var(--shadow-primary-lg)';
        }}
      >
        <PlusOutlined />
      </div>

      <div style={{ maxWidth: '1600px', margin: '0 auto', width: '100%' }}>
        {/* Hero Section */}
        <div className="premium-card hero-section" style={{
          marginBottom: 'var(--space-8)',
          padding: 'var(--space-12) var(--space-8)',
          textAlign: 'center',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'radial-gradient(circle at 30% 20%, var(--color-primary-50) 0%, transparent 50%), radial-gradient(circle at 80% 80%, var(--color-primary-100) 0%, transparent 50%)',
            opacity: 0.6,
            zIndex: 0
          }} />
          <div style={{ position: 'relative', zIndex: 1 }}>
            <h1 className="gradient-text" style={{
              fontSize: 'clamp(2.25rem, 5vw, 3.5rem)',
              margin: '0 0 var(--space-4) 0',
              fontWeight: 'var(--font-weight-extrabold)',
              lineHeight: 'var(--line-height-tight)',
              letterSpacing: '-0.02em'
            }}>
              <EnvironmentOutlined /> dina Workspace Center
            </h1>
            <p style={{
              fontSize: 'var(--font-size-xl)',
              color: theme === 'dark' ? '#cbd5e1' : 'var(--color-gray-600)',
              fontWeight: 'var(--font-weight-medium)',
              maxWidth: '700px',
              margin: '0 auto var(--space-8) auto',
              lineHeight: 'var(--line-height-relaxed)'
            }}>
              Verwalten Sie Ihre ESG-Arbeitsumgebungen mit modernster KI-Technologie und erstellen Sie neue Projekte mit nur einem Klick.
            </p>
            <Button
              type="primary"
              size="large"
              onClick={() => setModalOpen(true)}
              className="premium-button"
              style={{
                height: '56px',
                padding: '0 var(--space-8)',
                fontSize: 'var(--font-size-lg)',
                fontWeight: 'var(--font-weight-bold)',
                borderRadius: 'var(--radius-2xl)',
                boxShadow: 'var(--shadow-primary-lg)'
              }}
            >
              <PlusOutlined /> Neue Umgebung erstellen
            </Button>
          </div>
        </div>
        <div className="premium-card" style={{ overflow: 'hidden' }}>
          <Table<WorkspaceRow>
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={data}
            style={{
              background: 'transparent'
            }}
            pagination={{ 
              pageSize: 8,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) => `${range[0]}-${range[1]} von ${total} Umgebungen`,
              style: {
                background: 'linear-gradient(135deg, rgba(248, 250, 252, 0.8) 0%, rgba(255, 255, 255, 0.9) 100%)',
                borderRadius: '12px',
                padding: '16px',
                margin: '16px 0 0 0'
              }
            }}
          />
        </div>
        <Modal
          title={
            <div style={{ textAlign: 'center', padding: '8px 0' }}>
              <h2 className="gradient-text" style={{
                fontSize: '24px',
                fontWeight: 800,
                margin: 0,
                letterSpacing: '-0.5px'
              }}>
                Neue dina Umgebung
              </h2>
              <p style={{
                color: theme === 'dark' ? '#cbd5e1' : '#64748b',
                fontSize: '14px',
                margin: '4px 0 0 0',
                fontWeight: 500
              }}>
                Erstellen Sie einen neuen KI-Arbeitsbereich
              </p>
            </div>
          }
          open={modalOpen}
          onOk={handleCreate}
          onCancel={() => {
            setModalOpen(false);
            form.resetFields();
          }}
          okText="Erstellen"
          cancelText="Abbrechen"
          width={600}
          style={{
            top: '20vh'
          }}
          styles={{
            body: {
              background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(248, 250, 252, 0.9) 100%)',
              borderRadius: '16px',
              padding: '32px'
            },
            header: {
              background: 'linear-gradient(135deg, rgba(248, 250, 252, 0.9) 0%, rgba(255, 255, 255, 0.95) 100%)',
              borderBottom: '1px solid rgba(9, 153, 241, 0.1)',
              borderRadius: '16px 16px 0 0'
            }
          }}
        >
        <Form form={form} layout="vertical" name="createWorkspaceForm">
          <Form.Item
            name="title"
            label="Titel"
            rules={[{ required: true, message: "Bitte Titel eingeben" }]}
          >
            <Input placeholder="Name der Umgebung" />
          </Form.Item>
          <Form.Item name="description" label="Beschreibung">
            <Input.TextArea rows={3} placeholder="Kurzbeschreibung" />
          </Form.Item>
        </Form>
      </Modal>
      </div>
    </>
  );
}
