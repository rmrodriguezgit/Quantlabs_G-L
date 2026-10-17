import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
// Resolve from this checkout, including linked worktrees; freeze into the build.
const repository=fileURLToPath(new URL('..',import.meta.url));
let branch=process.env.LAYA_BUILD_BRANCH?.trim();
if(!branch){
  try {
    branch=execFileSync('git',['symbolic-ref','--short','HEAD'],{cwd:repository,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim();
  } catch {
    try {branch='detached@'+execFileSync('git',['rev-parse','--short','HEAD'],{cwd:repository,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim();}
    catch {branch='sin-git';}
  }
}
export default defineConfig({define:{__BUILD_BRANCH__:JSON.stringify(branch)},plugins:[react(),tailwindcss()],server:{proxy:{'/api':'http://127.0.0.1:8000','/ws':{target:'ws://127.0.0.1:8000',ws:true}}}});
