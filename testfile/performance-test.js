import http from 'k6/http';
import { check, sleep } from 'k6';
import { htmlReport } from 'https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

// Advanced load testing configuration
const MAX_CONCURRENT_REQUESTS = 10;  // Maximum number of concurrent requests
const MAX_USERS = 40;               // Maximum number of virtual users
const SLEEP_DURATION = 0;           // No wait time between requests
const QUEUE_SIZE = 5;               // Allow multiple requests in parallel
const API_URL = 'http://localhost:8000'; // API address for Docker Desktop
const REQUEST_TIMEOUT = '300s';  // Extended timeout (5 minutes) for large files

export const options = {
  // Advanced performance test scenarios
  scenarios: {
    // Test 1: Gradual load increase
    ramp_up_test: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 5 },     // Warm-up
        { duration: '30s', target: 10 },    // Gradual increase
        { duration: '1m', target: 20 },     // Moderate load
        { duration: '30s', target: 0 }      // Completion
      ],
      gracefulRampDown: '30s',
    },
    // Test 2: Constant heavy load
    constant_load_test: {
      executor: 'constant-vus',
      vus: 15,                             // Constant number of users
      duration: '2m',
      startTime: '3m',                     // Start after the first test completes
    },
    // Test 3: Stress test with peak load
    stress_test: {
      executor: 'ramping-arrival-rate',    // Control request rate instead of VUs
      startRate: 5,                        // Start with 5 requests per second
      timeUnit: '1s',
      preAllocatedVUs: 20,                 // Pre-allocate VUs for faster ramp-up
      maxVUs: 30,
      stages: [
        { duration: '30s', target: 10 },    // Ramp up to 10 RPS
        { duration: '1m', target: 20 },     // Ramp up to 20 RPS
        { duration: '30s', target: 30 },    // Peak at 30 RPS
        { duration: '1m', target: 0 }       // Ramp down
      ],
      startTime: '6m',                     // Start after the second test completes
    },
    // Test 4: Extreme test with large documents
    extreme_test: {
      executor: 'per-vu-iterations',
      vus: MAX_USERS,                      // Maximum number of users
      iterations: 2,                       // Each VU makes 2 requests with extreme data
      maxDuration: '5m',
      startTime: '10m',                    // Start after the third test completes
      tags: { testType: 'extreme' },
    }
  },
  thresholds: {
    // Response time thresholds
    'http_req_duration': ['p(95)<60000'],                                // 95% of all requests should be below 1 minute
    'http_req_duration{dataSize:small}': ['p(95)<5000'],                // Small requests: 95% under 5s
    'http_req_duration{dataSize:medium}': ['p(95)<15000'],              // Medium requests: 95% under 15s
    'http_req_duration{dataSize:large}': ['p(95)<60000'],               // Large requests: 95% under 1 minute
    'http_req_duration{dataSize:extreme}': ['p(95)<180000'],            // Extreme requests: 95% under 3 minutes
    
    // Error rate thresholds
    'http_req_failed': ['rate<0.1'],                                     // Overall: Less than 10% failure
    'http_req_failed{testType:ramp_up_test}': ['rate<0.05'],             // Ramp-up test: Less than 5% failure
    'http_req_failed{testType:constant_load_test}': ['rate<0.1'],        // Constant load: Less than 10% failure
    'http_req_failed{testType:stress_test}': ['rate<0.2'],               // Stress test: Less than 20% failure
    'http_req_failed{testType:extreme}': ['rate<0.3'],                   // Extreme test: Less than 30% failure
    
    // Throughput thresholds
    'http_reqs': ['rate>1'],                                             // At least 1 request per second on average
  },
};

