import { Avatar, Table, Button, Space, Dropdown, Typography } from 'antd';
import { DownloadOutlined, CopyOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { useTheme } from '../../contexts/ThemeContext';
import type { AgentResponseGroup, FinalResult , CalculationSummary } from '../../types';
import ReasoningSection from './ReasoningSection';
import { VisualizationDisplay } from './VisualizationDisplay';
import { CalculationDisplay } from './CalculationDisplay';
import { CorpusInfoDisplay } from './CorpusInfoDisplay';

interface AgentResponseContainerProps {
  group: AgentResponseGroup;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onCopyQuery?: (query: string) => void;
  getResultsExportMenu?: (vars: string[], results: unknown[]) => MenuProps;
}

interface SparqlResultData {
  query?: string;
  variables?: string[];
  results?: Array<Record<string, { value: string; type?: string }>>;
  message?: string;
}

interface VisualizationResultData {
  code?: string;
  imageBase64?: string;
}

interface CalculationResultData {
  code?: string;
  summary?: Record<string, unknown>;
  table?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
  json?: string;
}

interface CorpusInfoResultData {
  files?: Array<{
    filename: string;
    full_filename: string;
    description: string;
    relevance_score: number;
    is_embedded: boolean;
  }>;
  totalFiles?: number;
}

function FinalResultRenderer({
  result,
  theme,
  onCopyQuery,
  getResultsExportMenu,
}: {
  result: FinalResult;
  theme: 'light' | 'dark';
  onCopyQuery?: (query: string) => void;
  getResultsExportMenu?: (vars: string[], results: unknown[]) => MenuProps;
}) {
  switch (result.type) {
    case 'sparql_results': {
      const data = result.data as SparqlResultData;
      const results = data.results || [];
      const variables = data.variables || [];

      return (
        <div
          className="final-result-card"
          style={{
            background: theme === 'dark' ? '#1e293b' : '#ffffff',
            border: theme === 'dark' ? '1px solid #475569' : '1px solid #e2e8f0',
          }}
        >
          <div className="final-result-header">
            <Typography.Text
              strong
              style={{
                fontSize: '12px',
                color: theme === 'dark' ? '#cbd5e1' : '#666',
              }}
            >
              Ergebnisse ({results.length} Zeilen)
            </Typography.Text>
            <Space size="small">
              {data.query && onCopyQuery && (
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  type="text"
                  onClick={() => onCopyQuery(data.query!)}
                >
                  Query
                </Button>
              )}
              {results.length > 0 && variables.length > 0 && getResultsExportMenu && (
                <Dropdown
                  menu={getResultsExportMenu(variables, results)}
                  placement="bottomRight"
                  trigger={['click']}
                >
                  <Button size="small" icon={<DownloadOutlined />} type="text">
                    Export
                  </Button>
                </Dropdown>
              )}
            </Space>
          </div>
          {results.length > 0 && variables.length > 0 ? (
            <Table
              size="small"
              bordered
              dataSource={results.map((row, index) => ({ key: `row-${index}`, ...row }))}
              columns={variables.map((variable) => ({
                title: variable,
                dataIndex: variable,
                key: variable,
                render: (cell: { value?: string }) => cell?.value ?? 'N/A',
              }))}
              pagination={{ pageSize: 5, simple: true }}
              scroll={{ x: 'max-content' }}
            />
          ) : (
            <div
              className="final-result-empty"
              style={{
                background: theme === 'dark' ? '#374151' : '#fafafa',
              }}
            >
              <Typography.Text>
                {data.message || 'Die SPARQL-Anfrage ergab keine Ergebnisse.'}
              </Typography.Text>
            </div>
          )}
        </div>
      );
    }

    case 'visualization': {
      const data = result.data as VisualizationResultData;
      if (!data.imageBase64) return null;
      return (
        <VisualizationDisplay code={data.code || ''} imageBase64={data.imageBase64} />
      );
    }

    case 'calculation': {
      const data = result.data as CalculationResultData;
      return (
        <CalculationDisplay
          code={data.code || ''}
          summary={(data.summary || {}) as CalculationSummary}
          table={data.table || []}
          metadata={data.metadata || {}}
          json={data.json || '{}'}
        />
      );
    }

    case 'corpus_info': {
      const data = result.data as CorpusInfoResultData;
      if (!data.files) return null;
      return (
        <CorpusInfoDisplay
          files={data.files}
          totalFiles={data.totalFiles || data.files.length}
        />
      );
    }

    case 'text_response': {
      const data = result.data as { message?: string };
      if (!data.message) return null;
      return (
        <div
          className="final-result-text"
          style={{
            background: theme === 'dark' ? '#1e293b' : '#ffffff',
            border: theme === 'dark' ? '1px solid #475569' : '1px solid #e2e8f0',
            color: theme === 'dark' ? '#e2e8f0' : '#1e293b',
          }}
        >
          {data.message}
        </div>
      );
    }

    default:
      return null;
  }
}

export default function AgentResponseContainer({
  group,
  isExpanded,
  onToggleExpand,
  onCopyQuery,
  getResultsExportMenu,
}: AgentResponseContainerProps) {
  const { theme } = useTheme();

  return (
    <div className="agent-response-container">
      {/* Avatar */}
      <Avatar
        size={52}
        src="/dina_bird_2026.png"
        className="agent-response-avatar"
      />

      {/* Content */}
      <div className="agent-response-content">
        {/* Reasoning Section (Collapsible) */}
        {group.reasoningSteps.length > 0 && (
          <ReasoningSection
            steps={group.reasoningSteps}
            isExpanded={isExpanded}
            onToggle={onToggleExpand}
          />
        )}

        {/* Final Results (Always Visible) */}
        {group.finalResults.map((result, idx) => (
          <div key={`result-${idx}`} className="final-result-wrapper">
            <FinalResultRenderer
              result={result}
              theme={theme}
              onCopyQuery={onCopyQuery}
              getResultsExportMenu={getResultsExportMenu}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
