import { useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { QueryEngine } from '@comunica/query-sparql';
import { useSolidAuth } from '../contexts/SolidAuthContext';
import type {
  ComunicaDatasetUrl,
  ComunicaQueryResult,
} from '../types';

interface UseComunicaQueryReturn {
  executeQuery: (
    sparqlQuery: string,
    datasetUrls: ComunicaDatasetUrl[],
    onStatus?: (message: string) => void
  ) => Promise<ComunicaQueryResult>;
  cancelQuery: () => void;
  isLoggedIn: boolean;
}

// Singleton query engine instance to avoid re-initialization overhead
let queryEngineInstance: QueryEngine | null = null;

function getQueryEngine(): QueryEngine {
  if (!queryEngineInstance) {
    queryEngineInstance = new QueryEngine();
  }
  return queryEngineInstance;
}

export function useComunicaQuery(): UseComunicaQueryReturn {
  const { t } = useTranslation();
  const { isLoggedIn, fetch: authenticatedFetch } = useSolidAuth();
  const abortControllerRef = useRef<AbortController | null>(null);
  const isQueryingRef = useRef(false);

  const executeQuery = useCallback(
    async (
      sparqlQuery: string,
      datasetUrls: ComunicaDatasetUrl[],
      onStatus?: (message: string) => void
    ): Promise<ComunicaQueryResult> => {
      // Cancel any existing query
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();
      isQueryingRef.current = true;

      const startTime = performance.now();

      try {
        const engine = getQueryEngine();

        // Prepare sources from dataset URLs
        const sources = datasetUrls.map((dataset) => dataset.url);

        onStatus?.(t('errors.comunicaInit'));
        onStatus?.(t('errors.comunicaSources', {
          count: sources.length,
          titles: datasetUrls.map(d => d.title).join(', '),
        }));

        // Determine query type (SELECT, CONSTRUCT, ASK, DESCRIBE)
        const queryType = detectQueryType(sparqlQuery);
        onStatus?.(t('errors.comunicaRunning', { type: queryType }));

        let results: Record<string, { value: string; type?: string }>[] = [];
        let variables: string[] = [];

        if (queryType === 'SELECT') {
          // Execute SELECT query
          const bindingsStream = await engine.queryBindings(sparqlQuery, {
            sources,
            // Use authenticated fetch for Solid Pod access
            fetch: authenticatedFetch,
          });

          // Get variable names from the query
          const bindingArray: any[] = [];

          // Collect all bindings
          for await (const binding of bindingsStream) {
            if (!isQueryingRef.current) {
              throw new Error('Query cancelled');
            }

            const row: Record<string, { value: string; type?: string }> = {};

            // Extract variable names on first iteration
            if (variables.length === 0) {
              for (const key of binding.keys()) {
                variables.push(key.value);
              }
            }

            // Extract values for each variable
            for (const varName of variables) {
              const term = binding.get(varName);
              if (term) {
                row[varName] = {
                  value: term.value,
                  type: term.termType,
                };
              }
            }

            bindingArray.push(row);

            // Progress update every 100 results
            if (bindingArray.length % 100 === 0) {
              onStatus?.(t('errors.comunicaProgress', { count: bindingArray.length }));
            }
          }

          results = bindingArray;
        } else if (queryType === 'ASK') {
          // Execute ASK query
          const askResult = await engine.queryBoolean(sparqlQuery, {
            sources,
            fetch: authenticatedFetch,
          });

          variables = ['result'];
          results = [{ result: { value: askResult.toString(), type: 'Literal' } }];
        } else if (queryType === 'CONSTRUCT' || queryType === 'DESCRIBE') {
          // Execute CONSTRUCT/DESCRIBE query - returns quads
          const quadsStream = await engine.queryQuads(sparqlQuery, {
            sources,
            fetch: authenticatedFetch,
          });

          variables = ['subject', 'predicate', 'object'];
          const quadResults: Record<string, { value: string; type?: string }>[] = [];

          for await (const quad of quadsStream) {
            if (!isQueryingRef.current) {
              throw new Error('Query cancelled');
            }

            quadResults.push({
              subject: { value: quad.subject.value, type: quad.subject.termType },
              predicate: { value: quad.predicate.value, type: quad.predicate.termType },
              object: { value: quad.object.value, type: quad.object.termType },
            });
          }

          results = quadResults;
        }

        const endTime = performance.now();
        const executionTime = endTime - startTime;

        onStatus?.(t('errors.comunicaDone', {
          count: results.length,
          seconds: (executionTime / 1000).toFixed(2),
        }));

        return {
          variables,
          results,
          total: results.length,
          executionTime,
        };
      } catch (error) {
        if (error instanceof Error && error.message === 'Query cancelled') {
          throw error;
        }

        const errorMessage = error instanceof Error ? error.message : String(error);
        onStatus?.(t('errors.comunicaFailedWith', { message: errorMessage }));
        throw new Error(t('errors.comunicaWrapped', { message: errorMessage }));
      } finally {
        isQueryingRef.current = false;
        abortControllerRef.current = null;
      }
    },
    [authenticatedFetch, t]
  );

  const cancelQuery = useCallback(() => {
    isQueryingRef.current = false;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  return {
    executeQuery,
    cancelQuery,
    isLoggedIn,
  };
}

/**
 * Detect the type of SPARQL query
 */
function detectQueryType(query: string): 'SELECT' | 'ASK' | 'CONSTRUCT' | 'DESCRIBE' {
  const normalizedQuery = query.trim().toUpperCase();

  // Remove prefixes and comments to find the actual query type
  const lines = normalizedQuery.split('\n');
  for (const line of lines) {
    const trimmedLine = line.trim();
    if (trimmedLine.startsWith('PREFIX') || trimmedLine.startsWith('#') || trimmedLine === '') {
      continue;
    }

    if (trimmedLine.startsWith('SELECT')) return 'SELECT';
    if (trimmedLine.startsWith('ASK')) return 'ASK';
    if (trimmedLine.startsWith('CONSTRUCT')) return 'CONSTRUCT';
    if (trimmedLine.startsWith('DESCRIBE')) return 'DESCRIBE';
  }

  // Default to SELECT if we can't determine
  return 'SELECT';
}
