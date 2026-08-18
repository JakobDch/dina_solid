import { Code, Download } from 'lucide-react';

interface VisualizationDisplayProps {
  code: string;
  imageBase64: string;
}

/**
 * Component to display visualization results from the agent.
 * Shows the generated image and provides download buttons for both image and code.
 */
export function VisualizationDisplay({ code, imageBase64 }: VisualizationDisplayProps) {
  const handleDownloadCode = () => {
    const blob = new Blob([code], { type: 'text/x-python' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'visualization.py';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadImage = () => {
    const a = document.createElement('a');
    a.href = `data:image/png;base64,${imageBase64}`;
    a.download = 'visualization.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div
      className="visualization-display"
      style={{
        borderRadius: '16px',
        border: '2px solid var(--color-gray-200)',
        backgroundColor: 'white',
        padding: '20px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
        overflow: 'hidden'
      }}
    >
      {/* Image Display */}
      <div style={{
        backgroundColor: '#f8fafc',
        borderRadius: '12px',
        padding: '16px',
        marginBottom: '16px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center'
      }}>
        <img
          src={`data:image/png;base64,${imageBase64}`}
          alt="Visualisierung"
          style={{
            maxWidth: '100%',
            maxHeight: '450px',
            objectFit: 'contain',
            borderRadius: '8px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
          }}
        />
      </div>

      {/* Download Buttons */}
      <div style={{
        display: 'flex',
        gap: '12px',
        justifyContent: 'center',
        flexWrap: 'wrap'
      }}>
        <button
          onClick={handleDownloadImage}
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
          <Download size={16} />
          Bild herunterladen
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

export default VisualizationDisplay;
