import { FileText, Database, Search } from 'lucide-react';
import type { CorpusFileInfo } from '../../types';

interface CorpusInfoDisplayProps {
  files: CorpusFileInfo[];
  totalFiles: number;
  onSelectFile?: (filename: string) => void;
}

/**
 * Component to display corpus information results from the agent.
 * Shows available files with relevance scores and descriptions.
 */
export function CorpusInfoDisplay({ files, totalFiles, onSelectFile }: CorpusInfoDisplayProps) {
  const getRelevanceColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 dark:text-green-400';
    if (score >= 0.5) return 'text-yellow-600 dark:text-yellow-400';
    if (score > 0) return 'text-orange-600 dark:text-orange-400';
    return 'text-gray-400 dark:text-gray-500';
  };

  const getRelevanceBar = (score: number) => {
    const percentage = Math.min(score * 100, 100);
    let bgColor = 'bg-gray-300';
    if (score >= 0.8) bgColor = 'bg-green-500';
    else if (score >= 0.5) bgColor = 'bg-yellow-500';
    else if (score > 0) bgColor = 'bg-orange-500';

    return (
      <div className="w-16 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${bgColor} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    );
  };

  return (
    <div className="corpus-info-display rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 my-2">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-200 dark:border-gray-700">
        <Database size={18} className="text-blue-500" />
        <span className="font-medium text-gray-700 dark:text-gray-200">
          {totalFiles} Dateien im Workspace
        </span>
      </div>

      {/* File List */}
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {files.map((file, index) => (
          <div
            key={file.full_filename || index}
            className={`flex items-start gap-3 p-2 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${
              onSelectFile ? 'cursor-pointer' : ''
            }`}
            onClick={() => onSelectFile?.(file.full_filename)}
          >
            {/* File Icon */}
            <FileText size={16} className="text-gray-400 mt-0.5 flex-shrink-0" />

            {/* File Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-sm text-gray-800 dark:text-gray-200 truncate">
                  {file.filename}
                </span>
                {file.relevance_score > 0 && (
                  <div className="flex items-center gap-1">
                    {getRelevanceBar(file.relevance_score)}
                    <span className={`text-xs ${getRelevanceColor(file.relevance_score)}`}>
                      {(file.relevance_score * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
                {file.is_embedded && (
                  <span className="text-xs px-1.5 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded">
                    Indiziert
                  </span>
                )}
              </div>
              {file.description && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                  {file.description}
                </p>
              )}
            </div>

            {/* Action hint */}
            {onSelectFile && (
              <Search size={14} className="text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
            )}
          </div>
        ))}
      </div>

      {/* Footer - show if there are more files */}
      {files.length < totalFiles && (
        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700 text-center">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            + {totalFiles - files.length} weitere Dateien
          </span>
        </div>
      )}
    </div>
  );
}

export default CorpusInfoDisplay;
