const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const PYTHON_PATH = process.env.PYTHON_PATH || 'C:\\Users\\Bhavyashree\\AppData\\Local\\Programs\\Python\\Python313\\python.exe';

const possiblePaths = [
  path.join(__dirname, '..', 'ai_engine', 'bridge_runner.py'),
  path.join(__dirname, '..', '..', 'ai_engine', 'bridge_runner.py')
];

const ENGINE_SCRIPT = possiblePaths.find(p => fs.existsSync(p)) || possiblePaths[0];
const ENGINE_DIR = path.dirname(ENGINE_SCRIPT);

function callTeamEngine(action, payload) {
  return new Promise((resolve, reject) => {
    const pyProcess = spawn(PYTHON_PATH, [ENGINE_SCRIPT, action], {
      windowsHide: true,
      env: {
        ...process.env,
        PYTHONPATH: ENGINE_DIR,
        QUALCOMM_API_KEY: process.env.QUALCOMM_API_KEY || '',
        QUALCOMM_BASE_URL: process.env.QUALCOMM_BASE_URL || '',
        QUALCOMM_MODEL: process.env.QUALCOMM_MODEL || ''
      }
    });

    let outputData = '';
    let errorData = '';

    pyProcess.stdin.write(JSON.stringify(payload));
    pyProcess.stdin.end();

    pyProcess.stdout.on('data', (data) => { outputData += data.toString(); });
    pyProcess.stderr.on('data', (data) => { errorData += data.toString(); });

    pyProcess.on('close', (code) => {
      const cleanOutput = outputData.trim();
      try {
        const result = JSON.parse(cleanOutput);
        if (code !== 0) {
          const error = new Error(result.error || `Python engine failed on action: ${action}`);
          error.statusCode = result.error_type === 'ValueError' || result.error_type === 'TypeError'
            ? 422
            : 500;
          error.action = action;
          return reject(error);
        }
        resolve(result);
      } catch (err) {
        if (err.statusCode) {
          return reject(err);
        }
        if (cleanOutput) {
          resolve({ output: cleanOutput, raw: true });
        } else {
          reject(new Error(`JSON parse error. Stderr: "${errorData}"`));
        }
      }
    });
  });
}

module.exports = { callTeamEngine };