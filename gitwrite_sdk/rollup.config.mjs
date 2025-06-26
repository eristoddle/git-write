import typescript from '@rollup/plugin-typescript';
import { dts } from 'rollup-plugin-dts';

export default [
  // This is the first object in the exported array in rollup.config.mjs
  {
    input: 'src/index.ts',
    output: [
      {
        file: 'dist/cjs/index.js',
        format: 'cjs',
        sourcemap: true,
      },
      {
        file: 'dist/esm/index.js',
        format: 'esm',
        sourcemap: true,
      },
    ],
    plugins: [typescript({ declaration: true, declarationDir: undefined })],
    external: ['axios'],
  },
  {
    input: 'src/index.ts',
    output: [{ file: 'dist/types/index.d.ts', format: 'es' }],
    plugins: [dts()],
  },
];