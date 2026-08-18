import { ChevronDown, ChevronUp, Check, X, Loader2, Minus } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import type { ReasoningStep } from '../../types';

interface ReasoningSectionProps {
  steps: ReasoningStep[];
  isExpanded: boolean;
  onToggle: () => void;
}

function StepStatusIcon({ status }: { status: ReasoningStep['status'] }) {
  switch (status) {
    case 'completed':
      return <Check size={16} className="step-icon step-icon-completed" />;
    case 'running':
      return <Loader2 size={16} className="step-icon step-icon-running" />;
    case 'failed':
      return <X size={16} className="step-icon step-icon-failed" />;
    case 'skipped':
      return <Minus size={16} className="step-icon step-icon-skipped" />;
    default:
      return <div className="step-icon step-icon-pending" />;
  }
}

export default function ReasoningSection({
  steps,
  isExpanded,
  onToggle,
}: ReasoningSectionProps) {
  const { theme } = useTheme();

  if (steps.length === 0) {
    return null;
  }

  return (
    <div
      className="reasoning-section"
      style={{
        borderColor: theme === 'dark' ? '#475569' : '#e2e8f0',
      }}
    >
      {/* Toggle Header */}
      <button
        onClick={onToggle}
        className="reasoning-toggle"
        style={{
          background: theme === 'dark' ? '#334155' : '#f8fafc',
          color: theme === 'dark' ? '#cbd5e1' : '#64748b',
        }}
      >
        <span>Reasoning ({steps.length} Schritte)</span>
        {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {/* Expandable Content */}
      {isExpanded && (
        <div
          className="reasoning-steps"
          style={{
            background: theme === 'dark' ? '#1e293b' : '#ffffff',
          }}
        >
          {steps.map((step, index) => (
            <div
              key={step.id}
              className="reasoning-step"
              style={{
                borderBottomColor:
                  index < steps.length - 1
                    ? theme === 'dark'
                      ? '#334155'
                      : '#f1f5f9'
                    : 'transparent',
              }}
            >
              <StepStatusIcon status={step.status} />
              <div className="reasoning-step-content">
                <div
                  className="reasoning-step-title"
                  style={{
                    color: theme === 'dark' ? '#f1f5f9' : '#374151',
                  }}
                >
                  {step.stepNumber}. {step.description}
                </div>
                {step.details && step.details !== step.description && (
                  <div
                    className="reasoning-step-details"
                    style={{
                      color: theme === 'dark' ? '#94a3b8' : '#6b7280',
                      borderLeftColor: theme === 'dark' ? '#475569' : '#e5e7eb',
                    }}
                  >
                    {step.details}
                  </div>
                )}
                {step.sparqlQuery && (
                  <details className="reasoning-sparql-details">
                    <summary
                      style={{ color: theme === 'dark' ? '#94a3b8' : '#6b7280' }}
                    >
                      SPARQL Query anzeigen
                    </summary>
                    <pre
                      className="reasoning-sparql-code"
                      style={{
                        background: theme === 'dark' ? '#0f172a' : '#f8fafc',
                        color: theme === 'dark' ? '#e2e8f0' : '#1e293b',
                      }}
                    >
                      {step.sparqlQuery}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
