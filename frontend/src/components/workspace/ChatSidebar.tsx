import { Button, Tooltip, Avatar } from 'antd';
import {
  PlusOutlined,
  CloseOutlined,
  UserOutlined
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useProfile } from '../../contexts/ProfileContext';
import DinaLogoReversed from '../../assets/dina_logo_2026_reversed.png';
import type { ChatTab } from '../../types';
import { useTranslation } from 'react-i18next';

interface ChatSidebarProps {
  tabs: ChatTab[];
  activeTabId: string | null;
  onTabClick: (tabId: string) => void;
  onTabClose: (tabId: string) => void;
  onNewTab: () => void;
}

export default function ChatSidebar({
  tabs,
  activeTabId,
  onTabClick,
  onTabClose,
  onNewTab
}: ChatSidebarProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id: workspaceId } = useParams<{ id: string }>();
  const { profile } = useProfile();

  return (
    <div style={{
      width: '260px',
      minWidth: '260px',
      height: '100%',
      background: '#164475',
      display: 'flex',
      flexDirection: 'column',
      borderRadius: '20px',
      overflow: 'hidden',
      boxShadow: '0 8px 32px rgba(22, 68, 117, 0.25)'
    }}>
      {/* Logo Section - Like reference image */}
      <div
        style={{
          padding: '28px 24px 24px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          cursor: 'pointer'
        }}
        onClick={() => navigate('/')}
      >
        <img
          src={DinaLogoReversed}
          alt="dina Logo"
          style={{
            height: '90px',
            width: 'auto'
          }}
        />
      </div>

      {/* New Analysis Button - Prominent */}
      <div style={{
        padding: '0 16px 16px'
      }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={onNewTab}
          style={{
            width: '100%',
            height: '40px',
            borderRadius: '10px',
            background: 'rgba(255, 255, 255, 0.15)',
            border: '1px solid rgba(255, 255, 255, 0.25)',
            color: '#ffffff',
            fontWeight: 500,
            fontSize: '14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
            transition: 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.25)';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.4)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.15)';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.25)';
          }}
        >
          Neue Analyse
        </Button>
      </div>

      {/* Section Title - "Letzte Analysen" */}
      <div style={{
        padding: '8px 20px 12px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <span style={{
          color: 'rgba(255, 255, 255, 0.7)',
          fontSize: '12px',
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}>
          Letzte Analysen
        </span>
      </div>

      {/* Tabs List */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '0 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: '2px'
      }}>
        {tabs.map((tab) => {
          const isActive = tab.id === activeTabId;
          return (
            <div
              key={tab.id}
              onClick={() => onTabClick(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 12px',
                borderRadius: '8px',
                cursor: 'pointer',
                background: isActive
                  ? 'rgba(91, 155, 213, 0.35)'
                  : 'transparent',
                borderLeft: isActive ? '3px solid #C6712F' : '3px solid transparent',
                transition: 'all 0.15s ease',
                position: 'relative'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              <div style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <span
                  style={{
                    color: '#ffffff',
                    fontSize: '14px',
                    fontWeight: isActive ? 600 : 400
                  }}
                >
                  {tab.title}
                </span>
              </div>

              {/* Icon on right side for active tab or close button */}
              {isActive ? (
                <div style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '6px',
                  background: 'rgba(255, 255, 255, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                  </svg>
                </div>
              ) : tabs.length > 1 && (
                <Tooltip title={t('chat.closeTab')}>
                  <Button
                    type="text"
                    size="small"
                    icon={<CloseOutlined style={{ fontSize: '10px' }} />}
                    onClick={(e) => {
                      e.stopPropagation();
                      onTabClose(tab.id);
                    }}
                    style={{
                      color: 'rgba(255, 255, 255, 0.4)',
                      width: '20px',
                      height: '20px',
                      minWidth: '20px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: '4px',
                      opacity: 0
                    }}
                    className="tab-close-btn"
                  />
                </Tooltip>
              )}
            </div>
          );
        })}
      </div>

      {/* Bottom User Profile Section */}
      <div style={{
        padding: '16px',
        marginTop: 'auto'
      }}>
        <div
          onClick={() => navigate(`/workspace/${workspaceId}/profile`)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '8px',
            borderRadius: '10px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}
        >
          {/* User Avatar */}
          {profile?.avatarUrl ? (
            <Avatar
              src={profile.avatarUrl}
              size={40}
              style={{
                flexShrink: 0,
                border: '2px solid rgba(255, 255, 255, 0.2)'
              }}
            />
          ) : (
            <Avatar
              icon={<UserOutlined />}
              size={40}
              style={{
                flexShrink: 0,
                background: 'rgba(255, 255, 255, 0.15)',
                border: '2px solid rgba(255, 255, 255, 0.2)'
              }}
            />
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                color: '#ffffff',
                fontSize: '14px',
                fontWeight: 500,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}
            >
              {profile?.name || 'Einstellungen'}
            </div>
            <div
              style={{
                color: 'rgba(255, 255, 255, 0.6)',
                fontSize: '12px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}
            >
              {profile?.institution || 'Datenquelle'}
            </div>
          </div>
        </div>
      </div>

      {/* CSS for hover effects on close buttons */}
      <style>{`
        .tab-close-btn {
          opacity: 0 !important;
          transition: opacity 0.15s ease !important;
        }
        div:hover > .tab-close-btn {
          opacity: 0.6 !important;
        }
        .tab-close-btn:hover {
          opacity: 1 !important;
          background: rgba(255, 255, 255, 0.1) !important;
          color: white !important;
        }
      `}</style>
    </div>
  );
}
