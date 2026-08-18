import { Button, Dropdown, Avatar, Space } from 'antd';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { LoginOutlined, LogoutOutlined, UserOutlined, DatabaseOutlined, ExportOutlined, KeyOutlined } from '@ant-design/icons';
import DinaLogo from '../../assets/dina_logo_2026.png';
import { api } from '../../api/apiClient';
import { useSolidAuth } from '../../contexts/SolidAuthContext';
import LoginIssuerModal from '../common/LoginIssuerModal';
import CatalogSelectModal from '../common/CatalogSelectModal';
import LanguageSwitcher from '../common/LanguageSwitcher';
import ApiKeySettingsModal from '../common/ApiKeySettingsModal';
import { useTranslation } from 'react-i18next';
import { config } from '../../config';

interface Workspace {
  id: string;
  title: string;
  created_at: string;
}

interface HeaderBarProps {
  showNavigation?: boolean;
}

export default function HeaderBar({ showNavigation = true }: HeaderBarProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { id: workspaceIdFromUrl } = useParams<{ id: string }>();
  const [latestWorkspaceId, setLatestWorkspaceId] = useState<string | null>(null);

  // Solid Auth
  const {
    isLoggedIn,
    webId,
    catalogId,
    catalogUrl,
    isLoading: authLoading,
    logout
  } = useSolidAuth();

  // Modal states
  const [loginModalVisible, setLoginModalVisible] = useState(false);
  const [catalogModalVisible, setCatalogModalVisible] = useState(false);
  const [apiKeyModalVisible, setApiKeyModalVisible] = useState(false);

  // Fetch latest workspace if no ID in URL
  useEffect(() => {
    if (!workspaceIdFromUrl) {
      const fetchLatestWorkspace = async () => {
        try {
          const res = await api.get<Workspace[]>('/api/v1/workspaces');
          if (res.data && res.data.length > 0) {
            const sorted = [...res.data].sort((a, b) =>
              new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setLatestWorkspaceId(sorted[0].id);
          }
        } catch (err) {
          console.error('Error fetching workspaces:', err);
        }
      };
      fetchLatestWorkspace();
    }
  }, [workspaceIdFromUrl]);

  // A catalog must be selected before the agent can query the dataspace, so
  // prompt for one as soon as the user is logged in without a selection.
  useEffect(() => {
    if (isLoggedIn && !authLoading && catalogId === null) {
      setCatalogModalVisible(true);
    }
  }, [isLoggedIn, authLoading, catalogId]);

  // Extract display name from WebID
  const getDisplayName = () => {
    if (!webId) return 'User';
    try {
      const url = new URL(webId);
      const pathParts = url.pathname.split('/').filter(Boolean);
      return pathParts[0] || url.hostname;
    } catch {
      return 'User';
    }
  };

  const handleLogout = async () => {
    await logout();
  };

  // Dropdown menu for logged in user
  const userMenuItems = [
    {
      key: 'webid',
      label: (
        <Space>
          <UserOutlined />
          <span style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {getDisplayName()}
          </span>
        </Space>
      ),
      disabled: true
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      label: t('nav.signOut'),
      icon: <LogoutOutlined />,
      onClick: handleLogout
    }
  ];

  const currentWorkspaceId = workspaceIdFromUrl || latestWorkspaceId;

  const isOnChatPage = (): boolean => {
    // Chat page is /workspace/:id without any suffix like /data-management or /profile
    if (!workspaceIdFromUrl) return false;
    const chatPath = `/workspace/${workspaceIdFromUrl}`;
    return location.pathname === chatPath;
  };

  const isActive = (path: string) => {
    if (path === '') return isOnChatPage();
    if (path !== '' && location.pathname.includes(path)) return true;
    return false;
  };

  const navigateToWorkspacePage = (page: string) => {
    if (currentWorkspaceId) {
      navigate(`/workspace/${currentWorkspaceId}${page}`);
    } else {
      navigate('/workspaces');
    }
  };

  const NavLink = ({ onClick, children, active }: { onClick: () => void; children: React.ReactNode; active?: boolean }) => (
    <span
      onClick={onClick}
      style={{
        color: active ? '#C6712F' : '#164475',
        textDecoration: 'none',
        fontWeight: 500,
        cursor: 'pointer',
        transition: 'color 0.2s ease',
        display: 'flex',
        alignItems: 'center',
        gap: '6px'
      }}
      onMouseEnter={(e) => e.currentTarget.style.color = '#C6712F'}
      onMouseLeave={(e) => e.currentTarget.style.color = active ? '#C6712F' : '#164475'}
    >
      {children}
    </span>
  );

  return (
    <header style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '20px 48px',
      background: '#ffffff',
      borderBottom: '1px solid #E4E8EB'
    }}>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}
        onClick={() => navigate('/')}
      >
        <img
          src={DinaLogo}
          alt="dina Logo"
          style={{ height: '70px', width: 'auto' }}
        />
      </div>
      <nav style={{ display: 'flex', alignItems: 'center', gap: '28px' }}>
        {showNavigation && (
          <>
            <NavLink onClick={() => navigateToWorkspacePage('/profile')} active={isActive('profile')}>
              {t('nav.profile')}
            </NavLink>
          </>
        )}
        <NavLink onClick={() => navigate('/workspaces')} active={location.pathname === '/workspaces'}>
          {t('nav.workspaces')}
        </NavLink>

        {/* Catalog selection - required before the agent can query the dataspace */}
        {isLoggedIn && catalogId === null && (
          <Button
            icon={<DatabaseOutlined />}
            onClick={() => setCatalogModalVisible(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'linear-gradient(135deg, #C6712F 0%, #d98745 100%)',
              borderColor: 'transparent',
              color: '#ffffff',
              fontWeight: 500,
              borderRadius: '8px',
              padding: '0 16px',
              height: '36px',
              boxShadow: '0 2px 4px rgba(198, 113, 47, 0.2)'
            }}
          >
            <span>{t('nav.selectCatalog')}</span>
          </Button>
        )}

        {/* Selected catalog - opens the dataspace browser in a new tab */}
        {isLoggedIn && catalogId !== null && (
          <Button
            icon={<DatabaseOutlined />}
            onClick={() => window.open(config.dataspaceUiUrl || catalogUrl || '', '_blank')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'linear-gradient(135deg, #164475 0%, #1e5a9e 100%)',
              borderColor: 'transparent',
              color: '#ffffff',
              fontWeight: 500,
              borderRadius: '8px',
              padding: '0 16px',
              height: '36px',
              boxShadow: '0 2px 4px rgba(22, 68, 117, 0.2)'
            }}
          >
            <span>{t('nav.dataCatalog')}</span>
            <ExportOutlined style={{ fontSize: '12px', opacity: 0.8 }} />
          </Button>
        )}

        {/* Solid Login/User Section */}
        {authLoading ? (
          <div style={{
            width: '32px',
            height: '32px',
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
        ) : isLoggedIn ? (
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Avatar
              style={{
                backgroundColor: '#164475',
                cursor: 'pointer',
                fontWeight: 600
              }}
              size="large"
            >
              {getDisplayName().charAt(0).toUpperCase()}
            </Avatar>
          </Dropdown>
        ) : (
          <Button
            icon={<LoginOutlined />}
            onClick={() => setLoginModalVisible(true)}
            style={{
              borderColor: '#164475',
              color: '#164475'
            }}
          >
            {t('nav.signInWithSolid')}
          </Button>
        )}

        <Button
          type="primary"
          size="large"
          onClick={() => navigateToWorkspacePage('')}
          style={{
            backgroundColor: isOnChatPage() ? '#C6712F' : '#164475',
            borderColor: isOnChatPage() ? '#C6712F' : '#164475',
            border: 'none',
            borderRadius: '8px',
            fontWeight: 600,
            padding: '0 24px',
            height: '44px'
          }}
        >
          {workspaceIdFromUrl ? t('nav.toChat') : t('nav.startFirstChat')}
        </Button>
        <Button
          type="text"
          icon={<KeyOutlined />}
          onClick={() => setApiKeyModalVisible(true)}
          aria-label={t('apiKeys.title')}
          title={t('apiKeys.title')}
        />
        <LanguageSwitcher />
      </nav>

      {/* Modals */}
      <LoginIssuerModal
        visible={loginModalVisible}
        onClose={() => setLoginModalVisible(false)}
      />
      <CatalogSelectModal
        visible={catalogModalVisible}
        onClose={() => setCatalogModalVisible(false)}
      />
      <ApiKeySettingsModal
        visible={apiKeyModalVisible}
        onClose={() => setApiKeyModalVisible(false)}
      />
    </header>
  );
}
