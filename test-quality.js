/**
 * RAG Quality Testing Script
 * Tests 8 query types and measures latency + response quality
 *
 * ARCHITECTURE:
 * - Uses a single CHAT_ID for the collection (documents uploaded here)
 * - Uses unique SESSION_IDs per query to prevent context/memory bleed
 * - Chat collection: chat_{CHAT_ID}
 * - Memory isolation: each query has fresh conversation history
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost';
const TEST_DOC_PATH = 'c:/Users/guyle/Desktop/Toon/original_rag/test-docs/system-design-primer.txt';

// Single chat ID for document collection
const CHAT_ID = `quality-test-${Date.now()}`;

// Generate unique session ID for memory isolation
function generateSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// 8 Query Types to Test
const TEST_QUERIES = [
  // 1. Simple Factual
  { type: 'simple_factual', query: 'What is the CAP theorem?', keywords: ['consistency', 'availability', 'partition'] },

  // 2. How-To
  { type: 'how_to', query: 'How does caching work?', keywords: ['cache', 'memory', 'store', 'ttl'] },

  // 3. Comparison
  { type: 'comparison', query: 'What is the difference between SQL and NoSQL?', keywords: ['sql', 'nosql', 'schema', 'acid'] },

  // 4. Conversational (follow-up style)
  { type: 'conversational', query: 'Tell me more about load balancing algorithms', keywords: ['round robin', 'least connections', 'algorithm'] },

  // 5. Short Query
  { type: 'short', query: 'What is CDN?', keywords: ['content', 'delivery', 'network', 'edge'] },

  // 6. Complex Multi-part
  { type: 'complex', query: 'Explain how distributed systems handle consistency and what trade-offs exist between CP and AP systems', keywords: ['consistency', 'partition', 'trade-off', 'distributed'] },

  // 7. Vague Query
  { type: 'vague', query: 'How does it scale?', keywords: [], expectGraceful: true },

  // 8. Out-of-Domain
  { type: 'out_of_domain', query: 'What is the weather forecast for tomorrow?', keywords: [], expectGraceful: true },
];

// Upload test document to a chat's collection via /chat/{chat_id}/documents
async function uploadTestDocument(port, chatId) {
  return new Promise((resolve, reject) => {
    // Read the file
    const fileContent = fs.readFileSync(TEST_DOC_PATH);
    const filename = path.basename(TEST_DOC_PATH);

    // Create multipart form data manually
    const boundary = '----FormBoundary' + Math.random().toString(36).substr(2);

    let body = '';
    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="files"; filename="${filename}"\r\n`;
    body += 'Content-Type: text/plain\r\n\r\n';

    const bodyEnd = `\r\n--${boundary}--\r\n`;

    const bodyBuffer = Buffer.concat([
      Buffer.from(body),
      fileContent,
      Buffer.from(bodyEnd)
    ]);

    const options = {
      hostname: 'localhost',
      port: port,
      path: `/chat/${chatId}/documents`,
      method: 'POST',
      headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        'Content-Length': bodyBuffer.length
      }
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          resolve(result);
        } catch (e) {
          resolve({ error: data, statusCode: res.statusCode });
        }
      });
    });

    req.on('error', reject);
    req.write(bodyBuffer);
    req.end();
  });
}

// Wait for ingestion job to complete
async function waitForIngestion(port, jobId, maxWaitMs = 60000) {
  const startTime = Date.now();

  while (Date.now() - startTime < maxWaitMs) {
    try {
      const status = await new Promise((resolve, reject) => {
        http.get(`http://localhost:${port}/ingest/status/${jobId}`, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => {
            try {
              resolve(JSON.parse(data));
            } catch (e) {
              resolve({ status: 'unknown' });
            }
          });
        }).on('error', reject);
      });

      if (status.status === 'completed') {
        return status;
      } else if (status.status === 'failed') {
        throw new Error('Ingestion failed: ' + JSON.stringify(status));
      }
    } catch (e) {
      // Ignore errors, keep waiting
    }

    await new Promise(r => setTimeout(r, 1000));
  }

  throw new Error('Ingestion timeout');
}

async function testQuery(port, query, chatId, sessionId, timeout = 120000) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    let responseText = '';
    let sources = [];

    // Include session_id in payload for memory isolation
    const postData = JSON.stringify({ message: query, session_id: sessionId });

    const options = {
      hostname: 'localhost',
      port: port,
      // Use chatId for collection, sessionId is in payload for memory
      path: `/chat/${chatId}/stream`,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = http.request(options, (res) => {
      res.setEncoding('utf8');

      res.on('data', (chunk) => {
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'token' && data.content) {
                responseText += data.content;
              } else if (data.type === 'sources') {
                sources = data.sources || [];
              }
            } catch (e) {}
          }
        }
      });

      res.on('end', () => {
        const latency = Date.now() - startTime;
        resolve({ responseText, sources, latency, error: null });
      });
    });

    req.on('error', (e) => {
      resolve({ responseText: '', sources: [], latency: Date.now() - startTime, error: e.message });
    });

    req.setTimeout(timeout, () => {
      req.destroy();
      resolve({ responseText, sources, latency: timeout, error: 'Timeout' });
    });

    req.write(postData);
    req.end();
  });
}

function calculateQuality(query, response, keywords, expectGraceful = false) {
  const responseLower = response.toLowerCase();

  if (keywords.length === 0) {
    // For vague/out-of-domain queries
    const gracefulIndicators = ['clarify', 'specific', 'context', 'rephrase', 'understand', 'help', 'information'];
    const hasGraceful = gracefulIndicators.some(ind => responseLower.includes(ind));

    if (expectGraceful) {
      // Good if it asks for clarification or admits it can't help
      return hasGraceful ? 85 : (response.length > 50 ? 60 : 30);
    }
    return response.length > 100 ? 70 : 50;
  }

  // Keyword coverage
  const found = keywords.filter(kw => responseLower.includes(kw.toLowerCase()));
  const coverage = (found.length / keywords.length) * 100;

  // Length bonus
  let bonus = 0;
  if (response.length > 300) bonus = 15;
  else if (response.length > 150) bonus = 10;
  else if (response.length > 50) bonus = 5;

  return Math.min(100, coverage + bonus);
}

async function runTests(port, label, chatId) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Testing: ${label} (port ${port})`);
  console.log(`Chat ID: ${chatId} (collection: chat_${chatId})`);
  console.log('='.repeat(60));

  const results = [];

  for (const test of TEST_QUERIES) {
    // Use unique session ID for EACH query to prevent memory bleed
    const sessionId = generateSessionId();

    console.log(`\n[${test.type}] "${test.query.slice(0, 50)}..."`);
    console.log(`  Session: ${sessionId}`);

    const { responseText, sources, latency, error } = await testQuery(port, test.query, chatId, sessionId);

    const quality = error ? 0 : calculateQuality(test.query, responseText, test.keywords, test.expectGraceful);
    const keywordsFound = test.keywords.filter(kw => responseText.toLowerCase().includes(kw.toLowerCase()));

    const result = {
      type: test.type,
      query: test.query,
      sessionId: sessionId,
      latencyMs: latency,
      responseLength: responseText.length,
      quality: quality,
      keywordsFound: keywordsFound,
      keywordsExpected: test.keywords,
      sourcesCount: sources.length,
      error: error,
      passed: quality >= 70 && latency < 120000 && !error
    };

    results.push(result);

    const status = result.passed ? '✓ PASS' : '✗ FAIL';
    console.log(`  ${status} | Latency: ${latency}ms | Quality: ${quality.toFixed(0)}% | Length: ${responseText.length}`);
    console.log(`  Keywords: ${keywordsFound.length}/${test.keywords.length} | Sources: ${sources.length}`);

    if (!result.passed && responseText) {
      console.log(`  Preview: "${responseText.slice(0, 100).replace(/\n/g, ' ')}..."`);
    }

    // Small delay between queries
    await new Promise(r => setTimeout(r, 500));
  }

  return results;
}

function generateReport(originalResults, agenticResults) {
  console.log('\n' + '='.repeat(60));
  console.log('COMPARISON REPORT');
  console.log('='.repeat(60));

  const originalPassed = originalResults.filter(r => r.passed).length;
  const agenticPassed = agenticResults ? agenticResults.filter(r => r.passed).length : 0;

  const originalAvgLatency = originalResults.reduce((s, r) => s + r.latencyMs, 0) / originalResults.length;
  const agenticAvgLatency = agenticResults ? agenticResults.reduce((s, r) => s + r.latencyMs, 0) / agenticResults.length : 0;

  const originalAvgQuality = originalResults.reduce((s, r) => s + r.quality, 0) / originalResults.length;
  const agenticAvgQuality = agenticResults ? agenticResults.reduce((s, r) => s + r.quality, 0) / agenticResults.length : 0;

  console.log('\nSummary:');
  console.log(`  original_rag: ${originalPassed}/${originalResults.length} passed | ${originalAvgLatency.toFixed(0)}ms avg | ${originalAvgQuality.toFixed(0)}% quality`);

  if (agenticResults) {
    console.log(`  agentic-rag:  ${agenticPassed}/${agenticResults.length} passed | ${agenticAvgLatency.toFixed(0)}ms avg | ${agenticAvgQuality.toFixed(0)}% quality`);

    const latencyDiff = ((agenticAvgLatency - originalAvgLatency) / originalAvgLatency * 100).toFixed(1);
    const qualityDiff = (agenticAvgQuality - originalAvgQuality).toFixed(1);

    console.log(`\n  Latency change: ${latencyDiff}% ${parseFloat(latencyDiff) < 0 ? '(faster)' : '(slower)'}`);
    console.log(`  Quality change: ${qualityDiff}% ${parseFloat(qualityDiff) > 0 ? '(better)' : '(worse)'}`);
  }

  console.log('\nBy Query Type:');
  for (let i = 0; i < TEST_QUERIES.length; i++) {
    const orig = originalResults[i];
    const agen = agenticResults ? agenticResults[i] : null;

    console.log(`  ${orig.type}:`);
    console.log(`    original: ${orig.quality.toFixed(0)}% quality, ${orig.latencyMs}ms`);
    if (agen) {
      console.log(`    agentic:  ${agen.quality.toFixed(0)}% quality, ${agen.latencyMs}ms`);
    }
  }

  return {
    original: {
      passed: originalPassed,
      total: originalResults.length,
      avgLatency: Math.round(originalAvgLatency),
      avgQuality: Math.round(originalAvgQuality),
      results: originalResults
    },
    agentic: agenticResults ? {
      passed: agenticPassed,
      total: agenticResults.length,
      avgLatency: Math.round(agenticAvgLatency),
      avgQuality: Math.round(agenticAvgQuality),
      results: agenticResults
    } : null
  };
}

async function main() {
  const args = process.argv.slice(2);
  const port = parseInt(args[0]) || 8001;
  const label = args[1] || 'original_rag';

  console.log('RAG Quality Testing Suite');
  console.log(`Testing port ${port} as "${label}"`);
  console.log(`Queries: ${TEST_QUERIES.length}`);
  console.log(`Started: ${new Date().toISOString()}`);
  console.log(`Chat ID: ${CHAT_ID} (collection: chat_${CHAT_ID})`);

  // Step 1: Upload test document to the chat's collection
  console.log('\n--- Uploading test document ---');
  try {
    const uploadResult = await uploadTestDocument(port, CHAT_ID);
    console.log('Upload result:', JSON.stringify(uploadResult, null, 2));

    // Check for successful upload
    if (uploadResult.uploaded && uploadResult.uploaded.length > 0) {
      console.log(`Successfully uploaded ${uploadResult.uploaded.length} document(s)`);
    } else if (uploadResult.error) {
      console.error('Upload error:', uploadResult.error);
    }
  } catch (e) {
    console.error('Upload failed:', e.message);
    console.log('Continuing with tests anyway...');
  }

  // Give the system a moment to index
  console.log('Waiting for indexing...');
  await new Promise(r => setTimeout(r, 3000));

  // Step 2: Warm-up query to load models (Ollama + LLMLingua)
  // This eliminates the 60-120s first-query spike from benchmark stats
  console.log('\n--- Warming up models (Ollama + LLMLingua) ---');
  const warmupStart = Date.now();
  await testQuery(port, 'Hello, this is a warm-up query.', CHAT_ID, 'warmup-session');
  console.log(`Warm-up complete in ${Date.now() - warmupStart}ms`);

  // Step 3: Run tests - all queries use same CHAT_ID (same collection)
  // but unique session IDs (isolated memory)
  console.log('\n--- Running quality tests ---');
  const results = await runTests(port, label, CHAT_ID);

  // Generate single-system report
  const report = generateReport(results, null);

  // Save results
  const outputFile = `c:\\Users\\guyle\\Desktop\\Toon\\test-results-${label}.json`;
  fs.writeFileSync(outputFile, JSON.stringify(report, null, 2));
  console.log(`\nResults saved to: ${outputFile}`);
}

main().catch(console.error);