// Test data - different document sizes
const testData = {
  small: {
    text: "Patient John Smith, born on 01.01.1980, residing at 123 Main St, Berlin, diagnosed with hypertension.",
    repeat: 1
  },
  medium: {
    text: "Medical record: Patient John Smith, born on 01.01.1980, residing at 123 Main St, Berlin. " +
          "Contact: +49 123 456789, email: john.smith@example.com. " +
          "Insurance: AOK, policy number 987654321. " +
          "Diagnosis: Hypertension, Diabetes type 2. " +
          "Current medication: Metformin 500mg, Ramipril 5mg. " +
          "Allergies: Penicillin, pollen. " +
          "Last visit: 15.03.2025, Dr. Maria Mueller, St. Anna Hospital.",
    repeat: 10
  },
  large: {
    text: "MEDICAL RECORD\n\n" +
          "PATIENT INFORMATION:\n" +
          "Name: John Smith\n" +
          "Date of Birth: 01.01.1980\n" +
          "Address: 123 Main St, 10115 Berlin\n" +
          "Phone: +49 123 456789\n" +
          "Email: john.smith@example.com\n" +
          "Insurance: AOK\n" +
          "Policy Number: 987654321\n" +
          "Emergency Contact: Jane Smith (Wife), +49 123 987654\n\n" +
          "MEDICAL HISTORY:\n" +
          "Hypertension (diagnosed 2018)\n" +
          "Diabetes Type 2 (diagnosed 2019)\n" +
          "Appendectomy (2010, Dr. Schmidt, Charité Hospital)\n" +
          "Fractured right tibia (2015, Dr. Weber, St. Joseph Hospital)\n\n" +
          "CURRENT MEDICATIONS:\n" +
          "Metformin 500mg, twice daily\n" +
          "Ramipril 5mg, once daily\n" +
          "Aspirin 100mg, once daily\n" +
          "Simvastatin 20mg, once daily at bedtime\n\n" +
          "ALLERGIES:\n" +
          "Penicillin (severe rash)\n" +
          "Pollen (seasonal rhinitis)\n\n" +
          "RECENT VISITS:\n" +
          "15.03.2025 - Dr. Maria Mueller, St. Anna Hospital\n" +
          "Assessment: Blood pressure 140/90, Blood glucose 130 mg/dL\n" +
          "Treatment: Adjusted Metformin dosage, recommended dietary changes\n" +
          "Next appointment: 15.06.2025\n\n" +
          "10.01.2025 - Dr. Thomas Fischer, Diabetes Clinic\n" +
          "Assessment: HbA1c 7.2%, Cholesterol 210 mg/dL\n" +
          "Treatment: Added Simvastatin, recommended increased physical activity\n" +
          "Next appointment: 10.07.2025\n\n" +
          "FAMILY HISTORY:\n" +
          "Father: Hypertension, Myocardial infarction at age 65\n" +
          "Mother: Type 2 Diabetes, Breast cancer at age 70\n" +
          "Sister: Asthma\n\n" +
          "SOCIAL HISTORY:\n" +
          "Occupation: Software Engineer at TechGmbH\n" +
          "Marital Status: Married\n" +
          "Children: Two (ages 10 and 8)\n" +
          "Alcohol: Occasional (2-3 drinks per week)\n" +
          "Smoking: Former smoker, quit in 2015\n" +
          "Exercise: Walking 30 minutes, 3 times per week\n\n" +
          "VACCINATION HISTORY:\n" +
          "COVID-19: Pfizer (15.02.2021, 15.05.2021, 15.11.2021)\n" +
          "Influenza: Yearly, last on 01.10.2024\n" +
          "Tetanus: 05.06.2020\n\n" +
          "LABORATORY RESULTS (05.03.2025):\n" +
          "HbA1c: 7.2%\n" +
          "Fasting Glucose: 130 mg/dL\n" +
          "Total Cholesterol: 210 mg/dL\n" +
          "LDL: 130 mg/dL\n" +
          "HDL: 45 mg/dL\n" +
          "Triglycerides: 180 mg/dL\n" +
          "Creatinine: 0.9 mg/dL\n" +
          "eGFR: 85 mL/min/1.73m²\n" +
          "Potassium: 4.2 mmol/L\n" +
          "Sodium: 138 mmol/L\n\n" +
          "TREATMENT PLAN:\n" +
          "Continue current medications\n" +
          "Low-carbohydrate diet\n" +
          "Increase physical activity to 150 minutes per week\n" +
          "Monitor blood glucose daily\n" +
          "Monitor blood pressure twice weekly\n" +
          "Follow-up appointment in 3 months\n\n" +
          "REFERRALS:\n" +
          "Ophthalmology: Dr. Anna Schmidt, for diabetic retinopathy screening\n" +
          "Podiatry: Dr. Michael Bauer, for diabetic foot examination\n\n" +
          "NOTES:\n" +
          "Patient reports occasional dizziness when standing up quickly\n" +
          "Patient is compliant with medication regimen\n" +
          "Patient has shown improvement in dietary habits\n" +
          "Discussed importance of regular foot care and eye examinations\n\n" +
          "SIGNED:\n" +
          "Dr. Maria Mueller\n" +
          "Internal Medicine\n" +
          "St. Anna Hospital\n" +
          "License #: 12345678\n" +
          "Date: 15.03.2025",
    repeat: 5
  },
  extreme: {
    text: "INSURANCE CONTRACT\n\n" +
          "POLICY NUMBER: LV-KV-2025-123456789\n\n" +
          "BETWEEN:\n" +
          "GesundPlus Insurance AG\n" +
          "Versicherungsstraße 1\n" +
          "10117 Berlin\n" +
          "Registration Number: HRB 123456 B\n" +
          "Tax ID: DE123456789\n" +
          "Represented by: Dr. Hans Müller, CEO\n\n" +
          "AND\n\n" +
          "Mr. John Smith\n" +
          "Date of Birth: 01.01.1980\n" +
          "Address: Hauptstraße 123, 10115 Berlin\n" +
          "Email: john.smith@example.com\n" +
          "Phone: +49 30 12345678\n" +
          "ID Number: L01X34567\n" +
          "Tax ID: 12/345/67890\n\n" +
          "INSURANCE DETAILS:\n\n" +
          "Type of Insurance: Comprehensive Health Insurance\n" +
          "Coverage Period: 01.01.2025 - 31.12.2025\n" +
          "Monthly Premium: €450.00\n" +
          "Payment Method: Direct Debit\n" +
          "Bank Details: Deutsche Bank, IBAN: DE89 3704 0044 0532 0130 00, BIC: DEUTDEBBXXX\n\n" +
          "COVERAGE INCLUDES:\n\n" +
          "1. Outpatient Treatment\n" +
          "   - General practitioner consultations: 100% coverage\n" +
          "   - Specialist consultations: 100% coverage\n" +
          "   - Prescribed medications: 90% coverage (minimum €5, maximum €50 per prescription)\n" +
          "   - Therapeutic appliances: 80% coverage up to €2,000 per calendar year\n" +
          "   - Alternative medicine treatments by licensed practitioners: 70% coverage up to €1,000 per calendar year\n\n" +
          "2. Inpatient Treatment\n" +
          "   - Hospital accommodation: 100% coverage for two-bed room\n" +
          "   - Medical treatment: 100% coverage\n" +
          "   - Surgeries: 100% coverage\n" +
          "   - Intensive care: 100% coverage\n" +
          "   - Accompanying parent for children under 12: 100% coverage\n\n" +
          "3. Dental Treatment\n" +
          "   - Preventive measures: 100% coverage\n" +
          "   - Basic dental services: 80% coverage\n" +
          "   - Dental prostheses: 60% coverage up to €3,000 per calendar year\n" +
          "   - Orthodontic treatment for children under 18: 80% coverage up to €5,000 total\n\n" +
          "4. Preventive Care\n" +
          "   - Annual health check-ups: 100% coverage\n" +
          "   - Vaccinations: 100% coverage for recommended vaccinations\n" +
          "   - Cancer screenings: 100% coverage according to statutory programs\n" +
          "   - Fitness club membership subsidy: €150 per calendar year\n\n" +
          "5. Additional Benefits\n" +
          "   - Vision aids: 80% coverage up to €300 every two calendar years\n" +
          "   - Hearing aids: 80% coverage up to €1,500 every three calendar years\n" +
          "   - Medical transport: 100% coverage for emergency transport\n" +
          "   - Rehabilitation: 100% coverage up to 28 days per calendar year\n" +
          "   - Psychological therapy: 90% coverage up to 30 sessions per calendar year\n\n" +
          "6. International Coverage\n" +
          "   - EU countries: 100% coverage as per domestic benefits\n" +
          "   - Non-EU countries: 100% coverage up to 6 weeks per trip, maximum €100,000\n" +
          "   - Medical repatriation: 100% coverage when medically necessary\n\n" +
          "EXCLUSIONS:\n\n" +
          "1. Pre-existing conditions not disclosed in the health questionnaire\n" +
          "2. Cosmetic treatments unless medically necessary\n" +
          "3. Experimental treatments not recognized by conventional medicine\n" +
          "4. Self-inflicted injuries\n" +
          "5. Consequences of substance abuse\n" +
          "6. War, civil unrest, and acts of terrorism\n" +
          "7. Hazardous sports activities (as defined in Appendix A)\n\n" +
          "WAITING PERIODS:\n\n" +
          "1. General waiting period: 3 months\n" +
          "2. Dental prostheses: 8 months\n" +
          "3. Maternity and childbirth: 8 months\n" +
          "4. Psychotherapy: 8 months\n\n" +
          "DEDUCTIBLE:\n\n" +
          "Annual deductible: €500 per calendar year\n" +
          "The deductible does not apply to preventive care and check-ups.\n\n" +
          "PREMIUM ADJUSTMENT:\n\n" +
          "The insurer reserves the right to adjust premiums based on:\n" +
          "1. Changes in healthcare costs\n" +
          "2. Changes in utilization patterns\n" +
          "3. Changes in life expectancy\n" +
          "Premium adjustments will be communicated at least 30 days before implementation.\n\n" +
          "TERMINATION:\n\n" +
          "1. By the policyholder: With 3 months' notice to the end of the insurance year\n" +
          "2. By the insurer: Only in cases of fraud, non-payment, or as permitted by law\n\n" +
          "DATA PROTECTION:\n\n" +
          "Personal and health data will be processed in accordance with the EU General Data Protection Regulation (GDPR) and the German Federal Data Protection Act (BDSG). Details are provided in the separate Privacy Policy document.\n\n" +
          "APPLICABLE LAW:\n\n" +
          "This contract is governed by the laws of the Federal Republic of Germany.\n\n" +
          "DISPUTE RESOLUTION:\n\n" +
          "In case of disputes, the parties agree to attempt mediation before pursuing legal action. The competent court is in Berlin, Germany.\n\n" +
          "SIGNATURES:\n\n" +
          "For GesundPlus Insurance AG:\n\n" +
          "____________________________\n" +
          "Dr. Hans Müller, CEO\n" +
          "Date: 15.12.2024\n\n" +
          "Policyholder:\n\n" +
          "____________________________\n" +
          "John Smith\n" +
          "Date: 15.12.2024\n\n" +
          "CONTACT INFORMATION:\n\n" +
          "Customer Service: +49 30 987654321\n" +
          "Email: service@gesundplus.de\n" +
          "Website: www.gesundplus.de\n" +
          "Emergency Assistance (24/7): +49 30 123456789",
    repeat: 10
  }
};

