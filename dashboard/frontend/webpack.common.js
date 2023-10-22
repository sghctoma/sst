const path = require('path');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = {
  entry: './src/index.js',
  optimization: {
    minimizer: [new TerserPlugin({
      extractComments: false,
    })],
  },
  output: {
    filename: 'main.js',
    path: path.resolve(__dirname, '../app/static'),
  },
}
