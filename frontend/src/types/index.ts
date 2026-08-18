// Type definitions extracted from App.tsx

export interface ChatMessage {
  key: string;
  id?: string;
  // A plain string covers every sender the backend may emit.
  sender: 'user' | 'llm' | 'system' | 'system_error' | string;
  message: string;
  timestamp: string;
  is_user_message: boolean;
  request_timestamp?: string;
  step_id?: string;
  event_type?: string; // SSE event type for filtering (e.g., 'sparql_result', 'pipeline_update')
  sparql_query?: string; // For SPARQL queries in messages
  sparql_variables?: string[];
  sparql_results?: any[];
  is_streaming?: boolean; // For streaming messages
  user_query?: string; // Original user query for correction
  model_info_blocks?: string; // Semantic models content for correction
  selected_models?: string[]; // Selected models for correction
}

export interface FileEntry {
  id: string; // Changed to string to match UUID from backend for models/templates/datasets
  filename: string;
  created: string;
  size: number;
}

export interface SemanticModelEntry extends FileEntry {
  is_embedded: boolean;
}

export interface WorkspaceBase {
  id: string;
  title: string;
  description?: string;
  created: string;
}

export interface WorkspaceRow extends WorkspaceBase {
  datasets?: FileEntry[];
  semantic_models?: FileEntry[];
}

export interface BackendSearchResultItem {
  text: string;
  score: number;
  source_model: string;
  model_average_score?: number;
}

export interface FrontendDisplayResultItem {
  page_content: string;
  metadata: {
    source_filename: string;
    score: number;
  };
}

export interface SearchDebugInfo {
  total_raw_hits: number;
  min_hits_threshold: number;
  models_considered_for_avg?: number;
  best_model_avg_score: number;
  score_threshold_for_models: number;
}

export interface SearchResponse {
  message: string;
  results: BackendSearchResultItem[];
  debug_info?: SearchDebugInfo;
}

export interface GroupedModelResult {
  modelName: string;
  modelAverageScore: number;
  topTriples: BackendSearchResultItem[];
}

// Model-Data Mapping types
export interface Dataset extends FileEntry {
  has_example_instance?: boolean;
  example_instance_path?: string;
  has_transformed_instance?: boolean;
  transformed_instance_path?: string;
  description?: string;
  file_size?: number;
  uploaded_at?: string;
}

export interface SemanticModel extends FileEntry {
  is_embedded: boolean;
  file_size?: number;
  uploaded_at?: string;
}

export interface WorkspaceDetailData extends WorkspaceRow {
  datasets: Array<Dataset>;
  semantic_models: Array<SemanticModel>;
  request_templates: Array<FileEntry>;
  datasets_count: number;
  datasets_size: number;
  models_count: number;
  models_size: number;
  request_templates_count: number;
  request_templates_size: number;
}

export interface ParsedTemplateAnfrage {
  fileId: string; // Changed to string for UUID
  filename: string;
  templateEntryId: string;
  anfrageText: string;
}

export interface DataModelMapping {
  id: string;
  workspace_id: string;
  rdf_dataset_id: string;
  semantic_model_id: string;
  rdf_dataset?: Dataset;
  semantic_model?: SemanticModel;
  created_at: string;
  created_by?: string;
}

export interface DataModelMappingCreate {
  rdf_dataset_id: string;
  semantic_model_id: string;
}

export interface DataModelMappingRead extends DataModelMapping {
  rdf_dataset: Dataset;
  semantic_model: SemanticModel;
}

export interface UnmappedFilesResponse {
  rdf_files: Dataset[];
  semantic_models: SemanticModel[];
}

// Data Unit types (Combined Dataset + Semantic Model)
export interface DataUnit {
  mapping_id: string;
  dataset: Dataset;
  semantic_model: SemanticModel;
  created_at: string;
}

export interface DataUnitsListResponse {
  data_units: DataUnit[];
  total_count: number;
  total_dataset_size: number;
  total_model_size: number;
}

export interface DataUnitUploadResponse {
  mapping_id: string;
  dataset: Dataset;
  semantic_model: SemanticModel;
  message: string;
  graphdb_task_id?: string;
  embedding_status?: string;
}

export interface EditItem {
  change: string;
  cost?: number;
}

export interface SparqlEditEvaluation {
  actual_edit_cost?: number;
  max_edit_cost?: number;
  edits?: EditItem[];
  cost_breakdown?: Array<{ label: string; cost: number }>;
  corrected_query?: string;
  error?: string;
  details?: string;
  skipped?: boolean;
  message?: string;
}