// Repeat text to create larger documents
for (const size in testData) {
  const original = testData[size].text;
  for (let i = 1; i < testData[size].repeat; i++) {
    testData[size].text += "\n\n" + original;
  }
}

// Advanced request queue with dynamic concurrency control
const requestQueue = {
  active: 0,
  maxConcurrent: QUEUE_SIZE,
  totalRequests: 0,
  completedRequests: 0,
  failedRequests: 0,
  activeRequests: new Set(),
  startTime: new Date(),
  
  // Get current queue stats
  get stats() {
    const now = new Date();
    const runTime = (now - this.startTime) / 1000;
    return {
      active: this.active,
      waiting: this.totalRequests - this.completedRequests - this.active,
      completed: this.completedRequests,
      failed: this.failedRequests,
      total: this.totalRequests,
      throughput: runTime > 0 ? this.completedRequests / runTime : 0,
      runTime: runTime.toFixed(1)
    };
  },
  
  // Log current queue status
  logStatus() {
    const stats = this.stats;
    console.log(`Queue status: ${stats.active} active, ${stats.waiting} waiting, ${stats.completed} completed, ${stats.failed} failed, ${stats.throughput.toFixed(2)} req/s (${stats.runTime}s)`); 
  },
  
  // Add request to queue with dynamic concurrency
  async add(fn) {
    const requestId = ++this.totalRequests;
    const requestStart = new Date();
    
    // Get current scenario and adjust concurrency
    let currentConcurrency = this.maxConcurrent;
    try {
      if (typeof exec !== 'undefined' && exec.scenario && exec.scenario.name) {
        // Adjust concurrency based on scenario
        if (exec.scenario.name === 'extreme_test') {
          currentConcurrency = 1; // Only one extreme request at a time
        } else if (exec.scenario.name === 'stress_test') {
          currentConcurrency = MAX_CONCURRENT_REQUESTS; // Maximum concurrency for stress test
        }
      }
    } catch (e) {
      // Fallback to default concurrency
    }
    
    console.log(`Request #${requestId} waiting (${this.active}/${currentConcurrency} active)...`);
    
    // Wait until we can process this request
    while (this.active >= currentConcurrency) {
      await new Promise(resolve => setTimeout(resolve, 100));
      // Periodically log queue status
      if (requestId % 10 === 0) {
        this.logStatus();
      }
    }
    
    // Now we can process this request
    this.active++;
    this.activeRequests.add(requestId);
    const waitTime = (new Date() - requestStart) / 1000;
    console.log(`Request #${requestId} starting after ${waitTime.toFixed(2)}s wait (${this.active}/${currentConcurrency} active)`);
    
    try {
      return await fn();
    } catch (e) {
      this.failedRequests++;
      throw e;
    } finally {
      this.completedRequests++;
      this.active--;
      this.activeRequests.delete(requestId);
      const processingTime = (new Date() - requestStart) / 1000;
      console.log(`Request #${requestId} completed in ${processingTime.toFixed(2)}s total`);
      
      // Log status after every 5th request or when queue is empty
      if (requestId % 5 === 0 || this.active === 0) {
        this.logStatus();
      }
    }
  }
};

