import { Avatar, Typography, List as AntList, Table, Dropdown, Button, Space, Tooltip } from 'antd';
import { UserOutlined, DownloadOutlined, CopyOutlined, MessageOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage, AgentMessage, AgentResponseGroup } from '../../types';
import { useProfile } from '../../contexts/ProfileContext';
import { useTheme } from '../../contexts/ThemeContext';
import assistantAvatar from '../../assets/dina_logo_2026.png';
import { VisualizationDisplay } from './VisualizationDisplay';
import { CalculationDisplay } from './CalculationDisplay';
import { CorpusInfoDisplay } from './CorpusInfoDisplay';
import DynamicLoadingIndicator from './DynamicLoadingIndicator';
import AgentResponseContainer from './AgentResponseContainer';
import { useTranslation } from 'react-i18next';

interface ChatMessageListProps {
  chatHistory: ChatMessage[];
  activeStreamIds: Set<string>;
  isChatLoading: boolean;
  exportingQuery: string | null;
  onCopyQuery: (query: string) => void;
  onExportResults: (variables: string[], results: any[], format: string) => void;
  getSparqlExportMenu: (sparqlQuery: string) => MenuProps;
  getResultsExportMenu: (variables: string[], results: any[]) => MenuProps;
  // ChatGPT-style reasoning display props
  responseGroups?: Map<string, AgentResponseGroup>;
  activeResponseGroup?: AgentResponseGroup | null;
  expandedGroups?: Set<string>;
  onToggleGroupExpand?: (groupId: string) => void;
}

