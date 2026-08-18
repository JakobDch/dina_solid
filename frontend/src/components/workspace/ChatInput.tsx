import { Form, Input, Button, Dropdown, Tooltip, Switch } from 'antd';
import { BulbOutlined, ExperimentOutlined, DownOutlined, SettingOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import DinaLogo from '../../assets/dina_logo_2026.png';
import { useTranslation } from 'react-i18next';

// Import logos (PNG for official logos, SVG for others)

// Model badge.
//
// Providers are shown as a lettered badge rather than their corporate logos:
// the marks are trademarked and would otherwise have to be redistributed with
// this repository.
const LLMIcon = ({ provider, size = 24 }: { provider: string; size?: number }) => {
  const palette: Array<{ match: string; label: string; background: string }> = [
    { match: 'deepseek', label: 'DS', background: 'linear-gradient(135deg, #4D6BFE 0%, #3B54CC 100%)' },
    { match: 'gpt', label: 'AI', background: 'linear-gradient(135deg, #10A37F 0%, #0D8768 100%)' },
    { match: 'openai', label: 'AI', background: 'linear-gradient(135deg, #10A37F 0%, #0D8768 100%)' },
    { match: 'qwen', label: 'QW', background: 'linear-gradient(135deg, #7C3AED 0%, #5B21B6 100%)' },
    { match: 'gemma', label: 'GM', background: 'linear-gradient(135deg, #4285F4 0%, #1A73E8 100%)' },
    { match: 'llama', label: 'LL', background: 'linear-gradient(135deg, #0866FF 0%, #0653CC 100%)' },
    { match: 'phi', label: 'PH', background: 'linear-gradient(135deg, #0078D4 0%, #005A9E 100%)' },
    { match: 'fireworks', label: 'FW', background: 'linear-gradient(135deg, #FF6B35 0%, #F72585 100%)' },
    { match: 'ollama', label: 'OL', background: 'linear-gradient(135deg, #374151 0%, #111827 100%)' },
  ];

  const entry = palette.find(({ match }) => provider.includes(match));

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '6px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        overflow: 'hidden',
        background: entry?.background ?? 'linear-gradient(135deg, #6B7280 0%, #4B5563 100%)',
        color: '#fff',
        fontWeight: 700,
        fontSize: size * 0.4,
        letterSpacing: '0.02em',
      }}
    >
      {entry?.label ?? 'AI'}
    </div>
  );
};

// LLM Options with icons
export interface LLMOption {
  value: string;
  label: string;
}

interface ChatInputProps {
  chatInput: string;
  isChatLoading: boolean;
  isWaitingForClarification: boolean;
  isFollowUpMode: boolean;
  activeSession: any;
  onChatInputChange: (value: string) => void;
  onSubmit: () => void;
  getSuggestionMenu: () => MenuProps;
  onCorrectLastQuery?: () => void;
  hasResultsDisplayed?: boolean;
  // LLM Selection Props
  selectedLLMProfile?: string;
  onLLMChange?: (value: string) => void;
  llmOptions?: LLMOption[];
  // Settings Props
  interactiveMode?: boolean;
  onInteractiveModeChange?: (value: boolean) => void;
  autoExecutePlans?: boolean;
  onAutoExecutePlansChange?: (value: boolean) => void;
  useAgentMode?: boolean;
  showKIConfiguration?: boolean;
  onToggleKIConfiguration?: () => void;
}