// Anonymize text via API with advanced metrics and error handling
async function anonymizeText(text, size = 'small', tags = {}) {
  const url = `${API_URL}/anonymize`;
  const payload = JSON.stringify({ text });
  
  // Set timeout based on data size
  let timeout = REQUEST_TIMEOUT;
  if (size === 'large' || size === 'extreme') {
    timeout = '600s'; // 10 minutes for large files
  }
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: timeout,
    tags: { 
      dataSize: size,
      testType: tags.testType || __ENV.testType || 'normal',
      vuId: tags.vuId || __VU.toString(),
      textLength: text.length.toString()
    }
  };
  
  const startTime = new Date();
  let success = false;
  let response;
  let error;
  
  try {
    // Use strict queue to ensure only one request at a time
    response = await requestQueue.add(() => {
      console.log(`Processing ${size} text (${text.length} chars)...`);
      return http.post(url, payload, params);
    });
    
    success = true;
  } catch (e) {
    error = e;
    console.error(`Error processing request: ${e.message}`);
  }
  
  const processingTime = (new Date() - startTime) / 1000;
  
  if (success) {
    // Check response
    const checkResult = check(response, {
      'Status is 200': (r) => r.status === 200,
      'Has session_id': (r) => r.json('session_id') !== undefined,
      'Has anonymized_text': (r) => r.json('anonymized_text') !== undefined,
    });
    
    if (checkResult) {
      console.log(`✅ Successfully anonymized ${size} text (${text.length} chars) in ${processingTime.toFixed(2)}s`);
      
      // No waiting - next request will start immediately
      return {
        session_id: response.json('session_id'),
        anonymized_text: response.json('anonymized_text'),
        processingTime
      };
    } else {
      console.log(`⚠️ Response validation failed for ${size} text after ${processingTime.toFixed(2)}s`);
      return { error: 'Response validation failed' };
    }
  } else {
    console.log(`❌ Failed to anonymize ${size} text after ${processingTime.toFixed(2)}s: ${error?.message || 'Unknown error'}`);
    return { error: error?.message || 'Unknown error' };
  }
}