export interface ExecuteAndCompareResponseData {
  results_match?: boolean;
  message?: string; // The top-level message from API
  actual_results?: any; // Optional, if needed later
  expected_results?: any; // Optional, if needed later
  edit_evaluation?: SparqlEditEvaluation;
  apiError?: string; // For general API call errors during execute/compare
}

export interface BenchmarkRun {
  run_id: string;
  generated_sparql?: string;
  corrected_sparql?: string;
  score?: number;
  edits?: number;
  error?: string;
}

export interface BenchmarkTemplateResult {
  template_id: string;
  user_query: string;
  groundtruth_sparql: string;
  summary: {
    total_runs: number;
    successful_runs: number;
    failed_runs: number;
    average_score?: number; // can be null if all fail
    scores: number[];
  };
  runs: BenchmarkRun[];
}

// Tab-related interfaces for chat tab management
export interface ChatTab {
  id: string;
  title: string;
  isActive: boolean;
  hasSession: boolean;
  sessionId?: string;
  initialQuery?: string;
  chatHistory: ChatMessage[];
  modelInfoBlocks: SemanticModelEntry[];
  modelCheckHints: string[];
  createdAt: string;
}

export interface TabManagerState {
  tabs: ChatTab[];
  activeTabId: string | null;
  nextTabId: number;
}

export interface ChatSessionData {
  sessionId?: string;
  isFollowUpMode: boolean;
  chatHistory: ChatMessage[];
  modelInfoBlocks: SemanticModelEntry[];
  modelCheckHints: string[];
  chatInput: string;
  isChatLoading: boolean;
  isWaitingForClarification: boolean;
  clarificationContext: any;
  activeStreamIds: Set<string>;
  exportingQuery: string | null;
}

// Agent-related types
export type AgentIntent =
  | 'data_extraction'
  | 'follow_up_query'
  | 'corpus_info'
  | 'data_visualization'
  | 'data_calculation'
  | 'new_query';

export type AgentResponseType =
  | 'sparql_result'
  | 'corpus_info'
  | 'visualization'
  | 'calculation'
  | 'new_session';

export interface CorpusFileInfo {
  filename: string;
  full_filename: string;
  description: string;
  relevance_score: number;
  is_embedded: boolean;
}

export interface AgentMessage extends ChatMessage {
  response_type?: AgentResponseType;
  intent?: AgentIntent;
  visualization_code?: string;
  visualization_image_base64?: string;
  corpus_files?: CorpusFileInfo[];
  total_files?: number;
  // Calculation fields
  calculation_code?: string;
  calculation_summary?: CalculationSummary;
  calculation_table?: Array<Record<string, unknown>>;
  calculation_metadata?: CalculationMetadata;
  calculation_json?: string;
}

export interface VisualizationData {
  code: string;
  imageBase64: string;
}

export interface CorpusInfoData {
  files: CorpusFileInfo[];
  totalFiles: number;
  message: string;
}

// Calculation-related types
export interface CalculationSummary {
  [key: string]: number | string;
}

export interface CalculationMetadata {
  unit?: string;
  calculation_type?: string;
  description?: string;
}

export interface CalculationData {
  code: string;
  summary: CalculationSummary;
  table: Array<Record<string, unknown>>;
  metadata: CalculationMetadata;
  json: string;
}

// Solid Pod and External Catalog types
export interface SolidUserInfo {
  webId: string;
  isLoggedIn: boolean;
}


export interface ExternalCatalogStatusEvent {
  message: string;
  step?: string;
}

export interface ExternalCatalogResultsEvent {
  variables: string[];
  results: Record<string, unknown>[];
  total: number;
}

export interface ExternalCatalogCompleteEvent {
  summary: string;
  total_results: number;
}

// Comunica execution types for client-side SPARQL execution
export interface ComunicaDatasetUrl {
  url: string;
  title: string;
  identifier: string;
}

/** Payload of the event asking the browser to run a query with Comunica. */
export interface ComunicaExecutionData {
  sparqlQuery: string;
  datasetUrls: ComunicaDatasetUrl[];
  summary: string;
  instructions?: string;
}

export interface ComunicaExecutionResponse {
  summary: string;
  sparql_query: string;
  dataset_urls: ComunicaDatasetUrl[];
  execution_method: 'comunica';
  instructions?: string;
}

export interface ComunicaQueryResult {
  variables: string[];
  results: Record<string, { value: string; type?: string }>[];
  total: number;
  executionTime: number;
}

export interface ComunicaQueryOptions {
  sparqlQuery: string;
  datasetUrls: ComunicaDatasetUrl[];
  authenticatedFetch?: typeof fetch;
  onStatus?: (message: string) => void;
  onProgress?: (processed: number, total?: number) => void;
  onError?: (error: Error) => void;
}

