import type { Dataset } from '../../types';

export interface MatchingPair {
  id: string;
  rdf_dataset: Dataset;
  semantic_model: Dataset;
  created_at: string;
  workspace_id: string;
}

export interface DragItem {
  type: string;
  file: Dataset;
}

export const ItemTypes = {
  RDF_FILE: 'rdf_file',
  SEMANTIC_MODEL: 'semantic_model'
} as const;