// Function to get random data size with weighted distribution
function getRandomDataSize(scenario) {
  // Define weights for each data size based on scenario
  let weights = {
    small: 0.25,
    medium: 0.25,
    large: 0.25,
    extreme: 0.25
  };
  
  // Adjust weights based on scenario
  if (scenario === 'extreme_test') {
    weights = { small: 0.1, medium: 0.1, large: 0.3, extreme: 0.5 };
  } else if (scenario === 'stress_test') {
    weights = { small: 0.5, medium: 0.3, large: 0.15, extreme: 0.05 };
  } else if (scenario === 'constant_load_test') {
    weights = { small: 0.2, medium: 0.4, large: 0.3, extreme: 0.1 };
  } else if (scenario === 'ramp_up_test') {
    weights = { small: 0.3, medium: 0.3, large: 0.3, extreme: 0.1 };
  }
  
  // Generate random number between 0 and 1
  const random = Math.random();
  
  // Determine data size based on weights
  let cumulativeWeight = 0;
  for (const [size, weight] of Object.entries(weights)) {
    cumulativeWeight += weight;
    if (random <= cumulativeWeight) {
      return size;
    }
  }
  
  // Fallback to small if something goes wrong
  return 'small';
}

// Default function executed for each virtual user
export default function() {
  // Determine which test is running based on scenario
  let testType = 'normal';
  
  try {
    if (typeof exec !== 'undefined' && exec.scenario && exec.scenario.name) {
      testType = exec.scenario.name;
    }
  } catch (e) {
    // Fallback if scenario info not available
    console.log(`Error getting scenario info: ${e.message}`);
  }
  
  // Get random data size with weighted distribution based on scenario
  let dataSize = getRandomDataSize(testType);
  
  // Add some randomness based on VU and iteration to ensure variety
  // This ensures we don't get the same size for all requests in a batch
  const randomFactor = (__VU * __ITER) % 10;
  if (randomFactor === 0) {
    // Force extreme occasionally for all scenarios
    dataSize = 'extreme';
  } else if (randomFactor === 1) {
    // Force small occasionally for all scenarios
    dataSize = 'small';
  }
  
  // Add tags for metrics grouping
  const tags = {
    dataSize: dataSize,
    testType: testType,
    vuId: __VU.toString()
  };
  
  console.log(`VU ${__VU} starting request with ${dataSize} data in ${testType} scenario`);
  
  // Anonymize text with advanced metrics
  anonymizeText(testData[dataSize].text, dataSize, tags);
}

// Handle test completion
export function handleSummary(data) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '');
  const prefix = 'performance-test';
  
  return {
    [`${prefix}-${timestamp}.json`]: JSON.stringify(data),
    [`${prefix}-${timestamp}.html`]: htmlReport(data),
    [`${prefix}-${timestamp}.txt`]: textSummary(data, { indent: ' ', enableColors: false }),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
