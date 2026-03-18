process.chdir('/Users/forestdragon/kakao_golf/.dashboard_libs');

const babel = require('@babel/core');
const fs = require('fs');
const jsx = fs.readFileSync(process.argv[2], 'utf8');

// import/export 처리 (Python 전처리 후 전달)
const result = babel.transformSync(jsx, {
  presets: [['@babel/preset-react', { runtime: 'classic' }]],
  filename: 'dashboard.jsx',
});
process.stdout.write(result.code);