export default function ChatInput({
  chatInput,
  isChatLoading,
  isWaitingForClarification,
  isFollowUpMode,
  activeSession,
  onChatInputChange,
  onSubmit,
  getSuggestionMenu,
  onCorrectLastQuery,
  hasResultsDisplayed,
  selectedLLMProfile = 'deepseek_chat',
  onLLMChange,
  llmOptions = [],
  interactiveMode = false,
  onInteractiveModeChange,
  autoExecutePlans = true,
  onAutoExecutePlansChange,
  useAgentMode = false,
  showKIConfiguration = false,
  onToggleKIConfiguration,
}: ChatInputProps) {

  // Get the currently selected LLM option
  const { t } = useTranslation();
  const selectedOption = llmOptions.find(opt => opt.value === selectedLLMProfile);

  // Build dropdown menu items
  const llmMenuItems: MenuProps['items'] = llmOptions.map(option => ({
    key: option.value,
    label: (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '4px 0'
      }}>
        <LLMIcon provider={option.value} size={22} />
        <span style={{
          fontSize: '13px',
          fontWeight: selectedLLMProfile === option.value ? 600 : 400,
          color: selectedLLMProfile === option.value ? '#164475' : '#374151'
        }}>
          {option.label}
        </span>
        {selectedLLMProfile === option.value && (
          <span style={{
            marginLeft: 'auto',
            color: '#10b981',
            fontSize: '14px'
          }}>✓</span>
        )}
      </div>
    ),
    onClick: () => onLLMChange?.(option.value)
  }));

  return (
    <Form layout="vertical" onFinish={onSubmit} style={{ marginTop: 'auto' }}>
      <Form.Item style={{ marginBottom: '12px' }}>
        <div style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
          background: '#ffffff',
          borderRadius: '50px',
          border: '2px solid var(--color-gray-200)',
          padding: '8px 8px 8px 12px',
          boxShadow: '0 2px 8px rgba(22, 68, 117, 0.05)',
          transition: 'all 0.2s ease'
        }}>
          {/* LLM Selection Dropdown - Left side */}
          {llmOptions.length > 0 && (
            <Dropdown
              menu={{ items: llmMenuItems }}
              placement="topLeft"
              trigger={['click']}
              disabled={isChatLoading}
              dropdownRender={(menu) => (
                <div style={{
                  borderRadius: '12px',
                  overflow: 'hidden',
                  boxShadow: '0 8px 32px rgba(22, 68, 117, 0.15)',
                  border: '1px solid var(--color-gray-200)',
                  background: '#fff'
                }}>
                  <div style={{
                    padding: '12px 16px 8px',
                    borderBottom: '1px solid var(--color-gray-100)',
                    background: 'linear-gradient(135deg, #f8fafc 0%, #fff 100%)'
                  }}>
                    <span style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      color: '#64748b',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      {t('chat.selectModel')}
                    </span>
                  </div>
                  {menu}
                </div>
              )}
            >
              <Tooltip
                title={selectedOption?.label || t('chat.selectModel')}
                placement="top"
                mouseEnterDelay={0.5}
              >
                <Button
                  style={{
                    height: '40px',
                    minWidth: '40px',
                    padding: '0 8px',
                    borderRadius: '20px',
                    border: '1px solid var(--color-gray-200)',
                    background: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    flexShrink: 0,
                    cursor: isChatLoading ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={(e) => {
                    if (!isChatLoading) {
                      e.currentTarget.style.background = '#f8fafc';
                      e.currentTarget.style.borderColor = '#164475';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = '#ffffff';
                    e.currentTarget.style.borderColor = 'var(--color-gray-200)';
                  }}
                >
                  <LLMIcon provider={selectedLLMProfile} size={24} />
                  <DownOutlined style={{
                    fontSize: '10px',
                    color: '#64748b',
                    transition: 'transform 0.2s ease'
                  }} />
                </Button>
              </Tooltip>
            </Dropdown>
          )}

          <Input.TextArea
            rows={1}
            value={chatInput}
            onChange={(e) => onChatInputChange(e.target.value)}
            placeholder={
              isWaitingForClarification
                ? t('chat.answerFollowUp')
                : isFollowUpMode && activeSession
                  ? t('chat.placeholder')
                  : t('chat.placeholder')
            }
            disabled={isChatLoading}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                onSubmit();
              }
            }}
            style={{
              border: 'none',
              background: 'transparent',
              boxShadow: 'none',
              fontSize: '15px',
              resize: 'none',
              flex: 1,
              padding: '8px 0'
            }}
            autoSize={{ minRows: 1, maxRows: 4 }}
          />

          {!isWaitingForClarification && (
            <>
              {/* Show suggestion button when no results have been displayed */}
              {!hasResultsDisplayed ? (
                <Dropdown
                  menu={getSuggestionMenu()}
                  placement="topRight"
                  trigger={['click']}
                >
                  <Button
                    icon={<BulbOutlined />}
                    disabled={isChatLoading}
                    style={{
                      height: '44px',
                      width: '44px',
                      borderRadius: '50%',
                      border: '1px solid var(--color-gray-200)',
                      background: '#ffffff',
                      color: '#164475',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}
                    title={t('chat.showSuggestions')}
                  />
                </Dropdown>
              ) : (
                /* Show correction button when results have been displayed */
                onCorrectLastQuery && (
                  <Button
                    icon={<ExperimentOutlined />}
                    disabled={isChatLoading}
                    onClick={onCorrectLastQuery}
                    style={{
                      height: '44px',
                      width: '44px',
                      borderRadius: '50%',
                      border: 'none',
                      background: 'linear-gradient(135deg, #C6712F 0%, #a85d26 100%)',
                      color: 'white',
                      boxShadow: '0 2px 8px rgba(198, 113, 47, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}
                    title="Letzte SPARQL-Query korrigieren"
                  />
                )
              )}
            </>
          )}

          {/* Settings Dropdown */}
          <Dropdown
            menu={{
              items: [
                {
                  key: 'interactive-mode',
                  label: (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px',
                      minWidth: '200px'
                    }}>
                      <span>Interaktiver Modus</span>
                      <Switch
                        size="small"
                        checked={interactiveMode}
                        onChange={(checked, e) => {
                          e.stopPropagation();
                          onInteractiveModeChange?.(checked);
                        }}
                        disabled={isChatLoading}
                        style={{
                          background: interactiveMode ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : undefined
                        }}
                      />
                    </div>
                  ),
                },
                ...(useAgentMode ? [{
                  key: 'auto-execute',
                  label: (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px',
                      minWidth: '200px'
                    }}>
                      <span>Auto-Execute</span>
                      <Switch
                        size="small"
                        checked={autoExecutePlans}
                        onChange={(checked, e) => {
                          e.stopPropagation();
                          onAutoExecutePlansChange?.(checked);
                        }}
                        disabled={isChatLoading}
                        style={{
                          background: autoExecutePlans ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : undefined
                        }}
                      />
                    </div>
                  ),
                }] : []),
                { type: 'divider' as const },
                {
                  key: 'ki-config',
                  label: (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <SettingOutlined />
                      <span>KI-Konfiguration</span>
                      <span style={{
                        marginLeft: 'auto',
                        color: showKIConfiguration ? '#C6712F' : '#94a3b8',
                        fontSize: '12px'
                      }}>
                        {showKIConfiguration ? 'An' : 'Aus'}
                      </span>
                    </div>
                  ),
                  onClick: () => onToggleKIConfiguration?.()
                }
              ]
            }}
            placement="topRight"
            trigger={['click']}
          >
            <Tooltip title="Einstellungen" placement="top">
              <Button
                icon={<SettingOutlined />}
                style={{
                  height: '44px',
                  width: '44px',
                  borderRadius: '50%',
                  border: '1px solid var(--color-gray-200)',
                  background: showKIConfiguration ? 'rgba(22, 68, 117, 0.08)' : '#ffffff',
                  color: showKIConfiguration ? '#164475' : '#64748b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  transition: 'all 0.2s ease'
                }}
              />
            </Tooltip>
          </Dropdown>

          {/* Bird icon on the right side */}
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '50%',
            background: 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            <img
              src={DinaLogo}
              alt="dina"
              style={{ height: '32px', width: 'auto', opacity: 0.6 }}
            />
          </div>

          {/* Send Button */}
          <Button
            type="primary"
            htmlType="submit"
            loading={isChatLoading}
            style={{
              height: '44px',
              minWidth: '100px',
              borderRadius: '50px',
              background: 'linear-gradient(135deg, #C6712F 0%, #a85d26 100%)',
              border: 'none',
              fontWeight: 600,
              fontSize: '14px',
              boxShadow: '0 4px 12px rgba(198, 113, 47, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              flexShrink: 0
            }}
          >
            Senden
          </Button>
        </div>
      </Form.Item>
    </Form>
  );
}