export interface SolidAuthContextType {
  isLoggedIn: boolean;
  webId: string | undefined;
  isLoading: boolean;
  login: (issuer: string) => Promise<void>;
  logout: () => Promise<void>;
  fetch: typeof fetch;
}

// ==========================================
// ChatGPT-Style Reasoning Display Types
// ==========================================

export interface CurrentStepInfo {
  stepNumber: number;
  totalSteps: number;
  description: string;
  intent?: string;
}

export interface AgentResponseGroup {
  groupId: string;
  userQueryKey: string;
  startedAt: string;
  completedAt?: string;
  status: 'processing' | 'completed' | 'error' | 'awaiting_clarification';
  currentStep?: CurrentStepInfo;
  reasoningSteps: ReasoningStep[];
  finalResults: FinalResult[];
}

export interface ReasoningStep {
  id: string;
  stepNumber: number;
  intent: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  details?: string;
  sparqlQuery?: string;
}

export interface FinalResult {
  type: 'sparql_results' | 'visualization' | 'calculation' | 'corpus_info' | 'text_response';
  data: Record<string, unknown>;
  messageKey: string;
}

// German descriptions for step_ids shown in loading indicator
/** Step identifiers emitted by the backend; the labels live in i18n under `steps.*`. */
export const STEP_IDS = [
  'agent_plan_created',
  'agent_plan_generating',
  'calculation_running',
  'catalog_query',
  'identify_keywords_success',
  'model_validation_success',
  'plan_step_completed',
  'plan_step_start',
  'retrieval_success_for_keyword',
  'sparql_execution_completed',
  'sparql_execution_completed_empty',
  'sparql_query_generated',
  'validation_passed',
  'visualization_generating'
] as const;

// Response types that represent final results (shown in chat, not hidden in reasoning section)
// This is a whitelist approach - only messages with these response types are shown directly in chat
export const FINAL_RESULT_RESPONSE_TYPES: AgentResponseType[] = [
  'visualization',    // Plots
  'calculation',      // Rechnungsergebnisse
  'corpus_info',      // Corpus-Informationen
  'sparql_result',    // Extracted data, when set via response_type
];

// Check if a message is a final result (should be shown in chat, not hidden in reasoning)
// This uses a whitelist approach based on message properties
export const isFinalResultMessage = (msg: ChatMessage): boolean => {
  // User messages are always shown
  if (msg.is_user_message) return true;

  // Check response_type (for agent responses like visualization, calculation, corpus_info)
  const agentMsg = msg as AgentMessage;
  if (agentMsg.response_type && FINAL_RESULT_RESPONSE_TYPES.includes(agentMsg.response_type)) {
    return true;
  }

  // Check for SPARQL results (messages with actual data)
  if (msg.sparql_results !== undefined && msg.sparql_variables !== undefined) {
    return true;
  }

  // Check for visualization data
  if (agentMsg.visualization_image_base64) {
    return true;
  }

  // Check for calculation data
  if (agentMsg.calculation_summary || agentMsg.calculation_table) {
    return true;
  }

  // Check for corpus info data
  if (agentMsg.corpus_files) {
    return true;
  }

  return false;
};

// Check if a message should be hidden from direct chat display (shown only in reasoning)
// Inverse of isFinalResultMessage - everything that is NOT a final result is reasoning-only
export const isReasoningOnlyMessage = (msg: ChatMessage): boolean => {
  // User messages are never reasoning-only
  if (msg.is_user_message) return false;

  // Final results are not reasoning-only
  return !isFinalResultMessage(msg);
};

// Step IDs that produce final results (shown in chat, not hidden in reasoning section)
// Whitelist approach: Only these step_ids are shown directly in chat
const FINAL_RESULT_STEP_IDS = [
  'sparql_execution_completed',
  'sparql_execution_completed_empty',
  'visualization_result',
  'calculation_result',
  'corpus_info',
  'corpus_info_text',       // Text response for corpus info queries
  'plan_summary',           // Summary at the end of plan execution
  'visualization_created',  // Visualization creation message
  'calculation_completed',  // Calculation completion message
];

// Check by step_id if a message should be hidden from direct chat display
// Uses whitelist approach: Everything that is NOT a final result step_id is reasoning-only
export const isReasoningOnlyStepId = (stepId: string | undefined): boolean => {
  // No step_id means we can't determine - default to showing (backwards compatibility)
  if (!stepId) return false;

  // Final result step_ids should NOT be reasoning-only (they should be shown)
  if (FINAL_RESULT_STEP_IDS.includes(stepId)) return false;

  // Everything else from pipeline/system is reasoning-only
  return true;
};
