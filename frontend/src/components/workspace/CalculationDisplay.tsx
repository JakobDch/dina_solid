import { FileJson, Code, Table, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import type { CalculationSummary, CalculationMetadata } from '../../types';

interface CalculationDisplayProps {
  code: string;
  summary: CalculationSummary;
  table: Array<Record<string, unknown>>;
  metadata: CalculationMetadata;
  json: string;
}

/**
 * Component to display calculation results from the agent.
 * Shows summary, table, and provides download buttons for JSON and code.
 */
export function CalculationDisplay({
  code,
  summary,
  table,
  metadata,
  json
}: CalculationDisplayProps) {
  const [isTableExpanded, setIsTableExpanded] = useState(false);
  const [isCodeVisible, setIsCodeVisible] = useState(false);

  const MAX_VISIBLE_ROWS = 10;
  const hasMoreRows = table.length > MAX_VISIBLE_ROWS;
  const visibleRows = isTableExpanded ? table : table.slice(0, MAX_VISIBLE_ROWS);
  const tableColumns = table.length > 0 ? Object.keys(table[0]) : [];

  const handleDownloadJson = () => {
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'calculation_result.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadCode = () => {
    const blob = new Blob([code], { type: 'text/x-python' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'calculation.py';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatValue = (value: unknown): string => {
    if (typeof value === 'number') {
      return value.toLocaleString('de-DE', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
      });
    }
    return String(value ?? '-');
  };

  return (
    <div
      className="calculation-display"
      style={{
        borderRadius: '16px',
        border: '2px solid var(--color-gray-200)',
        backgroundColor: 'white',
        padding: '20px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
        overflow: 'hidden'
      }}
    >
      {/* Summary Section */}
      {Object.keys(summary).length > 0 && (
        <div style={{
          backgroundColor: 'var(--color-primary-50)',
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '16px'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '12px',
            color: 'var(--color-primary-700)',
            fontWeight: 600,
            fontSize: '14px'
          }}>
            <Table size={18} />
            Zusammenfassung
            {metadata.unit && (
              <span style={{
                fontWeight: 400,
                color: 'var(--color-gray-500)',
                fontSize: '13px'
              }}>
                ({metadata.unit})
              </span>
            )}
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px'
          }}>
            {Object.entries(summary).map(([key, value]) => (
              <div
                key={key}
                style={{
                  backgroundColor: 'white',
                  borderRadius: '8px',
                  padding: '12px',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
                }}
              >
                <div style={{
                  fontSize: '12px',
                  color: 'var(--color-gray-500)',
                  marginBottom: '4px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}>
                  {key}
                </div>
                <div style={{
                  fontSize: '18px',
                  fontWeight: 600,
                  color: 'var(--color-gray-900)'
                }}>
                  {formatValue(value)}
                </div>
              </div>
            ))}
          </div>
          {metadata.description && (
            <div style={{
              marginTop: '12px',
              fontSize: '13px',
              color: 'var(--color-gray-600)',
              fontStyle: 'italic'
            }}>
              {metadata.description}
            </div>
          )}
        </div>
      )}

      {/* Table Section */}
      {table.length > 0 && (
        <div style={{
          backgroundColor: '#f8fafc',
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '16px',
          overflow: 'hidden'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '12px'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              color: 'var(--color-gray-700)',
              fontWeight: 600,
              fontSize: '14px'
            }}>
              <Table size={18} />
              Detaildaten ({table.length} Zeilen)
            </div>
          </div>

          <div style={{
            overflowX: 'auto',
            borderRadius: '8px',
            border: '1px solid var(--color-gray-200)'
          }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px'
            }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--color-gray-100)' }}>
                  {tableColumns.map((col) => (
                    <th
                      key={col}
                      style={{
                        padding: '10px 12px',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: 'var(--color-gray-700)',
                        borderBottom: '2px solid var(--color-gray-200)',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row, idx) => (
                  <tr
                    key={idx}
                    style={{
                      backgroundColor: idx % 2 === 0 ? 'white' : 'var(--color-gray-50)'
                    }}
                  >
                    {tableColumns.map((col) => (
                      <td
                        key={col}
                        style={{
                          padding: '10px 12px',
                          borderBottom: '1px solid var(--color-gray-100)',
                          color: 'var(--color-gray-800)'
                        }}
                      >
                        {formatValue(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMoreRows && (
            <button
              onClick={() => setIsTableExpanded(!isTableExpanded)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                width: '100%',
                padding: '10px',
                marginTop: '12px',
                backgroundColor: 'transparent',
                color: 'var(--color-primary-600)',
                border: '1px dashed var(--color-primary-300)',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 500,
                transition: 'all 0.2s ease'
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-primary-50)';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              {isTableExpanded ? (
                <>
                  <ChevronUp size={16} />
                  Weniger anzeigen
                </>
              ) : (
                <>
                  <ChevronDown size={16} />
                  {table.length - MAX_VISIBLE_ROWS} weitere Zeilen anzeigen
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* Code Section (collapsible) */}
      <div style={{ marginBottom: '16px' }}>
        <button
          onClick={() => setIsCodeVisible(!isCodeVisible)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            backgroundColor: 'transparent',
            color: 'var(--color-gray-600)',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: 500,
            transition: 'all 0.2s ease'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.color = 'var(--color-gray-800)';
            e.currentTarget.style.backgroundColor = 'var(--color-gray-100)';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.color = 'var(--color-gray-600)';
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
        >
          <Code size={16} />
          {isCodeVisible ? 'Code ausblenden' : 'Berechnungscode anzeigen'}
          {isCodeVisible ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {isCodeVisible && (
          <pre style={{
            marginTop: '8px',
            padding: '12px',
            backgroundColor: '#1e1e1e',
            color: '#d4d4d4',
            borderRadius: '8px',
            overflow: 'auto',
            fontSize: '12px',
            lineHeight: '1.5',
            maxHeight: '300px'
          }}>
            <code>{code}</code>
          </pre>
        )}
      </div>

      {/* Download Buttons */}
      <div style={{
        display: 'flex',
        gap: '12px',
        justifyContent: 'center',
        flexWrap: 'wrap'
      }}>
        <button
          onClick={handleDownloadJson}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            fontSize: '14px',
            fontWeight: 500,
            backgroundColor: 'var(--color-primary-500)',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            boxShadow: '0 2px 4px rgba(9, 153, 241, 0.3)'
          }}
          onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'var(--color-primary-600)'}
          onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'var(--color-primary-500)'}
        >
          <FileJson size={16} />
          JSON herunterladen
        </button>
        <button
          onClick={handleDownloadCode}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            fontSize: '14px',
            fontWeight: 500,
            backgroundColor: 'var(--color-gray-100)',
            color: 'var(--color-gray-700)',
            border: '1px solid var(--color-gray-300)',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--color-gray-200)';
            e.currentTarget.style.borderColor = 'var(--color-gray-400)';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--color-gray-100)';
            e.currentTarget.style.borderColor = 'var(--color-gray-300)';
          }}
        >
          <Code size={16} />
          Python-Code herunterladen
        </button>
      </div>
    </div>
  );
}

export default CalculationDisplay;
