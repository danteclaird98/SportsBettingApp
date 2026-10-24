import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {resolve} from 'node:path';
export default defineConfig({plugins:[react()],base:'/advanced/',resolve:{alias:{'@appdeploy/client':resolve('compat/client.ts')}},build:{outDir:'dist'}});