export default function ChatMessageList({
  chatHistory,
  activeStreamIds,
  isChatLoading,
  exportingQuery: _exportingQuery,
  onCopyQuery,
  onExportResults: _onExportResults,
  getSparqlExportMenu: _getSparqlExportMenu,
  getResultsExportMenu,
  responseGroups,
  activeResponseGroup,
  expandedGroups,
  onToggleGroupExpand
}: ChatMessageListProps) {
  const { t } = useTranslation();
  const { profile } = useProfile();
  const { theme } = useTheme();

  // Helper function to find the response group for a user message
  const getResponseGroupForMessage = (messageKey: string): AgentResponseGroup | undefined => {
    if (!responseGroups) return undefined;
    return Array.from(responseGroups.values()).find(group => group.userQueryKey === messageKey);
  };

  if (chatHistory.length === 0) {
    return (
      <div
        className="chat-empty-state"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          textAlign: 'center',
          padding: 'var(--space-10)',
          position: 'relative'
        }}
      >
        <div style={{
          position: 'absolute',
          top: '20%',
          left: '50%',
          transform: 'translateX(-50%)',
          width: '200px',
          height: '200px',
          background: 'radial-gradient(circle, var(--color-primary-100) 0%, transparent 70%)',
          borderRadius: '50%',
          opacity: 0.3,
        }} />

        <div
          className="chat-icon"
          style={{
            width: '96px',
            height: '96px',
            borderRadius: 'var(--radius-3xl)',
            background: 'linear-gradient(135deg, var(--color-primary-500) 0%, var(--color-primary-600) 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 'var(--space-6)',
            boxShadow: 'var(--shadow-primary-lg)',
            color: 'white',
            fontSize: 'var(--font-size-2xl)',
            fontWeight: 'var(--font-weight-extrabold)',
            position: 'relative',
          }}
        >
          <MessageOutlined />
        </div>

        <Typography.Title
          level={3}
          style={{
            color: 'var(--color-primary-700)',
            margin: '0 0 var(--space-3) 0',
            fontWeight: 'var(--font-weight-extrabold)',
            fontSize: 'var(--font-size-2xl)'
          }}
        >
          {t('chat.ready')}
        </Typography.Title>

        <Typography.Text
          style={{
            color: 'var(--color-gray-600)',
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-medium)',
            maxWidth: '400px',
            lineHeight: 'var(--line-height-relaxed)'
          }}
        >
          {t('chat.emptyState')}
        </Typography.Text>
      </div>
    );
  }

  return (
    <>
      <AntList
        dataSource={chatHistory}
        renderItem={(item) => (
          <>
          <AntList.Item key={item.key} style={{ border: 'none', padding: '8px 0' }}>
          <div style={{
            display: 'flex',
            flexDirection: item.sender === 'user' ? 'row-reverse' : 'row',
            alignItems: 'flex-end',
            gap: item.sender === 'user' ? '12px' : '4px',
            position: 'relative',
            width: '100%',
            justifyContent: item.sender === 'user' ? 'flex-start' : 'flex-start'
          }}>
            {/* Avatar */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: item.sender === 'user' ? 'flex-end' : 'flex-start' }}>
              <Tooltip
                title={item.sender === 'user' ? (profile?.name || 'Anonymous User') : t('chat.assistant')}
                placement={item.sender === 'user' ? 'left' : 'right'}
              >
                <Avatar
                  size={item.sender === 'user' ? 52 : 52}
                  icon={item.sender === 'user' ? <UserOutlined /> : undefined}
                  src={item.sender === 'user' ? (profile?.avatarUrl || undefined) : assistantAvatar}
                  className={`chat-avatar ${item.sender === 'user' ? 'user-avatar' : 'bot-avatar'} ${
                    item.is_streaming && item.sender !== 'user' ? 'streaming-avatar' : ''
                  }`}
                  style={{
                    backgroundColor: item.sender === 'user' ? 'var(--color-primary-500)' : 'transparent',
                    background: item.sender === 'user'
                      ? 'linear-gradient(135deg, var(--color-primary-500) 0%, var(--color-primary-600) 100%)'
                      : 'white',
                    flexShrink: 0,
                    zIndex: 2,
                    border: item.sender === 'user'
                      ? '2px solid white'
                      : '2px solid var(--color-primary-200)',
                    boxShadow: item.sender === 'user'
                      ? 'var(--shadow-primary)'
                      : 'var(--shadow-md)',
                    cursor: item.sender !== 'user' ? 'pointer' : 'default',
                    transition: 'all var(--transition-bounce)',
                    position: 'relative'
                  }}
                />
              </Tooltip>
              {item.sender === 'user' && profile?.name && (
                <Typography.Text
                  style={{
                    fontSize: '12px',
                    color: theme === 'dark' ? '#cbd5e1' : '#64748b',
                    marginTop: '3px',
                    textAlign: item.sender === 'user' ? 'right' : 'left',
                    maxWidth: '120px',
                    fontWeight: 500,
                    wordWrap: 'break-word',
                    whiteSpace: 'normal',
                    lineHeight: '1.2'
                  }}
                >
                  {profile.name}
                </Typography.Text>
              )}
            </div>
            
            {/* Message bubble with tail */}
            <div style={{
              position: 'relative',
              maxWidth: item.sender === 'user' ? '85%' : '75%',
              minWidth: '150px',
              width: item.sender === 'user' ? 'fit-content' : 'auto',
              marginLeft: item.sender === 'user' ? 'auto' : '0',
              marginRight: item.sender === 'user' ? '0' : 'auto',
              display: 'flex',
              justifyContent: item.sender === 'user' ? 'flex-end' : 'flex-start'
            }}>
              <div
                className={`chat-bubble ${item.sender === 'user' ? 'user-bubble' : 'bot-bubble'} ${
                  item.is_streaming ? 'streaming-bubble' : ''
                }`}
                style={{
                  background: item.sender === 'user'
                    ? 'linear-gradient(135deg, var(--color-primary-500) 0%, var(--color-primary-600) 100%)'
                    : 'white',
                  color: item.sender === 'user' ? 'white' : 'var(--color-gray-800)',
                  border: item.sender === 'user'
                    ? '2px solid var(--color-primary-400)'
                    : '2px solid var(--color-gray-200)',
                  borderRadius: item.sender === 'user'
                    ? 'var(--radius-2xl) var(--radius-2xl) var(--radius-sm) var(--radius-2xl)'
                    : 'var(--radius-2xl) var(--radius-2xl) var(--radius-2xl) var(--radius-sm)',
                  padding: 'var(--space-4) var(--space-5)',
                  position: 'relative',
                  margin: '0',
                  boxShadow: item.sender === 'user'
                    ? 'var(--shadow-primary)'
                    : 'var(--shadow-lg)',
                  width: '100%',
                  wordWrap: 'break-word',
                  backdropFilter: 'blur(10px)',
                  transition: 'all var(--transition-normal)'
                }}
              >
                
                {/* Special handling for SPARQL queries to preserve formatting */}
                {item.step_id === 'sparql_query_generated' ? (
                  <div>
                    <Typography.Paragraph
                      style={{ 
                        marginBottom: 8, 
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                        fontSize: '13px',
                        lineHeight: '1.4',
                        background: theme === 'dark' ? 'linear-gradient(135deg, #374151 0%, #334155 100%)' : 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
                        padding: '16px',
                        borderRadius: '8px',
                        border: theme === 'dark' ? '1px solid rgba(96, 165, 250, 0.3)' : '1px solid rgba(9, 153, 241, 0.1)',
                        boxShadow: theme === 'dark' ? 'inset 0 1px 3px rgba(96, 165, 250, 0.15)' : 'inset 0 1px 3px rgba(9, 153, 241, 0.05)',
                        color: theme === 'dark' ? '#f8fafc' : 'inherit'
                      }}
                    >
                      {item.message}
                    </Typography.Paragraph>
                    {/* Copy button for SPARQL queries */}
                    <Space size="small" style={{ marginTop: '8px' }}>
                      <Button
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() => onCopyQuery(item.message)}
                        type="text"
                      >
                        Copy Query
                      </Button>
                    </Space>
                  </div>
                ) : (
                  <Typography.Paragraph
                    style={{ 
                      marginBottom: 0, 
                      whiteSpace: 'pre-wrap',
                      color: item.sender === 'user' ? '#ffffff' : (theme === 'dark' ? '#f8fafc' : '#2d3748')
                    }}
                  >
                    <ReactMarkdown
                      components={{
                        p: ({children}) => <span style={{ color: item.sender === 'user' ? '#ffffff' : (theme === 'dark' ? '#f8fafc' : '#2d3748') }}>{children}</span>,
                        span: ({children}) => <span style={{ color: item.sender === 'user' ? '#ffffff' : (theme === 'dark' ? '#f8fafc' : '#2d3748') }}>{children}</span>
                      }}
                    >
                      {item.message}
                    </ReactMarkdown>
                  </Typography.Paragraph>
                )}
                
                {item.sparql_results && item.sparql_variables && (
                  <div style={{ marginTop: '10px', maxWidth: '100%', overflowX: 'auto' }}>
                    <div style={{ marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography.Text strong style={{ fontSize: '12px', color: theme === 'dark' ? '#cbd5e1' : '#666' }}>
                        Results ({item.sparql_results?.length || 0} rows)
                      </Typography.Text>
                      <Space size="small">
                        {item.sparql_results && item.sparql_results.length > 0 && item.sparql_variables && (
                          <Dropdown
                            menu={getResultsExportMenu(item.sparql_variables, item.sparql_results)}
                            placement="bottomRight"
                            trigger={['click']}
                          >
                            <Button
                              size="small"
                              icon={<DownloadOutlined />}
                              type="text"
                              style={{ fontSize: '12px' }}
                            >
                              Export Results
                            </Button>
                          </Dropdown>
                        )}
                      </Space>
                    </div>
                    {item.sparql_results && item.sparql_results.length > 0 && item.sparql_variables ? (
                      <Table
                        size="small"
                        bordered
                        dataSource={item.sparql_results.map((row, index) => ({ key: `row-${index}`, ...row }))}
                        columns={item.sparql_variables.map(variable => ({
                          title: variable,
                          dataIndex: variable,
                          key: variable,
                          render: (cell: any) => cell ? cell.value : 'N/A',
                        }))}
                        pagination={{ pageSize: 5, simple: true }}
                      />
                    ) : (
                      <div style={{
                        padding: '16px',
                        textAlign: 'center',
                        background: theme === 'dark' ? '#374151' : '#fafafa',
                        border: theme === 'dark' ? '1px solid #475569' : '1px solid #d9d9d9',
                        borderRadius: '6px',
                        color: theme === 'dark' ? '#cbd5e1' : '#666'
                      }}>
                        <Typography.Text style={{ fontSize: '14px' }}>
                          Die SPARQL-Anfrage ergab keine Ergebnisse.
                        </Typography.Text>
                      </div>
                    )}
                  </div>
                )}

{/* Visualization is rendered outside the bubble for full width */}

                {/* Corpus Info Display for agent corpus info responses */}
                {(item as AgentMessage).response_type === 'corpus_info' &&
                 (item as AgentMessage).corpus_files && (
                  <CorpusInfoDisplay
                    files={(item as AgentMessage).corpus_files!}
                    totalFiles={(item as AgentMessage).total_files || (item as AgentMessage).corpus_files!.length}
                  />
                )}
              </div>
            </div>
          </div>

          {/* Visualization Display - rendered outside the bubble for full width */}
          {(item as AgentMessage).response_type === 'visualization' &&
           (item as AgentMessage).visualization_image_base64 &&
           (item as AgentMessage).visualization_code && (
            <div style={{
              width: '100%',
              marginTop: '12px',
              marginLeft: '56px',  // Align with message content (avatar width + gap)
              paddingRight: '56px'
            }}>
              <VisualizationDisplay
                code={(item as AgentMessage).visualization_code!}
                imageBase64={(item as AgentMessage).visualization_image_base64!}
              />
            </div>
          )}

          {/* Calculation Display - rendered outside the bubble for full width */}
          {(item as AgentMessage).response_type === 'calculation' &&
           (item as AgentMessage).calculation_table && (
            <div style={{
              width: '100%',
              marginTop: '12px',
              marginLeft: '56px',  // Align with message content (avatar width + gap)
              paddingRight: '56px'
            }}>
              <CalculationDisplay
                code={(item as AgentMessage).calculation_code || ''}
                summary={(item as AgentMessage).calculation_summary || {}}
                table={(item as AgentMessage).calculation_table || []}
                metadata={(item as AgentMessage).calculation_metadata || {}}
                json={(item as AgentMessage).calculation_json || '{}'}
              />
            </div>
          )}
        </AntList.Item>
        {/* Show reasoning section after user messages (ChatGPT-style) */}
        {item.is_user_message && (() => {
          const group = getResponseGroupForMessage(item.key);
          if (group && group.status !== 'processing' && group.reasoningSteps.length > 0 && onToggleGroupExpand) {
            return (
              <div style={{ marginTop: '8px', marginBottom: '8px' }}>
                <AgentResponseContainer
                  group={group}
                  isExpanded={expandedGroups?.has(group.groupId) || false}
                  onToggleExpand={() => onToggleGroupExpand(group.groupId)}
                  onCopyQuery={onCopyQuery}
                  getResultsExportMenu={getResultsExportMenu}
                />
              </div>
            );
          }
          return null;
        })()}
        </>
        )}
      />

      {/* Loading animation inside chat when processing but not streaming */}
      {isChatLoading && activeStreamIds.size === 0 && (
        <DynamicLoadingIndicator currentStep={activeResponseGroup?.currentStep} />
      )}

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </>
  );
}